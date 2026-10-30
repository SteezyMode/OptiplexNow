#ifndef OPTIPLEX_NOW_WIZARD_SERVICES_H
#define OPTIPLEX_NOW_WIZARD_SERVICES_H

#include "config.h"

/* Return a bitmask of invalid Videos/Music/Downloads URLs (bit 0/1/2).
 * Valid fields are stored independently. Invalid fields retain their prior
 * values; an empty string intentionally clears one optional service. */
unsigned now_wizard_store_services(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *const urls[3]);

/* First-run wizard's config merge (no GTK or disk writes).
 * An invalid host/user or a newline in any first-five field rejects the
 * entire connection update, preserving the previous config in place.
 * A validated, explicitly imported preset supplies optional overrides.
 * Imported Videos/Music/Downloads URLs are all-or-nothing, deliberately
 * unlike the independent manual helper above: preserve legacy wizard Save.
 * Return 1 when connection details are valid, else 0.
 */
int now_wizard_merge_connection(
    char config[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    const char *host, const char *user,
    const char staged[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    int preset_loaded);

#endif
