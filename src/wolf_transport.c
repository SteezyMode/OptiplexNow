#include "wolf_transport.h"

typedef struct {
    char *script;
    char *action;
    char *host;
    char *user;
    char *payload;
} WolfRequest;

static void wolf_request_free(gpointer data)
{
    WolfRequest *request = data;
    g_free(request->script);
    g_free(request->action);
    g_free(request->host);
    g_free(request->user);
    g_free(request->payload);
    g_free(request);
}

static void wolf_request_worker(GTask *task, gpointer source_object,
                                gpointer task_data, GCancellable *cancellable)
{
    (void)source_object;
    WolfRequest *request = task_data;
    const gchar *argv[] = {"/usr/bin/python3", request->script,
                           request->action, request->host, request->user, NULL};

    if (g_task_return_error_if_cancelled(task)) {
        return;
    }

    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDIN_PIPE |
              G_SUBPROCESS_FLAGS_STDOUT_PIPE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);

    if (!process) {
        g_task_return_error(task, error);
        return;
    }

    gchar *output = NULL;
    gboolean communicated = g_subprocess_communicate_utf8(
        process, request->payload, cancellable, &output, NULL, &error);
    if (!communicated) {
        /* The dialog may have closed while SSH was waiting. */
        g_subprocess_force_exit(process);
        g_object_unref(process);
        g_free(output);
        g_task_return_error(task, error);
        return;
    }
    if (!g_subprocess_get_successful(process)) {
        g_object_unref(process);
        g_free(output);
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_FAILED,
                                "Wolf bridge rejected the request or host is unavailable");
        return;
    }

    g_object_unref(process);
    g_task_return_pointer(task, output ? output : g_strdup(""), g_free);
}

void now_wolf_request_async(const char *script, const char *action,
                            const char *host, const char *user,
                            const char *payload, GCancellable *cancellable,
                            GAsyncReadyCallback callback, gpointer user_data)
{
    GTask *task = g_task_new(NULL, cancellable, callback, user_data);
    g_task_set_source_tag(task, now_wolf_request_async);

    if (!script || !*script || !action || !host || !user ||
        (g_strcmp0(action, "pending-text") != 0 &&
         g_strcmp0(action, "pair") != 0)) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                                "Invalid Wolf bridge request");
        g_object_unref(task);
        return;
    }

    WolfRequest *request = g_new0(WolfRequest, 1);
    request->script = g_strdup(script);
    request->action = g_strdup(action);
    request->host = g_strdup(host);
    request->user = g_strdup(user);
    request->payload = payload ? g_strdup(payload) : NULL;
    g_task_set_task_data(task, request, wolf_request_free);
    g_task_run_in_thread(task, wolf_request_worker);
    g_object_unref(task);
}

char *now_wolf_request_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), NULL);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_wolf_request_async, NULL);
    return g_task_propagate_pointer(G_TASK(result), error);
}
