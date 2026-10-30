/* Real GTK Settings presentation contract on disposable Xvfb.
 * A mock callback table prevents any SSH, backup, service or host operation.
 * Preferences remain in an isolated temporary home and are not saved.
 */
#include <gtk/gtk.h>
#include <glib/gstdio.h>
#include <string.h>
#include "config.h"
#include "ui_settings.h"

static guint action_calls;
static void record_action(GtkWidget *widget, gpointer data)
{
    (void)widget;
    (void)data;
    ++action_calls;
}

static GtkWidget *button_named(GtkWidget *container, const char *caption)
{
    if (GTK_IS_BUTTON(container) &&
        g_strcmp0(gtk_button_get_label(GTK_BUTTON(container)), caption) == 0)
        return container;
    if (!GTK_IS_CONTAINER(container))
        return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(container));
    GtkWidget *found = NULL;
    for (GList *item = children; item && !found; item = item->next)
        found = button_named(GTK_WIDGET(item->data), caption);
    g_list_free(children);
    return found;
}

int main(int argc, char **argv)
{
    GError *error = NULL;
    gchar *home = g_dir_make_tmp("now-ui-settings.XXXXXX", &error);
    g_assert_no_error(error);
    g_assert_nonnull(home);
    g_setenv("HOME", home, TRUE);
    g_setenv("XDG_CONFIG_HOME", home, TRUE);
    gtk_init(&argc, &argv);

    now_config_load_from(NULL);
    g_strlcpy(cfg[0], "192.0.2.10", CONFIG_VALUE_SIZE);
    g_strlcpy(cfg[1], "owner", CONFIG_VALUE_SIZE);
    char preview[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    memcpy(preview, cfg, sizeof preview);
    g_strlcpy(preview[0], "198.51.100.8", CONFIG_VALUE_SIZE);

    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GtkWidget *main_pages = gtk_stack_new();
    gtk_container_add(GTK_CONTAINER(window), main_pages);
    gtk_stack_add_named(GTK_STACK(main_pages), gtk_label_new("Dashboard"),
                        "dashboard");

    const NowSettingsCallbacks actions = {
        .on_system_info = G_CALLBACK(record_action),
        .on_wizard = G_CALLBACK(record_action),
        .on_server_readiness = G_CALLBACK(record_action),
        .on_tail = G_CALLBACK(record_action),
        .on_pair_click = G_CALLBACK(record_action),
        .on_games_setup_from_settings = G_CALLBACK(record_action),
        .on_web_gaming_settings = G_CALLBACK(record_action),
        .on_web_gaming_admin = G_CALLBACK(record_action),
        .on_web_gaming_maintenance = G_CALLBACK(record_action),
        .on_export_preset = G_CALLBACK(record_action),
        .on_export_full_backup = G_CALLBACK(record_action),
        .on_restore_full_backup = G_CALLBACK(record_action),
        .on_discard = G_CALLBACK(record_action),
        .on_save = G_CALLBACK(record_action)
    };
    GtkWidget *tailscale_label = NULL;
    GtkWidget *root = now_settings_build(main_pages, window, &actions,
                                         preview, 207u, 255u, &tailscale_label);
    g_assert_nonnull(root);
    g_assert_true(gtk_stack_get_child_by_name(GTK_STACK(main_pages),
                                              "settings") == root);
    g_assert_nonnull(tailscale_label);
    g_assert_cmpstr(gtk_label_get_text(GTK_LABEL(tailscale_label)),
                    ==, "CHECKING TAILSCALE");
    NowSettingsForm *form =
        g_object_get_data(G_OBJECT(root), "now-settings-form");
    g_assert_nonnull(form);
    g_assert_true(form->root == root);
    g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(form->fields[0])),
                    ==, "198.51.100.8");
    g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(form->fields[1])),
                    ==, "owner");
    for (int i = 0; i < 8; ++i) {
        g_assert_nonnull(form->fields[i]);
        g_assert_nonnull(form->featured_checks[i]);
        g_assert_nonnull(form->tray_checks[i]);
    }
    NowSettingsDraft draft = {0};
    now_settings_collect(form, &draft);
    g_assert_cmpstr(draft.fields[0], ==, "198.51.100.8");
    g_assert_cmpstr(draft.fields[1], ==, "owner");
    g_assert_cmpstr(draft.startup_page, ==, "dashboard");
    for (int i = 0; i < 8; ++i) {
        g_assert_cmpint(draft.order[i], ==, i);
        g_assert_cmpuint(draft.tray_selected[i], ==, 1);
        g_assert_cmpuint(draft.featured_selected[i], ==, !!(207u & (1u << i)));
    }
    GtkWidget *pages = g_object_get_data(G_OBJECT(root),
                                         "now-settings-stack");
    g_assert_true(GTK_IS_STACK(pages));
    for (size_t i = 0; i < 4; ++i) {
        const char *name[] = {"home", "connection", "gaming",
                              "preferences"};
        g_assert_nonnull(gtk_stack_get_child_by_name(GTK_STACK(pages),
                                                      name[i]));
    }
    g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(pages)),
                    ==, "home");

    GtkWidget *gaming = button_named(root, "GAMING & STREAMING  ›");
    g_assert_nonnull(gaming);
    gtk_button_clicked(GTK_BUTTON(gaming));
    g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(pages)),
                    ==, "gaming");
    GtkWidget *back = button_named(gtk_stack_get_child_by_name(
        GTK_STACK(pages), "gaming"), "‹ BACK TO SETTINGS");
    g_assert_nonnull(back);
    gtk_button_clicked(GTK_BUTTON(back));
    g_assert_cmpstr(gtk_stack_get_visible_child_name(GTK_STACK(pages)),
                    ==, "home");

    GtkWidget *save = button_named(root, "SAVE SETTINGS");
    GtkWidget *cancel = button_named(root, "CANCEL");
    g_assert_nonnull(save);
    g_assert_nonnull(cancel);
    gtk_entry_set_text(GTK_ENTRY(form->fields[0]), "203.0.113.17");
    now_settings_collect(form, &draft);
    g_assert_cmpstr(draft.fields[0], ==, "203.0.113.17");
    g_assert_cmpstr(cfg[0], ==, "192.0.2.10");
    gtk_button_clicked(GTK_BUTTON(save));
    gtk_button_clicked(GTK_BUTTON(cancel));
    g_assert_cmpuint(action_calls, ==, 2);
    g_assert_cmpstr(cfg[0], ==, "192.0.2.10");

    gtk_widget_destroy(window);
    g_rmdir(home);
    g_free(home);
    g_print("GTK Settings extraction contract passed: page navigation, form, "
            "callbacks and no implicit save.\n");
    return 0;
}
