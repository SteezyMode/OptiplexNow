#include "ui_navigation.h"
#include <gtk/gtk.h>
#include <string.h>

static void check_selection(GtkWidget *stack, GtkWidget **tabs,
                            const char *page, unsigned selected) {
  gtk_stack_set_visible_child_name(GTK_STACK(stack), page);
  now_nav_update_tabs(G_OBJECT(stack), NULL,
                      g_object_get_data(G_OBJECT(stack), "test-nav"));
  for (unsigned i = 0; i < 5; i++) {
    gboolean active = gtk_style_context_has_class(
        gtk_widget_get_style_context(tabs[i]), "active");
    g_assert_cmpint(active, ==, i == selected);
  }
}

/* Exercise real GTK mapping, allocation and a child draw after first
 * selecting a Downloads-like nested stack; no host or network is involved. */
static gboolean count_draw(GtkWidget *widget,cairo_t *cr,gpointer data){
 (void)widget;(void)cr;
 ++*(unsigned *)data;
 return FALSE;
}
static void drain_gtk(void){
 for(int i=0;i<30;i++)
  while(gtk_events_pending())gtk_main_iteration();
}
static void test_first_downloads_paint(void){
 GtkWidget *window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
 gtk_window_set_default_size(GTK_WINDOW(window),430,450);
 GtkWidget *pages=gtk_stack_new();
 gtk_stack_set_hhomogeneous(GTK_STACK(pages),FALSE);
 gtk_stack_set_transition_type(GTK_STACK(pages),GTK_STACK_TRANSITION_TYPE_NONE);
 gtk_container_add(GTK_CONTAINER(window),pages);
 gtk_stack_add_named(GTK_STACK(pages),gtk_label_new("Dashboard"),"dashboard");
 GtkWidget *downloads=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 GtkWidget *nested=gtk_stack_new();
 GtkWidget *web=gtk_label_new("Advanced WebUI");
 GtkWidget *queue=gtk_label_new("Current downloads");
 gtk_stack_add_named(GTK_STACK(nested),web,"web");
 gtk_stack_add_named(GTK_STACK(nested),queue,"queue");
 gtk_box_pack_start(GTK_BOX(downloads),nested,TRUE,TRUE,0);
 gtk_stack_add_named(GTK_STACK(pages),downloads,"downloads");
 /* The same visibility-before-selection contract as now_downloads_page(). */
 gtk_widget_show_all(downloads);
 gtk_stack_set_visible_child_name(GTK_STACK(nested),"queue");
 unsigned paints=0;
 g_signal_connect(queue,"draw",G_CALLBACK(count_draw),&paints);
 gtk_stack_set_visible_child_name(GTK_STACK(pages),"dashboard");
 gtk_widget_show_all(window);
 drain_gtk();
 now_nav_show_page(pages,"downloads");
 now_nav_relayout_page(downloads);
 drain_gtk();
 g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(pages)),==,"downloads");
 g_assert_true(gtk_widget_get_mapped(queue));
 g_assert_cmpint(gtk_widget_get_allocated_width(queue),>,0);
 g_assert_cmpint(gtk_widget_get_allocated_height(queue),>,0);
 g_assert_cmpuint(paints,>,0);
 /* Closing before the queued idle runs must not access a dead widget. */
 now_nav_relayout_page(downloads);
 gtk_widget_destroy(window);
 drain_gtk();
 g_print("GTK Downloads first-paint allocation passed without window resize.\n");
}

int main(int argc, char **argv) {
  gtk_init(&argc, &argv);
  GtkWidget *stack = gtk_stack_new();
  GtkWidget *nav = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 4);
  GtkWidget *tabs[5] = {NULL};
  const char *pages[] = {"dashboard", "downloads", "games", "videos", "settings"};
  for (unsigned i = 0; i < 5; i++) {
    tabs[i] = gtk_button_new_with_label(pages[i]);
    now_nav_mark_tab(tabs[i], pages[i]);
    gtk_box_pack_start(GTK_BOX(nav), tabs[i], FALSE, FALSE, 0);
    gtk_stack_add_named(GTK_STACK(stack), gtk_label_new(pages[i]), pages[i]);
  }
  gtk_stack_add_named(GTK_STACK(stack), gtk_label_new("info"), "info");
  gtk_stack_add_named(GTK_STACK(stack), gtk_label_new("software"), "software");
  gtk_widget_show_all(stack);
  gtk_widget_show_all(nav);
  now_nav_bind_link(tabs[0], stack, "dashboard");
  g_object_set_data(G_OBJECT(stack), "test-nav", nav);
  g_signal_connect(stack, "notify::visible-child",
                   G_CALLBACK(now_nav_update_tabs), nav);

  for (unsigned i = 0; i < 5; i++)
    check_selection(stack, tabs, pages[i], i);
  check_selection(stack, tabs, "info", 4);
  check_selection(stack, tabs, "software", 4);
  g_signal_emit_by_name(tabs[0], "clicked");
  g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(stack)), ==, "dashboard");
  check_selection(stack, tabs, "dashboard", 0);
  test_first_downloads_paint();
  return 0;
}
