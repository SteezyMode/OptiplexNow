#ifndef OPTIPLEX_NOW_WIZARD_SERVICES_H
#define OPTIPLEX_NOW_WIZARD_SERVICES_H

#include "config.h"

/* Save the three service URLs as a unit. An invalid URL must never overwrite
 * a previously configured service or cause a partial three-field update.
 * Empty URLs are intentional: a user can clear an optional service. */
int now_wizard_store_services(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *const urls[3]);

#endif
