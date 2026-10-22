#include "wizard_services.h"
#include "presets.h"

#include <stdio.h>

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
