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
static void test_saved_game_location_remains_scoped_to_approved_root(void){
 GtkWidget *view=now_downloads_destination_view_new();
 now_downloads_destination_view_configure(view,"100.121.156.34","optiplex",
                                          "/test/owner-helper");
 Picker *s=state(view);
 g_assert_nonnull(s->new_folder);
 g_assert_nonnull(s->places_combo);
 g_assert_nonnull(s->pin_place);
 g_assert_cmpstr(gtk_button_get_label(GTK_BUTTON(s->pin_place)),==,"☆ Favorite");
 g_assert_true(read_response(s,'m',"CREATED"));
 g_assert_false(read_response(s,'m',"SUBMITTED"));
 g_free(s->root);s->root=g_strdup("bigdisk");
 g_free(s->relative);s->relative=g_strdup("Games");
 g_assert_true(read_response(s,'b',"FOLDERS\tbigdisk\tGames"));
 g_assert_true(remember_current_place(s));
 g_assert_cmpuint(s->places->len,==,1);
 /* A merely saved Favorite is not a Recent download. */
 g_assert_cmpuint(s->recents->len,==,0);
 SavedPlace *p=g_ptr_array_index(s->places,0);
 g_assert_cmpstr(p->host,==,"100.121.156.34");
 g_assert_cmpstr(p->user,==,"optiplex");
 g_assert_cmpstr(p->root,==,"bigdisk");
 g_assert_cmpstr(p->relative,==,"Games");
 gchar *file=places_path();
 gchar *raw=NULL;
 g_assert_true(g_file_get_contents(file,&raw,NULL,NULL));
 g_assert_null(strstr(raw,"/media/"));
 g_assert_null(strstr(raw,"/etc/"));
 g_free(raw);g_free(file);
 GtkWidget *another=now_downloads_destination_view_new();
 Picker *again=state(another);
 g_assert_cmpuint(again->places->len,==,1);
 now_downloads_destination_view_configure(another,"other.example","optiplex",
                                          "/test/owner-helper");
 GtkTreeModel *model=gtk_combo_box_get_model(GTK_COMBO_BOX(again->places_combo));
 g_assert_cmpint(gtk_tree_model_iter_n_children(model,NULL),==,1);
 now_downloads_destination_view_configure(another,"100.121.156.34","optiplex",
                                          "/test/owner-helper");
 g_assert_cmpint(gtk_tree_model_iter_n_children(model,NULL),==,2);
 SavedPlace *loaded=g_ptr_array_index(again->places,0);
 g_assert_cmpstr(loaded->relative,==,"Games");
 /* Star is a reversible Favorite toggle; it never submits a torrent. */
 g_free(again->root);again->root=g_strdup("bigdisk");
 g_free(again->relative);again->relative=g_strdup("Games");
 again->folder_valid=TRUE;
 on_save_place(NULL,another);
 g_assert_cmpuint(again->places->len,==,0);
 g_assert_cmpuint(again->recents->len,==,0);
 gtk_widget_destroy(another);
 gtk_widget_destroy(view);
}
static void test_recents_only_after_successful_download(void){
 GtkWidget *view=now_downloads_destination_view_new();
 now_downloads_destination_view_configure(view,"100.121.156.34","optiplex",
                                          "/test/owner-helper");
 Picker *s=state(view);
 g_free(s->root);s->root=g_strdup("bigdisk");
 g_free(s->relative);s->relative=g_strdup("Games");
 s->folder_valid=TRUE;
 /* Browsing or favoriting is not a download and cannot select a default. */
 g_assert_cmpuint(s->recents->len,==,0);
 g_assert_true(remember_current_place(s));
 g_assert_cmpuint(s->recents->len,==,0);
 g_assert_true(read_response(s,'a',"SUBMITTED"));
 g_assert_cmpuint(s->recents->len,==,1);
 SavedPlace *recent=g_ptr_array_index(s->recents,0);
 g_assert_cmpstr(recent->relative,==,"Games");
 GtkTreeModel *model=gtk_combo_box_get_model(GTK_COMBO_BOX(s->places_combo));
 g_assert_cmpint(gtk_tree_model_iter_n_children(model,NULL),==,3);
 /* Changing the configured server hides both Favorites and Recents. */
 now_downloads_destination_view_configure(view,"other.example","optiplex",
                                          "/test/owner-helper");
 g_assert_cmpint(gtk_tree_model_iter_n_children(model,NULL),==,1);
 gtk_widget_destroy(view);
}
static void flush_gtk_events(void){
 /* GTK's allocation/draw frame clock can run after the idle queue empties.
  * Exercise several real virtual-display frames, without manual resize. */
 for(guint i=0;i<20;i++){
   while(gtk_events_pending())gtk_main_iteration();
   g_usleep(10000);
 }
}
/* Primary baseline: conventional desktop aspect ratios. Keep the 4:3
 * projector and narrow window as compatibility cases, not product defaults.
 * GtkScrolledWindow must grow with available space instead of acting like
 * a fixed-height tiny viewport. */
