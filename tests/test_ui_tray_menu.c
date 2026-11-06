#include "tray_menu.h"
#include "tray_actions.h"
#include "tray_menu_lifetime.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { \
    if (!(expr)) { \
        fprintf(stderr, "tray-menu check failed at %d: %s\n", \
                __LINE__, #expr); \
        return 1; \
    } \
} while (0)

static int last_action = -1;
static int previous_calls = 0;
static int toggle_calls = 0;
static int next_calls = 0;
static int open_calls = 0;

static void action(GtkWidget *unused, gpointer data)
{
    (void)unused;
    last_action = GPOINTER_TO_INT(data);
}
static void previous(GtkWidget *unused, gpointer data)
{
    (void)unused;
    (void)data;
    ++previous_calls;
}
static void toggle(GtkWidget *unused, gpointer data)
{
    (void)unused;
    (void)data;
    ++toggle_calls;
}
static void next(GtkWidget *unused, gpointer data)
{
    (void)unused;
    (void)data;
    ++next_calls;
}

static void open_current(GtkWidget *unused, gpointer data)
{
    (void)unused;
    (void)data;
    ++open_calls;
}

/* Count actual finalization of production-built menus, rather than merely
 * calling destroy/unref and assuming the old references were released. */
static void menu_finalized(gpointer data, GObject *object)
{
    (void)object;
    ++*(unsigned *)data;
}

static GtkWidget *item_at(GtkWidget *menu, int index)
{
    GList *children = gtk_container_get_children(GTK_CONTAINER(menu));
    GtkWidget *item = g_list_nth_data(children, (guint)index);
    g_list_free(children);
    return item;
}

static int item_count(GtkWidget *menu)
{
    GList *children = gtk_container_get_children(GTK_CONTAINER(menu));
    int count = g_list_length(children);
    g_list_free(children);
    return count;
}

static int has_label(GtkWidget *menu, int index, const char *expected)
{
    GtkWidget *item = item_at(menu, index);
    return item && GTK_IS_MENU_ITEM(item) &&
           !GTK_IS_SEPARATOR_MENU_ITEM(item) &&
           !strcmp(gtk_menu_item_get_label(GTK_MENU_ITEM(item)), expected);
}

