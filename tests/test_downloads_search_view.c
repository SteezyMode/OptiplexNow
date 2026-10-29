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
static GtkWidget *find_named(GtkWidget *widget,const char *name){
 if(!g_strcmp0(gtk_widget_get_name(widget),name))return widget;
 if(!GTK_IS_CONTAINER(widget))return NULL;
 GList *children=gtk_container_get_children(GTK_CONTAINER(widget));
 GtkWidget *found=NULL;
 for(GList *at=children;at && !found;at=at->next)
   found=find_named(GTK_WIDGET(at->data),name);
 g_list_free(children);
 return found;
}
static guint visible_rows(GtkWidget *list){
 GList *rows=gtk_container_get_children(GTK_CONTAINER(list));
 guint visible=0;
 for(GList *at=rows;at;at=at->next)
   if(gtk_widget_get_visible(GTK_WIDGET(at->data)))visible++;
 g_list_free(rows);
 return visible;
}
static void test_mapped_full_results(void){
 /* Live regression: 100 results; 20 per page in a mapped GTK window. */
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 GtkWidget *view=now_downloads_search_view_new();
 gtk_window_set_default_size(GTK_WINDOW(window),860,650);
 gtk_container_add(GTK_CONTAINER(window),view);
 gtk_widget_show_all(window);
 GString *wire=g_string_new("SEARCH\t1\t130");
 for(int i=0;i<100;i++)
   g_string_append_printf(wire,
      "\nRESULT\t%u\t%u\t0\tLinux release %02d\t-",
      (unsigned)(i+1000),(unsigned)(i+1),i);
 GtkWidget *list=find_named(view,"nowsearchlist");
 g_assert_nonnull(list);
 for(int i=0;i<3;i++){
   g_assert_true(now_downloads_search_view_update(view,wire->str));
   while(gtk_events_pending())gtk_main_iteration();
   g_assert_cmpuint(visible_rows(list),==,20);
   GtkWidget *scroller=find_named(view,"nowsearchresults");
   g_assert_nonnull(scroller);
   g_assert_cmpint(gtk_widget_get_allocated_height(scroller),>,320);
   GList *controls=gtk_container_get_children(GTK_CONTAINER(view));
   GtkWidget *pager=g_list_last(controls)->data;
   g_list_free(controls);
   GList *buttons=gtk_container_get_children(GTK_CONTAINER(pager));
   GtkWidget *next=g_list_last(buttons)->data;
   GtkWidget *previous=buttons->data;
   g_list_free(buttons);
   g_assert_true(gtk_widget_get_sensitive(next));
   for(int page=0;page<4;page++){
     g_signal_emit_by_name(next,"clicked");
     g_assert_cmpuint(visible_rows(list),==,20);
   }
   g_assert_false(gtk_widget_get_sensitive(next));
   g_assert_true(gtk_widget_get_sensitive(previous));
   g_signal_emit_by_name(previous,"clicked");
   g_assert_true(gtk_widget_get_sensitive(next));
 }
 g_string_free(wire,TRUE);
 gtk_widget_destroy(window);
}
/* Regression: sort is applied across the full result batch, and partial
 * results offer an explicit deeper search without changing the first batch. */
static const char *first_result_title(GtkWidget *list){
 GtkListBoxRow *first=gtk_list_box_get_row_at_index(GTK_LIST_BOX(list),0);
 g_assert_nonnull(first);
 GtkWidget *content=gtk_bin_get_child(GTK_BIN(first));
 GList *labels=gtk_container_get_children(GTK_CONTAINER(content));
 g_assert_nonnull(labels);
 const char *title=gtk_label_get_text(GTK_LABEL(labels->data));
 g_list_free(labels);
 return title;
}
static void test_sort_and_more(void){
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 GtkWidget *view=now_downloads_search_view_new();
 gtk_window_set_default_size(GTK_WINDOW(window),800,560);
 gtk_container_add(GTK_CONTAINER(window),view);
 gtk_widget_show_all(window);
 GtkWidget *list=find_named(view,"nowsearchlist");
 GtkWidget *more=find_named(view,"nowsearchmore");
 GtkWidget *sort=find_named(view,"nowsearchsort");
 g_assert_nonnull(list);g_assert_nonnull(more);g_assert_nonnull(sort);
 g_assert_true(now_downloads_search_view_update(view,
   "SEARCH\t1\t35\n"
   "RESULT\t40000000000\t45\t0\t2160p huge\t-\n"
   "RESULT\t4000000000\t10\t0\t1080p moderate\t-\n"
   "RESULT\t-1\t-1\t0\tUnknown size\t-"));
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_true(gtk_widget_get_visible(more));
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 gtk_combo_box_set_active_id(GTK_COMBO_BOX(sort),"seeds");
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 gtk_combo_box_set_active_id(GTK_COMBO_BOX(sort),"large");
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 g_assert_true(now_downloads_search_view_update(view,"SEARCH\t0\t0"));
 g_assert_false(gtk_widget_get_visible(more));
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
 g_test_add_func("/search/sort-and-more",test_sort_and_more);
 g_test_add_func("/search/reject",test_reject);
 return g_test_run();
}
