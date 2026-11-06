#ifndef OPTIPLEX_NOW_MUSIC_QUEUE_ORDER_H
#define OPTIPLEX_NOW_MUSIC_QUEUE_ORDER_H

#include <glib.h>

/* Pure queue-index ordering, independent of GTK, playback, host and secrets.
 * The caller owns *order (a GArray of guint) and the cursor; the reset helper
 * preserves the historical first-selected-song / remaining permutation. */
void now_music_queue_order_reset(GArray **order, guint length, int start,
                                 gboolean shuffle, guint *cursor);

int now_music_queue_order_next(guint length, int index, gboolean shuffle,
                               const GArray *order, guint cursor);

int now_music_queue_order_previous(int index, gboolean shuffle,
                                   const GArray *order, guint cursor);

#endif
