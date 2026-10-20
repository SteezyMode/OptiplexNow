#include "now_discovery_ui.h"

#include <gio/gio.h>
#include <arpa/inet.h>
#include <string.h>

#define DISCOVERY_HELPER "/usr/lib/optiplex-now/find-now-hosts.py"
#define DISCOVERY_PYTHON "/usr/bin/python3"
#define DISCOVERY_TIMEOUT_SECONDS 12
#define DISCOVERY_MAX_OUTPUT 8192
#define DISCOVERY_MAX_ROWS 24

typedef struct {
    GtkWidget *dialog;
    GtkWidget *spinner;
    GtkWidget *status;
    GtkWidget *choice;
    GtkWidget *rescan;
    GtkWidget *choose;
    GtkEntry *host_entry;         /* owned by parent assistant */
    GtkLabel *notice;             /* owned by parent assistant */
    GSubprocess *child;
    guint timeout_id;
    gboolean closed;
    gboolean timed_out;
} NowDiscovery;

static gboolean valid_tailnet_ip(const char *value) {
    struct in_addr ip;
    if (!value || inet_pton(AF_INET, value, &ip) != 1) return FALSE;
    guint32 address = ntohl(ip.s_addr);
    return (address & 0xffc00000U) == 0x64400000U &&
           address != 0x64646464U; /* exclude local MagicDNS resolver */
}

static void set_status(NowDiscovery *state, const char *message) {
    gtk_label_set_text(GTK_LABEL(state->status), message);
}

static gboolean discovery_timeout(gpointer data) {
    NowDiscovery *state = data;
    state->timeout_id = 0;
    state->timed_out = TRUE;
    if (state->child && !g_subprocess_get_if_exited(state->child))
        g_subprocess_force_exit(state->child);
    return G_SOURCE_REMOVE;
}

static void discovery_finished(GObject *source, GAsyncResult *result,
                               gpointer data) {
    NowDiscovery *state = data;
    char *output = NULL, *stderr_text = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &output, &stderr_text, &error);
    gboolean success = ok && g_subprocess_get_successful(G_SUBPROCESS(source));
    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
        state->timeout_id = 0;
    }
    if (!state->closed) {
        gtk_spinner_stop(GTK_SPINNER(state->spinner));
        gtk_widget_set_sensitive(state->rescan, TRUE);
        gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->choice));
        int count = 0;
        if (success && output && strlen(output) <= DISCOVERY_MAX_OUTPUT) {
            char **lines = g_strsplit(output, "\n", DISCOVERY_MAX_ROWS + 2);
            for (int i = 0; lines[i] && count < DISCOVERY_MAX_ROWS; ++i) {
                char **parts = g_strsplit(lines[i], "\t", 3);
                if (parts[0] && parts[1] && parts[2] &&
                    valid_tailnet_ip(parts[0]) &&
                    strlen(parts[1]) < 100 && strlen(parts[2]) == 32) {
                    gboolean safe = TRUE;
                    for (const char *p = parts[1]; *p; p++)
                        if ((unsigned char)*p < 32 || (unsigned char)*p > 126)
                            safe = FALSE;
                    for (const char *p = parts[2]; *p; p++)
                        if (!g_ascii_isxdigit(*p)) safe = FALSE;
                    if (safe) {
                        gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(state->choice),
                                                  parts[0], parts[1]);
                        count++;
                    }
                }
                g_strfreev(parts);
            }
            g_strfreev(lines);
        }
        if (state->timed_out) {
            set_status(state, "Scan timed out. Check Tailscale and try again.");
        } else if (!success) {
            set_status(state, "Discovery unavailable. Connect Tailscale, then retry.");
        } else if (!output || strlen(output) > DISCOVERY_MAX_OUTPUT) {
            set_status(state, "Unexpected discovery output. No server selected.");
        } else if (count == 0) {
            set_status(state, "No NOW hosts found. The host agent must be started separately.");
        } else {
            char summary[100];
            g_snprintf(summary, sizeof summary, "%d NOW server%s found.",
                       count, count == 1 ? "" : "s");
            set_status(state, summary);
            gtk_combo_box_set_active(GTK_COMBO_BOX(state->choice), 0);
        }
        gtk_widget_set_sensitive(state->choose, count > 0);
    }
    g_free(output);
    g_free(stderr_text); /* may contain sensitive daemon diagnostics */
    g_clear_error(&error);
    g_clear_object(&state->child);
    if (state->closed) g_free(state);
}

