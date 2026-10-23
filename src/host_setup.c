/*
 * NOW Host Setup: host readiness review plus separately gated pilot install.
 *
 * Separate GTK3 program; avoids adding server state to the client main.c.
 * The normal CHECK THIS PC action only runs packaged read-only hardware,
 * planning and service-inventory helpers. A distinct ADVANCED clean-host
 * installer requires owner confirmation and OS authorization.
 */
#include <gtk/gtk.h>
#include <gio/gio.h>
#include <string.h>

#define PREFLIGHT "/usr/lib/optiplex-now/host_preflight.py"
#define PLAN "/usr/lib/optiplex-now/host_plan.py"
#define SERVICES "/usr/lib/optiplex-now/host_services.py"
#define ADOPTION "/usr/lib/optiplex-now/host_adoption.py"
#define INSTALLER "/usr/lib/optiplex-now/host_install.py"
#define MAX_RESULT 24576

typedef struct {
    GtkWidget *window;
    GtkWidget *status;
    GtkWidget *run_button;
    GtkWidget *verify_services_button;
    GtkWidget *gpu_choice;
    GtkWidget *render_entry;
    GtkWidget *digest_entry;
    GtkWidget *nvidia_sha_entry;
    GtkWidget *eligible_button;
    GtkWidget *install_button;
    gboolean eligible;
    gboolean installing;
    GtkTextBuffer *output;
    GCancellable *cancel;
    gboolean closing;
    gboolean running;
    guint settings_revision;
    guint eligibility_revision;
    unsigned step;
} HostSetupUI;

static void host_ui_free(gpointer data)
{
    HostSetupUI *ui = data;
    g_clear_object(&ui->cancel);
    g_free(ui);
}

static void append_result(HostSetupUI *ui, const char *text)
{
    GtkTextIter end;
    gtk_text_buffer_get_end_iter(ui->output, &end);
    gtk_text_buffer_insert(ui->output, &end, text, -1);
}

static void report_complete(HostSetupUI *ui, const char *message)
{
    ui->running = FALSE;
    if (ui->closing)
        return;
    gtk_label_set_text(GTK_LABEL(ui->status), message);
    gtk_window_set_title(GTK_WINDOW(ui->window),
        g_str_has_prefix(message, "REVIEW COMPLETE.") ?
        "OptiPlex NOW | Server Review Complete" :
        "OptiPlex NOW | Server Review Incomplete");
    gtk_widget_set_sensitive(ui->run_button, TRUE);
    gtk_widget_set_sensitive(ui->verify_services_button, TRUE);
}

static void run_read_only_step(HostSetupUI *ui);

static void read_only_done(GObject *source, GAsyncResult *result, gpointer data)
{
    GtkWidget *window = GTK_WIDGET(data);
    HostSetupUI *ui = g_object_get_data(G_OBJECT(window), "now-host-ui");
    gchar *output = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &output, NULL, &error);

    if (!ui->closing) {
        if (!ok || !g_subprocess_get_successful(G_SUBPROCESS(source))) {
            append_result(ui, "\nUnable to complete the read-only check.\n");
            report_complete(ui, "CHECK INCOMPLETE. NO CHANGES MADE.");
        } else if (!output || strlen(output) > MAX_RESULT ||
                   !g_utf8_validate(output, -1, NULL)) {
            append_result(ui, "\nHost check returned invalid or excessive output.\n");
            report_complete(ui, "CHECK INCOMPLETE. NO CHANGES MADE.");
        } else {
            append_result(ui, output);
            append_result(ui, "\n\n");
            if (ui->step < 3) {
                ui->step++;
                run_read_only_step(ui);
            } else {
                report_complete(ui, "REVIEW COMPLETE. NO CHANGES MADE.");
            }
        }
    }
    g_clear_error(&error);
    g_free(output);
    g_object_unref(window);
}

