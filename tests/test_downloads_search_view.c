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
 /* 100 rows remain visible and scrollable; later APPEND rows join the same
  * list without a page switch or resetting the reader to the top. */
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
 GtkWidget *scroller=find_named(view,"nowsearchresults");
 g_assert_nonnull(list);
 g_assert_nonnull(scroller);
 g_assert_true(now_downloads_search_view_update(view,wire->str));
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpuint(visible_rows(list),==,100);
 g_assert_cmpint(gtk_widget_get_allocated_height(scroller),>,320);
 GtkAdjustment *adjustment=gtk_scrolled_window_get_vadjustment(
    GTK_SCROLLED_WINDOW(scroller));
 g_assert_nonnull(adjustment);
 g_assert_cmpfloat(gtk_adjustment_get_upper(adjustment),>,
                   gtk_adjustment_get_page_size(adjustment));
 gtk_adjustment_set_value(adjustment,500);
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpfloat(gtk_adjustment_get_value(adjustment),>,0);

 GString *extra=g_string_new("APPEND\t1\t125");
 for(int i=100;i<125;i++)
   g_string_append_printf(extra,
      "\nRESULT\t%u\t%u\t0\tLinux release %02d\t-",
      (unsigned)(i+1000),(unsigned)(i+1),i);
 g_assert_true(now_downloads_search_view_update(view,extra->str));
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpuint(visible_rows(list),==,125);
 g_assert_cmpfloat(gtk_adjustment_get_value(adjustment),>,0);

 /* Even after stream completion, no rows vanish or require pagination. */
 g_assert_true(now_downloads_search_view_update(view,"APPEND\t0\t125"));
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpuint(visible_rows(list),==,125);
 gtk_adjustment_set_value(adjustment,gtk_adjustment_get_upper(adjustment));
 while(gtk_events_pending())gtk_main_iteration();
 g_assert_cmpfloat(gtk_adjustment_get_value(adjustment),>,0);

 g_string_free(wire,TRUE);
 g_string_free(extra,TRUE);
 gtk_widget_destroy(window);
}
/* Regression: sorting stays available while progressive snapshots arrive. */
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
static void test_sort_and_stream(void){
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 GtkWidget *view=now_downloads_search_view_new();
 gtk_window_set_default_size(GTK_WINDOW(window),900,560);
 gtk_container_add(GTK_CONTAINER(window),view);
 gtk_widget_show_all(window);
 GtkWidget *list=find_named(view,"nowsearchlist");
 GtkWidget *name=find_named(view,"nowsearchheader_name");
 GtkWidget *size=find_named(view,"nowsearchheader_size");
 GtkWidget *seeds=find_named(view,"nowsearchheader_seeds");
 GtkWidget *leechers=find_named(view,"nowsearchheader_leechers");
 GtkWidget *published=find_named(view,"nowsearchheader_published");
 g_assert_nonnull(list);
 g_assert_nonnull(name);g_assert_nonnull(size);
 g_assert_nonnull(seeds);g_assert_nonnull(leechers);
 g_assert_nonnull(published);
 g_assert_true(now_downloads_search_view_update(view,
   "SEARCH\t1\t35\n"
   "RESULT\t40000000000\t45\t0\t2160p huge\t-\t1767225600\t60\n"
   "RESULT\t4000000000\t10\t0\t1080p moderate\t-\t1727740800\t12\n"
   "RESULT\t-1\t-1\t0\tUnknown size\t-\t-1\t-1"));
 while(gtk_events_pending())gtk_main_iteration();
 /* Size ascending is the default; click the same heading to reverse. */
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 g_signal_emit_by_name(size,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 g_signal_emit_by_name(size,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 /* Seeders defaults descending and flips ascending on the next click. */
 g_signal_emit_by_name(seeds,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 g_signal_emit_by_name(seeds,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 g_signal_emit_by_name(leechers,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 g_signal_emit_by_name(leechers,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 /* Publish date defaults newest and flips oldest. Unknown is always last. */
 g_signal_emit_by_name(published,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"2160p huge");
 g_signal_emit_by_name(published,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 g_signal_emit_by_name(name,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"1080p moderate");
 g_signal_emit_by_name(name,"clicked");
 g_assert_cmpstr(first_result_title(list),==,"Unknown size");
 /* The later APPEND frame delivers only new rows from the same job. */
 g_assert_true(now_downloads_search_view_update(view,
   "APPEND\t0\t4\n"
   "RESULT\t2000000000\t14\t0\t720p release\t-\t1710000000\t7"));
 g_assert_cmpuint(visible_rows(list),==,4);
 g_assert_cmpstr(first_result_title(list),==,"Unknown size");
 /* An empty completion frame must retain all accumulated rows. */
 g_assert_true(now_downloads_search_view_update(view,"APPEND\t0\t4"));
 g_assert_cmpuint(visible_rows(list),==,4);
 /* Old 6-field host responses remain valid. */
 g_assert_true(now_downloads_search_view_update(view,
   "SEARCH\t0\t1\nRESULT\t42\t5\t0\tLegacy result\t-"));
 g_assert_cmpstr(first_result_title(list),==,"Legacy result");
 g_assert_true(now_downloads_search_view_update(view,"SEARCH\t0\t0"));
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
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\t-\tbad",
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\t-\t253402300800",
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\t-\t100\t-2",
   "SEARCH\t0\t1\nRESULT\t1\t5\t0\tname\t-\t100\tbad",
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
 g_test_add_func("/search/sort-and-stream",test_sort_and_stream);
 g_test_add_func("/search/reject",test_reject);
 return g_test_run();
}
