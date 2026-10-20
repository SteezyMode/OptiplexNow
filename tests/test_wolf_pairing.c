#include "wolf_pairing.h"

#include <stdio.h>
#include <string.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Wolf pairing contract failed at line %d: %s\n", __LINE__, #condition); \
        return 1; \
    } \
} while (0)

int main(void)
{
    NowWolfPending pending[NOW_WOLF_MAX_PENDING] = {0};
    char payload[256] = {0};

    EXPECT(now_wolf_parse_pending("", pending, NOW_WOLF_MAX_PENDING) == 0);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n", pending,
                                  NOW_WOLF_MAX_PENDING) == 1);
    EXPECT(pending[0].index == 1);
    EXPECT(strcmp(pending[0].client_ip, "100.100.1.2") == 0);
    EXPECT(now_wolf_make_pair_payload(&pending[0], "0123", payload,
                                      sizeof payload) == 1);
    EXPECT(strcmp(payload,
                  "{\"index\":1,\"client_ip\":\"100.100.1.2\",\"pin\":\"0123\"}") == 0);

    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n2\t2001:db8::2\n",
                                  pending, NOW_WOLF_MAX_PENDING) == 2);
    EXPECT(pending[1].index == 2);
    EXPECT(strcmp(pending[1].client_ip, "2001:db8::2") == 0);
    EXPECT(now_wolf_make_pair_payload(&pending[1], "5678", payload,
                                      sizeof payload) == 1);

    /* Malformed, duplicate, and ambiguous responses fail closed. */
    EXPECT(now_wolf_parse_pending("1\twrong-host\n", pending, 100) == -1);
    EXPECT(now_wolf_parse_pending("-1\t100.100.1.2\n", pending, 100) == -1);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\tother\n", pending, 100) == -1);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n1\t100.100.1.3\n",
                                  pending, 100) == -1);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n2\t100.100.1.2\n",
                                  pending, 100) == -1);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n2\t100.100.1.3\n",
                                  pending, 1) == -1);
    EXPECT(now_wolf_parse_pending("1\t100.100.1.2\n\n", pending, 100) == -1);
    EXPECT(now_wolf_make_pair_payload(&pending[0], "12ab", payload,
                                      sizeof payload) == 0);
    EXPECT(now_wolf_make_pair_payload(&pending[0], "1234", payload, 6) == 0);

    puts("Wolf pairing contract: parsing, identity and payload checks passed.");
    return 0;
}
