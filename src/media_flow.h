#ifndef NOW_MEDIA_FLOW_H
#define NOW_MEDIA_FLOW_H
/* The host supplies a bounded, host-bound Jellyfin endpoint; callbacks decide
 * whether to embed or use the desktop browser. No auth/cookie bypass. */
void now_media_bind(void (*status)(const char *),
                    void (*browser_open)(const char *),
                    void (*in_app_open)(const char *));
void now_media_open_videos(void);        /* External browser: legacy tray path */
void now_media_open_videos_in_app(void); /* Explicit embedded-player request */
#endif