static void run_read_only_step(HostSetupUI *ui)
{
    if (ui->closing)
        return;
    const gchar *script = ui->step == 0 ? PREFLIGHT :
                          ui->step == 1 ? PLAN :
                          ui->step == 2 ? SERVICES : ADOPTION;
    const gchar *args[] = {"/usr/bin/python3", script, NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        args, G_SUBPROCESS_FLAGS_STDOUT_PIPE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (!process) {
        append_result(ui, "\nRead-only host tools are unavailable. Reinstall NOW.\n");
        report_complete(ui, "CHECK INCOMPLETE. NO CHANGES MADE.");
        g_clear_error(&error);
        return;
    }
    if (ui->step == 0) {
        append_result(ui, "HOST PREFLIGHT\n==============================\n\n");
        gtk_label_set_text(GTK_LABEL(ui->status), "CHECKING THIS COMPUTER...");
    } else if (ui->step == 1) {
        append_result(ui, "INSTALLATION PLAN\n==============================\n\n");
        gtk_label_set_text(GTK_LABEL(ui->status), "REVIEWING REQUIREMENTS...");
    } else if (ui->step == 2) {
        append_result(ui, "EXISTING SERVICES | ADOPTION CANDIDATES\n==============================\n\n");
        gtk_label_set_text(GTK_LABEL(ui->status), "CHECKING EXISTING SERVICES...");
    } else {
        append_result(ui, "ADOPT EXISTING / SET UP NEW | SAFETY PLAN\n==============================\n\n");
        gtk_label_set_text(GTK_LABEL(ui->status), "PLANNING SAFE SERVICE ADOPTION...");
    }
    g_subprocess_communicate_utf8_async(
        process, NULL, ui->cancel, read_only_done,
        g_object_ref(ui->window));
    g_object_unref(process);
}

static void on_check_clicked(GtkButton *button, gpointer data)
{
    (void)button;
    HostSetupUI *ui = data;
    if (ui->running || ui->closing)
        return;
    ui->running = TRUE;
    ui->step = 0;
    g_clear_object(&ui->cancel);
    ui->cancel = g_cancellable_new();
    gtk_text_buffer_set_text(ui->output, "", -1);
    gtk_widget_set_sensitive(ui->run_button, FALSE);
    gtk_widget_set_sensitive(ui->verify_services_button, FALSE);
    run_read_only_step(ui);
}

/* Explicit, local OS authorization to inspect the host Docker socket.
 * Normal CHECK THIS PC never escalates. Only the fixed installed read-only
 * planner is launched here; no untrusted server, path or argv is accepted. */
static void privileged_services_done(GObject *source, GAsyncResult *result, gpointer data)
{
    GtkWidget *window = GTK_WIDGET(data);
    HostSetupUI *ui = g_object_get_data(G_OBJECT(window), "now-host-ui");
    gchar *out = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &out, NULL, &error);
    if (!ui->closing) {
        if (ok && g_subprocess_get_successful(G_SUBPROCESS(source)) &&
            out && strlen(out) <= MAX_RESULT && g_utf8_validate(out, -1, NULL) &&
            g_str_has_prefix(out, "ADOPT EXISTING / SET UP NEW | READ-ONLY PLAN")) {
            append_result(ui, out);
            append_result(ui, "\n");
            gtk_label_set_text(GTK_LABEL(ui->status),
                               "EXISTING SERVICES REVIEWED. NO CHANGES MADE.");
        } else {
            append_result(ui, "OS-APPROVED SERVICE CHECK CANCELLED OR UNAVAILABLE. "
                              "Nothing was changed.\n");
            gtk_label_set_text(GTK_LABEL(ui->status),
                               "SERVICE REVIEW INCOMPLETE. NO CHANGES MADE.");
        }
        ui->running = FALSE;
        gtk_widget_set_sensitive(ui->run_button, TRUE);
        gtk_widget_set_sensitive(ui->verify_services_button, TRUE);
    }
    g_clear_error(&error);
    g_free(out);
    g_object_unref(window);
}

