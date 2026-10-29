#ifndef NOW_DOWNLOADS_QUEUE_VIEW_H
#define NOW_DOWNLOADS_QUEUE_VIEW_H
#include <gtk/gtk.h>
/* Native, read-only owner queue. Does not implement search or download actions. */
GtkWidget *now_downloads_queue_view_new(void);
gboolean now_downloads_queue_view_update(GtkWidget *view, const char *wire);
void now_downloads_queue_view_message(GtkWidget *view, const char *message);
#endif