static void test_responsive_focused_step_mapping(void){
 const struct {int width,height;} cases[]={
   {430,700},   /* supported minimum-width window */
   {1024,768},  /* legacy 4:3 projector */
   {1366,768},  /* common widescreen laptop */
   {1280,800},  /* 16:10 laptop */
   {1920,1080}, /* mainstream 16:9 desktop */
 };
 gint viewport_heights[G_N_ELEMENTS(cases)]={0};
 gint viewport_widths[G_N_ELEMENTS(cases)]={0};
 for(guint i=0;i<G_N_ELEMENTS(cases);i++){
   GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
   gtk_window_set_default_size(GTK_WINDOW(window),
                               cases[i].width,cases[i].height);
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
   g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(workspace)),
                   ==,"results");
   /* Hidden picker becomes visible only when a torrent is selected. */
   gtk_widget_set_no_show_all(picker,FALSE);
   gtk_widget_show_all(picker);
   gtk_widget_set_no_show_all(picker,TRUE);
   gtk_stack_set_visible_child_name(GTK_STACK(workspace),"destination");
   gtk_widget_queue_resize(workspace);
   gtk_widget_queue_draw(workspace);
   flush_gtk_events();
   Picker *state_ptr=state(picker);
   g_assert_nonnull(state_ptr);
   g_assert_true(gtk_widget_get_mapped(state_ptr->folder_scroll));
   g_assert_true(gtk_widget_get_mapped(state_ptr->add));
   viewport_heights[i]=gtk_widget_get_allocated_height(state_ptr->folder_scroll);
   viewport_widths[i]=gtk_widget_get_allocated_width(state_ptr->folder_scroll);
   g_assert_cmpint(viewport_heights[i],>=,420);
   g_assert_cmpint(viewport_widths[i],>=,330);
   gtk_stack_set_visible_child_name(GTK_STACK(workspace),"results");
   flush_gtk_events();
   g_assert_true(gtk_widget_get_mapped(results));
   gtk_widget_destroy(window);
   flush_gtk_events();
 }
 /* The large desktop really gets a larger work area, not merely an
  * oversized frame containing the same 420px internal viewport. */
 g_assert_cmpint(viewport_heights[4],>,viewport_heights[1]+100);
 g_assert_cmpint(viewport_widths[4],>,viewport_widths[1]+400);
 g_print("Responsive focused Downloads viewport: 430px, 4:3, 16:9, 16:10 passed.\\n");
}

int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/destination/genres",test_folder_navigation_and_preserve_trailing_space);
 g_test_add_func("/destination/borrowed-combo-id",test_borrowed_combo_id_is_never_freed);
 g_test_add_func("/destination/reject",test_reject_untrusted_host_folder_reply);
 g_test_add_func("/destination/projector-picker",test_projector_picker_filters_and_confirm_above_browser);
 g_test_add_func("/destination/saved-games",test_saved_game_location_remains_scoped_to_approved_root);
 g_test_add_func("/destination/recent-only-on-add",test_recents_only_after_successful_download);
 g_test_add_func("/destination/responsive-drilldown",test_responsive_focused_step_mapping);
 return g_test_run();
}
