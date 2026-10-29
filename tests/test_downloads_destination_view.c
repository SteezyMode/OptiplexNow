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
int main(int argc,char **argv){
 gtk_init(&argc,&argv,NULL);
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/destination/genres",test_folder_navigation_and_preserve_trailing_space);
 g_test_add_func("/destination/reject",test_reject_untrusted_host_folder_reply);
 return g_test_run();
}
