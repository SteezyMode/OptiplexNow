#ifndef NOW_UI_WIZARD_H
#define NOW_UI_WIZARD_H

#include <gtk/gtk.h>
#include "config.h"

/* Borrowed GTK widgets. The assistant owns their lifetime; the caller
 * retains the view only while the assistant is alive. No network or owner
 * authority, file writes, or lifecycle timers are managed by this module. */
typedef struct {
    GtkWidget *assistant, *server_page, *games_page, *finish_page;
    GtkWidget *host, *user;
    GtkWidget *ts_state, *game_state, *wolf_state, *notice, *preset_notice;
    GtkWidget *find_button, *tailscale_button;
} NowWizardView;

/* Build the exact four-page first-run assistant. The caller handles
 * prepare, cancel, apply, destroy, state checks and user action callbacks.
 * 'values' and 'moonlight_status' are read-only, borrowed inputs.
 * Existing-connection button is shown only for a previously saved device.
 * All output widgets are owned by the returned GtkAssistant.
 */
GtkWidget *now_wizard_view_build(
    NowWizardView *view, GtkWindow *parent,
    const char values[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    gboolean has_existing_setup, const char *moonlight_status,
    GCallback on_action, GCallback on_validate, gpointer context);

/* Queue window destruction safely across nested GTK callbacks. The idle
 * source retains its own GtkWidget reference until it runs or is removed,
 * so another close path cannot leave the callback with a dangling pointer.
 * Does not save settings or alter owner/network state. */
void now_wizard_view_defer_destroy(GtkWidget *assistant);

#endif