static void on_verify_services(GtkButton *button, gpointer data)
{
    (void)button;
    HostSetupUI *ui = data;
    if (ui->running || ui->installing || ui->closing)
        return;
    /* A Docker socket is root-equivalent. Use a real OS permission prompt
     * rather than adding the ordinary NOW user to the docker group. */
    const gchar *argv[] = {"/usr/bin/pkexec", "/usr/bin/python3", ADOPTION, NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
        &error);
    if (!process) {
        gtk_label_set_text(GTK_LABEL(ui->status),
                           "OS SERVICE REVIEW UNAVAILABLE. NO CHANGES MADE.");
        g_clear_error(&error);
        return;
    }
    ui->running = TRUE;
    gtk_widget_set_sensitive(ui->run_button, FALSE);
    gtk_widget_set_sensitive(ui->verify_services_button, FALSE);
    append_result(ui, "\nEXISTING SERVICES | OS-AUTHORIZED READ-ONLY REVIEW\n"
                      "==============================\n\n");
    gtk_label_set_text(GTK_LABEL(ui->status),
                       "AWAITING LOCAL OS AUTHORIZATION FOR SERVICE REVIEW...");
    g_subprocess_communicate_utf8_async(
        process, NULL, NULL, privileged_services_done,
        g_object_ref(ui->window));
    g_object_unref(process);
}

static void on_window_destroy(GtkWidget *window, gpointer data)
{
    (void)window;
    HostSetupUI *ui = data;
    ui->closing = TRUE;
    if (ui->cancel)
        g_cancellable_cancel(ui->cancel);
    gtk_main_quit();
}


/* Real clean-host installation requires eligibility first, then owner consent
 * via both this review dialog and the local OS polkit authentication agent.
 * The privileged installer reruns every eligibility and conflict check. */
static const char *selected_gpu(HostSetupUI *ui)
{
    int active = gtk_combo_box_get_active(GTK_COMBO_BOX(ui->gpu_choice));
    return active == 0 ? "amd" : active == 1 ? "intel" : "nvidia";
}

static gboolean valid_pinned_digest(const char *digest)
{
    if (!digest || !g_str_has_prefix(digest, "sha256:") ||
        strlen(digest) != 71)
        return FALSE;
    for (const char *c = digest + 7; *c; c++)
        if (!((*c >= '0' && *c <= '9') || (*c >= 'a' && *c <= 'f')))
            return FALSE;
    return TRUE;
}

static void invalidate_install(GtkWidget *widget, gpointer data)
{
    (void)widget;
    HostSetupUI *ui = data;
    ui->settings_revision++;
    ui->eligible = FALSE;
    gtk_widget_set_sensitive(ui->install_button, FALSE);
    if (!ui->installing)
        gtk_label_set_text(GTK_LABEL(ui->status),
            "INSTALL SETTINGS CHANGED. CHECK ELIGIBILITY AGAIN.");
}

