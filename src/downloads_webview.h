#ifndef NOW_DOWNLOADS_WEBVIEW_H
#define NOW_DOWNLOADS_WEBVIEW_H
#include <gtk/gtk.h>

/* Optional WebKitGTK runtime. Returns NULL unless the URL is an approved,
 * private, same-host qBittorrent endpoint and WebKitGTK is available.
 * Authentication is always managed by qBittorrent itself. */
/* Reuse the existing tightly same-origin WebKit renderer for Jellyfin.
 * Returns NULL for missing WebKit, non-approved origins or unsupported URLs. */
GtkWidget *now_media_embedded_webview_new(const char *url,
                                          const char *approved_host);
GtkWidget *now_downloads_webview_new(const char *url, const char *approved_host);
gboolean now_downloads_webview_url_allowed(const char *url, const char *approved_host);
#endif
