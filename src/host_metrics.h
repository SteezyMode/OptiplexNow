#ifndef OPTIPLEX_NOW_HOST_METRICS_H
#define OPTIPLEX_NOW_HOST_METRICS_H

#include <stddef.h>

#define NOW_HOST_MAX_DRIVES 16

/* The remote host's telemetry is untrusted text, never GTK markup. */
typedef struct {
    char path[256];
    char size[32];
    char free_space[32];
    char used_percent[16];
} NowHostDrive;

/* Extract a single printable key=value line. Empty on absent or bad input. */
void now_host_get_metric(char *dest, size_t size, const char *text,
                         const char *key);

/* Parse physical mount entries between explicit section markers, filtering
 * recovery/system mounts. Returns a bounded count, never modifies the host. */
int now_host_parse_drives(const char *text, NowHostDrive *drives,
                          size_t capacity);

/* Validate configured mount paths even when telemetry has not been fetched. */
int now_host_safe_disk_path(const char *path);

#endif
