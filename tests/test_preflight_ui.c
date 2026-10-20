#include "server_preflight_ui.h"

#include <gtk/gtk.h>

/* GTK lifecycle test. Uses no live remote host, Tailscale login, Docker
 * mutation, or production configuration. Runs inside disposable Xvfb. */
static gboolean exercise_dialog(gpointer data) {
    GtkWidget *dialog = GTK_WIDGET(data);
    g_assert_true(GTK_IS_DIALOG(dialog));
    g_assert_true(gtk_widget_get_visible(dialog));
    GtkWidget *again = gtk_dialog_get_widget_for_response(
        GTK_DIALOG(dialog), GTK_RESPONSE_APPLY);
    g_assert_nonnull(again);
    g_assert_true(GTK_IS_WIDGET(again));

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
