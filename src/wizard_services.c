#include "wizard_services.h"
#include "presets.h"

#include <stdio.h>
#include <string.h>

unsigned now_wizard_store_services(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *const urls[3])
{
    if (!config || !urls) {
        return 7u;
    }
    unsigned invalid = 0;
    for (int i = 0; i < 3; i++) {
        if (!urls[i] || !now_safe_preset_url(urls[i])) {
            invalid |= 1u << i;
            continue;
        }
        snprintf(config[5 + i], CONFIG_VALUE_SIZE, "%s", urls[i]);
    }
    return invalid;
}

/* Preserve the original first-run wizard's merge semantics verbatim.
 * Only the application shell persists config.ini and updates GTK notices. */
int now_wizard_merge_connection(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *host, const char *user,
    const char staged[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    int preset_loaded)
{
    if (!config || !host || !user || !staged)
        return 0;

    const char *const values[5] = {
        host, user, staged[2], staged[3], staged[4]
    };
    int valid = now_valid_host(host) && now_valid_user(user);
    for (int i = 0; i < 5; ++i)
        if (strchr(values[i], '\n') || strchr(values[i], '\r'))
            valid = 0;
    if (!valid)
        return 0;

    for (int i = 0; i < 5; ++i)
        snprintf(config[i], CONFIG_VALUE_SIZE, "%s", values[i]);

    if (preset_loaded) {
        /* Import these three settings only from a previously validated
         * preset. The wizard never clears them during normal onboarding. */
        snprintf(config[10], CONFIG_VALUE_SIZE, "%s", staged[10]);
        snprintf(config[14], CONFIG_VALUE_SIZE, "%s", staged[14]);
        snprintf(config[16], CONFIG_VALUE_SIZE, "%s", staged[16]);

        const char *const urls[3] = {staged[5], staged[6], staged[7]};
        int urls_valid = 1;
        for (int i = 0; i < 3; ++i)
            if (!now_safe_preset_url(urls[i]))
                urls_valid = 0;
        if (urls_valid)
            for (int i = 0; i < 3; ++i)
                snprintf(config[5 + i], CONFIG_VALUE_SIZE, "%s", urls[i]);
    }
    return 1;
}
