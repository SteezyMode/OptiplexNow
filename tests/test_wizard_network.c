#define _GNU_SOURCE
#include "wizard_network.h"

#include <glib.h>
#include <glib/gstdio.h>
#include <stdio.h>
#include <string.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Wizard lifecycle test line %d: %s\n", __LINE__, #condition); \
        return 1; \
    } \
} while (0)

typedef struct {
    GMainLoop *loop;
    NowWizardNetwork *network;
    int calls;
    int status_calls;
    int discovery_calls;
    int timeouts;
    int expected;
    gboolean close_on_callback;
    char result[128];
} Scenario;

static void completion(gpointer data, NowWizardNetworkKind kind,
                       const char *reply, const GError *error)
{
    Scenario *scenario = data;
    scenario->calls++;
    if (kind == NOW_WIZARD_NET_STATUS) {
        scenario->status_calls++;
    } else if (kind == NOW_WIZARD_NET_DISCOVERY) {
        scenario->discovery_calls++;
    }
    if (reply) {
        g_strlcpy(scenario->result, reply, sizeof scenario->result);
    }
    if (g_error_matches(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT)) {
        scenario->timeouts++;
    }
    if (scenario->close_on_callback) {
        now_wizard_network_close(scenario->network);
        scenario->network = NULL;
    }
    if (scenario->calls >= scenario->expected && scenario->loop) {
        g_main_loop_quit(scenario->loop);
    }
}

static gboolean deadline(gpointer data)
{
    g_main_loop_quit(data);
    return G_SOURCE_REMOVE;
}

static void drain_for(Scenario *state, guint duration_ms)
{
    state->loop = g_main_loop_new(NULL, FALSE);
    guint id = g_timeout_add(duration_ms, deadline, state->loop);
    g_main_loop_run(state->loop);
    if (g_main_context_find_source_by_id(NULL, id)) {
        g_source_remove(id);
    }
    g_main_loop_unref(state->loop);
    state->loop = NULL;
}

int main(void)
{
    GError *error = NULL;
    char *dir = g_dir_make_tmp("now-wizard-jobs-XXXXXX", &error);
    EXPECT(dir != NULL);
    char *fast = g_build_filename(dir, "fast.py", NULL);
    char *slow = g_build_filename(dir, "slow.py", NULL);
    char *discovery = g_build_filename(dir, "discovery.py", NULL);
    EXPECT(g_file_set_contents(fast, "print('CONNECTED')\n", -1, &error));
    EXPECT(g_file_set_contents(slow,
        "import time\ntime.sleep(5)\nprint('CONNECTED')\n", -1, &error));
    EXPECT(g_file_set_contents(discovery,
        "print('100.64.2.3\\tserver')\n", -1, &error));

    Scenario state = {.expected = 1};
    state.network = now_wizard_network_new(completion, &state, 1500);
    EXPECT(state.network != NULL);
    EXPECT(!now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS,
                                      "relative-path.py"));
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, fast));
    EXPECT(now_wizard_network_busy(state.network, NOW_WIZARD_NET_STATUS));
    EXPECT(!now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, fast));
    drain_for(&state, 1200);
    EXPECT(state.calls == 1 && state.status_calls == 1);
    EXPECT(g_str_has_prefix(state.result, "CONNECTED"));
    EXPECT(!now_wizard_network_busy(state.network, NOW_WIZARD_NET_STATUS));
    now_wizard_network_close(state.network);

    /* Status and discovery are independent, so the wizard remains usable
     * while one request is slow. The timeout cancels only its own job. */
    memset(&state, 0, sizeof state);
    state.expected = 2;
    state.network = now_wizard_network_new(completion, &state, 180);
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, slow));
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_DISCOVERY,
                                    discovery));
    EXPECT(!now_wizard_network_start(state.network, NOW_WIZARD_NET_DISCOVERY,
                                     discovery));
    drain_for(&state, 1700);
    EXPECT(state.calls == 2);
    EXPECT(state.status_calls == 1 && state.discovery_calls == 1);
    EXPECT(state.timeouts == 1);
    EXPECT(g_str_has_prefix(state.result, "100.64."));
    /* A timed-out request can be retried without stale busy flags. */
    state.expected = 3;
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, fast));
    drain_for(&state, 1200);
    EXPECT(state.calls == 3 && state.timeouts == 1);
    now_wizard_network_close(state.network);

    /* Close while slow worker is running: never invoke a stale UI callback. */
    memset(&state, 0, sizeof state);
    state.expected = 1;
    state.network = now_wizard_network_new(completion, &state, 1000);
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, slow));
    now_wizard_network_close(state.network);
    state.network = NULL;
    drain_for(&state, 400);
    EXPECT(state.calls == 0);

    /* A callback itself may close its owner while nested GTK UI unwinds. */
    memset(&state, 0, sizeof state);
    state.expected = 1;
    state.close_on_callback = TRUE;
    state.network = now_wizard_network_new(completion, &state, 1000);
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, fast));
    drain_for(&state, 1200);
    EXPECT(state.calls == 1 && state.network == NULL);

    /* A fast status reply can close the wizard while independent discovery
     * is still running. That cancelled job must never call the old UI,
     * even if it completes after the nested callback unwinds. */
    memset(&state, 0, sizeof state);
    state.expected = 2; /* Do not quit the drain after the first callback. */
    state.close_on_callback = TRUE;
    state.network = now_wizard_network_new(completion, &state, 1000);
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, fast));
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_DISCOVERY,
                                    slow));
    drain_for(&state, 500);
    EXPECT(state.calls == 1 && state.status_calls == 1);
    EXPECT(state.discovery_calls == 0 && state.network == NULL);
    drain_for(&state, 350);
    EXPECT(state.calls == 1); /* No late discovery callback. */

    /* Closing while both operations are pending must suppress both. */
    memset(&state, 0, sizeof state);
    state.network = now_wizard_network_new(completion, &state, 1500);
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_STATUS, slow));
    EXPECT(now_wizard_network_start(state.network, NOW_WIZARD_NET_DISCOVERY,
                                    slow));
    now_wizard_network_close(state.network);
    state.network = NULL;
    drain_for(&state, 400);
    EXPECT(state.calls == 0);

    g_remove(fast);
    g_remove(slow);
    g_remove(discovery);
    g_rmdir(dir);
    g_free(fast);
    g_free(slow);
    g_free(discovery);
    g_free(dir);
    puts("Wizard lifecycle: concurrency, timeout, retry, close and callback teardown passed.");
    return 0;
}
