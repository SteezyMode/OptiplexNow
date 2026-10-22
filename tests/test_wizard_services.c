#define _GNU_SOURCE
#include "wizard_services.h"
#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Wizard service persistence test line %d: %s\\n", \
                __LINE__, #condition); \
        return 1; \
    } \
} while (0)

static int test_save_round_trip(void)
{
    memset(cfg, 0, sizeof cfg);
    const char *urls[3] = {
        "https://media.example.test",
        "https://music.example.test",
        "https://downloads.example.test"
    };
    EXPECT(now_wizard_store_services(cfg, urls));
    EXPECT(strcmp(cfg[5], urls[0]) == 0);

    char path[] = "/tmp/now-wizard-service-test-XXXXXX";
    int fd = mkstemp(path);
    EXPECT(fd >= 0);
    close(fd);
    EXPECT(now_config_save_to(path));
    memset(cfg, 0, sizeof cfg);
    EXPECT(now_config_load_from(path) == 1);
    unlink(path);
    for (int i = 0; i < 3; i++) {
        EXPECT(strcmp(cfg[5 + i], urls[i]) == 0);
    }
    return 0;
}

static int test_invalid_url_is_atomic(void)
{
    memset(cfg, 0, sizeof cfg);
    snprintf(cfg[5], CONFIG_VALUE_SIZE, "%s", "https://existing.example.test");
    snprintf(cfg[6], CONFIG_VALUE_SIZE, "%s", "https://music.example.test");
    snprintf(cfg[7], CONFIG_VALUE_SIZE, "%s", "https://downloads.example.test");
    const char *urls[3] = {
        "https://replacement.example.test",
        "https://wrong.example.test@other.example.test",
        "https://new-downloads.example.test"
    };
    EXPECT(!now_wizard_store_services(cfg, urls));
    EXPECT(strcmp(cfg[5], "https://existing.example.test") == 0);
    EXPECT(strcmp(cfg[6], "https://music.example.test") == 0);
    EXPECT(strcmp(cfg[7], "https://downloads.example.test") == 0);
    EXPECT(!now_wizard_store_services(cfg, NULL));
    return 0;
}

static int test_intentional_clear(void)
{
    const char *urls[3] = {"https://media.example.test", "", ""};
    EXPECT(now_wizard_store_services(cfg, urls));
    EXPECT(strcmp(cfg[5], urls[0]) == 0);
    EXPECT(cfg[6][0] == '\0');
    EXPECT(cfg[7][0] == '\0');
    return 0;
}

int main(void)
{
    EXPECT(test_save_round_trip() == 0);
    EXPECT(test_invalid_url_is_atomic() == 0);
    EXPECT(test_intentional_clear() == 0);
    puts("Wizard service URLs: atomic validation, persistence and clear passed.");
    return 0;
}
