#include "service_probe.h"

#include "presets.h"

#include <string.h>

struct NowServiceProbe {
    NowServiceProbeCallback callback;
    gpointer context;
    GCancellable *cancel;
    guint timeout_id;
    guint deadline_ms;
    unsigned references;
    gboolean closed;
    gboolean timed_out;
};

typedef struct {
    char url[NOW_SERVICE_PROBE_COUNT][NOW_SERVICE_PROBE_URL_MAX];
    NowServiceProbeEntry result[NOW_SERVICE_PROBE_COUNT];
} ProbeTask;

static void probe_unref(NowServiceProbe *probe)
{
    g_assert(probe->references > 0);
    if (--probe->references == 0) {
        g_free(probe);
    }
}

static gboolean probe_timeout(gpointer data)
{
    NowServiceProbe *probe = data;
    probe->timeout_id = 0;
    probe->timed_out = TRUE;
    if (probe->cancel) {
        g_cancellable_cancel(probe->cancel);
    }
    return G_SOURCE_REMOVE;
}

static gboolean probe_url(const char *url, GCancellable *cancel,
                           char state[NOW_SERVICE_PROBE_STATE_MAX],
                           GError **error)
{
    const char *const argv[] = {
        "curl", "--silent", "--show-error", "--location",
        "--max-time", "3", "--connect-timeout", "2",
        "--output", "/dev/null", "--write-out", "%{http_code}", url, NULL
    };
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
        error);
    if (!process) {
        return FALSE;
    }

    char *stdout_text = NULL;
    gboolean completed = g_subprocess_communicate_utf8(
        process, NULL, cancel, &stdout_text, NULL, error);
    if (!completed) {
        g_subprocess_force_exit(process);
        g_subprocess_wait(process, NULL, NULL);
        g_object_unref(process);
        g_free(stdout_text);
        return FALSE;
    }

    gboolean success = g_subprocess_get_successful(process);
    if (success && stdout_text && strlen(stdout_text) == 3 &&
        stdout_text[0] >= '2' && stdout_text[0] <= '4' &&
        g_ascii_isdigit(stdout_text[1]) &&
        g_ascii_isdigit(stdout_text[2])) {
        g_strlcpy(state, "RESPONDING", NOW_SERVICE_PROBE_STATE_MAX);
    } else {
        g_strlcpy(state, "UNREACHABLE", NOW_SERVICE_PROBE_STATE_MAX);
    }
    g_object_unref(process);
    g_free(stdout_text);
    return TRUE;
}

static void probe_worker(GTask *task, gpointer source, gpointer data,
                         GCancellable *cancel)
{
    (void)source;
    ProbeTask *work = data;
    for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; index++) {
        if (g_task_return_error_if_cancelled(task)) {
            return;
        }
        const char *url = work->url[index];
        if (!*url) {
            g_strlcpy(work->result[index].state, "NOT SET UP",
                      NOW_SERVICE_PROBE_STATE_MAX);
            continue;
        }
        GError *error = NULL;
        if (!probe_url(url, cancel, work->result[index].state, &error)) {
            if (g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)) {
                g_task_return_error(task, error);
                return;
            }
            /* Missing curl or an OS execution failure is a per-service
             * unavailable state, not a crash of the entire wizard.
             */
            g_clear_error(&error);
            g_strlcpy(work->result[index].state, "NOT CHECKED",
                      NOW_SERVICE_PROBE_STATE_MAX);
        }
    }
    g_task_return_pointer(task, g_memdup2(work->result, sizeof work->result),
                          g_free);
}

static void probe_finished(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    NowServiceProbe *probe = data;
    GError *error = NULL;
    NowServiceProbeEntry *entries = g_task_propagate_pointer(G_TASK(result), &error);

    if (probe->timeout_id) {
        g_source_remove(probe->timeout_id);
        probe->timeout_id = 0;
    }
    gboolean expired = probe->timed_out;
    probe->timed_out = FALSE;
    g_clear_object(&probe->cancel);

    if (expired) {
        g_clear_error(&error);
        error = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_TIMED_OUT,
                                    "Service check timed out");
        g_clear_pointer(&entries, g_free);
    }

    if (!probe->closed && probe->callback) {
        probe->callback(probe->context, entries, error);
    }

    g_free(entries);
    g_clear_error(&error);
    probe_unref(probe);
}

NowServiceProbe *now_service_probe_new(NowServiceProbeCallback callback,
                                       gpointer context, guint deadline_ms)
{
    g_return_val_if_fail(callback != NULL, NULL);
    NowServiceProbe *probe = g_new0(NowServiceProbe, 1);
    probe->callback = callback;
    probe->context = context;
    probe->deadline_ms = deadline_ms ? deadline_ms : 16000;
    probe->references = 1;
    return probe;
}

gboolean now_service_probe_start(NowServiceProbe *probe,
                                  const char *const urls[NOW_SERVICE_PROBE_COUNT])
{
    if (!probe || probe->closed || probe->cancel || !urls) {
        return FALSE;
    }
    ProbeTask *work = g_new0(ProbeTask, 1);
    for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; index++) {
        if (!urls[index] || !now_safe_preset_url(urls[index])) {
            g_free(work);
            return FALSE;
        }
        g_strlcpy(work->url[index], urls[index], NOW_SERVICE_PROBE_URL_MAX);
    }
    probe->cancel = g_cancellable_new();
    probe->references++;
    probe->timeout_id = g_timeout_add(probe->deadline_ms, probe_timeout, probe);

    GTask *task = g_task_new(NULL, probe->cancel, probe_finished, probe);
    g_task_set_source_tag(task, now_service_probe_start);
    g_task_set_task_data(task, work, g_free);
    g_task_run_in_thread(task, probe_worker);
    g_object_unref(task);
    return TRUE;
}

gboolean now_service_probe_busy(const NowServiceProbe *probe)
{
    return probe && !probe->closed && probe->cancel != NULL;
}

void now_service_probe_close(NowServiceProbe *probe)
{
    if (!probe || probe->closed) {
        return;
    }
    probe->closed = TRUE;
    probe->callback = NULL;
    probe->context = NULL;
    if (probe->cancel) {
        g_cancellable_cancel(probe->cancel);
    }
    probe_unref(probe);
}
