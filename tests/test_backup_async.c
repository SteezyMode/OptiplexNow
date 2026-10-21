#include "backup_async.h"

#include <gio/gio.h>
#include <glib/gstdio.h>
#include <stdio.h>
#include <string.h>

#define EXPECT(cond) do { \
    if (!(cond)) { \
        fprintf(stderr, "Async backup test failed at %d: %s\n", __LINE__, #cond); \
        return 1; \
    } \
} while (0)

typedef struct {
    GMainLoop *loop;
    gboolean done;
    gboolean success;
    gboolean responsive;
    GError *error;
} Run;

static gboolean mark_responsive(gpointer data)
{
    ((Run *)data)->responsive = TRUE;
    return G_SOURCE_REMOVE;
}

static gboolean deadline(gpointer data)
{
    Run *run = data;
    if (!run->done)
        g_main_loop_quit(run->loop);
    return G_SOURCE_REMOVE;
}

static void completed(GObject *source, GAsyncResult *res, gpointer data)
{
    (void)source;
    Run *run = data;
    run->success = now_backup_run_finish(res, &run->error);
    run->done = TRUE;
    g_main_loop_quit(run->loop);
}

static int run_case(const char *helper, const char *path, const char *mode,
                    gboolean restore, gboolean success, GIOErrorEnum err)
{
    Run run = {0};
    run.loop = g_main_loop_new(NULL, FALSE);
    g_setenv("NOW_BACKUP_TEST_MODE", mode, TRUE);
    now_backup_run_async(helper, restore, path, "correct-horse-battery",
                         completed, &run);
    g_idle_add(mark_responsive, &run);
    guint timeout = g_timeout_add_seconds(7, deadline, &run);
    g_main_loop_run(run.loop);
    if (g_main_context_find_source_by_id(NULL, timeout))
        g_source_remove(timeout);
    int ok = run.done && run.responsive && run.success == success &&
             (success ? run.error == NULL :
              g_error_matches(run.error, G_IO_ERROR, err));
    if (!ok) {
        fprintf(stderr, "mode=%s done=%d success=%d error=%s\n",
                mode, run.done, run.success,
                run.error ? run.error->message : "(none)");
    }
    g_clear_error(&run.error);
    g_main_loop_unref(run.loop);
    return ok;
}

int main(void)
{
    GError *error = NULL;
    char *dir = g_dir_make_tmp("now-backup-async-XXXXXX", &error);
    EXPECT(dir != NULL);
    char *script = g_build_filename(dir, "fake-backup", NULL);
    char *log = g_build_filename(dir, "arguments.log", NULL);
    char *backup = g_build_filename(dir, "test backup.onb", NULL);
    const char *fake = "#!/bin/sh\n"
        "printf '%s\\n' \"$1\" \"$2\" > \"$NOW_BACKUP_TEST_LOG\"\n"
        "IFS= read -r secret || exit 4\n"
        "[ \"$secret\" = correct-horse-battery ] || exit 5\n"
        "case \"$NOW_BACKUP_TEST_MODE\" in\n"
        " slow) sleep 0.3;;\n"
        " fail) exit 9;;\n"
        "esac\n"
        "exit 0\n";
    EXPECT(g_file_set_contents(script, fake, -1, &error));
    EXPECT(g_chmod(script, 0700) == 0);
    g_setenv("NOW_BACKUP_TEST_LOG", log, TRUE);
    EXPECT(run_case(script, backup, "success", FALSE, TRUE, G_IO_ERROR_FAILED));
    char *args = NULL;
    EXPECT(g_file_get_contents(log, &args, NULL, &error));
    EXPECT(g_str_has_prefix(args, "export\n"));
    EXPECT(strstr(args, backup) != NULL);
    EXPECT(strstr(args, "correct-horse") == NULL);
    g_free(args);
    EXPECT(run_case(script, backup, "success", TRUE, TRUE, G_IO_ERROR_FAILED));
    EXPECT(g_file_get_contents(log, &args, NULL, &error));
    EXPECT(g_str_has_prefix(args, "restore\n"));
    g_free(args);
    EXPECT(run_case(script, backup, "slow", TRUE, TRUE, G_IO_ERROR_FAILED));
    EXPECT(run_case(script, backup, "fail", FALSE, FALSE, G_IO_ERROR_FAILED));
    char *missing = g_build_filename(dir, "absent-helper", NULL);
    EXPECT(run_case(missing, backup, "success", FALSE, FALSE, G_IO_ERROR_NOT_FOUND));

    /* Invalid input is rejected before the subprocess is created. */
    Run invalid = {0};
    invalid.loop = g_main_loop_new(NULL, FALSE);
    now_backup_run_async(script, FALSE, "relative/path", "correct-horse-battery",
                         completed, &invalid);
    g_main_loop_run(invalid.loop);
    EXPECT(!invalid.success && invalid.done &&
           g_error_matches(invalid.error, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT));
    g_clear_error(&invalid.error);
    g_main_loop_unref(invalid.loop);

    g_remove(log);
    g_remove(script);
    g_rmdir(dir);
    g_free(missing);
    g_free(script);
    g_free(log);
    g_free(backup);
    g_free(dir);
    puts("Async backup: stdin secrecy, export/restore, failures and responsive main loop passed.");
    return 0;
}
