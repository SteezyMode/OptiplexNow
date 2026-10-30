#include "settings_persistence.h"
#include "desktop_autostart.h"
#include "host_metrics.h"
#include "presets.h"
#include "ui_state.h"

#include <stdio.h>
#include <string.h>

static void copy_value(char value[CONFIG_VALUE_SIZE], const char *text)
{
    snprintf(value, CONFIG_VALUE_SIZE, "%s", text ? text : "");
}

NowSettingsApplyResult now_settings_apply(
    const NowSettingsDraft *draft,
    char values[CONFIG_COUNT][CONFIG_VALUE_SIZE])
{
    if (!draft || !values)
        return NOW_SETTINGS_APPLY_INVALID_DRAFT;

    /* The autostart guard intentionally precedes every other mutation.
     * A foreign/unrecognized desktop entry must never be overwritten. */
    gboolean login_tray_enabled = FALSE;
    if (!now_desktop_autostart_get(&login_tray_enabled) ||
        (login_tray_enabled != !!draft->login_tray_enabled &&
         !now_desktop_autostart_set(!!draft->login_tray_enabled)))
        return NOW_SETTINGS_APPLY_AUTOSTART_FAILED;

    /* Keep invalid newline-containing fields unchanged, as before.
     * Check the untruncated value, not the eventual 511-byte copy. */
    for (int i = 0; i < 8; ++i) {
        const char *text = draft->fields[i];
        if (!text || strchr(text, '\n') || strchr(text, '\r'))
            continue;
        copy_value(values[i], text);
    }

    static const char *const browsers[] = {
        "auto", "system", "chrome-flatpak", "chrome"
    };
    if (now_host_safe_disk_path(draft->disk_path))
        copy_value(values[10], draft->disk_path);
    int browser_choice = draft->browser_choice;
    copy_value(values[8], browsers[browser_choice >= 0 &&
                                    browser_choice < 4 ? browser_choice : 0]);

    unsigned tray = 0, featured = 0;
    for (int i = 0; i < NOW_TRAY_ACTIONS; ++i) {
        if (draft->tray_selected[i]) tray |= 1u << i;
        if (draft->featured_selected[i]) featured |= 1u << i;
    }
    snprintf(values[TRAY_MASK_SETTING], CONFIG_VALUE_SIZE, "%u", tray);
    snprintf(values[FEATURED_MASK_SETTING], CONFIG_VALUE_SIZE, "%u", featured);

    if (draft->desktop_caption && *draft->desktop_caption &&
        !strchr(draft->desktop_caption, '\n') &&
        !strchr(draft->desktop_caption, '\r'))
        now_tray_desktop_caption_save(draft->desktop_caption);

    now_tray_order_save(draft->order);

    /* An invalid optional Web Gaming override never replaces the saved URL.
     * The rest of the Settings save still succeeds. */
    int invalid_web_url = !now_safe_preset_url(draft->web_gaming_url);
    if (!invalid_web_url)
        copy_value(values[16], draft->web_gaming_url);

    now_ui_state_set_start_page(draft->startup_page);
    now_ui_state_save();

    return invalid_web_url ? NOW_SETTINGS_APPLY_INVALID_WEB_URL :
                             NOW_SETTINGS_APPLY_OK;
}
