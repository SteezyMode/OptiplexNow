#include "host_job_target.h"

#include <string.h>

bool now_host_job_target_capture(NowHostJobTarget *target, const char *host,
                                 const char *user, const char *wake_path)
{
    if (!target || !host || !user || !wake_path)
        return false;

    size_t host_len = strnlen(host, NOW_JOB_TARGET_FIELD_SIZE);
    size_t user_len = strnlen(user, NOW_JOB_TARGET_FIELD_SIZE);
    size_t wake_len = strnlen(wake_path, NOW_JOB_TARGET_FIELD_SIZE);
    if (host_len == NOW_JOB_TARGET_FIELD_SIZE ||
        user_len == NOW_JOB_TARGET_FIELD_SIZE ||
        wake_len == NOW_JOB_TARGET_FIELD_SIZE)
        return false;

    NowHostJobTarget snapshot = {0};
    memcpy(snapshot.host, host, host_len + 1);
    memcpy(snapshot.user, user, user_len + 1);
    memcpy(snapshot.wake_path, wake_path, wake_len + 1);
    *target = snapshot;
    return true;
}

bool now_host_job_target_matches(const NowHostJobTarget *target,
                                 const char *host, const char *user,
                                 const char *wake_path)
{
    return target && host && user && wake_path &&
           strcmp(target->host, host) == 0 &&
           strcmp(target->user, user) == 0 &&
           strcmp(target->wake_path, wake_path) == 0;
}
