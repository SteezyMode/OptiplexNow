#include "server_preflight_ui.h"

#include <gtk/gtk.h>
#include <string.h>

/* GTK lifecycle test. Uses no live remote host, Tailscale login, Docker
 * mutation, or production configuration. Runs inside disposable Xvfb. */
static GtkWidget *find_named(GtkWidget *root, const char *name) {
    if (!strcmp(gtk_widget_get_name(root), name)) return root;
    if (!GTK_IS_CONTAINER(root)) return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(root));
    GtkWidget *found = NULL;
    for (GList *it = children; it; it = it->next) {
        found = find_named(GTK_WIDGET(it->data), name);
        if (found) break;
    }
    g_list_free(children);
    return found;
}

static gboolean exercise_dialog(gpointer data) {
    GtkWidget *dialog = GTK_WIDGET(data);
    g_assert_true(GTK_IS_DIALOG(dialog));
    g_assert_true(gtk_widget_get_visible(dialog));
    GtkWidget *again = gtk_dialog_get_widget_for_response(
        GTK_DIALOG(dialog), GTK_RESPONSE_APPLY);
    g_assert_nonnull(again);
    g_assert_true(GTK_IS_WIDGET(again));

    GtkWidget *backend = find_named(dialog, "now-preflight-backend");
    g_assert_nonnull(backend);
    g_assert_cmpstr(gtk_combo_box_get_active_id(GTK_COMBO_BOX(backend)), ==, "sunshine");
    gtk_combo_box_set_active_id(GTK_COMBO_BOX(backend), "wolf");
    g_assert_cmpstr(gtk_combo_box_get_active_id(GTK_COMBO_BOX(backend)), ==, "wolf");

    /* Repeated checks must not start overlapping children. */
    gtk_dialog_response(GTK_DIALOG(dialog), GTK_RESPONSE_APPLY);
    gtk_dialog_response(GTK_DIALOG(dialog), GTK_RESPONSE_APPLY);

    /* The dialog must be closable even before the child finishes. */
    gtk_dialog_response(GTK_DIALOG(dialog), GTK_RESPONSE_CLOSE);
    return G_SOURCE_REMOVE;
}

static gboolean finish_test(gpointer ignored) {
    (void)ignored;
    gtk_main_quit();
    return G_SOURCE_REMOVE;
}

int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *dialog = now_preflight_open(NULL);
    g_assert_nonnull(dialog);
    g_timeout_add(150, exercise_dialog, dialog);
    g_timeout_add(1100, finish_test, NULL);
    gtk_main();
    return 0;
}
