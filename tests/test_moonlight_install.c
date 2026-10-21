#include "moonlight_install.h"

#include <gio/gio.h>
#include <glib/gstdio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Moonlight install test line %d: %s\n", __LINE__, #condition); \
        return 1; \
    } \
} while (0)

typedef struct {
    GMainLoop *loop;
    gboolean success;
    GError *error;
    gboolean completed;
    gboolean main_loop_responsive;
} InstallResult;

static gboolean on_idle(gpointer data)
{
    ((InstallResult *)data)->main_loop_responsive = TRUE;
    return G_SOURCE_REMOVE;
}

static gboolean stop_after_deadline(gpointer data)
{
    InstallResult *state = data;
    if (!state->completed) {
        g_main_loop_quit(state->loop);
    }
    return G_SOURCE_REMOVE;
}

static gboolean cancel_install(gpointer data)
{
    g_cancellable_cancel(G_CANCELLABLE(data));
    return G_SOURCE_REMOVE;
}

static void installation_finished(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    InstallResult *state = data;
    state->success = now_moonlight_install_finish(result, &state->error);
    state->completed = TRUE;
    g_main_loop_quit(state->loop);
}

static int check(const char *mode, gboolean cancel, gboolean expect_success,
                 GIOErrorEnum failure, const char *log_path)
{
    InstallResult result = {0};
    result.loop = g_main_loop_new(NULL, FALSE);
    GCancellable *cancellable = g_cancellable_new();
    g_setenv("NOW_TEST_FLATPAK_MODE", mode, TRUE);
    g_file_set_contents(log_path, "", 0, NULL);
    now_moonlight_install_async(cancellable, installation_finished, &result);
    g_idle_add(on_idle, &result);
    guint cancel_source = 0;
    if (cancel) {
        cancel_source = g_timeout_add(100, cancel_install, cancellable);
    }
    guint deadline = g_timeout_add_seconds(8, stop_after_deadline, &result);
    g_main_loop_run(result.loop);
    if (cancel_source && g_main_context_find_source_by_id(NULL, cancel_source)) {
        g_source_remove(cancel_source);
    }
    if (g_main_context_find_source_by_id(NULL, deadline)) {
        g_source_remove(deadline);
    }
    gboolean expected = result.completed && result.main_loop_responsive &&
                        result.success == expect_success &&
                        (expect_success ? result.error == NULL :
                         g_error_matches(result.error, G_IO_ERROR, failure));
    char *log = NULL;
    g_file_get_contents(log_path, &log, NULL, NULL);
    if (expected && !cancel && expect_success) {
        expected = log &&
                   strstr(log, "remote-add --user --if-not-exists flathub ") &&
                   strstr(log, "https://dl.flathub.org/repo/flathub.flatpakrepo") &&
                   strstr(log, "install --user --assumeyes --noninteractive flathub "
                               "com.moonlight_stream.Moonlight");
    }
    if (expected && !cancel && !expect_success &&
        strcmp(mode, "fail-remote") == 0) {
        expected = log && strstr(log, "remote-add") && !strstr(log, "install --user");
    }
    if (!expected) {
        fprintf(stderr, "mode=%s finished=%d success=%d error=%s log=%s\n",
                mode, result.completed, result.success,
                result.error ? result.error->message : "(none)",
                log ? log : "(none)");
    }
    g_free(log);
    g_clear_error(&result.error);
    g_object_unref(cancellable);
    g_main_loop_unref(result.loop);
    return expected;
}

int main(void)
{
    GError *error = NULL;
    char *directory = g_dir_make_tmp("now-moonlight-test-XXXXXX", &error);
    EXPECT(directory != NULL);
    char *executable = g_build_filename(directory, "flatpak", NULL);
    char *log = g_build_filename(directory, "commands.log", NULL);
    const char *fake = "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$NOW_TEST_FLATPAK_LOG\"\n"
        "if [ \"$NOW_TEST_FLATPAK_MODE\" = slow ]; then exec sleep 5; fi\n"
        "if [ \"$NOW_TEST_FLATPAK_MODE\" = fail-remote ] && "
        "[ \"$1\" = remote-add ]; then exit 2; fi\n"
        "if [ \"$NOW_TEST_FLATPAK_MODE\" = fail-install ] && "
        "[ \"$1\" = install ]; then exit 3; fi\n"
        "exit 0\n";
    EXPECT(g_file_set_contents(executable, fake, -1, &error));
    EXPECT(g_chmod(executable, 0700) == 0);
    const char *old_path = g_getenv("PATH");
    char *path = g_strdup_printf("%s:%s", directory, old_path ? old_path : "");
    g_setenv("PATH", path, TRUE);
    g_setenv("NOW_TEST_FLATPAK_LOG", log, TRUE);

    EXPECT(check("success", FALSE, TRUE, G_IO_ERROR_FAILED, log));
    EXPECT(check("fail-remote", FALSE, FALSE, G_IO_ERROR_FAILED, log));
    EXPECT(check("fail-install", FALSE, FALSE, G_IO_ERROR_FAILED, log));
    EXPECT(check("slow", TRUE, FALSE, G_IO_ERROR_CANCELLED, log));

    g_remove(log);
    g_remove(executable);
    g_rmdir(directory);
    g_free(path);
    g_free(log);
    g_free(executable);
    g_free(directory);
    puts("Moonlight install: command contract, failures, GTK loop and cancellation passed.");
    return 0;
}
