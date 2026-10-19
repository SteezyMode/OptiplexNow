#define _GNU_SOURCE
#include "process.h"

#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* Run a subprocess with bounded output and a timeout. No shell expansion. */
int now_run(char *const argv[], char *out, size_t cap, int timeout) {
    if (out && cap) {
        out[0] = '\0';
    }
    if (!argv || !argv[0]) {
        return -1;
    }

    int fd[2];
    if (pipe(fd) != 0) {
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
        dup2(fd[1], STDOUT_FILENO);
        dup2(fd[1], STDERR_FILENO);
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
    fcntl(fd[0], F_SETFL, fcntl(fd[0], F_GETFL) | O_NONBLOCK);
    int status = 0, done = 0;
    size_t used = 0;
    long max_ticks = (long)timeout * 10;

    for (long n = 0; n < max_ticks; n++) {
        if (out && used + 1 < cap) {
            ssize_t k = read(fd[0], out + used, cap - used - 1);
            if (k > 0) {
                used += (size_t)k;
                out[used] = '\0';
            }
        }
        pid_t r = waitpid(pid, &status, WNOHANG);
        if (r == pid) {
            done = 1;
            break;
        }
        if (r < 0) {
            break;
        }
        usleep(100000);
    }

    if (!done) {
        kill(pid, SIGKILL);
        waitpid(pid, &status, 0);
    }
    if (out && used + 1 < cap) {
        ssize_t k = read(fd[0], out + used, cap - used - 1);
        if (k > 0) {
            used += (size_t)k;
            out[used] = '\0';
        }
    }
    close(fd[0]);
    return done && WIFEXITED(status) ? WEXITSTATUS(status) : -1;
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
