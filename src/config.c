#define _GNU_SOURCE
#include "config.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/*
 * The indices and key names are a persistent file-format contract.
 * Do not reorder them or rename the existing ~/.config/optiplex-desk folder.
 */
const char *const keys[CONFIG_COUNT] = {
    "host", "user", "relay", "relay_user", "wake_command",
    "videos", "music", "downloads", "browser", "moonlight_appimage",
    "storage_path", "model_host", "model_name", "tray_buttons",
    "ai_url", "featured_actions", "web_gaming_url"
};

static const char *const defaults[CONFIG_COUNT] = {
    "", "", "", "", "", "", "", "", "system", "", "/",
    "", "", "255", "", "207", ""
};

char cfg[CONFIG_COUNT][CONFIG_VALUE_SIZE];
int first_run = 0;

static void copy_value(char dest[CONFIG_VALUE_SIZE], const char *value)
{
    snprintf(dest, CONFIG_VALUE_SIZE, "%s", value ? value : "");
}

static int config_location(char path[PATH_MAX])
{
    char directory[PATH_MAX];
    const char *base = getenv("XDG_CONFIG_HOME");

    if (!base || !*base) {
        base = getenv("HOME");
        if (!base || !*base) {
            base = "/tmp";
        }
        if (snprintf(directory, sizeof directory, "%s/.config", base) >= (int)sizeof directory) {
            return 0;
        }
    } else if (snprintf(directory, sizeof directory, "%s", base) >= (int)sizeof directory) {
        return 0;
    }

    if (mkdir(directory, 0700) != 0 && errno != EEXIST) {
        return 0;
    }

    char app_dir[PATH_MAX];
    if (snprintf(app_dir, sizeof app_dir, "%s/optiplex-desk", directory) >= (int)sizeof app_dir) {
        return 0;
    }
    if (mkdir(app_dir, 0700) != 0 && errno != EEXIST) {
        return 0;
    }

    struct stat st;
    if (stat(app_dir, &st) != 0 || !S_ISDIR(st.st_mode)) {
        return 0;
    }
    return snprintf(path, PATH_MAX, "%s/config.ini", app_dir) < PATH_MAX;
}

int now_config_load_from(const char *path)
{
    for (int i = 0; i < CONFIG_COUNT; i++) {
        copy_value(cfg[i], defaults[i]);
    }
    first_run = 0;

    if (!path || !*path) {
        first_run = 1;
        return -1;
    }

    FILE *file = fopen(path, "r");
    if (!file) {
        first_run = 1;
        return errno == ENOENT ? 0 : -1;
    }

    int has_featured = 0;
    char line[1024];
    while (fgets(line, sizeof line, file)) {
        line[strcspn(line, "\r\n")] = '\0';
        char *value = strchr(line, '=');
        if (!value) {
            continue;
        }
        *value++ = '\0';
        for (int i = 0; i < CONFIG_COUNT; i++) {
            if (strcmp(line, keys[i]) == 0) {
                copy_value(cfg[i], value);
                if (i == FEATURED_MASK_SETTING) {
                    has_featured = 1;
                }
                break;
            }
        }
    }
    int ok = !ferror(file);
    if (fclose(file) != 0) {
        ok = 0;
    }

    /* Missing featured_actions means an upgrade from the original 8-tile UI. */
    if (!has_featured) {
        snprintf(cfg[FEATURED_MASK_SETTING], CONFIG_VALUE_SIZE, "%u",
                 EXISTING_INSTALL_FEATURED_MASK);
    }
    return ok ? 1 : -1;
}

int now_config_save_to(const char *path)
{
    if (!path || !*path) {
        return 0;
    }

    /* Newlines would corrupt the key=value format. Reject instead of writing. */
    for (int i = 0; i < CONFIG_COUNT; i++) {
        if (strchr(cfg[i], '\n') || strchr(cfg[i], '\r')) {
            return 0;
        }
    }

    char temporary[PATH_MAX];
    if (snprintf(temporary, sizeof temporary, "%s.tmp.XXXXXX", path) >=
        (int)sizeof temporary) {
        return 0;
    }
    int fd = mkstemp(temporary);
    if (fd < 0) {
        return 0;
    }
    if (fchmod(fd, 0600) != 0) {
        close(fd);
        unlink(temporary);
        return 0;
    }
    FILE *file = fdopen(fd, "w");
    if (!file) {
        close(fd);
        unlink(temporary);
        return 0;
    }

    int ok = 1;
    for (int i = 0; i < CONFIG_COUNT; i++) {
        if (fprintf(file, "%s=%s\n", keys[i], cfg[i]) < 0) {
            ok = 0;
            break;
        }
    }
    if (ok && fflush(file) != 0) {
        ok = 0;
    }
    if (ok && fsync(fd) != 0) {
        ok = 0;
    }
    if (fclose(file) != 0) {
        ok = 0;
    }
    if (ok && rename(temporary, path) != 0) {
        ok = 0;
    }
    if (!ok) {
        unlink(temporary);
    }
    return ok;
}

int now_config_load(void)
{
    char path[PATH_MAX];
    if (!config_location(path)) {
        return now_config_load_from(NULL);
    }
    return now_config_load_from(path);
}

int now_config_save(void)
{
    char path[PATH_MAX];
    return config_location(path) && now_config_save_to(path);
}
