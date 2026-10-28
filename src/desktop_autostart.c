#include "desktop_autostart.h"
#include <glib/gstdio.h>
#include <sys/stat.h>
#include <unistd.h>

#define NOW_DESKTOP_FILE "optiplex-now.desktop"
#define NOW_START_COMMAND "/usr/bin/optiplex-now --start-in-tray"
#define NOW_PLAIN_COMMAND "/usr/bin/optiplex-now"
#define MAX_ENTRY 8192

/* A user-created autostart entry must not be silently overwritten.
 * Also recognize the documented manual cp/sed version without an owner tag. */
static char *entry_path(void)
{
    return g_build_filename(g_get_user_config_dir(), "autostart",
                            NOW_DESKTOP_FILE, NULL);
}

static gboolean recognized(const char *path, gboolean *enabled,
                           gboolean *exists)
{
    struct stat st;
    if (g_lstat(path, &st) != 0) {
        if (errno == ENOENT) {
            *exists = FALSE;
            *enabled = FALSE;
            return TRUE;
        }
        return FALSE;
    }
    *exists = TRUE;
    if (!S_ISREG(st.st_mode) || st.st_uid != geteuid() ||
        st.st_size > MAX_ENTRY || st.st_nlink != 1)
        return FALSE;
    GKeyFile *key = g_key_file_new();
    GError *error = NULL;
    gboolean ok = g_key_file_load_from_file(key, path, G_KEY_FILE_NONE, &error);
    g_clear_error(&error);
    if (!ok) {
        g_key_file_unref(key);
        return FALSE;
    }
    char *type = g_key_file_get_string(key, "Desktop Entry", "Type", NULL);
    char *name = g_key_file_get_string(key, "Desktop Entry", "Name", NULL);
    char *exec = g_key_file_get_string(key, "Desktop Entry", "Exec", NULL);
    gboolean disabled = g_key_file_get_boolean(key, "Desktop Entry",
                                                "Hidden", NULL);
    ok = g_strcmp0(type, "Application") == 0 &&
         g_strcmp0(name, "OptiPlex Now") == 0 &&
         (g_strcmp0(exec, NOW_START_COMMAND) == 0 ||
          g_strcmp0(exec, NOW_PLAIN_COMMAND) == 0);
    *enabled = ok && !disabled && g_strcmp0(exec, NOW_START_COMMAND) == 0;
    g_free(exec);
    g_free(type);
    g_free(name);
    g_key_file_unref(key);
    return ok;
}

gboolean now_desktop_autostart_get(gboolean *enabled)
{
    if (!enabled)
        return FALSE;
    gboolean exists = FALSE;
    char *path = entry_path();
    gboolean result = recognized(path, enabled, &exists);
    g_free(path);
    return result;
}

gboolean now_desktop_autostart_set(gboolean enabled)
{
    char *path = entry_path();
    gboolean is_enabled = FALSE, exists = FALSE;
    if (!recognized(path, &is_enabled, &exists)) {
        g_free(path);
        return FALSE;
    }
    if (!enabled) {
        gboolean ok = !exists || g_remove(path) == 0;
        g_free(path);
        return ok;
    }
    if (exists && is_enabled) {
        g_free(path);
        return TRUE;
    }
    char *dir = g_path_get_dirname(path);
    gboolean ok = g_mkdir_with_parents(dir, 0700) == 0;
    g_free(dir);
    if (ok) {
        /* Auto-start uses a visible, non-privileged, per-user XDG entry.
         * Startup code already checks tray availability before hiding. */
        const char *data =
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=OptiPlex Now\n"
            "Comment=Start in the system tray at login\n"
            "Exec=" NOW_START_COMMAND "\n"
            "Icon=optiplex-now\n"
            "Terminal=false\n"
            "Categories=Network;Utility;\n"
            "X-GNOME-Autostart-enabled=true\n";
        ok = g_file_set_contents(path, data, -1, NULL);
    }
    g_free(path);
    return ok;
}
