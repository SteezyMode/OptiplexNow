#define _GNU_SOURCE
#include "instance_lock.h"
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void)
{
    char dir[] = "/tmp/now-instance-XXXXXX";
    assert(mkdtemp(dir) != NULL);
    assert(setenv("XDG_RUNTIME_DIR", dir, 1) == 0);

    char path[PATH_MAX];
    assert(snprintf(path, sizeof path, "%s/optiplex-now.lock", dir)
           < (int)sizeof path);

    /* O_NOFOLLOW: a user-supplied symlink is never an instance lock. */
    assert(symlink("/dev/null", path) == 0);
    assert(now_instance_claim() == -1);
    assert(unlink(path) == 0);

    /* First instance takes the exclusive lock and writes its own PID. */
    assert(now_instance_claim() == 1);
    FILE *f = fopen(path, "r");
    assert(f != NULL);
    long stored_pid = 0;
    assert(fscanf(f, "%ld", &stored_pid) == 1);
    assert(fclose(f) == 0);
    assert(stored_pid == (long)getpid());

    /* A second process must not spawn another UI; it signals the first. */
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        _exit(now_instance_claim() == 0 ? 0 : 10);
    }
    int status = 0;
    pid_t waited;
    do {
        waited = waitpid(child, &status, 0);
    } while (waited == -1 && errno == EINTR);
    assert(waited == child);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    assert(now_instance_reopen_pending() == 1);
    assert(now_instance_reopen_pending() == 0);

    assert(unlink(path) == 0);
    assert(rmdir(dir) == 0);
    puts("instance lock: singleton, symlink rejection, and reopen signal OK");
    return 0;
}
