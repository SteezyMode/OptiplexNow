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
  gtk_widget_show_all(stack);\n  gtk_widget_show_all(nav);\n  now_nav_bind_link(tabs[0], stack, "dashboard");
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
  return 0;
}
