/*
 * NOW Host Setup: real, read-only local hardware and installation review.
 *
 * Separate GTK3 program; avoids adding server state to the client main.c.
 * Executes only the packaged read-only Python scanner and planner. No shell,
 * sudo, Docker mutation, approval token, image pull or installation action.
 */
#include <gtk/gtk.h>
#include <gio/gio.h>
#include <string.h>

#define PREFLIGHT "/usr/lib/optiplex-now/host_preflight.py"
#define PLAN "/usr/lib/optiplex-now/host_plan.py"
#define MAX_RESULT 24576

typedef struct {
    GtkWidget *window;
    GtkWidget *status;
    GtkWidget *run_button;
    GtkTextBuffer *output;
    GCancellable *cancel;
    gboolean closing;
    gboolean running;
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
        strstr(message, "COMPLETE.") ?
        "OptiPlex NOW | Server Review Complete" :
        "OptiPlex NOW | Server Review Incomplete");
    gtk_widget_set_sensitive(ui->run_button, TRUE);
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
            if (ui->step == 0) {
                ui->step = 1;
                run_read_only_step(ui);
            } else {
                report_complete(ui, "REVIEW COMPLETE. INSTALLATION NOT AVAILABLE.");
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
    const gchar *script = ui->step == 0 ? PREFLIGHT : PLAN;
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
    } else {
        append_result(ui, "INSTALLATION PLAN\n==============================\n\n");
        gtk_label_set_text(GTK_LABEL(ui->status), "REVIEWING REQUIREMENTS...");
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
    run_read_only_step(ui);
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
    gtk_window_set_default_size(GTK_WINDOW(ui->window), 680, 480);
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
        "No installation is available in this build.\n"
        "Select CHECK THIS PC to see the actual local hardware findings,\n"
        "service conflicts and outstanding installation requirements.\n"
        "You can safely run this on a PC already hosting Wolf.",
        -1);

    GtkWidget *actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(actions), GTK_BUTTONBOX_END);
    gtk_box_pack_start(GTK_BOX(column), actions, FALSE, FALSE, 0);
    ui->run_button = gtk_button_new_with_label("CHECK THIS PC");
    gtk_container_add(GTK_CONTAINER(actions), ui->run_button);
    g_signal_connect(ui->run_button, "clicked",
                     G_CALLBACK(on_check_clicked), ui);
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
