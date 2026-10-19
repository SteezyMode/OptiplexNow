#define _GNU_SOURCE
#include "presets.h"

#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Original export/import formats are permanent migration inputs, even after renaming. */
#define PRESET_HEADER_V1 "# OptiPlex Now server preset v1\n"
#define PRESET_HEADER_V2 "# OptiPlex Now server preset v2\n"
#define PRESET_HEADER_V2_LEGACY "# OptiPlex Now server preset v2 (v1 imports supported)\n"

/* Only these ten non-secret settings are exported. */
#define PRESET_COUNT 10
static const int preset_indices[PRESET_COUNT]={0,1,2,3,4,5,6,7,10,14};

static void preset_copy(char *dest, size_t cap, const char *src) {
    snprintf(dest, cap, "%s", src ? src : "");
}

int now_valid_host(const char *s) {
    if (!s || !*s || strlen(s) > 250) {
        return 0;
    }
    for (; *s; s++) {
        if (!(isalnum((unsigned char)*s) || strchr(".-:_", *s))) {
            return 0;
        }
    }
    return 1;
}

int now_valid_user(const char *s) {
    if (!s || !*s || strlen(s) > 100 || *s == '-') {
        return 0;
    }
    for (; *s; s++) {
        if (!(isalnum((unsigned char)*s) || strchr("._-", *s))) {
            return 0;
        }
    }
    return 1;
}

int now_safe_wake_path(const char *s) {
    if (!s || !*s) {
        return 1;
    }
    if (*s != '/' || strlen(s) > 350) {
        return 0;
    }
    for (; *s; s++) {
        if (!(isalnum((unsigned char)*s) || strchr("/_.-", *s))) {
            return 0;
        }
    }
    return 1;
}

int now_safe_preset_url(const char *s) {
    if (!s || !*s) {
        return 1;
    }
    if (strncmp(s, "https://", 8) && strncmp(s, "http://", 7)) {
        return 0;
    }
    const char *start = strstr(s, "://") + 3;
    if (!*start || strchr(start, '@') || strchr(s, '?') || strchr(s, '#') || strlen(s) >= 500) {
        return 0;
    }
    for (; *s; s++) {
        if ((unsigned char)*s <= 32 || (unsigned char)*s >= 127) {
            return 0;
        }
    }
    return 1;
}

int now_preset_values_valid(char v[NOW_PRESET_CONFIG_COUNT][512]) {
    if (!now_valid_host(v[0]) || !now_valid_user(v[1])) return 0;
    if (*v[2] && !now_valid_host(v[2])) return 0;
    if (*v[3] && !now_valid_user(v[3])) return 0;
    if (!now_safe_wake_path(v[4])) return 0;
    for (int i = 5; i <= 7; i++) {
        if (!now_safe_preset_url(v[i])) return 0;
    }
    if(!now_safe_preset_url(v[14]))return 0;
    if (*v[10] && v[10][0] != '/') return 0;

    for (int i = 0; i < PRESET_COUNT; i++) {
        const char *value = v[preset_indices[i]];
        if (strchr(value, '\n') || strchr(value, '\r') || strlen(value) >= 500) {
            return 0;
        }
    }
    return 1;
}

/* Invalid imports leave existing settings untouched. */
int now_preset_read(const char *path, char v[NOW_PRESET_CONFIG_COUNT][512],
                    const char *const keys[NOW_PRESET_CONFIG_COUNT]) {
    FILE *f = fopen(path, "r");
    if (!f) {
        return 0;
    }
    char staged[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE];
    memcpy(staged, v, sizeof staged);

    char header[128];
    if (!fgets(header, sizeof header, f) ||
        (strcmp(header, PRESET_HEADER_V1) && strcmp(header, PRESET_HEADER_V2) &&
         strcmp(header, PRESET_HEADER_V2_LEGACY))) {
        fclose(f);
        return 0;
    }

    char line[1024];
    int found_host = 0;
    while (fgets(line, sizeof line, f)) {
        if (strlen(line) > 900 || (!strchr(line, '\n') && !feof(f))) {
            fclose(f);
            return 0;
        }
        line[strcspn(line, "\r\n")] = '\0';
        char *eq = strchr(line, '=');
        if (!eq) {
            if(*line && *line!='#') {
                fclose(f);
                return 0;
            }
            continue;
        }
        *eq++ = '\0';
        int match = 0;
        for (int i = 0; i < PRESET_COUNT; i++) {
            int j = preset_indices[i];
            if (!strcmp(line, keys[j])) {
                preset_copy(staged[j], NOW_PRESET_VALUE_SIZE, eq);
                match = 1;
                if (j == 0) {
                    found_host = 1;
                }
                break;
            }
        }
        if (!match) {
            fclose(f);
            return 0;
        }
    }
    int clean_eof = !ferror(f);
    fclose(f);
    if (!clean_eof || !found_host || !now_preset_values_valid(staged)) {
        return 0;
    }
    memcpy(v, staged, sizeof staged);
    return 1;
}

int now_preset_write(const char *path, char v[NOW_PRESET_CONFIG_COUNT][512],
                     const char *const keys[NOW_PRESET_CONFIG_COUNT]) {
    if (!now_preset_values_valid(v)) {
        return 0;
    }
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0) {
        return 0;
    }
    FILE *f = fdopen(fd, "w");
    if (!f) {
        close(fd);
        return 0;
    }
    int ok = fprintf(f, "%s", PRESET_HEADER_V2) > 0;
    for (int i = 0; i < PRESET_COUNT; i++) {
        int j = preset_indices[i];
        if (fprintf(f, "%s=%s\n", keys[j], v[j]) < 0) {
            ok = 0;
        }
    }
    if (fclose(f) != 0) {
        ok = 0;
    }
    return ok;
}
