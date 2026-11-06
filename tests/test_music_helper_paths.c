#include "music_helper_paths.h"

#include <glib.h>

static void assert_path(NowMusicHelperKind kind, const char *exe,
                        gboolean has_checkout, const char *expected)
{
    char *path = now_music_helper_path_for_executable(
        kind, exe, has_checkout);
    g_assert_nonnull(path);
    g_assert_cmpstr(path, ==, expected);
    g_free(path);
}

static void test_installed_binaries_never_run_checkout_helpers(void)
{
    for (int local = 0; local <= 1; local++) {
        assert_path(NOW_MUSIC_HELPER_PLAYER, "/usr/bin/optiplex-now",
                    local, "/usr/lib/optiplex-now/music_player.py");
        assert_path(NOW_MUSIC_HELPER_SUBSONIC, "/usr/bin/optiplex-now",
                    local, "/usr/lib/optiplex-now/music_subsonic.py");
        assert_path(NOW_MUSIC_HELPER_PLAYER, "/usr/bin/something-else",
                    local, "/usr/lib/optiplex-now/music_player.py");
    }
}

static void test_developer_checkout_and_fallback(void)
{
    assert_path(NOW_MUSIC_HELPER_PLAYER, "/tmp/build/optiplex-desk",
                TRUE, "src/music_player.py");
    assert_path(NOW_MUSIC_HELPER_SUBSONIC, "/home/user/test/optiplex-desk",
                TRUE, "src/music_subsonic.py");
    assert_path(NOW_MUSIC_HELPER_PLAYER, NULL,
                TRUE, "src/music_player.py");
    assert_path(NOW_MUSIC_HELPER_SUBSONIC, NULL,
                FALSE, "/usr/lib/optiplex-now/music_subsonic.py");
    assert_path(NOW_MUSIC_HELPER_PLAYER, "/tmp/optiplex-desk",
                FALSE, "/usr/lib/optiplex-now/music_player.py");
}

static void test_invalid_helper_type_is_rejected(void)
{
    g_assert_null(now_music_helper_path_for_executable(
        (NowMusicHelperKind)0, "/usr/bin/optiplex-now", TRUE));
    g_assert_null(now_music_helper_path_for_executable(
        (NowMusicHelperKind)99, "/tmp/optiplex-desk", TRUE));
    g_assert_null(now_music_helper_path((NowMusicHelperKind)99));
}

static void test_current_checkout_uses_explicit_builtin_only(void)
{
    char *player = now_music_helper_path(NOW_MUSIC_HELPER_PLAYER);
    char *subsonic = now_music_helper_path(NOW_MUSIC_HELPER_SUBSONIC);
    g_assert_nonnull(player);
    g_assert_nonnull(subsonic);
    g_assert_true(g_str_has_suffix(player, "/music_player.py"));
    g_assert_true(g_str_has_suffix(subsonic, "/music_subsonic.py"));
    g_assert_false(g_strstr_len(player, -1, "../") != NULL);
    g_assert_false(g_strstr_len(subsonic, -1, "../") != NULL);
    g_free(player);
    g_free(subsonic);
}

int main(int argc, char **argv)
{
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/music/helper/installed", test_installed_binaries_never_run_checkout_helpers);
    g_test_add_func("/music/helper/checkout", test_developer_checkout_and_fallback);
    g_test_add_func("/music/helper/invalid", test_invalid_helper_type_is_rejected);
    g_test_add_func("/music/helper/real-checkout", test_current_checkout_uses_explicit_builtin_only);
    return g_test_run();
}
