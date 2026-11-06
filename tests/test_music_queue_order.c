#include "music_queue_order.h"

#include <glib.h>

/* Mirror the frozen v1.22.1 algorithm only in this offline regression, so
 * a future "simplification" cannot change the selected-first permutation. */
static GArray *legacy_order(guint length, int start, gboolean shuffled)
{
    GArray *order = g_array_new(FALSE, FALSE, sizeof(guint));
    if (start < 0 || start >= (int)length)
        return order;
    guint first = (guint)start;
    g_array_append_val(order, first);
    for (guint i = 0; i < length; i++) {
        if (i != first)
            g_array_append_val(order, i);
    }
    if (shuffled) {
        for (guint i = order->len; i > 2; i--) {
            guint pick = g_random_int_range(1, i);
            guint tmp = g_array_index(order, guint, i - 1);
            g_array_index(order, guint, i - 1) =
                g_array_index(order, guint, pick);
            g_array_index(order, guint, pick) = tmp;
        }
    }
    return order;
}

static void compare_order(const GArray *a, const GArray *b)
{
    g_assert_nonnull(a);
    g_assert_nonnull(b);
    g_assert_cmpuint(a->len, ==, b->len);
    for (guint i = 0; i < a->len; i++)
        g_assert_cmpuint(g_array_index(a, guint, i), ==,
                         g_array_index(b, guint, i));
}

static void test_sequential_selection(void)
{
    GArray *order = NULL;
    guint cursor = 10;
    now_music_queue_order_reset(&order, 4, 2, FALSE, &cursor);
    const guint expected[] = {2, 0, 1, 3};
    g_assert_cmpuint(cursor, ==, 0);
    g_assert_cmpuint(order->len, ==, G_N_ELEMENTS(expected));
    for (guint i = 0; i < order->len; i++)
        g_assert_cmpuint(g_array_index(order, guint, i), ==, expected[i]);

    /* Sequential playback follows queue index, not the rotated order array. */
    g_assert_cmpint(now_music_queue_order_next(4, 2, FALSE, order, 0), ==, 3);
    g_assert_cmpint(now_music_queue_order_next(4, 3, FALSE, order, 0), ==, -1);
    g_assert_cmpint(now_music_queue_order_previous(2, FALSE, order, 0), ==, 1);
    g_assert_cmpint(now_music_queue_order_previous(0, FALSE, order, 0), ==, 0);
    g_assert_cmpint(now_music_queue_order_previous(-1, FALSE, order, 0), ==, -1);
    g_assert_cmpint(now_music_queue_order_next(4, -1, FALSE, order, 0), ==, -1);
    g_array_unref(order);
}

static void test_shuffle_matches_original_seeded_permutation(void)
{
    for (guint length = 1; length <= 48; length++) {
        for (guint start = 0; start < length; start++) {
            guint seed = length * 1301u + start * 13u + 9u;
            g_random_set_seed(seed);
            GArray *expected = legacy_order(length, (int)start, TRUE);
            g_random_set_seed(seed);
            GArray *order = NULL;
            guint cursor = 99;
            now_music_queue_order_reset(&order, length, (int)start,
                                        TRUE, &cursor);
            compare_order(expected, order);
            g_assert_cmpuint(cursor, ==, 0);
            g_assert_cmpuint(g_array_index(order, guint, 0), ==, start);
            gboolean seen[48] = {FALSE};
            for (guint i = 0; i < order->len; i++) {
                guint value = g_array_index(order, guint, i);
                g_assert_cmpuint(value, <, length);
                g_assert_false(seen[value]);
                seen[value] = TRUE;
                int next = now_music_queue_order_next(length, (int)value,
                                                       TRUE, order, i);
                g_assert_cmpint(next, ==, i + 1 < length ?
                         (int)g_array_index(order, guint, i + 1) : -1);
                if (i > 0) {
                    g_assert_cmpint(
                        now_music_queue_order_previous((int)value, TRUE, order, i),
                        ==, (int)g_array_index(order, guint, i - 1));
                }
            }
            g_array_unref(expected);
            g_array_unref(order);
        }
    }
}

static void test_invalid_and_edge_cases(void)
{
    GArray *order = NULL;
    guint cursor = 22;
    now_music_queue_order_reset(&order, 0, 0, TRUE, &cursor);
    g_assert_nonnull(order);
    g_assert_cmpuint(order->len, ==, 0);
    g_assert_cmpuint(cursor, ==, 22); /* Historical invalid-start semantics. */

    now_music_queue_order_reset(&order, 3, 1, TRUE, &cursor);
    g_assert_cmpuint(order->len, ==, 3);
    now_music_queue_order_reset(&order, 3, -1, TRUE, &cursor);
    g_assert_cmpuint(order->len, ==, 0);
    g_assert_cmpuint(cursor, ==, 0); /* Existing cursor left unchanged. */
    cursor = 17;
    now_music_queue_order_reset(&order, 3, 3, TRUE, &cursor);
    g_assert_cmpuint(order->len, ==, 0);
    g_assert_cmpuint(cursor, ==, 17);

    g_assert_cmpint(now_music_queue_order_next(0, 0, TRUE, NULL, 0), ==, -1);
    g_assert_cmpint(now_music_queue_order_next(4, 0, TRUE, NULL, 0), ==, -1);
    g_assert_cmpint(now_music_queue_order_previous(0, TRUE, NULL, 0), ==, 0);
    g_assert_cmpint(now_music_queue_order_previous(4, TRUE, NULL, 0), ==, 3);
    g_assert_cmpint(now_music_queue_order_previous(-1, TRUE, order, 3), ==, -1);
    g_array_unref(order);
}

int main(int argc, char **argv)
{
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/music/queue/sequential", test_sequential_selection);
    g_test_add_func("/music/queue/shuffle-baseline", test_shuffle_matches_original_seeded_permutation);
    g_test_add_func("/music/queue/invalid-and-edge", test_invalid_and_edge_cases);
    return g_test_run();
}
