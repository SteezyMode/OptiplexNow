#ifndef NOW_DOWNLOADS_SEARCH_VIEW_H
#define NOW_DOWNLOADS_SEARCH_VIEW_H
#include <gtk/gtk.h>
GtkWidget *now_downloads_search_view_new(void);
void now_downloads_search_view_configure(GtkWidget *view,const char *host,
                                          const char *user,const char *helper);
gboolean now_downloads_search_view_update(GtkWidget *view,const char *wire);
#endif
