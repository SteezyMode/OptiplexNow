#include "tailscale_async.h"

#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>

static void tailscale_helper_worker(GTask *task, gpointer source_object,
                                    gpointer task_data, GCancellable *cancellable)
{
    (void)source_object;
    const char *helper = task_data;
    const char *argv[] = {"/usr/bin/python3", helper, NULL};
    if (g_task_return_error_if_cancelled(task)) {
        return;
    }

    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
        &error);
    if (!process) {
        g_task_return_error(task, error);
        return;
    }

    char *output = NULL;
    gboolean completed = g_subprocess_communicate_utf8(
        process, NULL, cancellable, &output, NULL, &error);
    if (!completed) {
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
                                "Tailscale helper unavailable or returned an error");
        return;
    }

    g_object_unref(process);
    if (output && strlen(output) > 65536) {
        g_free(output);
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_DATA,
                                "Tailscale helper output too large");
        return;
    }
    g_task_return_pointer(task, output ? output : g_strdup(""), g_free);
}

void now_tailscale_run_async(const char *helper, GCancellable *cancellable,
                            GAsyncReadyCallback callback, gpointer user_data)
{
    GTask *task = g_task_new(NULL, cancellable, callback, user_data);
    g_task_set_source_tag(task, now_tailscale_run_async);
    if (!helper || !g_path_is_absolute(helper)) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                                "Invalid Tailscale helper");
    } else {
        g_task_set_task_data(task, g_strdup(helper), g_free);
        g_task_run_in_thread(task, tailscale_helper_worker);
    }
    g_object_unref(task);
}

char *now_tailscale_run_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), NULL);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_tailscale_run_async, NULL);
    return g_task_propagate_pointer(G_TASK(result), error);
}

static gboolean is_address(const char *address)
{
    struct in_addr v4;
    struct in6_addr v6;
    return inet_pton(AF_INET, address, &v4) == 1 ||
           inet_pton(AF_INET6, address, &v6) == 1;
}

int now_tailscale_parse_servers(const char *output, NowTailscaleServer *servers,
                               size_t capacity)
{
    if (!output || !servers || capacity == 0) {
        return -1;
    }

    size_t count = 0;
    const char *cursor = output;
    while (*cursor) {
        const char *end = strchr(cursor, '\n');
        size_t length = end ? (size_t)(end - cursor) : strlen(cursor);
        if (length > 0 && cursor[length - 1] == '\r') {
            length--;
        }
        if (length == 0 || length > 511 || count >= capacity) {
            return -1;
        }
        char line[512];
        memcpy(line, cursor, length);
        line[length] = '\0';
        char *label = strchr(line, '\t');
        if (!label || label == line || label[1] == '\0' ||
            strchr(label + 1, '\t')) {
            return -1;
        }
        *label++ = '\0';
        if (!is_address(line) || strlen(line) >= sizeof servers[0].address ||
            strlen(label) >= sizeof servers[0].label) {
            return -1;
        }
        for (size_t i = 0; i < count; i++) {
            if (strcmp(servers[i].address, line) == 0) {
                return -1;
            }
        }
        snprintf(servers[count].address, sizeof servers[count].address, "%s", line);
        snprintf(servers[count].label, sizeof servers[count].label, "%s", label);
        count++;
        cursor = end ? end + 1 : cursor + strlen(cursor);
    }
    return (int)count;
}
