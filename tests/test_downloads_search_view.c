/* Isolated GTK search parser. No SSH, Docker, plugins, media or torrent write. */
#include "downloads_search_view.h"
#include <gtk/gtk.h>
#include <glib.h>

static void test_valid(void){
 GtkWidget *view=now_downloads_search_view_new();
 g_assert_true(now_downloads_search_view_update(view,
   "SEARCH\t0\t2\n"
   "RESULT\t9876543\t12\t1\tExample Linux ISO\n"
   "RESULT\t-1\t-1\t0\tUnsupported plugin link"));
 g_assert_true(now_downloads_search_view_update(view,"SEARCH\t1\t0"));
 gtk_widget_destroy(view);
}
static void test_reject(void){
 GtkWidget *view=now_downloads_search_view_new();
 const char *bad[]={
   "", "SEARCH\t1", "SEARCH\t2\t0", "SEARCH\t0\t-1",
   "SEARCH\t0\t0\n",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\t",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\tname\tprivate",
   "SEARCH\t0\t1\nRESULT\t1\t5\t2\tname",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\tname\n",
   NULL
 };
 for(guint i=0;bad[i];i++)
   g_assert_false(now_downloads_search_view_update(view,bad[i]));
 gtk_widget_destroy(view);
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/search/valid",test_valid);
 g_test_add_func("/search/reject",test_reject);
 return g_test_run();
}