int main(int argc, char **argv)
{
    gtk_init(&argc, &argv);
    NowTrayMenuModel model = {0};
    for (int i = 0; i < NOW_TRAY_ACTIONS; ++i) {
        model.service_order[i] = i;
    }
    model.on_action = G_CALLBACK(action);
    model.on_music_open_current = G_CALLBACK(open_current);
    model.on_music_previous = G_CALLBACK(previous);
    model.on_music_toggle_pause = G_CALLBACK(toggle);
    model.on_music_next = G_CALLBACK(next);
    model.desktop_caption = "XFCE";

    CHECK(now_tray_menu_new(NULL) == NULL);

    /* Without configured service shortcuts, legacy utility actions remain. */
    GtkWidget *menu = now_tray_menu_new(&model);
    CHECK(menu != NULL);
    CHECK(item_count(menu) == 8);
    CHECK(has_label(menu, 0, "Open OptiPlex Now"));
    CHECK(has_label(menu, 2, "Restart streaming service…"));
    CHECK(has_label(menu, 4, "System Info"));
    CHECK(has_label(menu, 5, "Settings"));
    CHECK(has_label(menu, 7, "Quit"));
    g_signal_emit_by_name(item_at(menu, 5), "activate");
    CHECK(last_action == NOW_TRAY_OPEN_SETTINGS);
    now_tray_menu_owned_destroy(menu);

    /* Reorder only selected service IDs; transient playback never changes
     * those persisted action numbers. */
    model.service_mask = (1u << 2) | (1u << 4);
    model.service_order[0] = 4;
    model.service_order[1] = 2;
    model.service_order[2] = 0;
    model.service_order[3] = 1;
    model.service_order[4] = 3;
    model.music_session = TRUE;
    model.music_paused = TRUE;
    model.music_can_next = FALSE;
    model.music_caption =
        "An intentionally long music track caption that must be truncated in the tray";
    menu = now_tray_menu_new(&model);
    CHECK(menu != NULL);
    CHECK(item_count(menu) == 16);
    CHECK(has_label(menu, 2, "Downloads — VueTorrent"));
    CHECK(has_label(menu, 3, "Music — Dropped Needle"));
    CHECK(has_label(menu, 14, "▶  Play"));
    CHECK(has_label(menu, 15, "⏭  Next"));
    CHECK(gtk_widget_get_sensitive(item_at(menu, 12)));
    gchar *tooltip = gtk_widget_get_tooltip_text(item_at(menu, 12));
    CHECK(tooltip != NULL && !strcmp(tooltip, model.music_caption));
    g_free(tooltip);
    g_signal_emit_by_name(item_at(menu, 12), "activate");
    CHECK(open_calls == 1);
    CHECK(!gtk_widget_get_sensitive(item_at(menu, 15)));
    CHECK(g_utf8_strlen(gtk_menu_item_get_label(
          GTK_MENU_ITEM(item_at(menu, 12))), -1) <= 46);
    g_signal_emit_by_name(item_at(menu, 2), "activate");
    CHECK(last_action == 4);
    g_signal_emit_by_name(item_at(menu, 3), "activate");
    CHECK(last_action == 2);
    g_signal_emit_by_name(item_at(menu, 13), "activate");
    g_signal_emit_by_name(item_at(menu, 14), "activate");
    CHECK(previous_calls == 1);
    CHECK(toggle_calls == 1);
    CHECK(next_calls == 0);
    now_tray_menu_owned_destroy(menu);

    /* A playable session preserves the same controls with proper labels. */
    model.music_paused = FALSE;
    model.music_can_next = TRUE;
    model.music_caption = "Song";
    menu = now_tray_menu_new(&model);
    CHECK(has_label(menu, 12, "Song"));
    CHECK(has_label(menu, 14, "⏸  Pause"));
    CHECK(gtk_widget_get_sensitive(item_at(menu, 15)));
    g_signal_emit_by_name(item_at(menu, 15), "activate");
    CHECK(next_calls == 1);
    g_signal_emit_by_name(item_at(menu, 12), "activate");
    CHECK(open_calls == 2);

    /* Model AppIndicator releasing its old reference before the app invokes
     * its final widget destruction, repeated across music state changes.
     * Every old production menu must actually finalize after the app lets go. */
    unsigned finalized = 0;
    g_object_weak_ref(G_OBJECT(menu), menu_finalized, &finalized);
    for (int i = 0; i < 40; ++i) {
        GtkWidget *replacement = now_tray_menu_new(&model);
        CHECK(replacement != NULL);
        CHECK(!g_object_is_floating(G_OBJECT(replacement)));
        g_object_weak_ref(G_OBJECT(replacement), menu_finalized, &finalized);
        g_object_ref(menu);
        g_object_unref(menu);
        now_tray_menu_owned_destroy(menu);
        CHECK(finalized == (unsigned)i + 1);
        menu = replacement;
    }
    now_tray_menu_owned_destroy(menu);
    CHECK(finalized == 41);

    /* Multibyte Japanese titles truncate by Unicode code point, never a
     * byte offset, and preserve full text for the clickable tooltip. */
    GString *japanese = g_string_new("");
    for (int i = 0; i < 48; ++i)
        g_string_append(japanese, "あ");
    model.music_caption = japanese->str;
    menu = now_tray_menu_new(&model);
    GtkWidget *title = item_at(menu, 12);
    CHECK(title != NULL && gtk_widget_get_sensitive(title));
    const gchar *label = gtk_menu_item_get_label(GTK_MENU_ITEM(title));
    CHECK(g_utf8_validate(label, -1, NULL));
    CHECK(g_utf8_strlen(label, -1) == 46);
    CHECK(g_str_has_suffix(label, "…"));
    tooltip = gtk_widget_get_tooltip_text(title);
    CHECK(tooltip != NULL && g_strcmp0(tooltip, japanese->str) == 0);
    g_free(tooltip);
    g_signal_emit_by_name(title, "activate");
    CHECK(open_calls == 3);
    now_tray_menu_owned_destroy(menu);
    g_string_free(japanese, TRUE);

    puts("Tray menu: services, order, dispatch, transient playback passed.");
    return 0;
}
