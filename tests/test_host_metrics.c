#include "host_metrics.h"

#include <stdio.h>
#include <string.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Host telemetry test line %d: %s\n", __LINE__, #condition); \
        return 1; \
    } \
} while (0)

int main(void)
{
    char value[32] = {0};
    now_host_get_metric(value, sizeof value,
                        "READY\nCPU=42C\nRAM_USED=4 / 16 GiB\n", "CPU=");
    EXPECT(strcmp(value, "42C") == 0);
    now_host_get_metric(value, sizeof value, "PREFIX_CPU=incorrect\n", "CPU=");
    EXPECT(value[0] == '\0');
    now_host_get_metric(value, sizeof value, NULL, "CPU=");
    EXPECT(value[0] == '\0');
    now_host_get_metric(value, 4, "CPU=long_value\n", "CPU=");
    EXPECT(strcmp(value, "lon") == 0);

    NowHostDrive drives[NOW_HOST_MAX_DRIVES] = {0};
    const char *report = "READY\nMODEL=Generic\nDRIVE=/outside|1G|1G|0%\n"
        "DRIVES_BEGIN\n"
        "DRIVE=/|200G|100G|50%\n"
        "DRIVE=/mnt/media|2T|1T|50%\n"
        "DRIVE=/boot|1G|800M|20%\n"
        "DRIVE=/recovery|2G|1G|50%\n"
        "DRIVE=/run/container|1G|0G|100%\n"
        "DRIVE=relative/path|2T|1T|50%\n"
        "DRIVE=/mnt/broken|1G\n"
        "DRIVES_END\nDRIVE=/outside_after|1G|1G|0%\n";
    EXPECT(now_host_parse_drives(report, drives, NOW_HOST_MAX_DRIVES) == 2);
    EXPECT(strcmp(drives[0].path, "/") == 0);
    EXPECT(strcmp(drives[1].path, "/mnt/media") == 0);
    EXPECT(strcmp(drives[1].free_space, "1T") == 0);
    EXPECT(now_host_parse_drives(report, drives, 1) == 1);
    EXPECT(now_host_parse_drives("DRIVE=/foo|1G|1G|0%\n", drives, 16) == 0);
    EXPECT(now_host_parse_drives("DRIVES_BEGIN\nDRIVE=/foo|1G|1G|0%\n",
                                 drives, 16) == 0);
    EXPECT(now_host_parse_drives(NULL, drives, 16) == 0);
    puts("Host telemetry: bounded metrics, mounted disks and malformed rows passed.");
    return 0;
}
