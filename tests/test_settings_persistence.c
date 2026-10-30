#define _GNU_SOURCE
#include "settings_persistence.h"
#include "desktop_autostart.h"
#include "tray_prefs.h"
#include "ui_state.h"
#include <glib.h>
#include <glib/gstdio.h>
#include <string.h>

/* No GTK or application binary: all writes are confined to disposable HOME
 * and XDG_CONFIG_HOME. This is NOT a host/release acceptance test. */
static void clean_file(const char *dir, const char *name)
{
    char *path = g_build_filename(dir, name, NULL);
    g_assert_cmpint(g_remove(path), ==, 0);
    g_free(path);
}

int main(void)
{
    GError *error = NULL;
    char *root = g_dir_make_tmp("now-settings-save.XXXXXX", &error);
    g_assert_no_error(error);
    g_assert_nonnull(root);
    char *home = g_build_filename(root, "home", NULL);
    char *xdg = g_build_filename(root, "xdg", NULL);
    g_assert_cmpint(g_mkdir(home, 0700), ==, 0);
    g_assert_cmpint(g_mkdir(xdg, 0700), ==, 0);
    g_setenv("HOME", home, TRUE);
    g_setenv("XDG_CONFIG_HOME", xdg, TRUE);
    /* Existing users already have the legacy preference directories.
     * The tray helpers intentionally do not provision them on Save. */
    char *tray_dir = g_build_filename(xdg, "optiplex-desk", NULL);
    char *home_dotconfig = g_build_filename(home, ".config", NULL);
    char *home_config = g_build_filename(home_dotconfig, "optiplex-desk", NULL);
    g_assert_cmpint(g_mkdir(tray_dir, 0700), ==, 0);
    g_assert_cmpint(g_mkdir(home_dotconfig, 0700), ==, 0);
    g_assert_cmpint(g_mkdir(home_config, 0700), ==, 0);

    char values[CONFIG_COUNT][CONFIG_VALUE_SIZE] = {{0}};
    g_strlcpy(values[0], "old-server", CONFIG_VALUE_SIZE);
    g_strlcpy(values[1], "old-owner", CONFIG_VALUE_SIZE);
    g_strlcpy(values[10], "/", CONFIG_VALUE_SIZE);
    g_strlcpy(values[16], "https://previous.example", CONFIG_VALUE_SIZE);
    char before[sizeof values];
    memcpy(before, values, sizeof before);

    NowSettingsDraft draft = {0};
    const char *fields[] = {
        "192.0.2.10", "owner", "192.0.2.20", "relay", "/opt/wake",
        "https://media.example", "https://music.example",
        "https://downloads.example"
    };
    for (int i = 0; i < 8; ++i) {
        draft.fields[i] = fields[i];
        draft.order[i] = 7 - i;
        draft.tray_selected[i] = (i % 2) == 0;
        draft.featured_selected[i] = (i % 2) != 0;
    }
    draft.disk_path = "/mnt/library";
    draft.browser_choice = 2;
    draft.desktop_caption = "Projector";
    draft.web_gaming_url = "https://wolf.example";
    draft.startup_page = "games";
    draft.login_tray_enabled = 1;

    /* Foreign/autostart-conflicting files block ALL Settings changes, and
     * remain unmodified, before tray, UI state or config is written. */
    char *autostart_dir = g_build_filename(xdg, "autostart", NULL);
    g_assert_cmpint(g_mkdir(autostart_dir, 0700), ==, 0);
    char *autostart = g_build_filename(autostart_dir,
                                      "optiplex-now.desktop", NULL);
    const char *foreign = "[Desktop Entry]\nType=Application\n"
                          "Name=Other Program\nExec=/usr/bin/other\n";
    g_assert_true(g_file_set_contents(autostart, foreign, -1, NULL));
    g_assert_cmpint(now_settings_apply(&draft, values), ==,
                    NOW_SETTINGS_APPLY_AUTOSTART_FAILED);
    g_assert_cmpmem(values, sizeof values, before, sizeof before);
    char *stored = NULL;
    g_assert_true(g_file_get_contents(autostart, &stored, NULL, NULL));
    g_assert_cmpstr(stored, ==, foreign);
    g_free(stored);
    g_assert_cmpint(g_remove(autostart), ==, 0);

    /* Authorized, unchanged Save order: autostart, 8 fields, disk,
     * browser, independent tray masks, caption/order, URL, UI start page. */
    now_ui_state_load();
    g_assert_cmpint(now_settings_apply(&draft, values), ==,
                    NOW_SETTINGS_APPLY_OK);
    g_assert_cmpstr(values[0], ==, "192.0.2.10");
    g_assert_cmpstr(values[1], ==, "owner");
    g_assert_cmpstr(values[5], ==, "https://media.example");
    g_assert_cmpstr(values[8], ==, "chrome-flatpak");
    g_assert_cmpstr(values[10], ==, "/mnt/library");
    g_assert_cmpstr(values[TRAY_MASK_SETTING], ==, "85");
    g_assert_cmpstr(values[FEATURED_MASK_SETTING], ==, "170");
    g_assert_cmpstr(values[16], ==, "https://wolf.example");
    g_assert_cmpstr(now_ui_state_start_page(), ==, "games");

    gboolean enabled = FALSE;
    g_assert_true(now_desktop_autostart_get(&enabled));
    g_assert_true(enabled);
    int order[8] = {0};
    now_tray_order_load(order);
    for (int i = 0; i < 8; ++i)
        g_assert_cmpint(order[i], ==, 7 - i);
    char caption[128];
    now_tray_desktop_caption(caption, sizeof caption);
    g_assert_cmpstr(caption, ==, "Projector");
    char *legacy_conf = g_build_filename(xdg, "optiplex-desk",
                                         "config.ini", NULL);
    g_assert_false(g_file_test(legacy_conf, G_FILE_TEST_EXISTS));

    /* Invalid values are ignored independently; valid changes still save.
     * This intentionally preserves original best-effort behavior. */
    draft.fields[0] = "bad\nserver";
    draft.fields[1] = "new-owner";
    draft.disk_path = "/bad path";
    draft.browser_choice = 88;
    draft.desktop_caption = "bad\ncaption";
    draft.order[0] = draft.order[1];  /* invalid duplicate order */
    draft.web_gaming_url = "javascript:alert(1)";
    draft.startup_page = "downloads"; /* unsupported startup preference */
    g_assert_cmpint(now_settings_apply(&draft, values), ==,
                    NOW_SETTINGS_APPLY_INVALID_WEB_URL);
    g_assert_cmpstr(values[0], ==, "192.0.2.10");
    g_assert_cmpstr(values[1], ==, "new-owner");
    g_assert_cmpstr(values[8], ==, "auto");
    g_assert_cmpstr(values[10], ==, "/mnt/library");
    g_assert_cmpstr(values[16], ==, "https://wolf.example");
    g_assert_cmpstr(now_ui_state_start_page(), ==, "games");
    now_tray_order_load(order);
    for (int i = 0; i < 8; ++i)
        g_assert_cmpint(order[i], ==, 7 - i);
    now_tray_desktop_caption(caption, sizeof caption);
    g_assert_cmpstr(caption, ==, "Projector");

    /* Recognized start-in-tray preferences may be switched off. */
    draft.login_tray_enabled = 0;
    draft.web_gaming_url = "";
    g_assert_cmpint(now_settings_apply(&draft, values), ==,
                    NOW_SETTINGS_APPLY_OK);
    g_assert_false(g_file_test(autostart, G_FILE_TEST_EXISTS));
    g_assert_cmpstr(values[16], ==, "");
    g_assert_cmpint(now_settings_apply(NULL, values), ==,
                    NOW_SETTINGS_APPLY_INVALID_DRAFT);

    /* Explicitly remove only files under the test's new private root. */
    char *ui_dir = g_build_filename(xdg, "optiplex-now", NULL);
    clean_file(tray_dir, "tray-order");
    clean_file(ui_dir, "ui-state.ini");
    clean_file(home_config, "desktop-label");
    g_assert_cmpint(g_rmdir(tray_dir), ==, 0);
    g_assert_cmpint(g_rmdir(ui_dir), ==, 0);
    g_assert_cmpint(g_rmdir(home_config), ==, 0);
    g_assert_cmpint(g_rmdir(home_dotconfig), ==, 0);
    g_assert_cmpint(g_rmdir(autostart_dir), ==, 0);
    g_assert_cmpint(g_rmdir(xdg), ==, 0);
    g_assert_cmpint(g_rmdir(home), ==, 0);
    g_assert_cmpint(g_rmdir(root), ==, 0);
    g_free(legacy_conf);
    g_free(home_dotconfig);
    g_free(home_config);
    g_free(ui_dir);
    g_free(tray_dir);
    g_free(autostart);
    g_free(autostart_dir);
    g_free(home);
    g_free(xdg);
    g_free(root);
    g_print("Settings persistence passed: independent validation, real local "
            "writes, blocked foreign autostart and legacy data safety.\n");
    return 0;
}
