#include "music_helper_paths.h"

/* Two previously identical native Music helper path policies are maintained
 * here. This enum is an authorization boundary against arbitrary filenames. */
static const char *music_helper_basename(NowMusicHelperKind kind)
{
    switch (kind) {
    case NOW_MUSIC_HELPER_PLAYER:
        return "music_player.py";
    case NOW_MUSIC_HELPER_SUBSONIC:
        return "music_subsonic.py";
    default:
        return NULL;
    }
}

char *now_music_helper_path_for_executable(NowMusicHelperKind kind,
                                           const char *executable,
                                           gboolean checkout_has_helper)
{
    const char *filename = music_helper_basename(kind);
    if (!filename)
        return NULL;
    /* An installed binary must never execute a checkout's local helper. */
    if ((!executable || !g_str_has_prefix(executable, "/usr/bin/")) &&
        checkout_has_helper)
        return g_build_filename("src", filename, NULL);
    return g_build_filename("/usr/lib/optiplex-now", filename, NULL);
}

char *now_music_helper_path(NowMusicHelperKind kind)
{
    const char *filename = music_helper_basename(kind);
    if (!filename)
        return NULL;
    char *exe = g_file_read_link("/proc/self/exe", NULL);
    /* In installed mode we intentionally skip the developer file lookup. */
    gboolean installed = exe && g_str_has_prefix(exe, "/usr/bin/");
    gboolean local_exists = FALSE;
    if (!installed) {
        char *local = g_build_filename("src", filename, NULL);
        local_exists = g_file_test(local, G_FILE_TEST_IS_REGULAR);
        g_free(local);
    }
    char *selected = now_music_helper_path_for_executable(
        kind, exe, local_exists);
    g_free(exe);
    return selected;
}