static void eligibility_done(GObject *source, GAsyncResult *result, gpointer data)
{
    GtkWidget *window = GTK_WIDGET(data);
    HostSetupUI *ui = g_object_get_data(G_OBJECT(window), "now-host-ui");
    gchar *out = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &out, NULL, &error);
    if (!ui->closing) {
        ui->running = FALSE;
        gtk_widget_set_sensitive(ui->eligible_button, TRUE);
        if (ui->eligibility_revision != ui->settings_revision) {
            /* The user edited the settings after this check started.
             * Never apply a previous machine/configuration result. */
            append_result(ui, "\nSettings changed while eligibility was being checked. Recheck.\n");
            ui->eligible = FALSE;
            gtk_widget_set_sensitive(ui->install_button, FALSE);
            gtk_label_set_text(GTK_LABEL(ui->status),
                "SETTINGS CHANGED. CHECK ELIGIBILITY AGAIN.");
        } else if (!ok || !g_subprocess_get_successful(G_SUBPROCESS(source)) ||
                   !out || strlen(out) > MAX_RESULT) {
            append_result(ui, "\nHost installation eligibility check failed.\n");
            gtk_label_set_text(GTK_LABEL(ui->status), "INSTALLATION CHECK FAILED.");
        } else {
            append_result(ui, "\nCLEAN-HOST INSTALL ELIGIBILITY\n");
            append_result(ui, out);
            append_result(ui, "\n");
            ui->eligible = (strstr(out, "\"decision\": \"candidate\"") != NULL ||
                            strstr(out, "\"decision\": \"candidate_after_admin_check\"") != NULL);
            gtk_widget_set_sensitive(ui->install_button, ui->eligible);
            gtk_label_set_text(GTK_LABEL(ui->status),
                ui->eligible ? "CANDIDATE. OS AUTHORIZATION WILL RECHECK DOCKER." :
                               "INSTALLATION BLOCKED. NO CHANGES MADE.");
        }
    }
    g_clear_error(&error);
    g_free(out);
    g_object_unref(window);
}

static void on_eligibility(GtkButton *button, gpointer data)
{
    (void)button;
    HostSetupUI *ui = data;
    if (ui->running || ui->closing || ui->installing)
        return;
    ui->eligible = FALSE;
    gtk_widget_set_sensitive(ui->install_button, FALSE);
    ui->eligibility_revision = ui->settings_revision;
    ui->running = TRUE;
    gtk_widget_set_sensitive(ui->eligible_button, FALSE);
    const gchar *argv[] = {
        "/usr/bin/python3", INSTALLER, "--check",
        "--gpu", selected_gpu(ui),
        "--render-node", gtk_entry_get_text(GTK_ENTRY(ui->render_entry)),
        NULL
    };
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (!process) {
        ui->running = FALSE;
        gtk_widget_set_sensitive(ui->eligible_button, TRUE);
        gtk_label_set_text(GTK_LABEL(ui->status),
                           "INSTALLER CHECK UNAVAILABLE. NO CHANGES MADE.");
        g_clear_error(&error);
        return;
    }
    gtk_label_set_text(GTK_LABEL(ui->status), "CHECKING CLEAN-HOST ELIGIBILITY...");
    g_subprocess_communicate_utf8_async(
        process, NULL, NULL, eligibility_done, g_object_ref(ui->window));
    g_object_unref(process);
}

static void installation_done(GObject *source, GAsyncResult *result, gpointer data)
{
    GtkWidget *window = GTK_WIDGET(data);
    HostSetupUI *ui = g_object_get_data(G_OBJECT(window), "now-host-ui");
    gchar *out = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &out, NULL, &error);
    if (!ui->closing) {
        ui->installing = FALSE;
        if (ok && g_subprocess_get_successful(G_SUBPROCESS(source)) &&
            out && strlen(out) <= MAX_RESULT &&
            strstr(out, "\"result\": \"running_stream_unverified\"")) {
            append_result(ui, "\nINSTALLATION RESULT\n");
            append_result(ui, out);
            gtk_label_set_text(GTK_LABEL(ui->status),
                "WOLF STARTED. REAL GAME/VIDEO/INPUT STREAM NOT YET VERIFIED.");
        } else {
            append_result(ui,
                "\nINSTALLATION INCOMPLETE. DO NOT REPEAT INSTALL BLINDLY.\n"
                "Inspect the owner state under /var/lib/optiplex-now/host.\n"
                "Existing unrelated services were not targeted for removal.\n");
            gtk_label_set_text(GTK_LABEL(ui->status),
                "INSTALL INCOMPLETE. OWNER REVIEW REQUIRED.");
        }
        gtk_widget_set_sensitive(ui->eligible_button, TRUE);
    }
    g_clear_error(&error);
    g_free(out);
    g_object_unref(window);
}

