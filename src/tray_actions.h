#ifndef OPTIPLEX_NOW_TRAY_ACTIONS_H
#define OPTIPLEX_NOW_TRAY_ACTIONS_H

#include "tray_prefs.h"

/* Stable IDs used by both the GTK status-icon menu and AppIndicator menu. */
enum {
    NOW_TRAY_OPEN_WINDOW = 10,
    NOW_TRAY_OPEN_SETTINGS = 11,
    NOW_TRAY_OPEN_SYSTEM_INFO = 12,
    NOW_TRAY_QUIT = 13,
    NOW_TRAY_RESTART_STREAMING = 14
};

/* UI and application actions are implemented by the caller. No GTK objects
 * or global application state are accessed by the dispatcher.
 */
typedef struct {
    void (*show_window)(void *context);
    void (*open_settings)(void *context);
    void (*open_system_info)(void *context);
    void (*quit)(void *context);
    void (*restart_streaming)(void *context);
    void (*launch_service)(void *context, int index);
    int (*moonlight_available)(void *context);
} NowTrayActions;

/* Returns 1 if dispatched. Invalid IDs and missing required handlers do
 * nothing and return 0. Games opens NOW first if Moonlight is unavailable.
 */
int now_tray_dispatch_action(int action, const NowTrayActions *handlers,
                             void *context);

#endif
