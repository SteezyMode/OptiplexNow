/* Offline Games GTK-free transport tests; no real SSH/Wolf credentials. */
#include "games_flow.h"
#include <glib.h>
#include <glib/gstdio.h>

typedef struct {
    GMainLoop *loop;
    gboolean ok;
    NowGamesReply reply;
    GError *error;
} Result;

static void done(GObject *source, GAsyncResult *res, gpointer user)
{
    (void)source;
    Result *result = user;
    result->ok = now_games_request_finish(res, &result->reply, &result->error);
    g_main_loop_quit(result->loop);
}

static void run_test(const char *script, const char *action, gboolean expected_ok,
                     NowGamesReply expected_reply)
{
    Result result = {0};
    result.loop = g_main_loop_new(NULL, FALSE);
    now_games_request_async(script, action, "127.0.0.1", "owner",
                            NULL, done, &result);
    g_main_loop_run(result.loop);
    g_assert_cmpint(result.ok, ==, expected_ok);
    if (expected_ok) {
        g_assert_no_error(result.error);
        g_assert_cmpint(result.reply, ==, expected_reply);
    } else {
        g_assert_nonnull(result.error);
        g_clear_error(&result.error);
    }
    g_main_loop_unref(result.loop);
}

static void test_helper_location(void)
{
    gchar *path = now_games_helper_for_executable("/usr/bin/optiplex-now");
    g_assert_cmpstr(path, ==,
                    "/usr/lib/optiplex-now/owner-games-client.py");
    g_free(path);

    path = now_games_helper_for_executable(
        "/home/test/Downloads/now-pr180/usr/bin/optiplex-now");
    g_assert_cmpstr(path, ==,
        "/home/test/Downloads/now-pr180/usr/lib/optiplex-now/owner-games-client.py");
    g_free(path);

    path = now_games_helper_for_executable("/tmp/now-client/optiplex-now");
    g_assert_cmpstr(path, ==,
                    "/usr/lib/optiplex-now/owner-games-client.py");
    g_free(path);

    path = now_games_helper_for_executable(NULL);
    g_assert_cmpstr(path, ==,
                    "/usr/lib/optiplex-now/owner-games-client.py");
    g_free(path);
}

static void test_parser(void)
{
    NowGamesReply result;
    static const struct {
        const char *line;
        NowGamesReply expected;
    } values[] = {
        {"needs_wolf_ui\n", NOW_GAMES_NEEDS_WOLF_UI},
        {"wolf_ui_connected\n", NOW_GAMES_WOLF_UI_CONNECTED},
        {"busy\n", NOW_GAMES_BUSY},
        {"in_use\n", NOW_GAMES_IN_USE},
        {"joined\n", NOW_GAMES_JOINED},
        {"idle\n", NOW_GAMES_IDLE}
    };
    for (gsize i = 0; i < G_N_ELEMENTS(values); ++i) {
        g_assert_true(now_games_parse_reply(values[i].line, &result));
        g_assert_cmpint(result, ==, values[i].expected);
    }
    for (gsize i = 0; i < 7; ++i) {
        const char *invalid[] = {
            "", "UNAVAILABLE", "{\"status\":\"joined\"}", "joined\nidle\n",
            " joined", "joined\r\n",
            "joined\nPRIVATE_STEAM_PIN=12345678"
        };
        g_assert_false(now_games_parse_reply(invalid[i], &result));
    }
    g_assert_false(now_games_parse_reply(NULL, &result));
    g_assert_false(now_games_parse_reply("joined", NULL));
}

static void test_async_helper(void)
{
    gchar *directory = g_dir_make_tmp("now-games-flow-XXXXXX", NULL);
    g_assert_nonnull(directory);
    gchar *file = g_build_filename(directory, "fake-helper.py", NULL);
    const char *valid =
        "import sys\n"
        "if sys.argv[1:] == ['--ui','status','127.0.0.1','owner']:\n"
        " print('wolf_ui_connected')\n"
        "elif sys.argv[1:] == ['--ui','start','127.0.0.1','owner']:\n"
        " print('joined')\n"
        "elif sys.argv[1:] == ['--ui','stop','127.0.0.1','owner']:\n"
        " print('idle')\n"
        "else:\n"
        " print('unavailable')\n"
        " sys.exit(1)\n";
    g_assert_true(g_file_set_contents(file, valid, -1, NULL));
    run_test(file, "status", TRUE, NOW_GAMES_WOLF_UI_CONNECTED);
    run_test(file, "start", TRUE, NOW_GAMES_JOINED);
    run_test(file, "stop", TRUE, NOW_GAMES_IDLE);
    run_test(file, "exec", FALSE, NOW_GAMES_BUSY);

    const char *refuse = "import sys\nprint('denied')\nsys.exit(1)\n";
    g_assert_true(g_file_set_contents(file, refuse, -1, NULL));
    run_test(file, "start", FALSE, NOW_GAMES_BUSY);

    const char *tampered =
        "print('joined\\nSTEAM_PRIVATE_KEY: do not expose')\n";
    g_assert_true(g_file_set_contents(file, tampered, -1, NULL));
    run_test(file, "start", FALSE, NOW_GAMES_BUSY);

    g_assert_cmpint(g_remove(file), ==, 0);
    g_assert_cmpint(g_rmdir(directory), ==, 0);
    g_free(file);
    g_free(directory);
}

int main(int argc, char **argv)
{
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/games/helper-location", test_helper_location);
    g_test_add_func("/games/reply-parser", test_parser);
    g_test_add_func("/games/async-helper", test_async_helper);
    return g_test_run();
}
