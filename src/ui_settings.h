#ifndef NOW_UI_SETTINGS_H
#define NOW_UI_SETTINGS_H

#include <gtk/gtk.h>
#include "config.h"

/* GTK presentation only. Callers own configuration commits, owner SSH,
 * backup/restore, installer launches and other privileged operations.
 * This struct intentionally mirrors the existing per-page callback contexts;
 * pointers are valid only for the lifetime of the returned root widget.
 */
typedef struct {
    GtkWidget *inputs[8];
    int relay;
    GtkWidget *parent;
} PairContext;

typedef struct {
    GtkWidget *parent, *fields[8], *disk;
} PresetExportContext;

typedef struct {
    GtkWidget *fields[8], *diskentry, *combo, *featured_checks[8], *tray_checks[8];
    GtkWidget *order_list, *web_url_entry, *desktop_caption_entry;
    GtkWidget *startup_choice, *login_tray_toggle, *root;
    PairContext server_context, relay_context;
    PresetExportContext export_context;
} NowSettingsForm;

typedef struct {
    GCallback on_system_info;
    GCallback on_wizard;
    GCallback on_server_readiness;
    GCallback on_tail;
    GCallback on_pair_click;
    GCallback on_games_setup_from_settings;
    GCallback on_web_gaming_settings;
    GCallback on_web_gaming_admin;
    GCallback on_web_gaming_maintenance;
    GCallback on_export_preset;
    GCallback on_export_full_backup;
    GCallback on_restore_full_backup;
    GCallback on_discard;
    GCallback on_save;
} NowSettingsCallbacks;

/* Builds and displays the existing Settings page using the app's callbacks.
 * All widget/form ownership is attached to the returned GTK root; no
 * independently owned global form state and no host operations here.
 * values are a borrowed, read-only snapshot of the current config values;
 * masks are already-validated legacy config preferences supplied by app.
 * tailscale_label_out is a borrowed widget pointer; clear on page removal.
 */
GtkWidget *now_settings_build(GtkWidget *main_pages, GtkWidget *parent,
                              const NowSettingsCallbacks *callbacks,
                              const char values[CONFIG_COUNT][CONFIG_VALUE_SIZE],
                              unsigned featured_mask, unsigned tray_mask,
                              GtkWidget **tailscale_label_out);

#endif
