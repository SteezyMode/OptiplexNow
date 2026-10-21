#include <gtk/gtk.h>
#include <stdio.h>
#include <string.h>

static gboolean is_host_confirmation(const char *prompt)
{
    return (strstr(prompt, "Are you sure you want to continue connecting") != NULL ||
            strstr(prompt, "yes/no/") != NULL) &&
           (strstr(prompt, "fingerprint") != NULL ||
            strstr(prompt, "yes/no/") != NULL);
}

static gboolean is_password_question(const char *prompt)
{
    return g_strrstr(prompt, "password") != NULL ||
           g_strrstr(prompt, "Password") != NULL ||
           g_strrstr(prompt, "passphrase") != NULL ||
           g_strrstr(prompt, "Passphrase") != NULL;
}

int main(int argc, char **argv)
{
    const char *prompt = argc > 1 ? argv[1] : "";
    if (strlen(prompt) > 2048 ||
        (!is_host_confirmation(prompt) && !is_password_question(prompt))) {
        return 1;
    }

    if (!gtk_init_check(&argc, &argv)) {
        return 1;
    }
    gboolean host_key = is_host_confirmation(prompt);
    GtkWidget *dialog = gtk_dialog_new_with_buttons(
        host_key ? "Verify SSH Host Key" : "Authorize SSH Access", NULL,
        GTK_DIALOG_MODAL, "Cancel", GTK_RESPONSE_CANCEL,
        host_key ? "Trust This Host Key" : "Continue", GTK_RESPONSE_OK, NULL);
    gtk_window_set_keep_above(GTK_WINDOW(dialog), TRUE);
    gtk_window_set_position(GTK_WINDOW(dialog), GTK_WIN_POS_CENTER_ALWAYS);
    gtk_window_set_default_size(GTK_WINDOW(dialog), 460, -1);

    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 18);
    GtkWidget *label = gtk_label_new(host_key
        ? "Verify this host fingerprint through a trusted channel before approving. "
          "An unexpected key could be another computer."
        : "Enter your existing server account password or SSH key passphrase.");
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    gtk_label_set_xalign(GTK_LABEL(label), 0);
    gtk_box_pack_start(GTK_BOX(area), label, FALSE, FALSE, 8);

    GtkWidget *question = gtk_label_new(prompt);
    gtk_label_set_selectable(GTK_LABEL(question), TRUE);
    gtk_label_set_line_wrap(GTK_LABEL(question), TRUE);
    gtk_label_set_xalign(GTK_LABEL(question), 0);
    gtk_box_pack_start(GTK_BOX(area), question, FALSE, FALSE, 8);

    GtkWidget *entry = NULL;
    if (!host_key) {
        entry = gtk_entry_new();
        gtk_entry_set_visibility(GTK_ENTRY(entry), FALSE);
        gtk_entry_set_invisible_char(GTK_ENTRY(entry), 0x2022);
        gtk_entry_set_activates_default(GTK_ENTRY(entry), TRUE);
        gtk_box_pack_start(GTK_BOX(area), entry, FALSE, FALSE, 8);
    }

    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_OK);
    gtk_widget_show_all(dialog);
    if (entry) {
        gtk_widget_grab_focus(entry);
    }
    int response = gtk_dialog_run(GTK_DIALOG(dialog));
    if (response == GTK_RESPONSE_OK) {
        const char *answer = host_key ? "yes" : gtk_entry_get_text(GTK_ENTRY(entry));
        if (*answer && !strchr(answer, '\n') && !strchr(answer, '\r')) {
            fputs(answer, stdout);
            fputc('\n', stdout);
            fflush(stdout);
            gtk_widget_destroy(dialog);
            return 0;
        }
    }
    gtk_widget_destroy(dialog);
    return 1;
}
