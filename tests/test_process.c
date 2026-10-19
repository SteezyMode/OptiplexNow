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
    if (now_program_exists("/nonexistent/optiplex-now-test-exec")) return fail("missing executable");

    if (now_run(ok, output, sizeof output, 3) != 0) return fail("successful exit code");
    if (strcmp(output, "hello") != 0) return fail("captured stdout");
    if (now_run(nonzero, NULL, 0, 3) != 7) return fail("nonzero exit code");

    puts("Process helpers: exit status, stdout capture, executable search verified.");
    return 0;
}
