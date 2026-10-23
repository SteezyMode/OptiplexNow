#ifndef NOW_DOWNLOADS_FLOW_H
#define NOW_DOWNLOADS_FLOW_H
#include <gtk/gtk.h>
GtkWidget *now_downloads_page(void);
void now_downloads_refresh(const char *host, const char *user);
#endif
