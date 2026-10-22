#include "games_flow.h"
#include <string.h>

typedef struct {
    char *script;
    char *action;
    char *host;
    char *user;
} GamesRequest;

static void games_free(gpointer data)
{
    GamesRequest *request = data;
    g_free(request->script);
    g_free(request->action);
    g_free(request->host);
    g_free(request->user);
    g_free(request);
}

char *now_games_helper_for_executable(const char *executable_path)
{
    const char *installed = "/usr/lib/optiplex-now/owner-games-client.py";
    if (!executable_path || !g_path_is_absolute(executable_path)) {
        return g_strdup(installed);
    }
    gchar *bin_dir = g_path_get_dirname(executable_path);
    gchar *bin_name = g_path_get_basename(bin_dir);
    gchar *usr_dir = g_path_get_dirname(bin_dir);
    gchar *usr_name = g_path_get_basename(usr_dir);

    /*
     * A .deb unpacked under a user's own directory retains usr/bin and
     * usr/lib/optiplex-now. Use only that SAME extracted package helper.
     * Never fall through to the system helper if this package is incomplete.
     */
    gboolean is_portable = (g_strcmp0(bin_name, "bin") == 0 &&
                            g_strcmp0(usr_name, "usr") == 0 &&
                            g_strcmp0(bin_dir, "/usr/bin") != 0);
    gchar *result = NULL;
    if (is_portable) {
        gchar *root = g_path_get_dirname(usr_dir);
        result = g_build_filename(root, "usr", "lib", "optiplex-now",
                                  "owner-games-client.py", NULL);
        g_free(root);
    } else {
        result = g_strdup(installed);
    }
    g_free(usr_name);
    g_free(usr_dir);
    g_free(bin_name);
    g_free(bin_dir);
    return result;
}

gboolean now_games_parse_reply(const char *line, NowGamesReply *reply)
{
    if (!line || !reply || strlen(line) > 48) {
        return FALSE;
    }
    static const struct {
        const char *name;
        NowGamesReply result;
    } replies[] = {
        {"needs_wolf_ui", NOW_GAMES_NEEDS_WOLF_UI},
        {"wolf_ui_connected", NOW_GAMES_WOLF_UI_CONNECTED},
        {"busy", NOW_GAMES_BUSY},
        {"in_use", NOW_GAMES_IN_USE},
        {"joined", NOW_GAMES_JOINED},
        {"idle", NOW_GAMES_IDLE}
    };
    /* Input is a single result token plus the optional trailing LF from the
     * fixed helper. No JSON, newlines beyond LF, error strings or secrets. */
    char *copy = g_strdup(line);
    gsize length = strlen(copy);
    if (length > 0 && copy[length - 1] == '\n') {
        copy[--length] = '\0';
    }
    for (gsize i = 0; i < G_N_ELEMENTS(replies); ++i) {
        if (strcmp(copy, replies[i].name) == 0) {
            *reply = replies[i].result;
            g_free(copy);
            return TRUE;
        }
    }
    g_free(copy);
    return FALSE;
}

static void games_worker(GTask *task, gpointer source, gpointer data,
                         GCancellable *cancellable)
{
    (void)source;
    GamesRequest *request = data;
    if (g_task_return_error_if_cancelled(task)) {
        return;
    }

    const gchar *argv[] = {
        "/usr/bin/python3", request->script, "--ui",
        request->action, request->host, request->user, NULL
    };
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (!process) {
        g_task_return_error(task, error);
        return;
    }
    gchar *output = NULL;
    gboolean communicated = g_subprocess_communicate_utf8(
        process, NULL, cancellable, &output, NULL, &error);
    if (!communicated) {
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
                                "Restricted Games host refused or is unavailable");
        return;
    }
    g_object_unref(process);

    NowGamesReply reply;
    gboolean accepted = now_games_parse_reply(output, &reply);
    g_free(output);
    if (!accepted) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_DATA,
                                "Invalid restricted Games host response");
        return;
    }
    g_task_return_int(task, (gint)reply);
}

void now_games_request_async(const char *script, const char *action,
                             const char *host, const char *user,
                             GCancellable *cancellable,
                             GAsyncReadyCallback callback, gpointer user_data)
{
    GTask *task = g_task_new(NULL, cancellable, callback, user_data);
    g_task_set_source_tag(task, now_games_request_async);
    if (!script || !*script || !host || !*host || !user || !*user ||
        !action || (strcmp(action, "status") != 0 &&
                    strcmp(action, "start") != 0 &&
                    strcmp(action, "stop") != 0)) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                                "Invalid restricted Games request");
        g_object_unref(task);
        return;
    }
    GamesRequest *request = g_new0(GamesRequest, 1);
    request->script = g_strdup(script);
    request->action = g_strdup(action);
    request->host = g_strdup(host);
    request->user = g_strdup(user);
    g_task_set_task_data(task, request, games_free);
    g_task_run_in_thread(task, games_worker);
    g_object_unref(task);
}

gboolean now_games_request_finish(GAsyncResult *result, NowGamesReply *reply,
                                  GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), FALSE);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_games_request_async, FALSE);
    gint value = g_task_propagate_int(G_TASK(result), error);
    if (value < 0) {
        return FALSE;
    }
    if (reply) {
        *reply = (NowGamesReply)value;
    }
    return TRUE;
}
