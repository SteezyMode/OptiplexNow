#ifndef OPTIPLEX_NOW_WOLF_PAIRING_H
#define OPTIPLEX_NOW_WOLF_PAIRING_H

#include <stddef.h>

#define NOW_WOLF_MAX_PENDING 100

typedef struct {
    int index;
    char client_ip[64];
} NowWolfPending;

/*
 * Parse the output of wolf-pair-client.py pending-text.
 * Returns 0 for no requests, a positive count for valid requests and -1
 * if the response is malformed, ambiguous or exceeds capacity.
 * No request is ever selected or authorized by this parser.
 */
int now_wolf_parse_pending(const char *text, NowWolfPending *out, size_t capacity);

/* Build the narrow host-helper request for a selected pending device and PIN. */
int now_wolf_make_pair_payload(const NowWolfPending *client, const char *pin,
                               char *out, size_t capacity);

#endif
