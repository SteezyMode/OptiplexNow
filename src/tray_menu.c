#include "tray_menu.h"
#include "tray_actions.h"
#include "tray_menu_lifetime.h"

static void append_separator(GtkWidget *menu)
{
    GtkWidget *item = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
}

static void append_action(GtkWidget *menu, const char *caption, int action,
                          GCallback handler)
{
    GtkWidget *item = gtk_menu_item_new_with_label(caption);
    if (handler) {
        g_signal_connect_data(item, "activate", handler,
                              GINT_TO_POINTER(action), NULL, 0);
    }
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
}

static GtkWidget *append_music_action(GtkWidget *menu, const char *caption,
                                gboolean enabled, GCallback handler)
{
    GtkWidget *item = gtk_menu_item_new_with_label(caption);
    gtk_widget_set_sensitive(item, enabled);
    if (handler) {
        g_signal_connect_data(item, "activate", handler, NULL, NULL, 0);
    }
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
    return item;
}

GtkWidget *now_tray_menu_new(const NowTrayMenuModel *model)
{
    if (!model) {
        return NULL;
    }

    /* Strong app-owned root ref survives synchronous AppIndicator menu swaps. */
    GtkWidget *menu = now_tray_menu_owned_new();
    append_action(menu, "Open OptiPlex Now", NOW_TRAY_OPEN_WINDOW,
                  model->on_action);

    unsigned mask = model->service_mask & NOW_TRAY_DEFAULT_MASK;
    if (mask) {
        append_separator(menu);
        for (int position = 0; position < NOW_TRAY_ACTIONS; ++position) {
            int action = model->service_order[position];
            if (action < 0 || action >= NOW_TRAY_ACTIONS ||
                !(mask & (1u << action))) {
                continue;
            }
            char caption[256];
            if (!now_tray_service_caption(action, model->desktop_caption,
                                          caption, sizeof caption)) {
                continue;
            }
            append_action(menu, caption, action, model->on_action);
        }
    }

    append_separator(menu);
    append_action(menu, "Restart streaming service…",
                  NOW_TRAY_RESTART_STREAMING, model->on_action);
    append_separator(menu);
    append_action(menu, "System Info", NOW_TRAY_OPEN_SYSTEM_INFO,
                  model->on_action);
    append_action(menu, "Settings", NOW_TRAY_OPEN_SETTINGS, model->on_action);
    append_separator(menu);
    append_action(menu, "Quit", NOW_TRAY_QUIT, model->on_action);

    /* This is a transient, client-local section. Persisted service IDs,
     * ordering and visibility remain completely separate. */
    if (model->music_session) {
        append_separator(menu);
        const char *caption = model->music_caption ? model->music_caption : "";
        char *short_title;
        if (g_utf8_strlen(caption, -1) > 46) {
            /* The prefix is separately allocated; release it on every
             * playback-driven menu rebuild instead of leaking each title. */
            char *prefix = g_utf8_substring(caption, 0, 45);
            short_title = g_strconcat(prefix, "…", NULL);
            g_free(prefix);
        } else {
            short_title = g_strdup(caption);
        }
        GtkWidget *playing = append_music_action(menu, short_title, TRUE,
                                                  model->on_music_open_current);
        gtk_widget_set_tooltip_text(playing, caption);
        g_free(short_title);
        append_music_action(menu, "⏮  Previous", TRUE,
                            model->on_music_previous);
        append_music_action(menu, model->music_paused ? "▶  Play" : "⏸  Pause",
                            TRUE, model->on_music_toggle_pause);
        append_music_action(menu, "⏭  Next", model->music_can_next,
                            model->on_music_next);
    }

    gtk_widget_show_all(menu);
    return menu;
}
