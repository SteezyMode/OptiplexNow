#include "settings_values.h"

#include "host_metrics.h"
#include "presets.h"

#include <stdio.h>
#include <string.h>

/* Retain the established Settings Save behavior without GTK dependencies. */
int now_settings_prepare_config(
    NowSettingsPrepared *output,
    const char existing[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const NowSettingsInput *input)
{
    if (!output || !existing || !input || !input->disk_path ||
        !input->web_gaming_url)
        return 0;
    for (int i = 0; i < 8; ++i)
        if (!input->connection[i])
            return 0;

    /* Prepare in a local object: invalid inputs must not partially mutate
     * the output or the saved config, even when values alias the caller. */
    NowSettingsPrepared next = {0};
    memcpy(next.values, existing, sizeof next.values);

    for (int i = 0; i < 8; ++i) {
        const char *value = input->connection[i];
        if (strchr(value, '\n') || strchr(value, '\r'))
            continue;
        snprintf(next.values[i], CONFIG_VALUE_SIZE, "%s", value);
    }

    if (now_host_safe_disk_path(input->disk_path))
        snprintf(next.values[10], CONFIG_VALUE_SIZE, "%s", input->disk_path);

    const char *browsers[] = {"auto", "system", "chrome-flatpak", "chrome"};
    const int choice = input->browser_choice;
    snprintf(next.values[8], CONFIG_VALUE_SIZE, "%s",
             browsers[choice >= 0 && choice < 4 ? choice : 0]);

    snprintf(next.values[13], CONFIG_VALUE_SIZE, "%u", input->tray_mask);
    snprintf(next.values[FEATURED_MASK_SETTING], CONFIG_VALUE_SIZE, "%u",
             input->featured_mask);

    next.web_gaming_url_valid = now_safe_preset_url(input->web_gaming_url);
    if (next.web_gaming_url_valid)
        snprintf(next.values[16], CONFIG_VALUE_SIZE, "%s",
                 input->web_gaming_url);

    *output = next;
    return 1;
}
