#define _GNU_SOURCE
#include "wolf_transport.h"

#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct {
    GMainLoop *loop;
    char *result;
    GError *error;
    gboolean idle_seen;
    guint heartbeat;
} TransportTest;

static gboolean mark_idle(gpointer user_data)
{
    TransportTest *test = user_data;
    test->idle_seen = TRUE;
    test->heartbeat++;
    return G_SOURCE_REMOVE;
}

static void result_ready(GObject *source, GAsyncResult *result, gpointer user_data)
{
    (void)source;
    TransportTest *test = user_data;
    test->result = now_wolf_request_finish(result, &test->error);
    g_main_loop_quit(test->loop);
}

static gboolean cancel_request(gpointer user_data)
{
    g_cancellable_cancel(G_CANCELLABLE(user_data));
    return G_SOURCE_REMOVE;
}

static int run_case(const char *script, gboolean cancel)
{
    TransportTest test = {0};
    test.loop = g_main_loop_new(NULL, FALSE);
    GCancellable *cancellable = g_cancellable_new();

    now_wolf_request_async(script, "pending-text", "host.example", "tester", NULL,
                           cancellable, result_ready, &test);
    g_idle_add(mark_idle, &test);
    if (cancel) {
        g_timeout_add(100, cancel_request, cancellable);
    }

    g_main_loop_run(test.loop);
    int passed = test.idle_seen &&
                 (cancel ? (test.result == NULL &&
                            g_error_matches(test.error, G_IO_ERROR, G_IO_ERROR_CANCELLED))
                         : (test.result && strstr(test.result, "1\t100.100.1.2")));
    g_free(test.result);
    g_clear_error(&test.error);
    g_object_unref(cancellable);
    g_main_loop_unref(test.loop);
    return passed;
}

int main(void)
{
    char directory[] = "/tmp/now-wolf-transport-XXXXXX";
    if (!mkdtemp(directory)) {
        return 1;
    }
    char script[512];
    snprintf(script, sizeof script, "%s/mock_bridge.py", directory);

    FILE *file = fopen(script, "w");
    if (!file) {
        rmdir(directory);
        return 1;
    }
    fputs("import time\n"
          "import sys\n"
          "if sys.argv[2] == 'slow.example':\n"
          "    time.sleep(10)\n"
          "print('1\\t100.100.1.2')\n", file);
    fclose(file);
    chmod(script, 0600);

    int ok = run_case(script, FALSE);
    if (ok) {
        /* The script checks argv[2], which is host in the bridge call. */
        file = fopen(script, "w");
        if (file) {
            fputs("import time\n"
                  "time.sleep(10)\n"
                  "print('1\\t100.100.1.2')\n", file);
            fclose(file);
            ok = run_case(script, TRUE);
        } else {
            ok = 0;
        }
    }
    unlink(script);
    rmdir(directory);
    if (!ok) {
        fprintf(stderr, "Wolf async transport test failed\n");
        return 1;
    }
    puts("Wolf transport: responsive main loop and cancellation passed.");
    return 0;
}
