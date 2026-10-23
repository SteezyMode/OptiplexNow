#ifndef NOW_DOWNLOADS_WEBVIEW_H
#define NOW_DOWNLOADS_WEBVIEW_H
#include <gtk/gtk.h>

/* Optional WebKitGTK runtime. Returns NULL unless the URL is an approved,
 * private, same-host qBittorrent endpoint and WebKitGTK is available.
 * Authentication is always managed by qBittorrent itself. */
GtkWidget *now_downloads_webview_new(const char *url, const char *approved_host);
gboolean now_downloads_webview_url_allowed(const char *url, const char *approved_host);
#endif