static void on_install(GtkButton *button, gpointer data)
{
    (void)button;
    HostSetupUI *ui = data;
    if (!ui->eligible || ui->running || ui->installing || ui->closing)
        return;
    const char *digest = gtk_entry_get_text(GTK_ENTRY(ui->digest_entry));
    if (!valid_pinned_digest(digest)) {
        gtk_label_set_text(GTK_LABEL(ui->status),
            "ENTER A VERIFIED SHA256 WOLF IMAGE DIGEST BEFORE INSTALLING.");
        return;
    }
    const char *gpu = selected_gpu(ui);
    const char *nvidia_sha = gtk_entry_get_text(GTK_ENTRY(ui->nvidia_sha_entry));
    if (g_strcmp0(gpu, "nvidia") == 0 &&
        (!nvidia_sha || strlen(nvidia_sha) != 64 ||
         strspn(nvidia_sha, "0123456789abcdef") != 64)) {
        gtk_label_set_text(GTK_LABEL(ui->status),
            "NVIDIA REQUIRES A VERIFIED 64-CHARACTER DRIVER INSTALLER SHA256.");
        return;
    }
    GtkWidget *confirm = gtk_message_dialog_new(
        GTK_WINDOW(ui->window), GTK_DIALOG_MODAL,
        GTK_MESSAGE_WARNING, GTK_BUTTONS_NONE,
        "Install a NEW Wolf streaming server on this computer?");
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(confirm),
        "Only for an EMPTY, ELIGIBLE new Linux host.\n"
        "Image: ghcr.io/games-on-whales/wolf@%s\n"
        "NVIDIA will build the verified driver userspace volume.\n"
        "The supplied driver checksum MUST be independently verified.\n"
        "Managed data: /var/lib/optiplex-now/host\n"
        "Wolf requires administrative Docker socket access.\n"
        "The OS will ask for administrator authentication.\n"
        "No existing Wolf installations will be imported or replaced.\n"
        "Running does not mean streaming has been verified.",
        digest);
    gtk_dialog_add_buttons(GTK_DIALOG(confirm), "CANCEL", GTK_RESPONSE_CANCEL,
                           "INSTALL ON THIS HOST", GTK_RESPONSE_ACCEPT, NULL);
    gboolean approved = gtk_dialog_run(GTK_DIALOG(confirm)) == GTK_RESPONSE_ACCEPT;
    gtk_widget_destroy(confirm);
    if (!approved)
        return;
    const gchar *argv[17] = {
        "/usr/bin/pkexec", INSTALLER, "--install",
        "--gpu", gpu,
        "--render-node", gtk_entry_get_text(GTK_ENTRY(ui->render_entry)),
        "--image-digest", digest, "--confirm", "INSTALL-WOLF",
        NULL, NULL, NULL
    };
    if (g_strcmp0(gpu, "nvidia") == 0) {
        argv[11] = "--nvidia-installer-sha256";
        argv[12] = nvidia_sha;
        argv[13] = NULL;
    }
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE |
              G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (!process) {
        gtk_label_set_text(GTK_LABEL(ui->status),
            "COULD NOT START OS AUTHORIZATION. NOTHING INSTALLED BY NOW.");
        g_clear_error(&error);
        return;
    }
    ui->installing = TRUE;
    ui->eligible = FALSE;
    gtk_widget_set_sensitive(ui->install_button, FALSE);
    gtk_widget_set_sensitive(ui->eligible_button, FALSE);
    gtk_label_set_text(GTK_LABEL(ui->status),
        "INSTALLATION REQUESTED. DO NOT START ANOTHER INSTALLATION.");
    g_subprocess_communicate_utf8_async(
        process, NULL, NULL, installation_done, g_object_ref(ui->window));
    g_object_unref(process);
}

