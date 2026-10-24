#ifndef NOW_DOWNLOADS_FLOW_H
#define NOW_DOWNLOADS_FLOW_H
#include <gtk/gtk.h>
GtkWidget *now_downloads_page(void);
void now_downloads_refresh(const char *host, const char *user);
/* Opens embedded configured WebUI when approved and available, else queue. */
void now_downloads_open(const char *host, const char *user, const char *webui_url);
#endif
