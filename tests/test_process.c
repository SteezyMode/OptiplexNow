#include "process.h"

#include <stdio.h>
#include <string.h>

static int fail(const char *reason) {
    fprintf(stderr, "process helper test failed: %s\n", reason);
    return 1;
}

int main(void) {
    char output[80] = {0};
    char *const ok[] = {"/bin/sh", "-c", "printf hello", NULL};
    char *const nonzero[] = {"/bin/sh", "-c", "exit 7", NULL};

    if (!now_program_exists("/bin/sh")) return fail("absolute executable");
    if (!now_program_exists("sh")) return fail("PATH executable");
    if (now_program_exists(NULL) || now_program_exists("")) return fail("invalid executable name");
    if (now_program_exists("/nonexistent/optiplex-now-test-exec")) return fail("missing executable");

    if (now_run(ok, output, sizeof output, 3) != 0) return fail("successful exit code");
    if (strcmp(output, "hello") != 0) return fail("captured stdout");
    if (now_run(nonzero, NULL, 0, 3) != 7) return fail("nonzero exit code");
    if (now_run(NULL, NULL, 0, 3) != -1) return fail("invalid command");

    /* Previously the child deadlocked after the capture filled (or with no
     * capture at all): stdout was not drained and the pipe filled up.
     * A 256 KiB output must complete rather than hit the process timeout.
     */
    char *const verbose[] = {"/bin/sh", "-c", "yes abc | head -c 262144", NULL};
    char small[8] = {0};
    if (now_run(verbose, small, sizeof small, 4) != 0) return fail("verbose output with small capture");
    if (strcmp(small, "abc\nabc") != 0) return fail("small capture prefix");
    if (now_run(verbose, NULL, 0, 4) != 0) return fail("verbose output with no capture");

    char *const sleepy[] = {"/bin/sh", "-c", "exec sleep 2", NULL};
    if (now_run(sleepy, NULL, 0, 1) != -1) return fail("command timeout");
    if (now_run(ok, NULL, 0, 0) != -1) return fail("invalid zero timeout");


    puts("Process helpers: capture, large output, timeout, status and lookup verified.");
    return 0;
}
