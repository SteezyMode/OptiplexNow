/* Disposable Xvfb smoke for the extracted four-page wizard presentation.
 * Never runs discovery, Tailscale, Moonlight, SSH, Wolf or host operations.
 */
#include "ui_wizard.h"
#include <glib.h>
#include <string.h>

typedef struct {
    NowWizardView view;
    guint actions;
    char last_action[64];
    guint validations;
} Fixture;

static void on_action(GtkWidget *widget, gpointer opaque)
{
    Fixture *fixture = opaque;
    fixture->actions++;
    g_strlcpy(fixture->last_action, gtk_widget_get_name(widget),
              sizeof fixture->last_action);
}

static void on_validate(GtkWidget *widget, gpointer opaque)
{
    (void)widget;
    Fixture *fixture = opaque;
    fixture->validations++;
    const char *host = gtk_entry_get_text(GTK_ENTRY(fixture->view.host));
    const char *user = gtk_entry_get_text(GTK_ENTRY(fixture->view.user));
    gtk_assistant_set_page_complete(GTK_ASSISTANT(fixture->view.assistant),
                                    fixture->view.server_page,
                                    *host && *user);
}

static GtkWidget *find_name(GtkWidget *parent, const char *name)
{
    if (g_strcmp0(gtk_widget_get_name(parent), name) == 0)
        return parent;
    if (!GTK_IS_CONTAINER(parent))
        return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(parent));
    GtkWidget *result = NULL;
    for (GList *node = children; node && !result; node = node->next)
        result = find_name(GTK_WIDGET(node->data), name);
    g_list_free(children);
    return result;
}

