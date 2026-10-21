#ifndef OPTIPLEX_NOW_TRAY_PREFS_H
#define OPTIPLEX_NOW_TRAY_PREFS_H

#include <stddef.h>

#define NOW_TRAY_ACTIONS 8
#define NOW_TRAY_DEFAULT_MASK 255u

/* Independent from the featured action mask and persisted config indices. */
unsigned now_tray_parse_mask(const char *value);

/* A malformed saved order fails closed to the original 0..7 order. */
int now_tray_parse_order(const char *text, int order[NOW_TRAY_ACTIONS]);
void now_tray_order_load(int order[NOW_TRAY_ACTIONS]);
int now_tray_order_save(const int order[NOW_TRAY_ACTIONS]);

/* Preserve the legacy ~/.config/optiplex-desk/desktop-label file location. */
void now_tray_desktop_caption(char *out, size_t capacity);
int now_tray_desktop_caption_save(const char *value);

/* Service metadata is independent of GTK and the menu backend. */
const char *now_tray_service_name(int index);
int now_tray_service_caption(int index, const char *desktop, char *out,
                             size_t capacity);

#endif
