#define _GNU_SOURCE
#include "tray_prefs.h"

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *const service_names[NOW_TRAY_ACTIONS] = {
    "Games", "Videos", "Music", "Files", "Downloads", "Terminal",
    "Desktop", "Web Gaming"
};
static const char *const service_descriptions[NOW_TRAY_ACTIONS] = {
    "Steam", "Jellyfin", "Dropped Needle", "SFTP", "VueTorrent", "SSH",
    "", "Wolf UI"
};

unsigned now_tray_parse_mask(const char *value)
{
    if (!value || !*value || value[0] == '-' || value[0] == '+') {
        return NOW_TRAY_DEFAULT_MASK;
    }
    char *end = NULL;
    errno = 0;
    unsigned long parsed = strtoul(value, &end, 10);
    if (errno || end == value || *end || parsed > NOW_TRAY_DEFAULT_MASK) {
        return NOW_TRAY_DEFAULT_MASK;
    }
    return (unsigned)parsed;
}

static void default_order(int order[NOW_TRAY_ACTIONS])
{
    for (int i = 0; i < NOW_TRAY_ACTIONS; ++i) {
        order[i] = i;
    }
}

int now_tray_parse_order(const char *text, int order[NOW_TRAY_ACTIONS])
{
    if (!order) {
        return 0;
    }
    default_order(order);
    if (!text) {
        return 0;
    }

    size_t len = strlen(text);
    if (len && text[len - 1] == '\n') {
        --len;
    }
    if (len && text[len - 1] == '\r') {
        --len;
    }
    if (len != NOW_TRAY_ACTIONS) {
        return 0;
    }

    unsigned seen = 0;
    int parsed[NOW_TRAY_ACTIONS];
    for (int i = 0; i < NOW_TRAY_ACTIONS; ++i) {
        char digit = text[i];
        if (digit < '0' || digit >= '0' + NOW_TRAY_ACTIONS) {
            return 0;
        }
        int id = digit - '0';
        if (seen & (1u << id)) {
            return 0;
        }
        parsed[i] = id;
        seen |= 1u << id;
    }
    if (seen != NOW_TRAY_DEFAULT_MASK) {
        return 0;
    }
    memcpy(order, parsed, sizeof parsed);
    return 1;
}

/* Tray ordering already uses XDG_CONFIG_HOME; preserve that contract. */
static int tray_order_path(char *out, size_t size)
{
    const char *xdg = getenv("XDG_CONFIG_HOME");
    const char *home = getenv("HOME");
    int written;
    if (xdg && *xdg) {
        written = snprintf(out, size, "%s/optiplex-desk/tray-order", xdg);
    } else if (home && *home) {
        written = snprintf(out, size, "%s/.config/optiplex-desk/tray-order", home);
    } else {
        return 0;
    }
    return written > 0 && (size_t)written < size;
}

/* The caption was historically saved below HOME even with XDG set. */
static int desktop_label_path(char *out, size_t size)
{
    const char *home = getenv("HOME");
    if (!home || !*home) {
        return 0;
    }
    int written = snprintf(out, size, "%s/.config/optiplex-desk/desktop-label", home);
    return written > 0 && (size_t)written < size;
}

/* Videos is a per-device preference, not part of portable host presets.
 * Do not create a second config directory: reuse legacy tray settings. */
static int videos_tray_path(char *out,size_t size){
 const char *xdg=getenv("XDG_CONFIG_HOME");
 const char *home=getenv("HOME");
 int written;
 if(xdg && *xdg)
   written=snprintf(out,size,"%s/optiplex-desk/videos-tray-target",xdg);
 else if(home && *home)
   written=snprintf(out,size,"%s/.config/optiplex-desk/videos-tray-target",home);
 else return 0;
 return written>0 && (size_t)written<size;
}

/* Write a per-user preference without exposing partially written values. */
static int atomic_private_write(const char *path, const char *data, size_t length)
{
    char temporary[PATH_MAX];
    int used = snprintf(temporary, sizeof temporary, "%s.tmp.XXXXXX", path);
    if (used <= 0 || (size_t)used >= sizeof temporary) {
        return 0;
    }
    int fd = mkstemp(temporary);
    if (fd < 0) {
        return 0;
    }
    int ok = fchmod(fd, 0600) == 0;
    size_t offset = 0;
    while (ok && offset < length) {
        ssize_t written = write(fd, data + offset, length - offset);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            ok = 0;
            break;
        }
        offset += (size_t)written;
    }
    if (ok && fsync(fd) != 0) {
        ok = 0;
    }
    if (close(fd) != 0) {
        ok = 0;
    }
    if (ok && rename(temporary, path) == 0) {
        return 1;
    }
    unlink(temporary);
    return 0;
}