static void check_assistant(gboolean existing_setup)
{
    char values[CONFIG_COUNT][CONFIG_VALUE_SIZE] = {{0}};
    g_strlcpy(values[0], "100.64.9.5", CONFIG_VALUE_SIZE);
    g_strlcpy(values[1], "owner", CONFIG_VALUE_SIZE);
    char original[sizeof values];
    memcpy(original, values, sizeof values);

    Fixture fixture = {0};
    GtkWidget *parent = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GtkWidget *wizard = now_wizard_view_build(
        &fixture.view, GTK_WINDOW(parent), values,
        existing_setup, "NATIVE MOONLIGHT READY",
        G_CALLBACK(on_action), G_CALLBACK(on_validate), &fixture);
    g_assert_true(GTK_IS_ASSISTANT(wizard));
    g_assert_true(fixture.view.assistant == wizard);
    g_assert_true(gtk_window_get_transient_for(GTK_WINDOW(wizard)) ==
                  GTK_WINDOW(parent));
    g_assert_true(gtk_window_get_modal(GTK_WINDOW(wizard)));
    g_assert_cmpint(gtk_assistant_get_n_pages(GTK_ASSISTANT(wizard)), ==, 4);
    const char *titles[] = {
        "NOW Setup: Tailscale", "NOW Setup: Server",
        "NOW Setup: Games", "NOW Setup: Finish"
    };
    const GtkAssistantPageType types[] = {
        GTK_ASSISTANT_PAGE_INTRO, GTK_ASSISTANT_PAGE_CONTENT,
        GTK_ASSISTANT_PAGE_CONTENT, GTK_ASSISTANT_PAGE_CONFIRM
    };
    for (int i = 0; i < 4; ++i) {
        GtkWidget *page = gtk_assistant_get_nth_page(GTK_ASSISTANT(wizard), i);
        g_assert_nonnull(page);
        g_assert_cmpstr(gtk_assistant_get_page_title(GTK_ASSISTANT(wizard),
                                                    page), ==, titles[i]);
        g_assert_cmpint(gtk_assistant_get_page_type(GTK_ASSISTANT(wizard),
                                                    page), ==, types[i]);
    }
    g_assert_true(fixture.view.server_page ==
                  gtk_assistant_get_nth_page(GTK_ASSISTANT(wizard), 1));
    g_assert_true(fixture.view.games_page ==
                  gtk_assistant_get_nth_page(GTK_ASSISTANT(wizard), 2));
    g_assert_true(fixture.view.finish_page ==
                  gtk_assistant_get_nth_page(GTK_ASSISTANT(wizard), 3));
    g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(fixture.view.host)),
                    ==, "100.64.9.5");
    g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(fixture.view.user)),
                    ==, "owner");
    g_assert_cmpstr(gtk_label_get_text(GTK_LABEL(fixture.view.game_state)),
                    ==, "NATIVE MOONLIGHT READY");

    g_assert_nonnull(find_name(wizard, "w_find"));
    g_assert_nonnull(find_name(wizard, "w_moonlight"));
    g_assert_nonnull(find_name(wizard, "w_wolf"));
    g_assert_nonnull(find_name(wizard, "w_owner_approve"));
    g_assert_nonnull(find_name(wizard, "w_import"));
    g_assert_nonnull(find_name(wizard, "w_restore"));
    g_assert_true((find_name(wizard, "w_keep") != NULL) == existing_setup);
    g_assert_null(find_name(wizard, "w_pair"));
    g_assert_null(find_name(wizard, "w_relay"));

    g_assert_cmpuint(fixture.actions, ==, 0);
    gtk_button_clicked(GTK_BUTTON(find_name(wizard, "w_find")));
    g_assert_cmpstr(fixture.last_action, ==, "w_find");
    gtk_button_clicked(GTK_BUTTON(find_name(wizard, "w_owner_approve")));
    g_assert_cmpstr(fixture.last_action, ==, "w_owner_approve");
    g_assert_cmpuint(fixture.actions, ==, 2);

    gtk_entry_set_text(GTK_ENTRY(fixture.view.host), "");
    g_assert_cmpuint(fixture.validations, >, 0);
    g_assert_false(gtk_assistant_get_page_complete(GTK_ASSISTANT(wizard),
                                                    fixture.view.server_page));
    gtk_entry_set_text(GTK_ENTRY(fixture.view.host), "100.64.9.6");
    g_assert_true(gtk_assistant_get_page_complete(GTK_ASSISTANT(wizard),
                                                   fixture.view.server_page));
    g_assert_cmpmem(values, sizeof values, original, sizeof original);

    gtk_widget_destroy(wizard);
    gtk_widget_destroy(parent);
}

/* An idle scheduled by Save/Cancel must never dereference a widget
 * already destroyed by another GTK close path. Assert both close orders. */
static void destroy_count(GtkWidget *widget, gpointer opaque)
{
    (void)widget;
    ++*(guint *)opaque;
}

static void drain_idle(void)
{
    while (g_main_context_pending(NULL))
        g_main_context_iteration(NULL, FALSE);
}

static void test_deferred_destroy(void)
{
    guint destroyed = 0;
    GtkWidget *first = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    g_object_ref_sink(first);
    g_signal_connect(first, "destroy", G_CALLBACK(destroy_count), &destroyed);
    now_wizard_view_defer_destroy(first);
    /* A different close path destroys it before our pending idle runs. */
    gtk_widget_destroy(first);
    g_assert_cmpuint(destroyed, ==, 1);
    drain_idle();
    g_assert_cmpuint(destroyed, ==, 1);
    g_object_unref(first);

    GtkWidget *second = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    g_object_ref_sink(second);
    g_signal_connect(second, "destroy", G_CALLBACK(destroy_count), &destroyed);
    now_wizard_view_defer_destroy(second);
    drain_idle();
    g_assert_cmpuint(destroyed, ==, 2);
    g_object_unref(second);
}

int main(int argc, char **argv)
{
    gtk_init(&argc, &argv);
    check_assistant(FALSE);
    check_assistant(TRUE);
    test_deferred_destroy();
    g_print("GTK wizard pages: four-page structure, callbacks and no side effects passed.\n");
    return 0;
}
