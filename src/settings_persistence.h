#ifndef NOW_SETTINGS_PERSISTENCE_H
#define NOW_SETTINGS_PERSISTENCE_H

#include "config.h"
#include "tray_prefs.h"

/* Borrowed values from the live GTK form. This snapshot must be applied
 * synchronously while the form is alive; it owns no strings or widgets.
 * The persistence layer deliberately has no GTK or host-service dependency.
 */
typedef struct {
    const char *fields[8];
    const char *disk_path;
    int browser_choice;
    unsigned tray_selected[NOW_TRAY_ACTIONS];
    unsigned featured_selected[NOW_TRAY_ACTIONS];
    const char *desktop_caption;
    int order[NOW_TRAY_ACTIONS];
    const char *web_gaming_url;
    const char *startup_page;
    int login_tray_enabled;
} NowSettingsDraft;

typedef enum {
    NOW_SETTINGS_APPLY_OK = 0,
    NOW_SETTINGS_APPLY_INVALID_WEB_URL = 1,
    NOW_SETTINGS_APPLY_AUTOSTART_FAILED = 2,
    NOW_SETTINGS_APPLY_INVALID_DRAFT = 3
} NowSettingsApplyResult;

/* Preserve existing Save semantics: safely verify/apply autostart first,
 * then apply fields to the caller's config, write tray prefs and UI state.
 * Does NOT write config.ini: the application still owns config_save() and
 * its model heading update. Partial failures of independent tray/UI writes
 * remain best-effort, as before; the result only reports a rejected URL
 * (still a successful save) or the blocking autostart/invalid-draft error.
 */
NowSettingsApplyResult now_settings_apply(
    const NowSettingsDraft *draft,
    char values[CONFIG_COUNT][CONFIG_VALUE_SIZE]);

#endif
