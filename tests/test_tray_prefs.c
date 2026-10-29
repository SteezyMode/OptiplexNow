#define _GNU_SOURCE
#include "tray_prefs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Tray prefs test failed at line %d: %s\n", __LINE__, #condition); \
        goto cleanup; \
    } \
} while (0)

static int same_order(const int left[8], const int right[8])
{
    return memcmp(left, right, 8 * sizeof(int)) == 0;
}

int main(void)
{
    char directory[] = "/tmp/now-tray-test-XXXXXX";
    if (!mkdtemp(directory)) {
        return 1;
    }
    char home[512], xdg[512], config[512], legacy[512], path[512];
    snprintf(home, sizeof home, "%s/home", directory);
    snprintf(xdg, sizeof xdg, "%s/xdg", directory);
    snprintf(config, sizeof config, "%s/optiplex-desk", xdg);
    snprintf(legacy, sizeof legacy, "%s/.config", home);
    int passed = 0;

    EXPECT(mkdir(home, 0700) == 0);
    EXPECT(mkdir(xdg, 0700) == 0);
    EXPECT(mkdir(config, 0700) == 0);
    EXPECT(mkdir(legacy, 0700) == 0);
    snprintf(path, sizeof path, "%s/optiplex-desk", legacy);
    EXPECT(mkdir(path, 0700) == 0);
    EXPECT(setenv("HOME", home, 1) == 0);
    EXPECT(setenv("XDG_CONFIG_HOME", xdg, 1) == 0);

    int identity[8] = {0,1,2,3,4,5,6,7};
    int reversed[8] = {7,6,5,4,3,2,1,0};
    int order[8] = {0};
    EXPECT(now_tray_parse_order("76543210\n", order) == 1);
    EXPECT(same_order(order, reversed));
    EXPECT(now_tray_parse_order("01234567\r\n", order) == 1);
    EXPECT(same_order(order, identity));
    EXPECT(now_tray_parse_order("0123456", order) == 0);
    EXPECT(same_order(order, identity));
    EXPECT(now_tray_parse_order("00123456\n", order) == 0);
    EXPECT(same_order(order, identity));
    EXPECT(now_tray_parse_order("012345678", order) == 0);
    EXPECT(now_tray_parse_order("01234567\nx", order) == 0);
    EXPECT(now_tray_parse_mask("0") == 0);
    EXPECT(now_tray_parse_mask("173") == 173);
    EXPECT(now_tray_parse_mask("255") == 255);
    EXPECT(now_tray_parse_mask("256") == 255);
    EXPECT(now_tray_parse_mask("-1") == 255);
    EXPECT(now_tray_parse_mask("3garbage") == 255);
    EXPECT(now_tray_parse_mask(NULL) == 255);

    now_tray_order_load(order);
    EXPECT(same_order(order, identity));
    EXPECT(now_tray_order_save(reversed) == 1);
    now_tray_order_load(order);
    EXPECT(same_order(order, reversed));
    snprintf(path, sizeof path, "%s/tray-order", config);
    struct stat st;
    EXPECT(stat(path, &st) == 0);
    EXPECT((st.st_mode & 077) == 0);
    int duplicates[8] = {0,0,2,3,4,5,6,7};
    EXPECT(now_tray_order_save(duplicates) == 0);
    now_tray_order_load(order);
    EXPECT(same_order(order, reversed));

    /* Videos tray routing is a local preference; legacy default is browser. */
    EXPECT(now_tray_videos_open_in_app() == 0);
    EXPECT(now_tray_videos_set_open_in_app(1) == 1);
    EXPECT(now_tray_videos_open_in_app() == 1);
    snprintf(path, sizeof path, "%s/videos-tray-target", config);
    EXPECT(stat(path, &st) == 0);
    EXPECT((st.st_mode & 077) == 0);
    EXPECT(now_tray_videos_set_open_in_app(0) == 1);
    EXPECT(now_tray_videos_open_in_app() == 0);
    EXPECT(now_tray_videos_set_open_in_app(1) == 1);
    EXPECT(now_tray_videos_open_in_app() == 1);

    char caption[128];
    now_tray_desktop_caption(caption, sizeof caption);
    EXPECT(strcmp(caption, "XFCE") == 0);
    EXPECT(now_tray_desktop_caption_save("Steam Deck") == 1);
    now_tray_desktop_caption(caption, sizeof caption);
    EXPECT(strcmp(caption, "Steam Deck") == 0);
    EXPECT(now_tray_desktop_caption_save("bad\ncaption") == 0);
    now_tray_desktop_caption(caption, sizeof caption);
    EXPECT(strcmp(caption, "Steam Deck") == 0);
    snprintf(path, sizeof path, "%s/optiplex-desk/desktop-label", legacy);
    EXPECT(stat(path, &st) == 0);
    EXPECT((st.st_mode & 077) == 0);

    char service[128];
    EXPECT(now_tray_service_caption(6, "Steam Deck", service, sizeof service));
    EXPECT(strcmp(service, "Desktop — Steam Deck") == 0);
    EXPECT(now_tray_service_caption(1, "ignored", service, sizeof service));
    EXPECT(strcmp(service, "Videos — Jellyfin") == 0);
    EXPECT(!now_tray_service_caption(8, "bad", service, sizeof service));

    passed = 1;
cleanup:
    snprintf(path, sizeof path, "%s/videos-tray-target", config);
    unlink(path);
    snprintf(path, sizeof path, "%s/tray-order", config);
    unlink(path);
    snprintf(path, sizeof path, "%s/optiplex-desk/desktop-label", legacy);
    unlink(path);
    snprintf(path, sizeof path, "%s/optiplex-desk", legacy);
    rmdir(path);
    rmdir(legacy);
    rmdir(config);
    rmdir(xdg);
    rmdir(home);
    rmdir(directory);
    if (passed) {
        puts("Tray prefs: order, legacy caption, masks, labels and private saves passed.");
    }
    return passed ? 0 : 1;
}
