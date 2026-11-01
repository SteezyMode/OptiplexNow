/* Native GTK queue regression. Disposable Xvfb only; no network, Docker or SSH. */
#include "downloads_queue_view.h"
#include <glib.h>
#define HASH_A "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#define HASH_B "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

static void test_queue_items(void){
 GtkWidget *view=now_downloads_queue_view_new();
 g_assert_true(now_downloads_queue_view_update(view,
   "ITEM\t21.2\tdownloading\tExample Movie\t" HASH_A "\t150\t180\t7\n"
   "ITEM\t100.0\tstalledUP\tOlder File\t" HASH_B "\t0\t-1\t0"));
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
static void test_compact_context_menu_rows(void){
 GtkWidget *view=now_downloads_queue_view_new();
 const char *wire=
  "ITEM\t21.2\tdownloading\tExample Movie\t" HASH_A "\t150\t180\t7\n"
  "ITEM\t90.0\tdownloading\tExample Game\t" HASH_B "\t200\t60\t4";
 g_assert_true(now_downloads_queue_view_update(view,wire));
 GtkWidget *list=g_object_get_data(G_OBJECT(view),"now-download-list");
 GtkListBoxRow *row=gtk_list_box_get_row_at_index(GTK_LIST_BOX(list),0);
 g_assert_nonnull(row);
 GtkWidget *event_box=gtk_bin_get_child(GTK_BIN(row));
 g_assert_true(GTK_IS_EVENT_BOX(event_box));
 g_assert_cmpstr(g_object_get_data(G_OBJECT(event_box),"now-torrent-hash"),==,HASH_A);
 g_assert_true(gtk_widget_get_can_focus(event_box));
 GtkWidget *content=gtk_bin_get_child(GTK_BIN(event_box));
 g_assert_true(GTK_IS_BOX(content));
 GList *children=gtk_container_get_children(GTK_CONTAINER(content));
 g_assert_cmpint(g_list_length(children),==,3);
 g_list_free(children);
 /* No Actions rows should be added, including on background refresh. */
 g_assert_true(now_downloads_queue_view_update(view,wire));
 row=gtk_list_box_get_row_at_index(GTK_LIST_BOX(list),0);
 event_box=gtk_bin_get_child(GTK_BIN(row));
 content=gtk_bin_get_child(GTK_BIN(event_box));
 children=gtk_container_get_children(GTK_CONTAINER(content));
 g_assert_cmpint(g_list_length(children),==,3);
 g_list_free(children);
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
   "ITEM\t5.0\tdownloading\tname\t" HASH_A "\t0\t0\t-2",
   "ITEM\t5.0\tdownloading\tname\n",
   "ITEM\t5.0\tdownloading\tname\nITEM\toops\tdownloading\tname",
   NULL
 };
 for(guint i=0;bad[i];i++)
   g_assert_false(now_downloads_queue_view_update(view,bad[i]));
 gtk_widget_destroy(view);
}

static gboolean cancel_dialog(gpointer unused){
 (void)unused;
 GList *windows=gtk_window_list_toplevels();
 for(GList *it=windows;it;it=it->next){
   if(GTK_IS_DIALOG(it->data)){
     gtk_dialog_response(GTK_DIALOG(it->data),GTK_RESPONSE_CANCEL);
     break;
   }
 }
 g_list_free(windows);
 return G_SOURCE_REMOVE;
}
static void test_files_dialog_wire_validation(void){
 GtkWidget *view=now_downloads_queue_view_new();
 g_assert_false(now_downloads_queue_view_files_dialog(view,
   "FILES\t" HASH_A "\t0\t1\nFILE\t123\t80.0\t1\t../secret",HASH_A,"test"));
 g_assert_false(now_downloads_queue_view_files_dialog(view,
   "FILES\t" HASH_B "\t0\t1\nFILE\t123\t80.0\t1\tHorror/movie.mkv",HASH_A,"test"));
 g_assert_false(now_downloads_queue_view_files_dialog(view,
   "FILES\t" HASH_A "\t0\t2\nFILE\t123\t80.0\t1\tHorror/movie.mkv",HASH_A,"test"));
 g_assert_false(now_downloads_queue_view_files_dialog(view,
   "FILES\t" HASH_A "\t0\t1\nFILE\t123\t110.0\t1\tHorror/movie.mkv",HASH_A,"test"));
 g_idle_add(cancel_dialog,NULL);
 g_assert_true(now_downloads_queue_view_files_dialog(view,
   "FILES\t" HASH_A "\t0\t1\nFILE\t123\t80.0\t1\tHorror/movie.mkv",HASH_A,"test"));
 gtk_widget_destroy(view);
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/native-downloads/items",test_queue_items);
 g_test_add_func("/native-downloads/context-menu-rows",test_compact_context_menu_rows);
 g_test_add_func("/native-downloads/malformed",test_malformed_refused);
 g_test_add_func("/native-downloads/files",test_files_dialog_wire_validation);
 return g_test_run();
}
