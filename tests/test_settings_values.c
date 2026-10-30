/* GTK- and filesystem-free regression for the Settings Save value merger.
 * No configuration file or user preferences are created by this test.
 */
#include "settings_values.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void original_config(char values[CONFIG_COUNT][CONFIG_VALUE_SIZE])
{
    for (int i = 0; i < CONFIG_COUNT; ++i)
        snprintf(values[i], CONFIG_VALUE_SIZE, "unchanged-%d", i);
    strcpy(values[8], "system");
    strcpy(values[10], "/mnt/old");
    strcpy(values[13], "255");
    strcpy(values[FEATURED_MASK_SETTING], "207");
    strcpy(values[16], "https://previous.example/video");
}

static NowSettingsInput example_input(void)
{
    NowSettingsInput input = {0};
    static const char *const fields[] = {
        "192.0.2.21", "owner", "192.0.2.22", "relay", "/usr/bin/wake",
        "https://video.example", "https://music.example", "https://dl.example"
    };
    for (int i = 0; i < 8; ++i)
        input.connection[i] = fields[i];
    input.disk_path = "/mnt/new-drive";
    input.browser_choice = 3;
    input.tray_mask = 85;
    input.featured_mask = 170;
    input.web_gaming_url = "https://web.example";
    return input;
}

static void test_normal_merge(void)
{
    char saved[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    char original[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    original_config(saved);
    memcpy(original, saved, sizeof original);
    NowSettingsInput input = example_input();
    NowSettingsPrepared prepared = {0};
    assert(now_settings_prepare_config(&prepared, saved, &input));
    assert(memcmp(saved, original, sizeof saved) == 0);
    for (int i = 0; i < 8; ++i)
        assert(strcmp(prepared.values[i], input.connection[i]) == 0);
    assert(strcmp(prepared.values[8], "chrome") == 0);
    assert(strcmp(prepared.values[10], "/mnt/new-drive") == 0);
    assert(strcmp(prepared.values[13], "85") == 0);
    assert(strcmp(prepared.values[FEATURED_MASK_SETTING], "170") == 0);
    assert(prepared.web_gaming_url_valid);
    assert(strcmp(prepared.values[16], "https://web.example") == 0);
    for (int i = 9; i < CONFIG_COUNT; ++i) {
        if (i == 10 || i == 13 || i == FEATURED_MASK_SETTING || i == 16)
            continue;
        assert(strcmp(prepared.values[i], saved[i]) == 0);
    }
}

static void test_rejected_edits_keep_original(void)
{
    char saved[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    original_config(saved);
    NowSettingsInput input = example_input();
    input.connection[0] = "server\\nspoof";
    input.connection[3] = "relay\\rinject";
    input.disk_path = "relative/untrusted";
    input.browser_choice = -1;
    input.tray_mask = 0;
    input.featured_mask = 255;
    input.web_gaming_url = "https://user:secret@host.example/?token=abc";
    NowSettingsPrepared prepared = {0};
    assert(now_settings_prepare_config(&prepared, saved, &input));
    assert(strcmp(prepared.values[0], saved[0]) == 0);
    assert(strcmp(prepared.values[3], saved[3]) == 0);
    assert(strcmp(prepared.values[10], "/mnt/old") == 0);
    assert(strcmp(prepared.values[8], "auto") == 0);
    assert(strcmp(prepared.values[13], "0") == 0);
    assert(strcmp(prepared.values[FEATURED_MASK_SETTING], "255") == 0);
    assert(!prepared.web_gaming_url_valid);
    assert(strcmp(prepared.values[16], saved[16]) == 0);
}

static void test_empty_override_and_long_values(void)
{
    char saved[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    original_config(saved);
    char huge[900];
    memset(huge, 'X', sizeof huge - 1);
    huge[sizeof huge - 1] = '\0';
    NowSettingsInput input = example_input();
    input.connection[1] = huge;
    input.disk_path = "/mnt/disk-with-spaces";
    input.browser_choice = 99;
    input.web_gaming_url = "";
    NowSettingsPrepared prepared = {0};
    assert(now_settings_prepare_config(&prepared, saved, &input));
    assert(strlen(prepared.values[1]) == CONFIG_VALUE_SIZE - 1);
    assert(prepared.values[1][CONFIG_VALUE_SIZE - 1] == '\0');
    assert(strcmp(prepared.values[10], saved[10]) == 0);
    assert(strcmp(prepared.values[8], "auto") == 0);
    assert(prepared.web_gaming_url_valid);
    assert(strcmp(prepared.values[16], "") == 0);
}

static void test_reject_missing_input_without_output_mutation(void)
{
    char saved[CONFIG_COUNT][CONFIG_VALUE_SIZE];
    original_config(saved);
    NowSettingsInput input = example_input();
    NowSettingsPrepared prepared;
    memset(&prepared, 0x5a, sizeof prepared);
    NowSettingsPrepared before = prepared;
    assert(!now_settings_prepare_config(NULL, saved, &input));
    assert(!now_settings_prepare_config(&prepared, NULL, &input));
    assert(!now_settings_prepare_config(&prepared, saved, NULL));
    input.connection[6] = NULL;
    assert(!now_settings_prepare_config(&prepared, saved, &input));
    input = example_input();
    input.disk_path = NULL;
    assert(!now_settings_prepare_config(&prepared, saved, &input));
    input = example_input();
    input.web_gaming_url = NULL;
    assert(!now_settings_prepare_config(&prepared, saved, &input));
    assert(memcmp(&prepared, &before, sizeof prepared) == 0);
}

int main(void)
{
    test_normal_merge();
    test_rejected_edits_keep_original();
    test_empty_override_and_long_values();
    test_reject_missing_input_without_output_mutation();
    puts("Settings values: safe merge, preserved fields, masks, URLs and no writes passed.");
    return 0;
}
