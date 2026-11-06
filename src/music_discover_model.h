#ifndef OPTIPLEX_NOW_MUSIC_DISCOVER_MODEL_H
#define OPTIPLEX_NOW_MUSIC_DISCOVER_MODEL_H

#include <glib.h>

/* Pure local Discover recommendation data. UI widgets, user actions, player,
 * acquisition and network credentials remain exclusively in ui_music.c. */
typedef struct {
    char *kind, *id, *title, *artist, *cover;
    int category;
} MusicDiscoverEntry;

typedef struct {
    char *title, *description;
} MusicDiscoverShelf;

enum { DISC_FOR_YOU, DISC_NEW_ARTISTS, DISC_FRESH, DISC_GENRES,
       DISC_EXPLORE, DISC_TRENDING, DISC_GROUPS, DISC_DYNAMIC_START=DISC_GROUPS,
       DISC_MAX_DYNAMIC=4 };

void now_music_discover_entry_free(gpointer data);
void now_music_discover_shelf_free(gpointer data);

/* Shared strict, size-bounded base64 protocol decoder for Music replies. */
char *now_music_discover_decode_field(const char *encoded);
int now_music_discover_group_for(const char *key);

/* Modifies the two existing GPtrArray models and *building only. Arrays
 * must own their entries via the free functions above. No UI or requests. */
int now_music_discover_parse(const char *output, GPtrArray *entries,
                             GPtrArray *shelves, gboolean *building);

#endif
