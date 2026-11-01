#ifndef NOW_UI_STATE_H
#define NOW_UI_STATE_H
#include <glib.h>

/* Local-only presentation choices, deliberately separate from server .onp. */
void now_ui_state_load(void);
void now_ui_state_window_size(int *width, int *height);
void now_ui_state_remember_size(int width, int height);
const char *now_ui_state_start_page(void);
void now_ui_state_set_start_page(const char *name);
/* Optional per-device host management: disabled on all fresh installs. */
gboolean now_ui_state_gpu_power_enabled(void);
void now_ui_state_set_gpu_power_enabled(gboolean enabled);
gboolean now_ui_state_save(void);
#endif
