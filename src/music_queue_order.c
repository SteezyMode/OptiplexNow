#include "music_queue_order.h"

/* Selected song first, then remaining songs in a Fisher-Yates permutation
 * that deliberately never moves slot zero. Match the v1.22.1 algorithm,
 * including the invalid-start early return and cursor semantics. */
void now_music_queue_order_reset(GArray **order, guint length, int start,
                                 gboolean shuffle, guint *cursor)
{
    if (!*order)
        *order = g_array_new(FALSE, FALSE, sizeof(guint));
    g_array_set_size(*order, 0);
    if (start < 0 || start >= (int)length)
        return;
    guint first = (guint)start;
    g_array_append_val(*order, first);
    for (guint i = 0; i < length; i++) {
        if (i != first)
            g_array_append_val(*order, i);
    }
    if (shuffle) {
        for (guint i = (*order)->len; i > 2; i--) {
            guint pick = g_random_int_range(1, i);
            guint tmp = g_array_index(*order, guint, i - 1);
            g_array_index(*order, guint, i - 1) =
                g_array_index(*order, guint, pick);
            g_array_index(*order, guint, pick) = tmp;
        }
    }
    *cursor = 0;
}

int now_music_queue_order_next(guint length, int index, gboolean shuffle,
                               const GArray *order, guint cursor)
{
    if (index < 0)
        return -1;
    if (shuffle) {
        if (!order || cursor + 1 >= order->len)
            return -1;
        return (int)g_array_index(order, guint, cursor + 1);
    }
    return index + 1 < (int)length ? index + 1 : -1;
}

int now_music_queue_order_previous(int index, gboolean shuffle,
                                   const GArray *order, guint cursor)
{
    if (index < 0)
        return -1;
    if (shuffle && order && cursor > 0)
        return (int)g_array_index(order, guint, cursor - 1);
    return MAX(0, index - 1);
}
