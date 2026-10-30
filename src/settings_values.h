#ifndef NOW_SETTINGS_VALUES_H
#define NOW_SETTINGS_VALUES_H

#include "config.h"

/* GTK-free snapshot of the user-editable values from the Settings form.
 * The caller retains ownership of all pointers for this synchronous call.
 * Administrative actions, autostart, and file writes are not performed here.
 */
typedef struct {
    const char *connection[8];
    const char *disk_path;
    int browser_choice;
    unsigned tray_mask;
    unsigned featured_mask;
    const char *web_gaming_url;
} NowSettingsInput;

typedef struct {
    char values[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    /* A rejected optional override preserves the previously saved value. */
    int web_gaming_url_valid;
} NowSettingsPrepared;

/* Merge edited fields with the existing 17-field config without mutating it.
 * Preserve all untouched fields and the original config field ordering.
 * Return 0 only for missing required pointers; never write output in that case.
 */
int now_settings_prepare_config(
    NowSettingsPrepared *output,
    const char existing[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const NowSettingsInput *input);

#endif
