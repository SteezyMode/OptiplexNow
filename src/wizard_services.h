#ifndef OPTIPLEX_NOW_WIZARD_SERVICES_H
#define OPTIPLEX_NOW_WIZARD_SERVICES_H

#include "config.h"

/* Return a bitmask of invalid Videos/Music/Downloads URLs (bit 0/1/2).
 * Valid fields are stored independently. Invalid fields retain their prior
 * values; an empty string intentionally clears one optional service. */
unsigned now_wizard_store_services(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *const urls[3]);

#endif
