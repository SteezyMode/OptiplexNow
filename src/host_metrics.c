#define _GNU_SOURCE
#include "host_metrics.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

void now_host_get_metric(char *dest, size_t size, const char *text,
                         const char *key)
{
    if (!dest || size == 0) {
        return;
    }
    dest[0] = '\0';
    if (!text || !key || !*key) {
        return;
    }

    size_t length = strlen(key);
    const char *line = text;
    while (*line) {
        if (strncmp(line, key, length) == 0) {
            const char *value = line + length;
            size_t count = 0;
            while (*value && *value != '\r' && *value != '\n' &&
                   count + 1 < size) {
                if (isprint((unsigned char)*value)) {
                    dest[count++] = *value;
                }
                value++;
            }
            dest[count] = '\0';
            return;
        }
        const char *next = strchr(line, '\n');
        if (!next) {
            break;
        }
        line = next + 1;
    }
}

static int allowed_disk_path(const char *path)
{
    if (!path || path[0] != '/' || strlen(path) > 350) {
        return 0;
    }
    for (const char *p = path; *p; p++) {
        if (!isalnum((unsigned char)*p) && !strchr("/_.-", *p)) {
            return 0;
        }
    }
    return 1;
}

static int system_mount(const char *path)
{
    if (!path || path[0] != '/') {
        return 1;
    }
    if (strcmp(path, "/") == 0) {
        return 0;
    }
    if (strncmp(path, "/run/", 5) == 0 ||
        strncmp(path, "/dev/", 5) == 0 ||
        strncmp(path, "/proc/", 6) == 0 ||
        strncmp(path, "/sys/", 5) == 0) {
        return 1;
    }

    const char *part = path;
    while (*part) {
        while (*part == '/') {
            part++;
        }
        if (!*part) {
            break;
        }
        const char *end = strchr(part, '/');
        size_t n = end ? (size_t)(end - part) : strlen(part);

        if ((n == 4 && strncasecmp(part, "boot", 4) == 0) ||
            (n == 3 && strncasecmp(part, "efi", 3) == 0) ||
            (n == 4 && strncasecmp(part, "snap", 4) == 0) ||
            (n >= 8 && strcasestr(part, "recovery") &&
             (size_t)(strcasestr(part, "recovery") - part) < n)) {
            return 1;
        }
        if (!end) {
            break;
        }
        part = end + 1;
    }
    return 0;
}

int now_host_parse_drives(const char *text, NowHostDrive *drives,
                          size_t capacity)
{
    if (!text || !drives || capacity == 0) {
        return 0;
    }
    const char *begin = strstr(text, "DRIVES_BEGIN\n");
    if (!begin) {
        return 0;
    }
    begin += strlen("DRIVES_BEGIN\n");
    const char *end = strstr(begin, "DRIVES_END");
    if (!end) {
        return 0;
    }

    size_t count = 0;
    while (begin < end && count < capacity) {
        const char *next = memchr(begin, '\n', (size_t)(end - begin));
        if (!next) {
            break;
        }
        if ((size_t)(next - begin) < 6 ||
            strncmp(begin, "DRIVE=", 6) != 0) {
            begin = next + 1;
            continue;
        }
        size_t length = (size_t)(next - begin) - 6;
        if (length == 0 || length >= 512) {
            begin = next + 1;
            continue;
        }

        char record[512];
        memcpy(record, begin + 6, length);
        record[length] = '\0';
        char *fields[4] = {record};
        char *cursor = record;
        int valid = 1;
        for (int i = 1; i < 4; i++) {
            char *separator = strchr(cursor, '|');
            if (!separator) {
                valid = 0;
                break;
            }
            *separator = '\0';
            fields[i] = separator + 1;
            cursor = fields[i];
        }
        if (valid && !strchr(fields[3], '|') &&
            allowed_disk_path(fields[0]) && !system_mount(fields[0])) {
            NowHostDrive *drive = &drives[count];
            snprintf(drive->path, sizeof drive->path, "%s", fields[0]);
            snprintf(drive->size, sizeof drive->size, "%s", fields[1]);
            snprintf(drive->free_space, sizeof drive->free_space, "%s", fields[2]);
            snprintf(drive->used_percent, sizeof drive->used_percent, "%s",
                     fields[3]);
            count++;
        }
        begin = next + 1;
    }
    return (int)count;
}
