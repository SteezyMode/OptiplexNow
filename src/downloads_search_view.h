#ifndef NOW_DOWNLOADS_SEARCH_VIEW_H
#define NOW_DOWNLOADS_SEARCH_VIEW_H
#include <gtk/gtk.h>
typedef void (*NowDownloadsMagnetSelected)(const char *magnet,gpointer user_data);
GtkWidget *now_downloads_search_view_new(void);
void now_downloads_search_view_on_select(GtkWidget *view,
                                         NowDownloadsMagnetSelected callback,
                                         gpointer user_data);
void now_downloads_search_view_configure(GtkWidget *view,const char *host,
                                          const char *user,const char *helper);
gboolean now_downloads_search_view_update(GtkWidget *view,const char *wire);
#endif
