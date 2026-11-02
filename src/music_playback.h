#ifndef NOW_MUSIC_PLAYBACK_H
#define NOW_MUSIC_PLAYBACK_H

#include <glib.h>

typedef struct NowMusicPlayback NowMusicPlayback;
typedef void (*NowMusicPlaybackEvent)(const char *event, void *user_data);

/* One local NOW playback session at a time. Worker holds a short-lived user
 * credential via stdin; mpv receives decoded audio only and never a URL/key.
 * Events arrive on the main GTK context; only caller owns the UI/queue.
 */
NowMusicPlayback *now_music_playback_new(NowMusicPlaybackEvent cb,
                                        void *user_data);
gboolean now_music_playback_start(NowMusicPlayback *playback,
                                  const char *server, const char *username,
                                  const char *app_password, const char *track_id);
void now_music_playback_pause(NowMusicPlayback *playback, gboolean paused);
void now_music_playback_stop(NowMusicPlayback *playback);
gboolean now_music_playback_active(const NowMusicPlayback *playback);
void now_music_playback_free(NowMusicPlayback *playback);

#endif
