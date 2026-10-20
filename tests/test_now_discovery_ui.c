#include "now_discovery_ui.h"
#include <gtk/gtk.h>
#include <string.h>

/* No live tailnet and no production settings: verifies GTK picker lifecycle. */
static GtkWidget *find_named(GtkWidget *widget, const char *name) {
    if (strcmp(gtk_widget_get_name(widget), name) == 0) return widget;
    if (!GTK_IS_CONTAINER(widget)) return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    GtkWidget *found = NULL;
    for (GList *item = children; item; item = item->next) {
        found = find_named(GTK_WIDGET(item->data), name);
        if (found) break;
    }
    g_list_free(children);
    return found;
}

static gboolean check_picker(gpointer data) {
    GtkWidget *dialog = GTK_WIDGET(data);
    g_assert_true(GTK_IS_DIALOG(dialog));
    g_assert_true(gtk_widget_get_visible(dialog));
    g_assert_nonnull(find_named(dialog, "now-host-selector"));
    g_assert_nonnull(gtk_dialog_get_widget_for_response(
        GTK_DIALOG(dialog), GTK_RESPONSE_ACCEPT));
    gtk_dialog_response(GTK_DIALOG(dialog), GTK_RESPONSE_APPLY);
    gtk_dialog_response(GTK_DIALOG(dialog), GTK_RESPONSE_CLOSE);
    return G_SOURCE_REMOVE;
}

static gboolean finish(gpointer ignored) {
    (void)ignored;
    gtk_main_quit();
    return G_SOURCE_REMOVE;
}

int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *parent = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GtkWidget *host = gtk_entry_new();
    GtkWidget *notice = gtk_label_new("unchanged");
    GtkWidget *dialog = now_discovery_open(GTK_WINDOW(parent),
                                           GTK_ENTRY(host), GTK_LABEL(notice));
    g_timeout_add(120, check_picker, dialog);
    g_timeout_add(1000, finish, NULL);
    gtk_main();
    g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(host)), ==, "");
    g_assert_cmpstr(gtk_label_get_text(GTK_LABEL(notice)), ==, "unchanged");
    gtk_widget_destroy(parent);
    gtk_widget_destroy(host);
    gtk_widget_destroy(notice);
    return 0;
}
