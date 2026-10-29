#ifndef NOW_DOWNLOADS_DESTINATION_VIEW_H
#define NOW_DOWNLOADS_DESTINATION_VIEW_H
#include <gtk/gtk.h>
GtkWidget *now_downloads_destination_view_new(void);
void now_downloads_destination_view_configure(GtkWidget *view,const char *host,
                                              const char *user,const char *helper);
void now_downloads_destination_view_select(GtkWidget *view,const char *magnet);
void now_downloads_destination_view_on_added(GtkWidget *view,
                                             void (*callback)(gpointer),gpointer data);
#endif
