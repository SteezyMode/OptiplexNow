#define _GNU_SOURCE
#include "wizard_services.h"
#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Wizard service persistence test line %d: %s\n", \
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
    EXPECT(now_wizard_store_services(cfg, urls) == 0);
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

static int test_invalid_url_does_not_block_other_services(void)
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
    EXPECT(now_wizard_store_services(cfg, urls) == (1u << 1));
    EXPECT(strcmp(cfg[5], "https://replacement.example.test") == 0);
    EXPECT(strcmp(cfg[6], "https://music.example.test") == 0);
    EXPECT(strcmp(cfg[7], "https://new-downloads.example.test") == 0);
    EXPECT(now_wizard_store_services(cfg, NULL) == 7u);
    EXPECT(strcmp(cfg[5], "https://replacement.example.test") == 0);
    return 0;
}

static int test_intentional_clear(void)
{
    const char *urls[3] = {"https://media.example.test", "", ""};
    EXPECT(now_wizard_store_services(cfg, urls) == 0);
    EXPECT(strcmp(cfg[5], urls[0]) == 0);
    EXPECT(cfg[6][0] == '\0');
    EXPECT(cfg[7][0] == '\0');
    return 0;
}


/* The first-run wizard has stricter, group-atomic imported URL semantics
 * than the optional per-field editor above. Keep both contracts distinct. */
static int test_first_run_keeps_optional_settings(void)
{
    memset(cfg, 0, sizeof cfg);
    strcpy(cfg[5], "https://existing-media.example");
    strcpy(cfg[6], "https://existing-music.example");
    strcpy(cfg[7], "https://existing-downloads.example");
    strcpy(cfg[10], "/mnt/existing");
    strcpy(cfg[14], "https://existing-ai.example");
    strcpy(cfg[16], "https://existing-web.example");

    char staged[CONFIG_COUNT][CONFIG_VALUE_SIZE] = {{0}};
    strcpy(staged[2], "192.0.2.22");
    strcpy(staged[3], "relay");
    strcpy(staged[4], "/usr/bin/wake");

    EXPECT(now_wizard_merge_connection(
        cfg, "198.51.100.20", "owner", staged, 0));
    EXPECT(strcmp(cfg[0], "198.51.100.20") == 0);
    EXPECT(strcmp(cfg[1], "owner") == 0);
    EXPECT(strcmp(cfg[2], "192.0.2.22") == 0);
    EXPECT(strcmp(cfg[3], "relay") == 0);
    EXPECT(strcmp(cfg[4], "/usr/bin/wake") == 0);
    EXPECT(strcmp(cfg[5], "https://existing-media.example") == 0);
    EXPECT(strcmp(cfg[6], "https://existing-music.example") == 0);
    EXPECT(strcmp(cfg[7], "https://existing-downloads.example") == 0);
    EXPECT(strcmp(cfg[10], "/mnt/existing") == 0);
    EXPECT(strcmp(cfg[14], "https://existing-ai.example") == 0);
    EXPECT(strcmp(cfg[16], "https://existing-web.example") == 0);
    return 0;
}

static int test_first_run_invalid_server_is_nonmutating(void)
{
    char staged[CONFIG_COUNT][CONFIG_VALUE_SIZE] = {{0}};
    strcpy(staged[2], "192.0.2.22");
    strcpy(staged[3], "relay");
    strcpy(staged[4], "/usr/bin/wake");
    char before[sizeof cfg];
    memcpy(before, cfg, sizeof before);

    EXPECT(!now_wizard_merge_connection(
        cfg, "invalid host", "owner", staged, 1));
    EXPECT(memcmp(cfg, before, sizeof cfg) == 0);
    EXPECT(!now_wizard_merge_connection(
        cfg, "198.51.100.2", "bad user", staged, 0));
    EXPECT(memcmp(cfg, before, sizeof cfg) == 0);
    strcpy(staged[4], "bad\nwake");
    EXPECT(!now_wizard_merge_connection(
        cfg, "198.51.100.2", "owner", staged, 0));
    EXPECT(memcmp(cfg, before, sizeof cfg) == 0);
    EXPECT(!now_wizard_merge_connection(cfg, NULL, "owner", staged, 0));
    EXPECT(memcmp(cfg, before, sizeof cfg) == 0);
    return 0;
}

static int test_explicit_preset_import_all_or_nothing_services(void)
{
    char staged[CONFIG_COUNT][CONFIG_VALUE_SIZE] = {{0}};
    strcpy(staged[2], "192.0.2.22");
    strcpy(staged[3], "relay");
    strcpy(staged[4], "/usr/bin/wake");
    strcpy(staged[5], "https://new-media.example");
    strcpy(staged[6], "https://new-music.example");
    strcpy(staged[7], "https://new-downloads.example");
    strcpy(staged[10], "/mnt/imported");
    strcpy(staged[14], "https://imported-ai.example");
    strcpy(staged[16], "https://imported-web.example");

    EXPECT(now_wizard_merge_connection(
        cfg, "198.51.100.21", "owner", staged, 1));
    EXPECT(strcmp(cfg[5], staged[5]) == 0);
    EXPECT(strcmp(cfg[6], staged[6]) == 0);
    EXPECT(strcmp(cfg[7], staged[7]) == 0);
    EXPECT(strcmp(cfg[10], "/mnt/imported") == 0);
    EXPECT(strcmp(cfg[14], staged[14]) == 0);
    EXPECT(strcmp(cfg[16], staged[16]) == 0);

    /* Even one malformed URL retains all three previous service URLs.
     * This differs intentionally from now_wizard_store_services(). */
    strcpy(staged[5], "https://replacement-media.example");
    strcpy(staged[6], "https://user:pw@other.example");
    strcpy(staged[7], "https://replacement-downloads.example");
    strcpy(staged[10], "/mnt/another-import");
    EXPECT(now_wizard_merge_connection(
        cfg, "198.51.100.25", "owner", staged, 1));
    EXPECT(strcmp(cfg[0], "198.51.100.25") == 0);
    EXPECT(strcmp(cfg[5], "https://new-media.example") == 0);
    EXPECT(strcmp(cfg[6], "https://new-music.example") == 0);
    EXPECT(strcmp(cfg[7], "https://new-downloads.example") == 0);
    EXPECT(strcmp(cfg[10], "/mnt/another-import") == 0);

    strcpy(staged[5], "");
    strcpy(staged[6], "");
    strcpy(staged[7], "");
    EXPECT(now_wizard_merge_connection(
        cfg, "198.51.100.25", "owner", staged, 1));
    for (int i = 5; i <= 7; ++i)
        EXPECT(cfg[i][0] == '\0');
    return 0;
}

int main(void)
{
    EXPECT(test_save_round_trip() == 0);
    EXPECT(test_invalid_url_does_not_block_other_services() == 0);
    EXPECT(test_intentional_clear() == 0);
    EXPECT(test_first_run_keeps_optional_settings() == 0);
    EXPECT(test_first_run_invalid_server_is_nonmutating() == 0);
    EXPECT(test_explicit_preset_import_all_or_nothing_services() == 0);
    puts("Wizard service URLs: independent validation, persistence and clear passed.");
    return 0;
}
