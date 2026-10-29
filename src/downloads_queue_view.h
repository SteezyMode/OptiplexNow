#ifndef NOW_DOWNLOADS_QUEUE_VIEW_H
#define NOW_DOWNLOADS_QUEUE_VIEW_H
#include <gtk/gtk.h>
/* Native queue rendering; actions are delegated to the owner-checked broker. */
typedef void (*NowDownloadQueueAction)(const char *operation,
                                       const char *torrent_hash,
                                       const char *name,
                                       gpointer user_data);
void now_downloads_queue_view_on_action(GtkWidget *view,
                                       NowDownloadQueueAction callback,
                                       gpointer user_data);
GtkWidget *now_downloads_queue_view_new(void);
gboolean now_downloads_queue_view_update(GtkWidget *view, const char *wire);
void now_downloads_queue_view_message(GtkWidget *view, const char *message);
#endif