static void discovery_start(NowDiscovery *state) {
    if (state->closed || state->child) return;
    gtk_widget_set_sensitive(state->choose, FALSE);
    gtk_widget_set_sensitive(state->rescan, FALSE);
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->choice));
    if (!g_file_test(DISCOVERY_HELPER, G_FILE_TEST_IS_REGULAR) ||
        !g_file_test(DISCOVERY_PYTHON, G_FILE_TEST_IS_EXECUTABLE)) {
        set_status(state, "NOW discovery helper not installed.");
        gtk_widget_set_sensitive(state->rescan, TRUE);
        return;
    }
    const char *cmd[] = {DISCOVERY_PYTHON, DISCOVERY_HELPER, NULL};
    GError *error = NULL;
    state->child = g_subprocess_newv(cmd,
        G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, &error);
    if (!state->child) {
        set_status(state, "Could not start discovery. No changes made.");
        gtk_widget_set_sensitive(state->rescan, TRUE);
        g_clear_error(&error);
        return;
    }
    state->timed_out = FALSE;
    set_status(state, "Searching authorized Tailscale peers...");
    gtk_spinner_start(GTK_SPINNER(state->spinner));
    state->timeout_id = g_timeout_add_seconds(
        DISCOVERY_TIMEOUT_SECONDS, discovery_timeout, state);
    g_subprocess_communicate_utf8_async(
        state->child, NULL, NULL, discovery_finished, state);
}

static void discovery_response(GtkDialog *dialog, gint response, gpointer data) {
    NowDiscovery *state = data;
    if (response == GTK_RESPONSE_APPLY) {
        discovery_start(state);
        return;
    }
    if (response == GTK_RESPONSE_ACCEPT) {
        const char *address = gtk_combo_box_get_active_id(
            GTK_COMBO_BOX(state->choice));
        if (!state->child && valid_tailnet_ip(address) && state->host_entry) {
            gtk_entry_set_text(state->host_entry, address);
            if (state->notice)
                gtk_label_set_text(state->notice,
                    "NOW SERVER FOUND. COMPLETE THE NORMAL PAIRING STEPS.");
            gtk_widget_destroy(GTK_WIDGET(dialog));
        }
        return;
    }
    gtk_widget_destroy(GTK_WIDGET(dialog));
}

static void discovery_destroy(GtkWidget *widget, gpointer data) {
    NowDiscovery *state = data;
    (void)widget;
    state->closed = TRUE;
    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
        state->timeout_id = 0;
    }
    if (state->child) {
        if (!g_subprocess_get_if_exited(state->child))
            g_subprocess_force_exit(state->child);
        /* Async callback owns the state until child reaping finishes. */
    } else {
        g_free(state);
    }
}

GtkWidget *now_discovery_open(GtkWindow *parent, GtkEntry *host_entry,
                              GtkLabel *notice) {
    NowDiscovery *state = g_new0(NowDiscovery, 1);
    state->host_entry = host_entry;
    state->notice = notice;
    state->dialog = gtk_dialog_new_with_buttons(
        "Find NOW server", parent,
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "SCAN AGAIN", GTK_RESPONSE_APPLY,
        "USE THIS SERVER", GTK_RESPONSE_ACCEPT,
        "CLOSE", GTK_RESPONSE_CLOSE, NULL);
    gtk_window_set_default_size(GTK_WINDOW(state->dialog), 520, 230);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(state->dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 18);
    GtkWidget *column = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    gtk_box_pack_start(GTK_BOX(area), column, TRUE, TRUE, 0);

    GtkWidget *hint = gtk_label_new(
        "Find NOW-enabled computers on your authorized Tailscale network.");
    gtk_label_set_xalign(GTK_LABEL(hint), 0.0);
    gtk_label_set_line_wrap(GTK_LABEL(hint), TRUE);
    gtk_box_pack_start(GTK_BOX(column), hint, FALSE, FALSE, 0);

    GtkWidget *status_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(column), status_row, FALSE, FALSE, 0);
    state->spinner = gtk_spinner_new();
    gtk_box_pack_start(GTK_BOX(status_row), state->spinner, FALSE, FALSE, 0);
    state->status = gtk_label_new("Not checked.");
    gtk_label_set_xalign(GTK_LABEL(state->status), 0.0);
    gtk_label_set_line_wrap(GTK_LABEL(state->status), TRUE);
    gtk_box_pack_start(GTK_BOX(status_row), state->status, TRUE, TRUE, 0);

    state->choice = gtk_combo_box_text_new();
    gtk_widget_set_name(state->choice, "now-host-selector");
    gtk_widget_set_hexpand(state->choice, TRUE);
    gtk_box_pack_start(GTK_BOX(column), state->choice, FALSE, FALSE, 0);

    GtkWidget *footer = gtk_label_new(
        "Discovery is read-only. Pairing and device approval are still required.");
    gtk_label_set_xalign(GTK_LABEL(footer), 0.0);
    gtk_label_set_line_wrap(GTK_LABEL(footer), TRUE);
    gtk_box_pack_start(GTK_BOX(column), footer, FALSE, FALSE, 0);

    state->rescan = gtk_dialog_get_widget_for_response(
        GTK_DIALOG(state->dialog), GTK_RESPONSE_APPLY);
    state->choose = gtk_dialog_get_widget_for_response(
        GTK_DIALOG(state->dialog), GTK_RESPONSE_ACCEPT);
    gtk_widget_set_sensitive(state->choose, FALSE);
    g_signal_connect(state->dialog, "response",
                     G_CALLBACK(discovery_response), state);
    g_signal_connect(state->dialog, "destroy",
                     G_CALLBACK(discovery_destroy), state);
    gtk_widget_show_all(state->dialog);
    discovery_start(state);
    return state->dialog;
}
