#define _GNU_SOURCE
#include "service_probe.h"

#include <glib.h>
#include <glib/gstdio.h>
#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "Service probe test line %d: %s\n", __LINE__, #expr); \
    return 1; \
} } while (0)

typedef struct {
    GMainLoop *loop;
    NowServiceProbe *probe;
    int callbacks;
    int timed_out;
    int failures;
    gboolean close_in_callback;
    NowServiceProbeEntry result[NOW_SERVICE_PROBE_COUNT];
} Scenario;

static void completed(gpointer context,
                      const NowServiceProbeEntry entries[NOW_SERVICE_PROBE_COUNT],
                      const GError *error)
{
    Scenario *scenario = context;
    scenario->callbacks++;
    if (error) {
        scenario->failures++;
        if (g_error_matches(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT)) {
            scenario->timed_out++;
        }
    } else if (entries) {
        memcpy(scenario->result, entries, sizeof scenario->result);
    }
    if (scenario->close_in_callback) {
        now_service_probe_close(scenario->probe);
        scenario->probe = NULL;
    }
    if (scenario->loop) {
        g_main_loop_quit(scenario->loop);
    }
}

static gboolean exit_loop(gpointer data)
{
    g_main_loop_quit(data);
    return G_SOURCE_REMOVE;
}

static void run_for(Scenario *scenario, guint ms)
{
    scenario->loop = g_main_loop_new(NULL, FALSE);
    guint source = g_timeout_add(ms, exit_loop, scenario->loop);
    g_main_loop_run(scenario->loop);
    if (g_main_context_find_source_by_id(NULL, source)) {
        g_source_remove(source);
    }
    g_main_loop_unref(scenario->loop);
    scenario->loop = NULL;
}

int main(void)
{
    GError *error = NULL;
    char *folder = g_dir_make_tmp("now-service-probe-XXXXXX", &error);
    CHECK(folder != NULL);
    char *fake_curl = g_build_filename(folder, "curl", NULL);
    const char *script =
        "#!/bin/sh\n"
        "url=\"\"; for part in \"$@\"; do url=\"$part\"; done\n"
        "if [ \"$NOW_TEST_PROBE_SLOW\" = 1 ]; then exec sleep 4; fi\n"
        "case \"$url\" in\n"
        "  */ok) printf 200;;\n"
        "  */auth) printf 401;;\n"
        "  */down) printf 503;;\n"
        "  */refused) exit 7;;\n"
        "  *) printf 000;;\n"
        "esac\n";
    CHECK(g_file_set_contents(fake_curl, script, -1, &error));
    CHECK(g_chmod(fake_curl, 0700) == 0);
    const char *previous = g_getenv("PATH");
    char *new_path = g_strdup_printf("%s:%s", folder, previous ? previous : "");
    g_setenv("PATH", new_path, TRUE);
    const char *urls[NOW_SERVICE_PROBE_COUNT] = {
        "http://example.test/ok", "https://example.test/auth", ""
    };

    Scenario scenario = {0};
    scenario.probe = now_service_probe_new(completed, &scenario, 3000);
    CHECK(scenario.probe != NULL);
    CHECK(!now_service_probe_busy(scenario.probe));
    CHECK(now_service_probe_start(scenario.probe, urls));
    CHECK(now_service_probe_busy(scenario.probe));
    CHECK(!now_service_probe_start(scenario.probe, urls));
    run_for(&scenario, 1600);
    CHECK(scenario.callbacks == 1 && scenario.failures == 0);
    CHECK(strcmp(scenario.result[0].state, "RESPONDING") == 0);
    CHECK(strcmp(scenario.result[1].state, "RESPONDING") == 0);
    CHECK(strcmp(scenario.result[2].state, "NOT SET UP") == 0);
    CHECK(!now_service_probe_busy(scenario.probe));

    const char *bad[NOW_SERVICE_PROBE_COUNT] = {
        "https://example.test/ok", "file:///etc/passwd", ""
    };
    CHECK(!now_service_probe_start(scenario.probe, bad));
    CHECK(scenario.callbacks == 1);

    const char *second[NOW_SERVICE_PROBE_COUNT] = {
        "http://example.test/down", "https://example.test/refused", ""
    };
    CHECK(now_service_probe_start(scenario.probe, second));
    run_for(&scenario, 1600);
    CHECK(scenario.callbacks == 2 && scenario.failures == 0);
    CHECK(strcmp(scenario.result[0].state, "UNREACHABLE") == 0);
    CHECK(strcmp(scenario.result[1].state, "UNREACHABLE") == 0);
    now_service_probe_close(scenario.probe);

    /* Cancellation from wizard teardown suppresses the callback completely. */
    memset(&scenario, 0, sizeof scenario);
    scenario.probe = now_service_probe_new(completed, &scenario, 1200);
    g_setenv("NOW_TEST_PROBE_SLOW", "1", TRUE);
    CHECK(now_service_probe_start(scenario.probe, urls));
    now_service_probe_close(scenario.probe);
    scenario.probe = NULL;
    run_for(&scenario, 500);
    CHECK(scenario.callbacks == 0);

    /* A timeout is a single actionable failure; retry is permitted. */
    memset(&scenario, 0, sizeof scenario);
    scenario.probe = now_service_probe_new(completed, &scenario, 125);
    CHECK(now_service_probe_start(scenario.probe, urls));
    run_for(&scenario, 900);
    CHECK(scenario.callbacks == 1);
    CHECK(scenario.timed_out == 1);
    CHECK(!now_service_probe_busy(scenario.probe));
    g_unsetenv("NOW_TEST_PROBE_SLOW");
    CHECK(now_service_probe_start(scenario.probe, urls));
    run_for(&scenario, 1200);
    CHECK(scenario.callbacks == 2 && scenario.failures == 1);
    now_service_probe_close(scenario.probe);

    /* Handler can close its own owner safely. */
    memset(&scenario, 0, sizeof scenario);
    scenario.close_in_callback = TRUE;
    scenario.probe = now_service_probe_new(completed, &scenario, 1200);
    CHECK(now_service_probe_start(scenario.probe, urls));
    run_for(&scenario, 1200);
    CHECK(scenario.callbacks == 1 && scenario.probe == NULL);

    g_remove(fake_curl);
    g_rmdir(folder);
    g_free(fake_curl);
    g_free(new_path);
    g_free(folder);
    puts("Wizard services: real helper execution, invalid URLs, retry, timeouts and close passed.");
    return 0;
}
