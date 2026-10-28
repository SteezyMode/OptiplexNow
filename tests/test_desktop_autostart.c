#include "desktop_autostart.h"
#include <glib.h>
#include <glib/gstdio.h>
#include <unistd.h>
#include <sys/stat.h>
#include <string.h>

int main(void)
{
    /* This standalone process has never called g_get_user_config_dir yet. */
    GError *error = NULL;
    char *root = g_dir_make_tmp("now-autostart-test-XXXXXX", &error);
    g_assert_no_error(error);
    g_assert_nonnull(root);
    g_setenv("XDG_CONFIG_HOME", root, TRUE);

    gboolean enabled = TRUE;
    g_assert_true(now_desktop_autostart_get(&enabled));
    g_assert_false(enabled);
    g_assert_true(now_desktop_autostart_set(TRUE));
    g_assert_true(now_desktop_autostart_get(&enabled));
    g_assert_true(enabled);
    char *path = g_build_filename(root, "autostart", "optiplex-now.desktop", NULL);
    char *data = NULL;
    g_assert_true(g_file_get_contents(path, &data, NULL, NULL));
    g_assert_nonnull(strstr(data, "Exec=/usr/bin/optiplex-now --start-in-tray"));
    g_free(data);

    g_assert_true(now_desktop_autostart_set(FALSE));
    g_assert_false(g_file_test(path, G_FILE_TEST_EXISTS));
    g_assert_true(now_desktop_autostart_get(&enabled));
    g_assert_false(enabled);

    /* Preserve a different app's autostart file, including unrecognized Exec. */
    g_assert_true(g_file_set_contents(path,
        "[Desktop Entry]\nType=Application\nName=OptiPlex Now\n"
        "Exec=/usr/bin/other-launcher\n", -1, NULL));
    g_assert_false(now_desktop_autostart_get(&enabled));
    g_assert_false(now_desktop_autostart_set(TRUE));
    g_assert_false(now_desktop_autostart_set(FALSE));
    g_assert_true(g_file_test(path, G_FILE_TEST_EXISTS));

    /* The previously documented manual cp/sed autostart is recognizable. */
    g_assert_true(g_file_set_contents(path,
        "[Desktop Entry]\nType=Application\nName=OptiPlex Now\n"
        "Exec=/usr/bin/optiplex-now --start-in-tray\n", -1, NULL));
    g_assert_true(now_desktop_autostart_get(&enabled));
    g_assert_true(enabled);
    g_assert_true(now_desktop_autostart_set(FALSE));
    g_assert_false(g_file_test(path, G_FILE_TEST_EXISTS));

    /* Never replace an autostart symlink. */
    char *other = g_build_filename(root, "other.txt", NULL);
    g_assert_true(g_file_set_contents(other, "preserve", -1, NULL));
    g_assert_cmpint(symlink(other, path), ==, 0);
    g_assert_false(now_desktop_autostart_set(TRUE));
    g_assert_false(now_desktop_autostart_set(FALSE));
    g_assert_true(g_file_test(path, G_FILE_TEST_IS_SYMLINK));
    g_assert_cmpint(g_remove(path), ==, 0);
    g_assert_cmpint(g_remove(other), ==, 0);
    char *dir = g_build_filename(root, "autostart", NULL);
    g_assert_cmpint(g_rmdir(dir), ==, 0);
    g_assert_cmpint(g_rmdir(root), ==, 0);
    g_free(dir);
    g_free(other);
    g_free(path);
    g_free(root);
    return 0;
}
