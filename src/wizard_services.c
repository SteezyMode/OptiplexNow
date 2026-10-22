#include "wizard_services.h"
#include "presets.h"

#include <stdio.h>

int now_wizard_store_services(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *const urls[3])
{
    if (!config || !urls) {
        return 0;
    }
    for (int i = 0; i < 3; i++) {
        if (!urls[i] || !now_safe_preset_url(urls[i])) {
            return 0;
        }
    }
    for (int i = 0; i < 3; i++) {
        snprintf(config[5 + i], CONFIG_VALUE_SIZE, "%s", urls[i]);
    }
    return 1;
}
