#ifndef OPTIPLEX_NOW_PRESETS_H
#define OPTIPLEX_NOW_PRESETS_H

#include <stddef.h>

/* Keep legacy keys and headers stable: a public rebrand must not discard .onp data. */
#define NOW_PRESET_CONFIG_COUNT 17
#define NOW_PRESET_VALUE_SIZE 512

int now_valid_host(const char *host);
int now_valid_user(const char *user);
int now_safe_wake_path(const char *path);
int now_safe_preset_url(const char *url);
/* Build an optional user-configured MoonlightWeb endpoint safely. No default
 * public domain. Base may include a path; no query, userinfo or fragment. */
int now_web_gaming_url(const char *base, int settings, char *out, size_t cap);
int now_preset_values_valid(char values[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE]);
int now_preset_read(const char *path, char values[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE],
                    const char *const keys[NOW_PRESET_CONFIG_COUNT]);
int now_preset_write(const char *path, char values[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE],
                     const char *const keys[NOW_PRESET_CONFIG_COUNT]);

#endif
