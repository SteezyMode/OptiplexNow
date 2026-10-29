/* Isolated GTK search parser. No SSH, Docker, plugins, media or torrent write. */
#include "downloads_search_view.h"
#include <gtk/gtk.h>
#include <glib.h>

static void test_valid(void){
 GtkWidget *view=now_downloads_search_view_new();
 g_assert_true(now_downloads_search_view_update(view,
   "SEARCH\t0\t2\n"
   "RESULT\t9876543\t12\t1\tExample Linux ISO\t"
   "magnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff\n"
   "RESULT\t-1\t-1\t0\tUnsupported plugin link\t-"));
 g_assert_true(now_downloads_search_view_update(view,"SEARCH\t1\t0"));
 gtk_widget_destroy(view);
}
static void test_mapped_full_results(void){
 /* The live client populates twenty rows into a mapped GTK window.
  * Earlier tests only parsed two rows into an unparented view. */
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 GtkWidget *view=now_downloads_search_view_new();
 gtk_container_add(GTK_CONTAINER(window),view);
 gtk_widget_show_all(window);
 GString *wire=g_string_new("SEARCH\t1\t90");
 for(int i=0;i<20;i++)
   g_string_append_printf(wire,
      "\nRESULT\t%u\t%u\t0\tLinux release %02d\t-",
      (unsigned)(i+1000),(unsigned)(i+1),i);
 for(int i=0;i<8;i++){
   g_assert_true(now_downloads_search_view_update(view,wire->str));
   while(gtk_events_pending())gtk_main_iteration();
 }
 g_string_free(wire,TRUE);
 gtk_widget_destroy(window);
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
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\tname\t-",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\tname\t",
   "SEARCH\t0\t1\nRESULT\t1\t5\t1\tname\tbadmagnet",
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\tmagnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff",
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\t-\n",
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
 g_test_add_func("/search/mapped-full-results",test_mapped_full_results);
 g_test_add_func("/search/reject",test_reject);
 return g_test_run();
}
