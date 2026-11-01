/* GTK inline media picker tests. Bring in module to exercise private parser. */
#include "downloads_destination_view.c"
#include <gtk/gtk.h>
#include <glib.h>

static void test_folder_navigation_and_preserve_trailing_space(void){
 GtkWidget *view=now_downloads_destination_view_new();
 Picker *s=state(view);
 g_assert_nonnull(s);
 g_assert_true(read_response(s,'r',
     "ROOTS\nROOT\tbigdisk\t4 TB Media\nROOT\texpansion\t2 TB Media"));
 g_free(s->root);s->root=g_strdup("bigdisk");
 g_free(s->relative);s->relative=g_strdup("Movies");
 g_assert_true(read_response(s,'b',
     "FOLDERS\tbigdisk\tMovies\nFOLDER\tAction \nFOLDER\tHorror"));
 GList *buttons=gtk_container_get_children(GTK_CONTAINER(s->folders));
 g_assert_cmpint(g_list_length(buttons),==,2);
 g_assert_cmpstr(gtk_button_get_label(GTK_BUTTON(buttons->data)),==,"Action ");
 g_list_free(buttons);
 g_assert_true(s->folder_valid);
 g_assert_true(read_response(s,'a',"SUBMITTED"));
 gtk_widget_destroy(view);
}
static void test_borrowed_combo_id_is_never_freed(void){
 GtkWidget *view=now_downloads_destination_view_new();
 Picker *s=state(view);
 g_assert_true(read_response(s,'r',
     "ROOTS\nROOT\tbigdisk\t4 TB Media\nROOT\texpansion\t2 TB Media"));
 /* GTK 3 returns an interned borrowed pointer, not a heap allocation.
  * Ensure our state keeps a private copy, including when the root changes. */
 const char *borrowed=gtk_combo_box_get_active_id(GTK_COMBO_BOX(s->roots));
 g_assert_nonnull(borrowed);
 on_root(GTK_COMBO_BOX(s->roots),view);
 g_assert_cmpstr(s->root,==,"bigdisk");
 g_assert_true(s->root!=borrowed);
 gtk_combo_box_set_active(GTK_COMBO_BOX(s->roots),1);
 g_assert_cmpstr(s->root,==,"expansion");
 const char *borrowed_again=gtk_combo_box_get_active_id(GTK_COMBO_BOX(s->roots));
 g_assert_true(s->root!=borrowed_again);
 gtk_widget_destroy(view);
}
static void test_reject_untrusted_host_folder_reply(void){
 GtkWidget *view=now_downloads_destination_view_new();
 Picker *s=state(view);
 g_free(s->root);s->root=g_strdup("bigdisk");
 g_free(s->relative);s->relative=g_strdup("Movies");
 const char *bad[]={
   "FOLDERS\tbad\tMovies\nFOLDER\tHorror",
   "FOLDERS\tbigdisk\t../Movies\nFOLDER\tHorror",
   "FOLDERS\tbigdisk\tMovies\nFOLDER\t../escape",
   "FOLDERS\tbigdisk\tMovies\nFOLDER\tHorror\textra",
   "ROOTS\nROOT\t/etc\tUnsafe",
   "SUBMITTED\nextra",
   NULL
 };
 for(guint i=0;bad[i];i++){
   gboolean ok=read_response(s,(g_str_has_prefix(bad[i],"ROOTS")?'r':
                                 g_str_has_prefix(bad[i],"SUBMITTED")?'a':'b'),(char *)bad[i]);
   g_assert_false(ok);
 }
 gtk_widget_destroy(view);
}
static void test_projector_picker_filters_and_confirm_above_browser(void){
 GtkWidget *view=now_downloads_destination_view_new();
 Picker *s=state(view);
 gint width=0,height=0;
 gtk_widget_get_size_request(s->folder_scroll,&width,&height);
 g_assert_cmpint(height,>=,280);
 GList *parts=gtk_container_get_children(GTK_CONTAINER(view));
 g_assert_cmpint(g_list_index(parts,s->add),<,
                 g_list_index(parts,s->folder_scroll));
 g_list_free(parts);
 g_free(s->root);s->root=g_strdup("bigdisk");
 g_free(s->relative);s->relative=g_strdup("Movies");
 g_assert_true(read_response(s,'b',
   "FOLDERS\tbigdisk\tMovies\nFOLDER\tAction \nFOLDER\tHorror\nFOLDER\tComedy"));
 GList *buttons=gtk_container_get_children(GTK_CONTAINER(s->folders));
 g_assert_cmpint(g_list_length(buttons),==,3);
 GtkWidget *action=GTK_WIDGET(g_list_nth_data(buttons,0));
 GtkWidget *horror=GTK_WIDGET(g_list_nth_data(buttons,1));
 GtkWidget *comedy=GTK_WIDGET(g_list_nth_data(buttons,2));
 gtk_entry_set_text(GTK_ENTRY(s->filter),"hOrRoR");
 g_assert_false(gtk_widget_get_visible(action));
 g_assert_true(gtk_widget_get_visible(horror));
 g_assert_false(gtk_widget_get_visible(comedy));
 g_assert_cmpstr(s->root,==,"bigdisk");
 g_assert_cmpstr(s->relative,==,"Movies");
 gtk_entry_set_text(GTK_ENTRY(s->filter),"");
 g_assert_true(gtk_widget_get_visible(action));
 g_assert_true(gtk_widget_get_visible(comedy));
 g_list_free(buttons);
 gtk_widget_destroy(view);
}
static void flush_gtk_events(void){
 for(guint i=0;i<20;i++)
   while(gtk_events_pending())gtk_main_iteration();
}
static void test_1024x768_focused_step_mapping(void){
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 gtk_window_set_default_size(GTK_WINDOW(window),1024,768);
 GtkWidget *workspace=gtk_stack_new();
 gtk_stack_set_hhomogeneous(GTK_STACK(workspace),FALSE);
 gtk_stack_set_vhomogeneous(GTK_STACK(workspace),FALSE);
 gtk_stack_set_transition_type(GTK_STACK(workspace),
                               GTK_STACK_TRANSITION_TYPE_NONE);
 gtk_container_add(GTK_CONTAINER(window),workspace);
 GtkWidget *results=gtk_label_new("Search results");
 gtk_stack_add_named(GTK_STACK(workspace),results,"results");
 GtkWidget *folder_page=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
 GtkWidget *back=gtk_button_new_with_label("BACK TO RESULTS");
 gtk_box_pack_start(GTK_BOX(folder_page),back,FALSE,FALSE,0);
 GtkWidget *picker=now_downloads_destination_view_new();
 gtk_box_pack_start(GTK_BOX(folder_page),picker,TRUE,TRUE,0);
 gtk_stack_add_named(GTK_STACK(workspace),folder_page,"destination");
 gtk_widget_show_all(window);
 flush_gtk_events();
 g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(workspace)),==,
                 "results");
 /* As in the real application, a valid torrent selection reveals the
  * previously hidden chooser, then switches to its focused step. */
 gtk_widget_set_no_show_all(picker,FALSE);
 gtk_widget_show_all(picker);
 gtk_widget_set_no_show_all(picker,TRUE);
 gtk_stack_set_visible_child_name(GTK_STACK(workspace),"destination");
 flush_gtk_events();
 Picker *s=state(picker);
 g_assert_nonnull(s);
 g_assert_true(gtk_widget_get_mapped(s->folder_scroll));
 g_assert_cmpint(gtk_widget_get_allocated_height(s->folder_scroll),>=,420);
 g_assert_true(gtk_widget_get_mapped(s->add));
 gtk_stack_set_visible_child_name(GTK_STACK(workspace),"results");
 flush_gtk_events();
 g_assert_true(gtk_widget_get_mapped(results));
 gtk_widget_destroy(window);
 flush_gtk_events();
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/destination/genres",test_folder_navigation_and_preserve_trailing_space);
 g_test_add_func("/destination/borrowed-combo-id",test_borrowed_combo_id_is_never_freed);
 g_test_add_func("/destination/reject",test_reject_untrusted_host_folder_reply);
 g_test_add_func("/destination/projector-picker",test_projector_picker_filters_and_confirm_above_browser);
 g_test_add_func("/destination/projector-drilldown",test_1024x768_focused_step_mapping);
 return g_test_run();
}
