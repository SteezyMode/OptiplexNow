#ifndef OPTIPLEX_NOW_HOST_JOB_TARGET_H
#define OPTIPLEX_NOW_HOST_JOB_TARGET_H

#include <stdbool.h>

#define NOW_JOB_TARGET_FIELD_SIZE 512

/* Immutable input to a background host operation. Capture it on the GTK
 * thread before dispatching work; workers must not read mutable config. */
typedef struct {
    char host[NOW_JOB_TARGET_FIELD_SIZE];
    char user[NOW_JOB_TARGET_FIELD_SIZE];
    char wake_path[NOW_JOB_TARGET_FIELD_SIZE];
} NowHostJobTarget;

/* Empty fields are captured for ordinary validation by the caller. Oversized
 * values fail closed instead of silently changing the intended destination. */
bool now_host_job_target_capture(NowHostJobTarget *target, const char *host,
                                 const char *user, const char *wake_path);

/* Only compare on the UI thread against the currently selected endpoint. */
bool now_host_job_target_matches(const NowHostJobTarget *target,
                                 const char *host, const char *user,
                                 const char *wake_path);

#endif
