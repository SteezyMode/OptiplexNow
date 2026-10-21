#include "host_job_target.h"

#include <stdio.h>
#include <string.h>

#define EXPECT(test) do { \
    if (!(test)) { \
        fprintf(stderr, "Host job target test line %d: %s\n", __LINE__, #test); \
        return 1; \
    } \
} while (0)

int main(void)
{
    char host[512] = "host-a.example";
    char user[512] = "owner-a";
    char wake[512] = "/opt/scripts/wake-a";
    NowHostJobTarget target = {0};
    EXPECT(now_host_job_target_capture(&target, host, user, wake));
    EXPECT(now_host_job_target_matches(&target, host, user, wake));

    strcpy(host, "host-b.example");
    strcpy(user, "owner-b");
    strcpy(wake, "/opt/scripts/wake-b");
    EXPECT(strcmp(target.host, "host-a.example") == 0);
    EXPECT(strcmp(target.user, "owner-a") == 0);
    EXPECT(strcmp(target.wake_path, "/opt/scripts/wake-a") == 0);
    EXPECT(!now_host_job_target_matches(&target, host, user, wake));
    EXPECT(!now_host_job_target_matches(&target, target.host, target.user, wake));
    EXPECT(now_host_job_target_matches(&target, "host-a.example", "owner-a",
                                       "/opt/scripts/wake-a"));

    EXPECT(now_host_job_target_capture(&target, "relay.example", "relay-user",
                                       "/usr/local/bin/wake"));
    EXPECT(now_host_job_target_matches(&target, "relay.example", "relay-user",
                                       "/usr/local/bin/wake"));
    EXPECT(now_host_job_target_capture(&target, "", "", ""));
    EXPECT(now_host_job_target_matches(&target, "", "", ""));

    char maximum[512];
    memset(maximum, 'x', sizeof maximum);
    EXPECT(!now_host_job_target_capture(&target, maximum, "owner", ""));
    EXPECT(!now_host_job_target_capture(&target, "host", maximum, ""));
    EXPECT(!now_host_job_target_capture(&target, "host", "owner", maximum));
    EXPECT(now_host_job_target_matches(&target, "", "", ""));
    maximum[511] = '\0';
    EXPECT(now_host_job_target_capture(&target, maximum, "owner", ""));
    EXPECT(strlen(target.host) == 511);
    EXPECT(!now_host_job_target_capture(NULL, "host", "owner", ""));
    EXPECT(!now_host_job_target_capture(&target, NULL, "owner", ""));
    EXPECT(!now_host_job_target_matches(NULL, "host", "owner", ""));
    EXPECT(!now_host_job_target_matches(&target, NULL, "owner", ""));
    puts("Host job targets: immutable snapshots, stale matches and bounds passed.");
    return 0;
}