int main(int argc, char **argv)
{
    /* Useful for an actual end-to-end installed-package GUI check. */
    gboolean auto_check = argc == 2 && strcmp(argv[1], "--check-on-open") == 0;
    if (auto_check)
        argc = 1;
    gtk_init(&argc, &argv);

    HostSetupUI *ui = g_new0(HostSetupUI, 1);
    ui->window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(ui->window), "OptiPlex NOW | Server Setup");
    gtk_window_set_default_size(GTK_WINDOW(ui->window), 720, 590);
    gtk_window_set_position(GTK_WINDOW(ui->window), GTK_WIN_POS_CENTER);
    g_object_set_data_full(G_OBJECT(ui->window), "now-host-ui", ui, host_ui_free);
    g_signal_connect(ui->window, "destroy",
                     G_CALLBACK(on_window_destroy), ui);

    GtkWidget *column = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(column), 14);
    gtk_container_add(GTK_CONTAINER(ui->window), column);

    GtkWidget *heading = gtk_label_new("SERVER SETUP | COMPATIBILITY REVIEW");
    gtk_label_set_xalign(GTK_LABEL(heading), 0);
    gtk_box_pack_start(GTK_BOX(column), heading, FALSE, FALSE, 0);

    GtkWidget *description = gtk_label_new(
        "Check whether this Linux PC might qualify as a streaming host.\n"
        "This review will not install, configure, restart or remove anything.");
    gtk_label_set_xalign(GTK_LABEL(description), 0);
    gtk_label_set_line_wrap(GTK_LABEL(description), TRUE);
    gtk_box_pack_start(GTK_BOX(column), description, FALSE, FALSE, 0);

    ui->status = gtk_label_new("NOT CHECKED. NO CHANGES WILL BE MADE.");
    gtk_label_set_xalign(GTK_LABEL(ui->status), 0);
    gtk_box_pack_start(GTK_BOX(column), ui->status, FALSE, FALSE, 0);

    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                   GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_vexpand(scroll, TRUE);
    gtk_box_pack_start(GTK_BOX(column), scroll, TRUE, TRUE, 0);
    GtkWidget *view = gtk_text_view_new();
    ui->output = gtk_text_view_get_buffer(GTK_TEXT_VIEW(view));
    gtk_text_view_set_editable(GTK_TEXT_VIEW(view), FALSE);
    gtk_text_view_set_cursor_visible(GTK_TEXT_VIEW(view), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(view), GTK_WRAP_WORD_CHAR);
    gtk_container_add(GTK_CONTAINER(scroll), view);
    gtk_text_buffer_set_text(
        ui->output,
        "Install is only available after clean-host eligibility and OS approval.\n"
        "Select CHECK THIS PC to see the actual local hardware findings,\n"
        "existing Wolf/Jellyfin/downloader candidates and requirements.\n"
        "You can safely run this on a PC already hosting these services.",
        -1);

    GtkWidget *advanced = gtk_expander_new(
        "ADVANCED CLEAN-HOST INSTALL | AMD / INTEL / NVIDIA PILOT");
    GtkWidget *settings = gtk_grid_new();
    gtk_grid_set_column_spacing(GTK_GRID(settings), 8);
    gtk_grid_set_row_spacing(GTK_GRID(settings), 7);
    gtk_container_set_border_width(GTK_CONTAINER(settings), 8);
    gtk_container_add(GTK_CONTAINER(advanced), settings);
    gtk_box_pack_start(GTK_BOX(column), advanced, FALSE, FALSE, 0);

    GtkWidget *intro = gtk_label_new(
        "Pop!_OS or Ubuntu 24.04. NVIDIA additionally requires a trusted "
        "SHA256 for the exact NVIDIA driver installer. Only for clean hosts.");
    gtk_label_set_line_wrap(GTK_LABEL(intro), TRUE);
    gtk_label_set_xalign(GTK_LABEL(intro), 0);
    gtk_grid_attach(GTK_GRID(settings), intro, 0, 0, 2, 1);

    gtk_grid_attach(GTK_GRID(settings), gtk_label_new("GPU"), 0, 1, 1, 1);
    ui->gpu_choice = gtk_combo_box_text_new();
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(ui->gpu_choice), "AMD");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(ui->gpu_choice), "Intel");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(ui->gpu_choice), "NVIDIA");
    gtk_combo_box_set_active(GTK_COMBO_BOX(ui->gpu_choice), 0);
    gtk_grid_attach(GTK_GRID(settings), ui->gpu_choice, 1, 1, 1, 1);

    gtk_grid_attach(GTK_GRID(settings), gtk_label_new("Render device"), 0, 2, 1, 1);
    ui->render_entry = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(ui->render_entry), "/dev/dri/renderD128");
    gtk_grid_attach(GTK_GRID(settings), ui->render_entry, 1, 2, 1, 1);

    gtk_grid_attach(GTK_GRID(settings), gtk_label_new("Wolf SHA256"), 0, 3, 1, 1);
    ui->digest_entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(ui->digest_entry),
                                   "sha256: (verified upstream image digest)");
    gtk_grid_attach(GTK_GRID(settings), ui->digest_entry, 1, 3, 1, 1);

    gtk_grid_attach(GTK_GRID(settings),
                    gtk_label_new("NVIDIA installer SHA256"), 0, 4, 1, 1);
    ui->nvidia_sha_entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(ui->nvidia_sha_entry),
                                   "64 hex characters; independently verified");
    gtk_grid_attach(GTK_GRID(settings), ui->nvidia_sha_entry, 1, 4, 1, 1);
    ui->eligible_button = gtk_button_new_with_label("CHECK INSTALL ELIGIBILITY");
    gtk_grid_attach(GTK_GRID(settings), ui->eligible_button, 0, 5, 1, 1);
    ui->install_button = gtk_button_new_with_label("INSTALL ON CLEAN HOST...");
    gtk_widget_set_sensitive(ui->install_button, FALSE);
    gtk_grid_attach(GTK_GRID(settings), ui->install_button, 1, 5, 1, 1);
    g_signal_connect(ui->gpu_choice, "changed",
                     G_CALLBACK(invalidate_install), ui);
    g_signal_connect(ui->render_entry, "changed",
                     G_CALLBACK(invalidate_install), ui);
    g_signal_connect(ui->digest_entry, "changed",
                     G_CALLBACK(invalidate_install), ui);
    g_signal_connect(ui->nvidia_sha_entry, "changed",
                     G_CALLBACK(invalidate_install), ui);
    g_signal_connect(ui->eligible_button, "clicked",
                     G_CALLBACK(on_eligibility), ui);
    g_signal_connect(ui->install_button, "clicked",
                     G_CALLBACK(on_install), ui);

    GtkWidget *actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(actions), GTK_BUTTONBOX_END);
    gtk_box_pack_start(GTK_BOX(column), actions, FALSE, FALSE, 0);
    ui->run_button = gtk_button_new_with_label("CHECK THIS PC");
    gtk_container_add(GTK_CONTAINER(actions), ui->run_button);
    g_signal_connect(ui->run_button, "clicked",
                     G_CALLBACK(on_check_clicked), ui);
    ui->verify_services_button = gtk_button_new_with_label(
        "VERIFY EXISTING SERVICES (OS APPROVAL)");
    gtk_container_add(GTK_CONTAINER(actions), ui->verify_services_button);
    g_signal_connect(ui->verify_services_button, "clicked",
                     G_CALLBACK(on_verify_services), ui);
    GtkWidget *close = gtk_button_new_with_label("CLOSE");
    gtk_container_add(GTK_CONTAINER(actions), close);
    g_signal_connect_swapped(close, "clicked",
                             G_CALLBACK(gtk_widget_destroy), ui->window);

    gtk_widget_show_all(ui->window);
    if (auto_check)
        on_check_clicked(GTK_BUTTON(ui->run_button), ui);
    gtk_main();
    return 0;
}
