#include "server_preflight_ui.h"

#include <gio/gio.h>
#include <string.h>

/* Stable packaged path. Never execute an unchecked hostname, remote command,
 * shell snippet, or script location from user-controlled settings. */
#define PREFLIGHT_HELPER "/usr/lib/optiplex-now/server-preflight"
#define PREFLIGHT_PYTHON "/usr/bin/python3"
#define PREFLIGHT_TIMEOUT_SECONDS 40
#define PREFLIGHT_OUTPUT_LIMIT 16384

typedef struct {
    GtkWidget *dialog;
    GtkWidget *status;
    GtkWidget *report;
    GtkWidget *spinner;
    GtkWidget *backend;
    GtkWidget *again;
    GSubprocess *child;
    guint timeout_id;
    gboolean closed;
    gboolean timed_out;
} PreflightUI;

static gboolean preflight_timeout(gpointer data) {
    PreflightUI *state = data;
    state->timeout_id = 0;
    state->timed_out = TRUE;
    if (state->child && !g_subprocess_get_if_exited(state->child))
        g_subprocess_force_exit(state->child);
    return G_SOURCE_REMOVE;
}

static void preflight_done(GObject *source, GAsyncResult *result, gpointer data) {
    PreflightUI *state = data;
    GError *error = NULL;
    char *stdout_text = NULL;
    char *stderr_text = NULL;
    gboolean communicated = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &stdout_text, &stderr_text, &error);
    gboolean success = communicated && g_subprocess_get_successful(G_SUBPROCESS(source));

    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
        state->timeout_id = 0;
    }
    if (!state->closed) {
        gtk_spinner_stop(GTK_SPINNER(state->spinner));
        gtk_widget_set_sensitive(state->again, TRUE);
        gtk_widget_set_sensitive(state->backend, TRUE);
        if (state->timed_out) {
            gtk_label_set_text(GTK_LABEL(state->status), "Check timed out");
            gtk_label_set_text(GTK_LABEL(state->report),
                "The local check did not finish. No changes were made.\n"
                "Check the installation or run the check again.");
        } else if (!success) {
            gtk_label_set_text(GTK_LABEL(state->status), "Check unavailable");
            gtk_label_set_text(GTK_LABEL(state->report),
                "Could not complete the local compatibility check.\n"
                "Check that NOW was installed correctly, then try again.\n"
                "No changes were made.");
        } else if (!stdout_text || !*stdout_text ||
                   strlen(stdout_text) > PREFLIGHT_OUTPUT_LIMIT) {
            gtk_label_set_text(GTK_LABEL(state->status), "Invalid check output");
            gtk_label_set_text(GTK_LABEL(state->report),
                "The local checker returned empty or oversized results.\n"
                "No changes were made.");
        } else {
            gtk_label_set_text(GTK_LABEL(state->status), "Read-only check complete");
            gtk_label_set_text(GTK_LABEL(state->report), stdout_text);
        }
    }

    /* Child stderr is deliberately not shown: it may include local details.
     * Error details are diagnostic only, never copied to the user's report. */
    g_free(stdout_text);
    g_free(stderr_text);
    g_clear_error(&error);
    g_clear_object(&state->child);
    /* Extra reference keeps the state alive if the window was closed mid-check. */
    g_object_unref(state->dialog);
}

static void preflight_begin(PreflightUI *state) {
    if (state->closed || state->child) return;
    if (!g_file_test(PREFLIGHT_HELPER, G_FILE_TEST_IS_REGULAR) ||
        !g_file_test(PREFLIGHT_PYTHON, G_FILE_TEST_IS_EXECUTABLE)) {
        gtk_label_set_text(GTK_LABEL(state->status), "Check unavailable");
        gtk_label_set_text(GTK_LABEL(state->report),
            "The local server checker is not installed.\n"
            "Use a NOW development package that includes server preflight.\n"
            "No changes were made.");
        return;
    }

    /* The GUI supplies only one of two statically defined values.
     * No user-entered command or path reaches subprocess execution. */
    const char *backend = gtk_combo_box_get_active_id(GTK_COMBO_BOX(state->backend));
    if (!backend || (strcmp(backend, "sunshine") && strcmp(backend, "wolf"))) {
        gtk_label_set_text(GTK_LABEL(state->status), "Choose a streaming backend");
        return;
    }
    const char *argv[] = {PREFLIGHT_PYTHON, PREFLIGHT_HELPER,
                          "--backend", backend, NULL};
    GError *error = NULL;
    state->child = g_subprocess_newv(argv,
        G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE,
        &error);
    if (!state->child) {
        gtk_label_set_text(GTK_LABEL(state->status), "Check unavailable");
        gtk_label_set_text(GTK_LABEL(state->report),
            "Could not start the local checker. No changes were made.");
        g_clear_error(&error);
        return;
    }
    state->timed_out = FALSE;
    gtk_label_set_text(GTK_LABEL(state->status), "Checking this computer...");
    gtk_label_set_text(GTK_LABEL(state->report),
        "Checking operating system, hardware, Tailscale and streaming services.\n"
        "This is a local, read-only inventory.");
    gtk_widget_set_sensitive(state->again, FALSE);
    gtk_widget_set_sensitive(state->backend, FALSE);
    gtk_spinner_start(GTK_SPINNER(state->spinner));

    /* Async child I/O keeps the GTK window responsive. Timeout and window
     * closure both terminate the subprocess without affecting host services. */
    g_object_ref(state->dialog);
    state->timeout_id = g_timeout_add_seconds(
        PREFLIGHT_TIMEOUT_SECONDS, preflight_timeout, state);
    g_subprocess_communicate_utf8_async(state->child, NULL, NULL,
                                       preflight_done, state);
}

