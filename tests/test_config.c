#define _GNU_SOURCE
#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define REQUIRE(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Configuration test failed at line %d: %s\n", __LINE__, #condition); \
        goto cleanup; \
    } \
} while (0)

int main(void)
{
    char directory[] = "/tmp/now-config-test-XXXXXX";
    if (!mkdtemp(directory)) {
        return 1;
    }
    char path[512];
    snprintf(path, sizeof path, "%s/config.ini", directory);
    int passed = 0;

    REQUIRE(now_config_load_from(path) == 0);
    REQUIRE(first_run == 1);
    REQUIRE(cfg[0][0] == '\0');
    REQUIRE(cfg[1][0] == '\0');
    REQUIRE(cfg[5][0] == '\0');
    REQUIRE(cfg[16][0] == '\0');
    REQUIRE(strcmp(cfg[FEATURED_MASK_SETTING], "207") == 0);

    snprintf(cfg[0], CONFIG_VALUE_SIZE, "server.example");
    snprintf(cfg[1], CONFIG_VALUE_SIZE, "alice");
    snprintf(cfg[5], CONFIG_VALUE_SIZE, "https://video.example");
    snprintf(cfg[16], CONFIG_VALUE_SIZE, "https://games.example");
    REQUIRE(now_config_save_to(path) == 1);

    struct stat st;
    REQUIRE(stat(path, &st) == 0);
    REQUIRE((st.st_mode & 077) == 0);
    REQUIRE(now_config_load_from(path) == 1);
    REQUIRE(first_run == 0);
    REQUIRE(strcmp(cfg[5], "https://video.example") == 0);
    REQUIRE(strcmp(cfg[16], "https://games.example") == 0);

    /* A bad value must not replace an already saved configuration. */
    snprintf(cfg[16], CONFIG_VALUE_SIZE, "bad\nvalue");
    REQUIRE(now_config_save_to(path) == 0);
    REQUIRE(now_config_load_from(path) == 1);
    REQUIRE(strcmp(cfg[16], "https://games.example") == 0);

    /* Older files had no featured_actions or Web Gaming URL keys. */
    FILE *legacy = fopen(path, "w");
    REQUIRE(legacy != NULL);
    REQUIRE(fputs("host=older-host\nuser=olduser\nvideos=https://old.example\n", legacy) >= 0);
    REQUIRE(fclose(legacy) == 0);
    REQUIRE(now_config_load_from(path) == 1);
    REQUIRE(strcmp(cfg[0], "older-host") == 0);
    REQUIRE(strcmp(cfg[5], "https://old.example") == 0);
    REQUIRE(cfg[16][0] == '\0');
    REQUIRE(strcmp(cfg[FEATURED_MASK_SETTING], "255") == 0);

    passed = 1;
cleanup:
    unlink(path);
    rmdir(directory);
    if (passed) {
        puts("Configuration tests: fresh, upgrade, restricted save and legacy loading passed.");
    }
    return passed ? 0 : 1;
}
