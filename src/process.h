#ifndef OPTIPLEX_NOW_PROCESS_H
#define OPTIPLEX_NOW_PROCESS_H

#include <stddef.h>

/* Run a command with bounded output capture and timeout (seconds).
 * Returns its exit status or -1 on launch error / timeout. */
int now_run(char *const argv[], char *out, size_t cap, int timeout);

/* Launch a detached process; retains the established NOW semantics. */
void now_launch(char *const argv[]);

/* Check whether a program is executable (absolute path or PATH lookup). */
int now_program_exists(const char *name);

#endif