static void preflight_response(GtkDialog *dialog, gint response, gpointer data) {
    PreflightUI *state = data;
    if (response == GTK_RESPONSE_APPLY) {
        preflight_begin(state);
    } else {
        gtk_widget_destroy(GTK_WIDGET(dialog));
    }
}

static void preflight_closed(GtkWidget *widget, gpointer data) {
    PreflightUI *state = data;
    (void)widget;
    state->closed = TRUE;
    if (state->child && !g_subprocess_get_if_exited(state->child))
        g_subprocess_force_exit(state->child);
}

GtkWidget *now_preflight_open(GtkWindow *parent) {
    PreflightUI *state = g_new0(PreflightUI, 1);
    state->dialog = gtk_dialog_new_with_buttons(
        "Server compatibility | NOW", parent,
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "CHECK AGAIN", GTK_RESPONSE_APPLY,
        "CLOSE", GTK_RESPONSE_CLOSE,
        NULL);
    g_object_set_data_full(G_OBJECT(state->dialog), "now-preflight-state",
                           state, g_free);

    gtk_window_set_default_size(GTK_WINDOW(state->dialog), 700, 440);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(state->dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 18);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_box_pack_start(GTK_BOX(area), box, TRUE, TRUE, 0);

    GtkWidget *title = gtk_label_new("CHECK THIS COMPUTER");
    gtk_widget_set_halign(title, GTK_ALIGN_START);
    gtk_style_context_add_class(gtk_widget_get_style_context(title), "title");
    gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);

    GtkWidget *hint = gtk_label_new(
        "Checks this Linux PC only. Nothing will be installed, changed or restarted.");
    gtk_label_set_xalign(GTK_LABEL(hint), 0.0f);
    gtk_label_set_line_wrap(GTK_LABEL(hint), TRUE);
    gtk_box_pack_start(GTK_BOX(box), hint, FALSE, FALSE, 0);

    GtkWidget *backend_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(box), backend_row, FALSE, FALSE, 0);
    GtkWidget *backend_label = gtk_label_new("Plan for");
    gtk_box_pack_start(GTK_BOX(backend_row), backend_label, FALSE, FALSE, 0);
    state->backend = gtk_combo_box_text_new();
    gtk_widget_set_name(state->backend, "now-preflight-backend");
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(state->backend),
                              "sunshine", "Sunshine - this desktop");
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(state->backend),
                              "wolf", "Wolf - independent desktop");
    gtk_combo_box_set_active_id(GTK_COMBO_BOX(state->backend), "sunshine");
    gtk_widget_set_hexpand(state->backend, TRUE);
    gtk_box_pack_start(GTK_BOX(backend_row), state->backend, TRUE, TRUE, 0);

    GtkWidget *status_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(box), status_row, FALSE, FALSE, 0);
    state->spinner = gtk_spinner_new();
    gtk_box_pack_start(GTK_BOX(status_row), state->spinner, FALSE, FALSE, 0);
    state->status = gtk_label_new("Not checked");
    gtk_label_set_xalign(GTK_LABEL(state->status), 0.0f);
    gtk_box_pack_start(GTK_BOX(status_row), state->status, TRUE, TRUE, 0);

    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                   GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_vexpand(scroll, TRUE);
    gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);

    state->report = gtk_label_new("No server configuration will be modified.");
    gtk_widget_set_halign(state->report, GTK_ALIGN_START);
    gtk_widget_set_valign(state->report, GTK_ALIGN_START);
    gtk_label_set_xalign(GTK_LABEL(state->report), 0.0f);
    gtk_label_set_yalign(GTK_LABEL(state->report), 0.0f);
    gtk_label_set_selectable(GTK_LABEL(state->report), TRUE);
    gtk_label_set_line_wrap(GTK_LABEL(state->report), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(state->report), PANGO_WRAP_WORD_CHAR);
    gtk_label_set_max_width_chars(GTK_LABEL(state->report), 88);
    gtk_container_add(GTK_CONTAINER(scroll), state->report);

    GtkWidget *disclaimer = gtk_label_new(
        "Proposed actions only. Installation is unavailable. "
        "Encoder performance, client pairing and remote streaming are not tested.");
    gtk_label_set_xalign(GTK_LABEL(disclaimer), 0.0f);
    gtk_label_set_line_wrap(GTK_LABEL(disclaimer), TRUE);
    gtk_box_pack_start(GTK_BOX(box), disclaimer, FALSE, FALSE, 0);

    state->again = gtk_dialog_get_widget_for_response(
        GTK_DIALOG(state->dialog), GTK_RESPONSE_APPLY);
    g_signal_connect(state->dialog, "response",
                     G_CALLBACK(preflight_response), state);
    g_signal_connect(state->dialog, "destroy",
                     G_CALLBACK(preflight_closed), state);
    gtk_widget_show_all(state->dialog);
    preflight_begin(state);
    return state->dialog;
}
