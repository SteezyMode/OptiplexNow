#define _GNU_SOURCE
#include "tailscale_async.h"

#include <gio/gio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define EXPECT(cond) do { if (!(cond)) { \
    fprintf(stderr, "Tailscale async contract line %d: %s\n", __LINE__, #cond); \
    return 1; \
} } while (0)

typedef struct {
    GMainLoop *loop;
    char *reply;
    GError *error;
    gboolean idle_seen;
} TestJob;

static gboolean mark_idle(gpointer data)
{
    ((TestJob *)data)->idle_seen = TRUE;
    return G_SOURCE_REMOVE;
}

static void result_ready(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    TestJob *job = data;
    job->reply = now_tailscale_run_finish(result, &job->error);
    g_main_loop_quit(job->loop);
}

static gboolean cancel_it(gpointer data)
{
    g_cancellable_cancel(data);
    return G_SOURCE_REMOVE;
}

static int check_job(const char *script, gboolean cancel)
{
    TestJob job = {0};
    job.loop = g_main_loop_new(NULL, FALSE);
    GCancellable *cancellable = g_cancellable_new();
    now_tailscale_run_async(script, cancellable, result_ready, &job);
    g_idle_add(mark_idle, &job);
    if (cancel) {
        g_timeout_add(100, cancel_it, cancellable);
    }
    g_main_loop_run(job.loop);
    int ok = job.idle_seen && (cancel ?
        (job.reply == NULL && g_error_matches(job.error, G_IO_ERROR, G_IO_ERROR_CANCELLED)) :
        (job.reply && strstr(job.reply, "CONNECTED")));
    g_clear_error(&job.error);
    g_free(job.reply);
    g_object_unref(cancellable);
    g_main_loop_unref(job.loop);
    return ok;
}

int main(void)
{
    NowTailscaleServer servers[NOW_TAILSCALE_MAX_SERVERS] = {0};
    EXPECT(now_tailscale_parse_servers("", servers, 200) == 0);
    EXPECT(now_tailscale_parse_servers(
        "100.64.0.2\tHome Server — Online\n2001:db8::2\tOther Device — Offline\n",
        servers, 200) == 2);
    EXPECT(!strcmp(servers[0].address, "100.64.0.2"));
    EXPECT(now_tailscale_parse_servers("garbage\tBad\n", servers, 200) == -1);
    EXPECT(now_tailscale_parse_servers("100.64.0.2\tOne\n100.64.0.2\tTwo\n",
                                       servers, 200) == -1);
    EXPECT(now_tailscale_parse_servers("100.64.0.2\tOne\tTwo\n",
                                       servers, 200) == -1);
    EXPECT(now_tailscale_parse_servers("100.64.0.2\tOne\n100.64.0.3\tTwo\n",
                                       servers, 1) == -1);

    char directory[] = "/tmp/now-tailscale-XXXXXX";
    EXPECT(mkdtemp(directory) != NULL);
    char script[512];
    snprintf(script, sizeof script, "%s/helper.py", directory);
    FILE *fp = fopen(script, "w");
    EXPECT(fp != NULL);
    fputs("print('CONNECTED')\n", fp);
    fclose(fp);
    EXPECT(check_job(script, FALSE));
    fp = fopen(script, "w");
    EXPECT(fp != NULL);
    fputs("import time\ntime.sleep(10)\nprint('CONNECTED')\n", fp);
    fclose(fp);
    EXPECT(check_job(script, TRUE));
    unlink(script);
    rmdir(directory);
    puts("Tailscale: valid discovery, async dispatch and cancellation passed.");
    return 0;
}
