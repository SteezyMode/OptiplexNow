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

static guint actions_seen=0;
static char last_action[32]={0};
static void recorded_action(const char *operation,const char *hash,
                            const char *name,gpointer data){
 (void)name;(void)data;
 ++actions_seen;
 g_strlcpy(last_action,operation,sizeof last_action);
 g_assert_cmpstr(hash,==,HASH_A);
}
static GtkWidget *find_button(GtkWidget *root,const char *label){
 if(GTK_IS_BUTTON(root) && g_strcmp0(gtk_button_get_label(GTK_BUTTON(root)),label)==0)
   return root;
 if(!GTK_IS_CONTAINER(root))return NULL;
 GList *children=gtk_container_get_children(GTK_CONTAINER(root));
 GtkWidget *found=NULL;
 for(GList *it=children;it&&!found;it=it->next)
   found=find_button(GTK_WIDGET(it->data),label);
 g_list_free(children);
 return found;
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
static void test_files_and_delete_controls(void){
 GtkWidget *view=now_downloads_queue_view_new();
 now_downloads_queue_view_on_action(view,recorded_action,NULL);
 g_assert_true(now_downloads_queue_view_update(view,
   "ITEM\t21.2\tdownloading\tExample Movie\t" HASH_A "\t150\t180\t7"));
 GtkWidget *files=find_button(view,"FILES");
 GtkWidget *keep=find_button(view,"REMOVE");
 GtkWidget *delete_data=find_button(view,"DELETE FILES");
 g_assert_nonnull(files);
 g_assert_nonnull(keep);
 g_assert_nonnull(delete_data);
 g_assert_cmpstr(gtk_widget_get_name(delete_data),==,"danger");
 gtk_button_clicked(GTK_BUTTON(files));
 g_assert_cmpuint(actions_seen,==,1);
 g_assert_cmpstr(last_action,==,"files");
 /* Cancel must never deliver either destructive action to the broker. */
 g_idle_add(cancel_dialog,NULL);
 gtk_button_clicked(GTK_BUTTON(keep));
 g_idle_add(cancel_dialog,NULL);
 gtk_button_clicked(GTK_BUTTON(delete_data));
 g_assert_cmpuint(actions_seen,==,1);
 gtk_widget_destroy(view);
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
 g_test_add_func("/native-downloads/malformed",test_malformed_refused);
 g_test_add_func("/native-downloads/actions",test_files_and_delete_controls);
 g_test_add_func("/native-downloads/files",test_files_dialog_wire_validation);
 return g_test_run();
}
