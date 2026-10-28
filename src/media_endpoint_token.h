#ifndef NOW_MEDIA_ENDPOINT_TOKEN_H
#define NOW_MEDIA_ENDPOINT_TOKEN_H
#include <glib.h>
/* Parse only the fixed media helper result. Host is already configured and
 * validated in main GTK; no hostname or credential can come from the helper. */
gchar *now_media_url_from_token(const char *host, const char *result);
#endif
