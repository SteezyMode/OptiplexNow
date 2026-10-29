/* Native GTK queue regression. Disposable Xvfb only; no network, Docker or SSH. */
#include "downloads_queue_view.h"
#include <glib.h>

static void test_queue_items(void){
 GtkWidget *view=now_downloads_queue_view_new();
 g_assert_true(now_downloads_queue_view_update(view,
   "ITEM\t21.2\tdownloading\tExample Movie\n"
   "ITEM\t100.0\tstalledUP\tOlder File"));
 GtkWidget *list=g_object_get_data(G_OBJECT(view),"now-download-list");
 g_assert_nonnull(list);
 GList *rows=gtk_container_get_children(GTK_CONTAINER(list));
 g_assert_cmpint(g_list_length(rows),==,2);
 g_list_free(rows);
 g_assert_true(now_downloads_queue_view_update(view,"EMPTY"));
 rows=gtk_container_get_children(GTK_CONTAINER(list));
 g_assert_cmpint(g_list_length(rows),==,1);
 g_list_free(rows);
 gtk_widget_destroy(view);
}
static void test_malformed_refused(void){
 GtkWidget *view=now_downloads_queue_view_new();
 const char *bad[]={
   "", "ITEM\t101.0\tdownloading\tname",
   "ITEM\t-1.0\tdownloading\tname",
   "ITEM\tnan\tdownloading\tname",
   "ITEM\t5.0\tbroken state\tname",
   "ITEM\t5.0\tdownloading\t",
   "ITEM\t5.0\tdownloading\tname\tprivate",
   "ITEM\t5.0\tdownloading\tname\n",
   "ITEM\t5.0\tdownloading\tname\nITEM\toops\tdownloading\tname",
   NULL
 };
 for(guint i=0;bad[i];i++)
   g_assert_false(now_downloads_queue_view_update(view,bad[i]));
 gtk_widget_destroy(view);
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/native-downloads/items",test_queue_items);
 g_test_add_func("/native-downloads/malformed",test_malformed_refused);
 return g_test_run();
}
