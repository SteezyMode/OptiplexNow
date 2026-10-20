#include "process.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <unistd.h>

static int fail(const char *reason) {
    fprintf(stderr, "process helper test failed: %s\n", reason);
    return 1;
}

/* Exercise exactly the command lookup NOW uses with GUI environments that
 * omit /snap/bin, without touching real system Snap installations. */
static int test_resolve_moonlight(void) {
    const char *name = "now-test-moonlight-lookup";
    char folder[] = "/tmp/now-moonlight-XXXXXX";
    if (!mkdtemp(folder)) return fail("cannot create lookup fixture");
    char path_command[PATH_MAX], fallback[PATH_MAX], actual[PATH_MAX];
    snprintf(path_command, sizeof path_command, "%s/%s", folder, name);
    snprintf(fallback, sizeof fallback, "%s/fallback", folder);
    if (symlink("/bin/sh", path_command) || symlink("/bin/sh", fallback)) {
        return fail("cannot create lookup executables");
    }
    const char *oldpath = getenv("PATH");
    char *saved = oldpath ? strdup(oldpath) : NULL;
    int failed = 0;
    if (setenv("PATH", folder, 1)) failed = 1;
    if (!failed && (!now_resolve_executable(name, fallback, actual, sizeof actual)
            || strcmp(actual, path_command))) failed = 2;
    if (!failed && setenv("PATH", "/this-directory-does-not-exist", 1)) failed = 3;
    if (!failed && (!now_resolve_executable(name, fallback, actual, sizeof actual)
            || strcmp(actual, fallback))) failed = 4;
    if (!failed && (now_resolve_executable(name, fallback, actual, 2)
            || actual[0] != '\0')) failed = 5;
    if (!failed && (now_resolve_executable(name, "/not/a/real/moonlight", actual, sizeof actual)
            || actual[0] != '\0')) failed = 6;
    if (!failed && now_resolve_executable("../unsafe", fallback, actual, sizeof actual)) failed = 7;
    if (!failed && now_resolve_executable(name, "relative/fallback", actual, sizeof actual)) failed = 8;
    if (!failed && now_resolve_executable(NULL, fallback, actual, sizeof actual)) failed = 9;
    if (saved) setenv("PATH", saved, 1);
    else unsetenv("PATH");
    free(saved);
    unlink(path_command);
    unlink(fallback);
    rmdir(folder);
    if (failed) {
        char reason[80];
        snprintf(reason, sizeof reason, "executable path / Snap fallback case %d", failed);
        return fail(reason);
    }
    return 0;
}

int main(void) {
    char output[80] = {0};
    char *const ok[] = {"/bin/sh", "-c", "printf hello", NULL};
    char *const nonzero[] = {"/bin/sh", "-c", "exit 7", NULL};

    if (test_resolve_moonlight()) return 1;
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
