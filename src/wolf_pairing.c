#include "wolf_pairing.h"

#include <arpa/inet.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int valid_ip_address(const char *address)
{
    struct in_addr ipv4;
    struct in6_addr ipv6;

    return inet_pton(AF_INET, address, &ipv4) == 1 ||
           inet_pton(AF_INET6, address, &ipv6) == 1;
}

int now_wolf_parse_pending(const char *text, NowWolfPending *out, size_t capacity)
{
    if (!text || !out || capacity == 0) {
        return -1;
    }

    size_t count = 0;
    const char *cursor = text;

    while (*cursor != '\0') {
        const char *end = strchr(cursor, '\n');
        size_t length = end ? (size_t)(end - cursor) : strlen(cursor);

        if (length > 0 && cursor[length - 1] == '\r') {
            length--;
        }
        if (length == 0 || length >= 128 || count >= capacity) {
            return -1;
        }

        char line[128];
        memcpy(line, cursor, length);
        line[length] = '\0';

        char *tab = strchr(line, '\t');
        if (!tab || tab == line || strchr(tab + 1, '\t')) {
            return -1;
        }
        *tab++ = '\0';

        /* Only positive decimal indices are valid. No signs or whitespace. */
        for (const char *p = line; *p; p++) {
            if (*p < '0' || *p > '9') {
                return -1;
            }
        }
        errno = 0;
        char *after_index = NULL;
        long index = strtol(line, &after_index, 10);
        if (errno || !after_index || *after_index || index < 1 || index > INT_MAX ||
            strlen(tab) >= sizeof out[0].client_ip || !valid_ip_address(tab)) {
            return -1;
        }

        for (size_t i = 0; i < count; i++) {
            if (out[i].index == (int)index || strcmp(out[i].client_ip, tab) == 0) {
                /* Ambiguous or duplicated requests must never be auto-selected. */
                return -1;
            }
        }

        out[count].index = (int)index;
        snprintf(out[count].client_ip, sizeof out[count].client_ip, "%s", tab);
        count++;
        cursor = end ? end + 1 : cursor + strlen(cursor);
    }
    return (int)count;
}

int now_wolf_make_pair_payload(const NowWolfPending *client, const char *pin,
                               char *out, size_t capacity)
{
    if (!client || !pin || !out || capacity == 0 ||
        client->index < 1 || !valid_ip_address(client->client_ip)) {
        return 0;
    }

    size_t length = strlen(pin);
    if (length < 4 || length > 12) {
        return 0;
    }
    for (size_t i = 0; i < length; i++) {
        if (pin[i] < '0' || pin[i] > '9') {
            return 0;
        }
    }

    int used = snprintf(out, capacity,
                        "{\"index\":%d,\"client_ip\":\"%s\",\"pin\":\"%s\"}",
                        client->index, client->client_ip, pin);
    return used > 0 && (size_t)used < capacity;
}
