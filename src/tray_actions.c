#include "tray_actions.h"

int now_tray_dispatch_action(int action, const NowTrayActions *handlers,
                             void *context)
{
    if (!handlers) {
        return 0;
    }

    if (action >= 0 && action < NOW_TRAY_ACTIONS) {
        if (!handlers->launch_service) {
            return 0;
        }
        if (action == 0) {
            /* Existing Games behavior: show the app when Moonlight is missing,
             * then let the normal service handler explain/install it.
             */
            if (!handlers->show_window || !handlers->moonlight_available) {
                return 0;
            }
            if (!handlers->moonlight_available(context)) {
                handlers->show_window(context);
            }
        } else if (action == 4) {
            /* Downloads is an embedded GTK stack page, unlike external
             * services. Restore the window before switching the stack.
             * Keep this rule in the tray dispatcher, not the UI monolith. */
            if (!handlers->show_window) {
                return 0;
            }
            handlers->show_window(context);
        }
        handlers->launch_service(context, action);
        return 1;
    }

    switch (action) {
    case NOW_TRAY_OPEN_WINDOW:
        if (!handlers->show_window) {
            return 0;
        }
        handlers->show_window(context);
        return 1;

    case NOW_TRAY_OPEN_SETTINGS:
        if (!handlers->show_window || !handlers->open_settings) {
            return 0;
        }
        handlers->show_window(context);
        handlers->open_settings(context);
        return 1;

    case NOW_TRAY_OPEN_SYSTEM_INFO:
        if (!handlers->show_window || !handlers->open_system_info) {
            return 0;
        }
        handlers->show_window(context);
        handlers->open_system_info(context);
        return 1;

    case NOW_TRAY_QUIT:
        if (!handlers->quit) {
            return 0;
        }
        handlers->quit(context);
        return 1;

    case NOW_TRAY_RESTART_STREAMING:
        if (!handlers->restart_streaming) {
            return 0;
        }
        handlers->restart_streaming(context);
        return 1;

    default:
        return 0;
    }
}