int now_tray_videos_open_in_app(void){
 char path[PATH_MAX],value[32];
 if(!videos_tray_path(path,sizeof path))return 0;
 FILE *file=fopen(path,"r");
 if(!file)return 0;
 char *read=fgets(value,sizeof value,file);
 fclose(file);
 return read && (!strcmp(value,"app\\n") || !strcmp(value,"app"));
}

int now_tray_videos_set_open_in_app(int enabled){
 char path[PATH_MAX];
 if(!videos_tray_path(path,sizeof path))return 0;
 const char *value=enabled?"app\\n":"browser\\n";
 return atomic_private_write(path,value,strlen(value));
}

void now_tray_order_load(int order[NOW_TRAY_ACTIONS])
{
    if (!order) {
        return;
    }
    default_order(order);

    char path[PATH_MAX], buffer[64];
    if (!tray_order_path(path, sizeof path)) {
        return;
    }
    FILE *file = fopen(path, "r");
    if (!file) {
        return;
    }
    char *text = fgets(buffer, sizeof buffer, file);
    fclose(file);
    if (text) {
        now_tray_parse_order(text, order);
    }
}

int now_tray_order_save(const int order[NOW_TRAY_ACTIONS])
{
    if (!order) {
        return 0;
    }
    char encoded[NOW_TRAY_ACTIONS + 2];
    unsigned seen = 0;
    for (int i = 0; i < NOW_TRAY_ACTIONS; ++i) {
        int id = order[i];
        if (id < 0 || id >= NOW_TRAY_ACTIONS || (seen & (1u << id))) {
            return 0;
        }
        seen |= 1u << id;
        encoded[i] = (char)('0' + id);
    }
    encoded[NOW_TRAY_ACTIONS] = '\n';
    encoded[NOW_TRAY_ACTIONS + 1] = '\0';

    char path[PATH_MAX];
    if (!tray_order_path(path, sizeof path)) {
        return 0;
    }
    return atomic_private_write(path, encoded, sizeof encoded - 1);
}

void now_tray_desktop_caption(char *out, size_t capacity)
{
    if (!out || capacity == 0) {
        return;
    }
    snprintf(out, capacity, "XFCE");
    char path[PATH_MAX], buffer[128];
    if (!desktop_label_path(path, sizeof path)) {
        return;
    }
    FILE *file = fopen(path, "r");
    if (!file) {
        return;
    }
    char *line = fgets(buffer, sizeof buffer, file);
    fclose(file);
    if (!line) {
        return;
    }
    buffer[strcspn(buffer, "\r\n")] = '\0';
    size_t length = strlen(buffer);
    if (length == 0 || length > 48) {
        return;
    }
    for (size_t i = 0; i < length; ++i) {
        if ((unsigned char)buffer[i] < 32 || (unsigned char)buffer[i] == 127) {
            return;
        }
    }
    snprintf(out, capacity, "%s", buffer);
}

int now_tray_desktop_caption_save(const char *value)
{
    if (!value) {
        return 0;
    }
    size_t length = strlen(value);
    if (length > 48) {
        return 0;
    }
    for (size_t i = 0; i < length; ++i) {
        if ((unsigned char)value[i] < 32 || (unsigned char)value[i] == 127) {
            return 0;
        }
    }
    char path[PATH_MAX];
    if (!desktop_label_path(path, sizeof path)) {
        return 0;
    }
    char encoded[50];
    memcpy(encoded, value, length);
    encoded[length] = '\n';
    return atomic_private_write(path, encoded, length + 1);
}

const char *now_tray_service_name(int index)
{
    return index >= 0 && index < NOW_TRAY_ACTIONS ? service_names[index] : NULL;
}

int now_tray_service_caption(int index, const char *desktop, char *out,
                             size_t capacity)
{
    if (index < 0 || index >= NOW_TRAY_ACTIONS || !out || capacity == 0) {
        return 0;
    }
    const char *detail = index == 6 ? desktop : service_descriptions[index];
    if (!detail || !*detail) {
        detail = "XFCE";
    }
    int used = snprintf(out, capacity, "%s — %s", service_names[index], detail);
    return used > 0 && (size_t)used < capacity;
}
