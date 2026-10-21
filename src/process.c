#define _GNU_SOURCE
#include "process.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Use monotonic time so clock adjustments cannot extend command timeouts. */
static long long monotonic_ms(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        return -1;
    }
    return (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

/* Run a subprocess with bounded captured output and a wall-clock timeout.
 * Always drain its stdout/stderr pipe, including when the caller does not
 * request output or the capture buffer is full. Otherwise a verbose child
 * can block on a full pipe until the timeout.
 */
int now_run(char *const argv[], char *out, size_t cap, int timeout) {
    if (out && cap) {
        out[0] = '\0';
    }
    if (!argv || !argv[0] || timeout <= 0) {
        return -1;
    }

    long long started = monotonic_ms();
    if (started < 0) {
        return -1;
    }
    long long deadline = started + (long long)timeout * 1000;
    int fd[2];
    if (pipe2(fd, O_CLOEXEC) != 0) {
        return -1;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(fd[0]);
        close(fd[1]);
        return -1;
    }
    if (pid == 0) {
        close(fd[0]);
        if (dup2(fd[1], STDOUT_FILENO) < 0 ||
            dup2(fd[1], STDERR_FILENO) < 0) {
            _exit(127);
        }
        close(fd[1]);
        int nullfd = open("/dev/null", O_RDONLY);
        if (nullfd >= 0) {
            dup2(nullfd, STDIN_FILENO);
            close(nullfd);
        }
        execvp(argv[0], argv);
        _exit(127);
    }

    close(fd[1]);
    int flags = fcntl(fd[0], F_GETFL);
    if (flags < 0 || fcntl(fd[0], F_SETFL, flags | O_NONBLOCK) < 0) {
        kill(pid, SIGKILL);
        while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {}
        close(fd[0]);
        return -1;
    }

    int status = 0, done = 0, failed = 0, eof = 0, timed_out = 0;
    size_t used = 0;
    for (;;) {
        /* Drain everything already available without blocking, even if
         * the output buffer cannot accept any additional bytes.
         */
        while (!eof) {
            char chunk[8192];
            ssize_t got = read(fd[0], chunk, sizeof chunk);
            if (got > 0) {
                if (out && cap && used < cap - 1) {
                    size_t available = cap - used - 1;
                    size_t take = (size_t)got < available ? (size_t)got : available;
                    memcpy(out + used, chunk, take);
                    used += take;
                    out[used] = '\0';
                }
                if (monotonic_ms() >= deadline) {
                    break;
                }
                continue;
            }
            if (got == 0) {
                eof = 1;
                break;
            }
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                break;
            }
            if (errno == EINTR) {
                continue;
            }
            failed = 1;
            break;
        }

        /* The child may exit before its buffered pipe output is readable.
         * Do not return until both the exit status and pipe EOF are seen.
         * Never call waitpid again after the child has been reaped.
         */
        if (!done) {
            pid_t reaped;
            do {
                reaped = waitpid(pid, &status, WNOHANG);
            } while (reaped < 0 && errno == EINTR);
            if (reaped == pid) {
                done = 1;
            } else if (reaped < 0) {
                failed = 1;
            }
        }
        if (failed || (done && eof)) {
            break;
        }

        long long remaining = deadline - monotonic_ms();
        if (remaining <= 0) {
            timed_out = 1;
            break;
        }
        int tick = remaining < 100 ? (int)remaining : 100;
        if (eof) {
            struct timespec nap = {.tv_sec = 0, .tv_nsec = tick * 1000000L};
            nanosleep(&nap, NULL);
        } else {
            struct pollfd ready = {.fd = fd[0], .events = POLLIN};
            if (poll(&ready, 1, tick) < 0 && errno != EINTR) {
                failed = 1;
                break;
            }
        }
    }
    if (!done) {
        kill(pid, SIGKILL);
        while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    }
    close(fd[0]);
    return done && !failed && !timed_out && WIFEXITED(status) ? WEXITSTATUS(status) : -1;
}

/* Double-fork to detach the launch; parent does not block on the program. */
void now_launch(char *const argv[]) {
    if (!argv || !argv[0]) {
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        pid_t nested = fork();
        if (nested > 0) {
            _exit(0);
        }
        int nullfd = open("/dev/null", O_RDWR);
        if (nullfd >= 0) {
            dup2(nullfd, STDIN_FILENO);
            dup2(nullfd, STDOUT_FILENO);
            dup2(nullfd, STDERR_FILENO);
            close(nullfd);
        }
        execvp(argv[0], argv);
        _exit(127);
    }
    if (pid > 0) {
        waitpid(pid, NULL, 0);
    }
}

/* Require the complete resolved path to fit. Never test truncated paths. */
int now_program_exists(const char *name) {
    if (!name || !*name) {
        return 0;
    }
    if (strchr(name, '/')) {
        return access(name, X_OK) == 0;
    }

    const char *path = getenv("PATH");
    if (!path) {
        return 0;
    }
    char *dup = strdup(path);
    if (!dup) {
        return 0;
    }
    char *save = NULL;
    int found = 0;
    for (char *p = strtok_r(dup, ":", &save); p; p = strtok_r(NULL, ":", &save)) {
        char file[PATH_MAX];
        int n = snprintf(file, sizeof file, "%s/%s", p, name);
        if (n > 0 && (size_t)n < sizeof file && access(file, X_OK) == 0) {
            found = 1;
            break;
        }
    }
    free(dup);
    return found;
}
