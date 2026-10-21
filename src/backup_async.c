#define _GNU_SOURCE
#include "backup_async.h"

#include <limits.h>
#include <string.h>
#include <unistd.h>

typedef struct {
    size_t length;
    char bytes[];
} Secret;

typedef struct {
    GSubprocess *process;
    GBytes *input;
} BackupJob;

static void erase_secret(gpointer data)
{
    Secret *secret = data;
    volatile unsigned char *p = (volatile unsigned char *)secret->bytes;
    for (size_t i = 0; i < secret->length; i++)
        p[i] = 0;
    g_free(secret);
}

static void backup_job_free(gpointer data)
{
    BackupJob *job = data;
    g_clear_object(&job->process);
    if (job->input)
        g_bytes_unref(job->input);
    g_free(job);
}

static void backup_completed(GObject *source, GAsyncResult *result, gpointer data)
{
    GTask *task = G_TASK(data);
    BackupJob *job = g_task_get_task_data(task);
    GError *error = NULL;
    gboolean communicated = g_subprocess_communicate_finish(
        G_SUBPROCESS(source), result, NULL, NULL, &error);
    if (!communicated) {
        g_task_return_error(task, error);
    } else if (!g_subprocess_get_successful(job->process)) {
        g_task_return_new_error(
            task, G_IO_ERROR, G_IO_ERROR_FAILED,
            "Encrypted backup helper failed. Check the file, password and permissions.");
    } else {
        g_task_return_boolean(task, TRUE);
    }
    g_object_unref(task);
}

void now_backup_run_async(const char *helper, gboolean restore, const char *path,
                          const char *password, GAsyncReadyCallback callback,
                          gpointer user_data)
{
    GTask *task = g_task_new(NULL, NULL, callback, user_data);
    g_task_set_source_tag(task, now_backup_run_async);
    if (!helper || helper[0] != '/' || access(helper, X_OK) != 0) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_NOT_FOUND,
                                "Encrypted backup helper is missing.");
        g_object_unref(task);
        return;
    }
    size_t pass_len = password ? strnlen(password, 1025) : 0;
    if (!path || !g_path_is_absolute(path) || strlen(path) >= PATH_MAX ||
        pass_len < 12 || pass_len > 1024 ||
        strchr(password, '\n') || strchr(password, '\r')) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                                "Invalid encrypted backup path or password.");
        g_object_unref(task);
        return;
    }

    /* GBytes owns and erases this copy only after stdin communication ends. */
    Secret *secret = g_malloc(sizeof(*secret) + pass_len + 1);
    secret->length = pass_len + 1;
    memcpy(secret->bytes, password, pass_len);
    secret->bytes[pass_len] = '\n';
    BackupJob *job = g_new0(BackupJob, 1);
    job->input = g_bytes_new_with_free_func(
        secret->bytes, secret->length, erase_secret, secret);
    g_task_set_task_data(task, job, backup_job_free);

    const gchar *argv[] = {helper, restore ? "restore" : "export", path, NULL};
    GError *error = NULL;
    job->process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDIN_PIPE |
              G_SUBPROCESS_FLAGS_STDOUT_SILENCE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (!job->process) {
        g_task_return_error(task, error);
        g_object_unref(task);
        return;
    }
    g_subprocess_communicate_async(job->process, job->input, NULL,
                                   backup_completed, task);
}

gboolean now_backup_run_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), FALSE);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_backup_run_async, FALSE);
    return g_task_propagate_boolean(G_TASK(result), error);
}
