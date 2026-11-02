/* Optional Bruiser Music native library browser (pre-player vertical slice).
 * The goal is a familiar first-party library UI without copying DroppedNeedle
 * admin pages or storing its administrator credentials. All requests are async.
 * Playback is intentionally not claimed until stream/queue/tray tests pass.
 */
#define _GNU_SOURCE
#include "ui_music.h"
#include "config.h"
#include "music_playback.h"
#include <gio/gio.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

typedef struct {
 char *id, *title, *artist, *album, *cover_id;
 gboolean liked;
} MusicTrack;
static void track_free(gpointer data){
 MusicTrack *t=data;
 if(!t)return;
 g_free(t->id);g_free(t->title);g_free(t->artist);g_free(t->album);g_free(t->cover_id);g_free(t);
}
static MusicTrack *track_copy(const MusicTrack *source){
 MusicTrack *t=g_new0(MusicTrack,1);
 t->id=g_strdup(source->id);
 t->title=g_strdup(source->title);
 t->artist=g_strdup(source->artist);
 t->album=g_strdup(source->album);
 t->liked=source->liked;
 t->cover_id=g_strdup(source->cover_id);
 return t;
}
typedef struct {
 GtkWidget *root, *status, *heading, *list, *password, *search, *connect_panel;
 GtkWidget *player_bar, *playing_label, *playing_artist_label, *pause_button, *previous_button, *next_button, *shuffle_button, *volume_slider, *seek_slider, *seek_caption;
 GtkWidget *hero_row, *hero_art, *hero_title, *hero_play, *playing_art, *load_more, *load_more_songs, *shuffle_all;
 GtkWidget *cards, *cards_scroll, *list_scroll, *active_nav;
 GQueue *pending_art;
 guint art_inflight;
 GPtrArray *visible_tracks, *queue;
 GHashTable *album_buttons; /* Borrowed GTK pointers, cleared before each view refresh */
 NowMusicPlayback *playback;
 int queue_index, album_offset, song_offset, volume;
 guint volume_debounce, seek_debounce, play_duration, status_timer;
 gboolean paused, seek_updating, seek_dragging, status_inflight;
 char *playing_caption;
 guint64 hero_art_serial, playing_art_serial, card_art_serial;
 guint card_art_count;
 gboolean grid_mode, shuffle_enabled;
 GArray *shuffle_order;
 guint shuffle_cursor;
 void (*tray_changed)(void);
 char *username, *app_password, *bound_url, *vault_attempted_url;
 gboolean busy, closing, vault_busy, remember_pending;
 gboolean auto_enroll_busy, auto_enroll_attempted;
 void (*open_url)(const char *);
 void (*open_settings)(void *, void *);
} MusicView;

typedef struct {
 GtkWidget *root;            /* strong reference: completion sees view state */
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
 char *operation;
 char *heading;
 gboolean append_albums, append_songs;
 int offset;
 char *input;                /* securely wiped on completion */
} MusicQuery;

static MusicView *active_music_view=NULL;
static void music_stop(MusicView *view);
static void music_start_track(MusicView *view,int index);
static void music_art_start(MusicView *view,const char *cover_id,gboolean playing);
static void music_refresh_status(MusicView *view);
static void music_next_clicked(GtkWidget *unused,gpointer data);
static void music_play_visible(MusicView *view,int index);
static void music_notify_tray(MusicView *view);
static void music_card_queue_pump(MusicView *view);
static gboolean music_status_tick(gpointer data);

static void wipe_free(char *value){
 if(!value)return;
 volatile char *ptr=(volatile char *)value;
 size_t len=strlen(value);
 while(len--)*ptr++=0;
 g_free(value);
}

typedef struct {
 char *cover_id;
 GtkWidget *image;
 guint64 serial;
} MusicPendingArt;
static void music_pending_free(gpointer data){
 MusicPendingArt *p=data;
 if(!p)return;
 g_free(p->cover_id);
 g_clear_object(&p->image);
 g_free(p);
}
static void music_pending_clear(MusicView *view){
 if(view->pending_art)g_queue_clear_full(view->pending_art,music_pending_free);
}
static void music_view_destroy(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 view->closing=TRUE;
 music_pending_clear(view);
 if(view->volume_debounce)g_source_remove(view->volume_debounce);
 if(view->seek_debounce)g_source_remove(view->seek_debounce);
 if(view->status_timer)g_source_remove(view->status_timer);
 view->status_timer=0;
 view->volume_debounce=view->seek_debounce=0;
 if(active_music_view==view)active_music_view=NULL;
 if(view->playback){
  now_music_playback_free(view->playback);
  view->playback=NULL;
 }
 wipe_free(view->app_password);
 view->app_password=NULL;
}

static void music_view_free(gpointer data){
 MusicView *view=data;
 wipe_free(view->app_password);
 g_free(view->username);
 g_free(view->bound_url);
 g_free(view->vault_attempted_url);
 g_free(view->playing_caption);
 if(view->visible_tracks)g_ptr_array_unref(view->visible_tracks);
 if(view->queue)g_ptr_array_unref(view->queue);
 if(view->shuffle_order)g_array_unref(view->shuffle_order);
 if(view->album_buttons)g_hash_table_destroy(view->album_buttons);
 if(view->pending_art)g_queue_free_full(view->pending_art,music_pending_free);
 g_free(view);
}

static void status_set(MusicView *view,const char *message){
 if(!view->closing && GTK_IS_LABEL(view->status))
  gtk_label_set_text(GTK_LABEL(view->status),message);
}

static char *helper_path(void){
 /* The package ships its own exact, tested helper; do not execute an
  * arbitrary relative file on a deployed client. Source checkouts may use
  * the local module for developer builds only. */
 gchar *exe=g_file_read_link("/proc/self/exe",NULL);
 if(exe && g_str_has_prefix(exe,"/usr/bin/")){
  g_free(exe);
  return g_strdup("/usr/lib/optiplex-now/music_subsonic.py");
 }
 g_free(exe);
 if(g_file_test("src/music_subsonic.py",G_FILE_TEST_IS_REGULAR))
  return g_strdup("src/music_subsonic.py");
 return g_strdup("/usr/lib/optiplex-now/music_subsonic.py");
}

static char *decode_field(const char *encoded){
 if(!encoded || strlen(encoded)>16384)return NULL;
 gsize len=0;
 guchar *decoded=g_base64_decode(encoded,&len);
 if(!decoded || len>4096 || memchr(decoded,0,len)){
  g_free(decoded);
  return NULL;
 }
 if(!g_utf8_validate((char*)decoded,(gssize)len,NULL)){
  g_free(decoded);
  return NULL;
 }
 char *answer=g_strndup((char*)decoded,len);
 g_free(decoded);
 return answer;
}

static void query_start(MusicView *view,const char *operation,
                        const char *value,const char *heading);
static void music_vault_begin(MusicView *view,const char *action,
                              const char *input);
static void music_auto_enroll(MusicView *view);

/* Shuffle is a permutation of the current queue, without repeats. */
static void music_shuffle_reset(MusicView *view,int start){
 if(!view->shuffle_order)view->shuffle_order=g_array_new(FALSE,FALSE,sizeof(guint));
 g_array_set_size(view->shuffle_order,0);
 if(start<0 || start>=(int)view->queue->len)return;
 guint first=(guint)start;
 g_array_append_val(view->shuffle_order,first);
 for(guint i=0;i<view->queue->len;i++){
  if(i!=first)g_array_append_val(view->shuffle_order,i);
 }
 if(view->shuffle_enabled){
  for(guint i=view->shuffle_order->len;i>2;i--){
   guint pick=g_random_int_range(1,i);
   guint tmp=g_array_index(view->shuffle_order,guint,i-1);
   g_array_index(view->shuffle_order,guint,i-1)=g_array_index(view->shuffle_order,guint,pick);
   g_array_index(view->shuffle_order,guint,pick)=tmp;
  }
 }
 view->shuffle_cursor=0;
}
static int music_next_queue_index(MusicView *view){
 if(!view->queue || view->queue_index<0)return -1;
 if(view->shuffle_enabled){
  if(!view->shuffle_order || view->shuffle_cursor+1>=view->shuffle_order->len)return -1;
  return (int)g_array_index(view->shuffle_order,guint,view->shuffle_cursor+1);
 }
 return view->queue_index+1<(int)view->queue->len?view->queue_index+1:-1;
}
static int music_previous_queue_index(MusicView *view){
 if(view->queue_index<0)return -1;
 if(view->shuffle_enabled && view->shuffle_order && view->shuffle_cursor>0)
  return (int)g_array_index(view->shuffle_order,guint,view->shuffle_cursor-1);
 return MAX(0,view->queue_index-1);
}
static GtkWidget *music_icon_button(const char *icon,const char *tooltip){
 GtkWidget *button=gtk_button_new_from_icon_name(icon,GTK_ICON_SIZE_BUTTON);
 gtk_style_context_add_class(gtk_widget_get_style_context(button),"music-transport");
 gtk_widget_set_tooltip_text(button,tooltip);
 gtk_widget_set_size_request(button,38,38);
 return button;
}
static void music_shuffle_clicked(GtkToggleButton *button,gpointer data){
 MusicView *view=data;
 view->shuffle_enabled=gtk_toggle_button_get_active(button);
 if(view->queue_index>=0)music_shuffle_reset(view,view->queue_index);
 gtk_widget_set_tooltip_text(GTK_WIDGET(button),view->shuffle_enabled?
     "Shuffle on":"Shuffle off");
 music_notify_tray(view);
}

static void music_notify_tray(MusicView *view){
 if(view->tray_changed)view->tray_changed();
}
static void music_update_controls(MusicView *view){
 if(!view->player_bar)return;
 gboolean active=view->playback && now_music_playback_active(view->playback);
 if(!active){
  gtk_widget_hide(view->player_bar);
  music_notify_tray(view);
  return;
 }
 MusicTrack *current=(view->queue_index>=0 &&
     view->queue_index<(int)view->queue->len)
    ?g_ptr_array_index(view->queue,view->queue_index):NULL;
 gtk_label_set_text(GTK_LABEL(view->playing_label),
     current?current->title:"Now playing");
 if(view->playing_artist_label){
  char *by=current && current->album && *current->album
      ?g_strdup_printf("%s · %s",current->artist,current->album)
      :g_strdup(current?current->artist:"");
  gtk_label_set_text(GTK_LABEL(view->playing_artist_label),by);
  g_free(by);
 }
 gtk_button_set_image(GTK_BUTTON(view->pause_button),
       gtk_image_new_from_icon_name(view->paused?
          "media-playback-start-symbolic":"media-playback-pause-symbolic",
          GTK_ICON_SIZE_BUTTON));
 gtk_widget_set_tooltip_text(view->pause_button,view->paused?"Play":"Pause");
 gtk_widget_set_sensitive(view->previous_button,TRUE);
 if(view->seek_slider)
  gtk_widget_set_sensitive(view->seek_slider,view->play_duration>0);
 gtk_widget_set_sensitive(view->next_button,
                  music_next_queue_index(view)>=0);
 gtk_widget_show(view->player_bar);
 music_notify_tray(view);
}
static void music_update_position(MusicView *view,unsigned position,unsigned duration){
 if(!view->seek_slider || !view->seek_caption)return;
 view->play_duration=duration;
 gtk_widget_set_sensitive(view->seek_slider,duration>0);
 if(!view->seek_dragging){
  view->seek_updating=TRUE;
  gtk_range_set_range(GTK_RANGE(view->seek_slider),0,duration);
  gtk_range_set_value(GTK_RANGE(view->seek_slider),position);
  view->seek_updating=FALSE;
 }
 char *label=g_strdup_printf("%u:%02u / %u:%02u",
      position/60,position%60,duration/60,duration%60);
 gtk_label_set_text(GTK_LABEL(view->seek_caption),label);
 g_free(label);
}
static void music_stop(MusicView *view){
 if(view->playback)now_music_playback_stop(view->playback);
 view->queue_index=-1;
 view->paused=FALSE;
 view->play_duration=0;
 if(view->seek_debounce)g_source_remove(view->seek_debounce);
 view->seek_debounce=0;
 if(view->seek_slider)music_update_position(view,0,0);
 g_clear_pointer(&view->playing_caption,g_free);
 view->playing_art_serial++;
 if(!view->closing){
  if(view->player_bar)gtk_widget_hide(view->player_bar);
  status_set(view,"Playback stopped.");
  music_notify_tray(view);
 }
}
static void music_player_event(const char *event,void *data){
 MusicView *view=data;
 if(view->closing)return;
 if(g_str_has_prefix(event,"POSITION ")){
  unsigned pos=0,duration=0;
  if(sscanf(event,"POSITION %u %u",&pos,&duration)==2 && duration>0 &&
     pos<=duration && duration<=604800)
   music_update_position(view,pos,duration);
  return;
 }
 if(!strcmp(event,"SEEK_UNAVAILABLE")){
  status_set(view,"This track cannot be scrubbed on this server.");
  return;
 }
 if(!strcmp(event,"ENDED")){
  music_next_clicked(NULL,view);
  return;
 }
 if(!strcmp(event,"ERROR") || !strcmp(event,"STOPPED")){
  music_stop(view);
  status_set(view,"Playback stopped or failed. Check audio output and mpv installation.");
  return;
 }
 if(!strcmp(event,"PAUSED"))view->paused=TRUE;
 else if(!strcmp(event,"PLAYING"))view->paused=FALSE;
 if(!strcmp(event,"BUFFERING"))status_set(view,"Buffering music...");
 else if(!strcmp(event,"PAUSED"))status_set(view,"Music paused.");
 else if(!strcmp(event,"PLAYING"))status_set(view,"Playing music locally.");
 music_update_controls(view);
}
static void music_start_track(MusicView *view,int index){
 if(view->closing || index<0 || index>=(int)view->queue->len)return;
 if(!view->app_password || !view->bound_url ||
    g_strcmp0(view->bound_url,cfg[6])!=0){
  music_stop(view);
  status_set(view,"Reconnect to your approved music server.");
  return;
 }
 MusicTrack *song=g_ptr_array_index(view->queue,index);
 if(!now_music_playback_start(view->playback,view->bound_url,
                             view->username,view->app_password,song->id,view->volume)){
  music_stop(view);
  status_set(view,"Cannot start local audio. Check music helper and mpv installation.");
  return;
 }
 view->queue_index=index;
 view->paused=FALSE;
 view->play_duration=0;
 if(view->seek_debounce)g_source_remove(view->seek_debounce);
 view->seek_debounce=0;
 if(view->seek_slider)music_update_position(view,0,0);
 g_free(view->playing_caption);
 char *full=g_strdup_printf("%s — %s",song->title,song->artist);
 g_strdelimit(full,"\r\n\t",' ');
 view->playing_caption=g_utf8_substring(full,0,
                            MIN(72,(int)g_utf8_strlen(full,-1)));
 g_free(full);
 status_set(view,"Buffering music...");
 music_art_start(view,song->cover_id,TRUE);
 music_update_controls(view);
}
static void music_prev_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(!view->playback || !now_music_playback_active(view->playback))return;
 int next=music_previous_queue_index(view);
 if(next<0)return;
 if(view->shuffle_enabled && view->shuffle_cursor>0)view->shuffle_cursor--;
 music_start_track(view,next);
}
static void music_next_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(!view->playback || !now_music_playback_active(view->playback))return;
 int next=music_next_queue_index(view);
 if(next>=0){
  if(view->shuffle_enabled)view->shuffle_cursor++;
  music_start_track(view,next);
 }else music_stop(view);
}
static void music_pause_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->playback && now_music_playback_active(view->playback))
  now_music_playback_pause(view->playback,!view->paused);
}
/* Do not block the GTK thread for every slider pixel; throttle IPC. */
static gboolean music_apply_seek(gpointer data){
 MusicView *view=data;
 view->seek_debounce=0;
 if(!view->closing && view->play_duration && view->playback &&
    now_music_playback_active(view->playback) && view->seek_slider){
  int target=CLAMP((int)gtk_range_get_value(GTK_RANGE(view->seek_slider)),
                   0,(int)view->play_duration);
  now_music_playback_seek(view->playback,target);
 }
 return G_SOURCE_REMOVE;
}
static void music_seek_changed(GtkRange *range,gpointer data){
 (void)range;
 MusicView *view=data;
 if(view->closing || view->seek_updating || !view->play_duration)return;
 if(view->seek_debounce)g_source_remove(view->seek_debounce);
 view->seek_debounce=g_timeout_add(350,music_apply_seek,view);
}
static gboolean music_seek_press(GtkWidget *widget,GdkEventButton *event,gpointer data){
 (void)widget;
 MusicView *view=data;
 if(event->button==1)view->seek_dragging=TRUE;
 return FALSE;
}
static gboolean music_seek_release(GtkWidget *widget,GdkEventButton *event,gpointer data){
 (void)widget;
 MusicView *view=data;
 if(event->button==1){
  view->seek_dragging=FALSE;
  if(view->seek_debounce)g_source_remove(view->seek_debounce);
  view->seek_debounce=0;
  music_apply_seek(view);
 }
 return FALSE;
}
static gboolean music_apply_volume(gpointer data){
 MusicView *view=data;
 view->volume_debounce=0;
 if(!view->closing && view->playback &&
    now_music_playback_active(view->playback))
  now_music_playback_volume(view->playback,view->volume);
 return G_SOURCE_REMOVE;
}
static void music_volume_changed(GtkRange *range,gpointer data){
 MusicView *view=data;
 if(view->closing)return;
 view->volume=CLAMP((int)gtk_range_get_value(range),0,100);
 if(view->volume_debounce)g_source_remove(view->volume_debounce);
 view->volume_debounce=g_timeout_add(120,music_apply_volume,view);
}
static void music_stop_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 music_stop(data);
}
/* Tray actions intentionally operate only this local NOW music session.
 * They never reach Amperfy or a remote DroppedNeedle browser instance. */
gboolean now_music_is_playing_session(void){
 return active_music_view && !active_music_view->closing &&
        active_music_view->playback &&
        now_music_playback_active(active_music_view->playback);
}
gboolean now_music_is_paused(void){
 return now_music_is_playing_session() && active_music_view->paused;
}
gboolean now_music_can_next(void){
 return now_music_is_playing_session() &&
    music_next_queue_index(active_music_view)>=0;
}
const char *now_music_caption(void){
 return now_music_is_playing_session() && active_music_view->playing_caption
       ? active_music_view->playing_caption:"Now playing";
}
void now_music_previous(void){
 if(now_music_is_playing_session())music_prev_clicked(NULL,active_music_view);
}
void now_music_toggle_pause(void){
 if(now_music_is_playing_session())music_pause_clicked(NULL,active_music_view);
}
void now_music_next(void){
 if(now_music_is_playing_session())music_next_clicked(NULL,active_music_view);
}

/* Cover artwork is a bounded, authenticated POST through the same helper.
 * Never embed the OpenSubsonic key in a URL, persist artwork to a public
 * cache, or allocate unbounded images from an untrusted media server. */
typedef struct {
 GtkWidget *root;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
 guint64 serial;
 gboolean playing;
 GtkWidget *card_target; /* reference; old cards are ignored after navigation */
 char *server_url;
 char *input; /* wipe after the worker completes */
} MusicArtJob;

static gboolean music_art_timeout(gpointer data){
 MusicArtJob *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}
static void music_art_free(MusicArtJob *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_object_unref(job->cancel);
 g_object_unref(job->process);
 g_object_unref(job->root);
 g_clear_object(&job->card_target);
 wipe_free(job->input);
 g_free(job->server_url);
 g_free(job);
}
static void music_art_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicArtJob *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 GBytes *output=NULL;
 GError *error=NULL;
 gboolean ok=g_subprocess_communicate_finish(job->process,result,&output,NULL,&error);
 if(view && !view->closing &&
    g_strcmp0(job->server_url,view->bound_url)==0 &&
    g_strcmp0(job->server_url,cfg[6])==0 &&
    job->serial==(job->card_target?view->card_art_serial:
        (job->playing?view->playing_art_serial:view->hero_art_serial)) &&
    ok && g_subprocess_get_successful(job->process) && output){
  gsize len=0;
  const guchar *bytes=g_bytes_get_data(output,&len);
  if(len>0 && len<=3*1024*1024){
   GdkPixbufLoader *loader=gdk_pixbuf_loader_new();
   const int pixels=job->card_target?128:(job->playing?44:120);
   gdk_pixbuf_loader_set_size(loader,pixels,pixels);
   gboolean valid=gdk_pixbuf_loader_write(loader,bytes,len,NULL);
   if(valid)valid=gdk_pixbuf_loader_close(loader,NULL);
   if(valid){
    GdkPixbuf *pixbuf=gdk_pixbuf_loader_get_pixbuf(loader);
    if(pixbuf){
     GtkWidget *target=job->card_target?job->card_target:
         (job->playing?view->playing_art:view->hero_art);
     if(target)gtk_image_set_from_pixbuf(GTK_IMAGE(target),pixbuf);
    }
   }
   g_object_unref(loader);
  }
 }
 if(output)g_bytes_unref(output);
 g_clear_error(&error);
 if(job->card_target && view && view->art_inflight>0){
  view->art_inflight--;
  if(!view->closing)music_card_queue_pump(view);
 }
 music_art_free(job);
}
static void music_art_start(MusicView *view,const char *cover_id,gboolean playing){
 if(view->closing)return;
 guint64 serial=playing?++view->playing_art_serial:++view->hero_art_serial;
 GtkWidget *target=playing?view->playing_art:view->hero_art;
 if(target)gtk_image_set_from_icon_name(GTK_IMAGE(target),
                                        "audio-x-generic",GTK_ICON_SIZE_DIALOG);
 if(!cover_id || !*cover_id || strlen(cover_id)>512 ||
    !view->app_password || !view->bound_url ||
    g_strcmp0(cfg[6],view->bound_url)!=0)return;
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  g_free(helper);return;
 }
 const gchar *argv[]={"/usr/bin/python3",helper,view->bound_url,
                      "art",cover_id,"--auth-format=form",NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
    G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
    G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
  g_clear_error(&error);
  return;
 }
 MusicArtJob *job=g_new0(MusicArtJob,1);
 job->process=proc;
 job->root=g_object_ref(view->root);
 job->cancel=g_cancellable_new();
 job->serial=serial;
 job->playing=playing;
 job->server_url=g_strdup(view->bound_url);
 char *key=g_uri_escape_string(view->app_password,NULL,FALSE);
 char *name=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
 job->input=g_strdup_printf("api_key=%s&username=%s",key,name);
 wipe_free(key);g_free(name);
 GBytes *sent=g_bytes_new(job->input,strlen(job->input));
 job->deadline=g_timeout_add_seconds(25,music_art_timeout,job);
 g_subprocess_communicate_async(proc,sent,job->cancel,
                                music_art_complete,job);
 g_bytes_unref(sent);
}

/* Cover art is loaded near the scroll viewport with four concurrent
 * workers. The previous fixed 16-card cutoff left most library cards blank.
 * No artwork requests are made for cards the user never reaches. */
static void music_card_art_launch(MusicView *view,const char *cover_id,
                                  GtkWidget *image){
 if(view->closing || !view->app_password || !view->bound_url ||
    g_strcmp0(cfg[6],view->bound_url)!=0)return;
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){g_free(helper);return;}
 const char *argv[]={"/usr/bin/python3",helper,view->bound_url,
                     "art",cover_id,"--auth-format=form",NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
     G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
     G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){g_clear_error(&error);return;}
 MusicArtJob *job=g_new0(MusicArtJob,1);
 job->process=proc;
 job->root=g_object_ref(view->root);
 job->card_target=g_object_ref(image);
 job->cancel=g_cancellable_new();
 job->serial=view->card_art_serial;
 job->server_url=g_strdup(view->bound_url);
 char *key=g_uri_escape_string(view->app_password,NULL,FALSE);
 char *name=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
 job->input=g_strdup_printf("api_key=%s&username=%s",key,name);
 wipe_free(key);g_free(name);
 GBytes *sent=g_bytes_new(job->input,strlen(job->input));
 job->deadline=g_timeout_add_seconds(25,music_art_timeout,job);
 view->art_inflight++;
 g_subprocess_communicate_async(proc,sent,job->cancel,music_art_complete,job);
 g_bytes_unref(sent);
}
static void music_card_art_start(MusicView *view,const char *cover_id,
                                 GtkWidget *image){
 if(view->closing || !image || !view->pending_art)return;
 if(!cover_id || !*cover_id || strlen(cover_id)>512){
  gtk_widget_set_tooltip_text(image,"No cover art provided for this album.");
  return;
 }
 MusicPendingArt *pending=g_new0(MusicPendingArt,1);
 pending->cover_id=g_strdup(cover_id);
 pending->image=g_object_ref(image);
 pending->serial=view->card_art_serial;
 g_queue_push_tail(view->pending_art,pending);
}
static void music_card_queue_pump(MusicView *view){
 if(view->closing || !view->pending_art || !view->cards ||
    !view->cards_scroll || !view->app_password)return;
 GtkAdjustment *adjustment=gtk_scrolled_window_get_vadjustment(
                                  GTK_SCROLLED_WINDOW(view->cards_scroll));
 double top=gtk_adjustment_get_value(adjustment);
 double height=gtk_adjustment_get_page_size(adjustment);
 GList *link=view->pending_art->head;
 while(link && view->art_inflight<4){
  GList *next=link->next;
  MusicPendingArt *item=link->data;
  gboolean stale=item->serial!=view->card_art_serial ||
                 !gtk_widget_get_parent(item->image);
  int x=0,y=0;
  gboolean placed=gtk_widget_translate_coordinates(
                        item->image,view->cards,0,0,&x,&y);
  gboolean visible=height<=0 || (placed && y+160>=top-180 &&
                                             y<=top+height+180);
  if(stale || visible){
   g_queue_delete_link(view->pending_art,link);
   if(!stale)music_card_art_launch(view,item->cover_id,item->image);
   music_pending_free(item);
  }
  link=next;
 }
}
static void music_card_scroll_changed(GtkAdjustment *unused,gpointer data){
 (void)unused;
 music_card_queue_pump(data);
}

/* A single queue action is shared by row selection and the album Play
 * button; it uses the authenticated visible track list, not download APIs. */
static void music_play_visible(MusicView *view,int index){
 if(view->closing || index<0 || index>=(int)view->visible_tracks->len)return;
 g_ptr_array_set_size(view->queue,0);
 for(guint i=0;i<view->visible_tracks->len;i++)
  g_ptr_array_add(view->queue,track_copy(g_ptr_array_index(view->visible_tracks,i)));
 music_shuffle_reset(view,index);
 music_start_track(view,index);
}
static void music_play_album(GtkWidget *unused,gpointer data){
 (void)unused;
 music_play_visible(data,0);
}

static void music_item_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 GtkWidget *button=GTK_WIDGET(data);
 MusicView *view=g_object_get_data(G_OBJECT(button),"music-view");
 const char *kind=g_object_get_data(G_OBJECT(button),"music-kind");
 const char *id=g_object_get_data(G_OBJECT(button),"music-id");
 const char *title=g_object_get_data(G_OBJECT(button),"music-title");
 const char *cover=g_object_get_data(G_OBJECT(button),"music-cover");
 if(!view || view->closing || !id || view->busy)return;
 if(!g_strcmp0(kind,"album") || !g_strcmp0(kind,"artist") ||
    !g_strcmp0(kind,"playlist")){
  if(view->hero_row){
   gtk_widget_show(view->hero_row);
   gtk_label_set_text(GTK_LABEL(view->hero_title),title);
   gtk_widget_set_sensitive(view->hero_play,FALSE);
  }
  music_art_start(view,cover,FALSE);
  query_start(view,kind,id,title);
 }else if(!g_strcmp0(kind,"song")){
  int selected=GPOINTER_TO_INT(
                 g_object_get_data(G_OBJECT(button),"music-song-index"))-1;
  if(selected<0 || selected>=(int)view->visible_tracks->len)return;
  music_play_visible(view,selected);
 }
}

/* DroppedNeedle owns acquisition. Bruiser only sends an authorized album
 * request to its existing API; there is no separate download manager.
 * The REST device session lives in Secret Service, never in GTK memory.
 */
typedef struct {
 GtkWidget *root, *button;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
} MusicAlbumRequest;

static gboolean music_request_timeout(gpointer data){
 MusicAlbumRequest *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}
static void music_request_free(MusicAlbumRequest *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_clear_object(&job->cancel);
 g_clear_object(&job->process);
 g_object_unref(job->root);
 g_object_unref(job->button);
 g_free(job);
}
static void music_request_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicAlbumRequest *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 gchar *output=NULL;
 GError *error=NULL;
 gboolean done=g_subprocess_communicate_utf8_finish(
     job->process,result,&output,NULL,&error);
 if(view && !view->closing){
  if(done && g_subprocess_get_successful(job->process)){
   gtk_button_set_label(GTK_BUTTON(job->button),"Requested");
   gtk_widget_set_sensitive(job->button,FALSE);
   status_set(view,"Album requested. DroppedNeedle handles downloading and import.");
   music_refresh_status(view);
  }else{
   gtk_widget_set_sensitive(job->button,TRUE);
   status_set(view,"Music request unavailable. Approve this device for Music in NOW.");
  }
 }
 g_free(output);
 g_clear_error(&error);
 music_request_free(job);
}
static void music_request_album(GtkWidget *button,gpointer data){
 MusicView *view=data;
 if(view->closing || !*cfg[6])return;
 const char *mbid=g_object_get_data(G_OBJECT(button),"music-request-mbid");
 if(!mbid || strlen(mbid)!=36)return;
 /* No credential ever enters argv, environment or a GUI entry field. */
 char *source=helper_path();
 char *dir=g_path_get_dirname(source);
 g_free(source);
 char *helper=g_build_filename(dir,"music_rest.py",NULL);
 g_free(dir);
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  status_set(view,"Music request integration is not installed.");
  g_free(helper);return;
 }
 const gchar *argv[]={"/usr/bin/python3",helper,cfg[6],"request",mbid,NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
      G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
      G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
  g_clear_error(&error);
  status_set(view,"Cannot start the Music request.");
  return;
 }
 MusicAlbumRequest *job=g_new0(MusicAlbumRequest,1);
 job->root=g_object_ref(view->root);
 job->button=g_object_ref(button);
 job->process=proc;
 job->cancel=g_cancellable_new();
 gtk_widget_set_sensitive(button,FALSE);
 status_set(view,"Sending album request...");
 job->deadline=g_timeout_add_seconds(25,music_request_timeout,job);
 g_subprocess_communicate_utf8_async(proc,"",job->cancel,
                                     music_request_complete,job);
}

/* The existing DroppedNeedle queue supplies the actual album status. One
 * bounded async read every 15 seconds while its catalog is visible. No
 * transfer scheduling, polling thread, or separate Music download manager. */
typedef struct {
 GtkWidget *root;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
} MusicStatusJob;

static gboolean music_status_timeout(gpointer data){
 MusicStatusJob *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}
static void music_status_free(MusicStatusJob *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_clear_object(&job->cancel);
 g_clear_object(&job->process);
 g_object_unref(job->root);
 g_free(job);
}
static void music_status_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicStatusJob *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 gchar *output=NULL;
 GError *error=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(
     job->process,result,&output,NULL,&error);
 if(view && !view->closing){
  view->status_inflight=FALSE;
  if(ok && g_subprocess_get_successful(job->process) && output){
   char **lines=g_strsplit(output,"\n",101);
   for(int i=0;lines[i] && i<100;i++){
    char **fields=g_strsplit(lines[i],"\t",2);
    if(g_strv_length(fields)==2 && strlen(fields[0])==36 &&
       strlen(fields[1])<72){
     GtkWidget *button=g_hash_table_lookup(view->album_buttons,fields[0]);
     if(button && GTK_IS_BUTTON(button)){
      gtk_button_set_label(GTK_BUTTON(button),fields[1]);
      if(g_strcmp0(fields[1],"Cancelled")==0)
       gtk_widget_set_sensitive(button,TRUE);
      else gtk_widget_set_sensitive(button,FALSE);
     }
    }
    g_strfreev(fields);
   }
   g_strfreev(lines);
  }
 }
 g_clear_error(&error);
 g_free(output);
 music_status_free(job);
}
static void music_refresh_status(MusicView *view){
 if(view->closing || view->status_inflight || !*cfg[6] ||
    !view->album_buttons || g_hash_table_size(view->album_buttons)==0)return;
 char *source=helper_path();
 char *dir=g_path_get_dirname(source);
 char *helper=g_build_filename(dir,"music_rest.py",NULL);
 g_free(source);g_free(dir);
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  g_free(helper);return;
 }
 const gchar *argv[]={"/usr/bin/python3",helper,cfg[6],"downloads",
                      "--format=rows",NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
  G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
  G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
  g_clear_error(&error);return;
 }
 MusicStatusJob *job=g_new0(MusicStatusJob,1);
 job->root=g_object_ref(view->root);
 job->process=proc;
 job->cancel=g_cancellable_new();
 view->status_inflight=TRUE;
 job->deadline=g_timeout_add_seconds(24,music_status_timeout,job);
 g_subprocess_communicate_utf8_async(proc,"",job->cancel,
                                     music_status_complete,job);
}
static gboolean music_status_tick(gpointer data){
 MusicView *view=data;
 if(!view->closing && gtk_widget_get_mapped(view->root))
  music_refresh_status(view);
 return G_SOURCE_CONTINUE;
}

/* Favorites and playlists use OpenSubsonic, on a separate async channel.
 * They do not block playback or clear the current library view. */
typedef struct {
 GtkWidget *root,*button;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
 char *operation,*song_id,*input;
} MusicActionJob;

static gboolean music_action_timeout(gpointer data){
 MusicActionJob *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}
static void music_action_free(MusicActionJob *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_clear_object(&job->cancel);
 g_clear_object(&job->process);
 g_clear_object(&job->root);
 g_clear_object(&job->button);
 g_free(job->operation);
 g_free(job->song_id);
 wipe_free(job->input);
 g_free(job);
}
static void music_action_start(MusicView *view,const char *operation,
                               const char *value,GtkWidget *button,
                               const char *song_id);
static void music_playlist_dialog(MusicView *view,const char *song_id,
                                  const char *output,GtkWidget *button){
 GtkWidget *parent=gtk_widget_get_toplevel(view->root);
 GtkWidget *dialog=gtk_dialog_new_with_buttons("Add to playlist",
   GTK_IS_WINDOW(parent)?GTK_WINDOW(parent):NULL,
   GTK_DIALOG_MODAL|GTK_DIALOG_DESTROY_WITH_PARENT,
   "Cancel",GTK_RESPONSE_CANCEL,"Add",GTK_RESPONSE_OK,NULL);
 gtk_window_set_default_size(GTK_WINDOW(dialog),420,-1);
 GtkWidget *content=gtk_dialog_get_content_area(GTK_DIALOG(dialog));
 gtk_container_set_border_width(GTK_CONTAINER(content),18);
 gtk_box_set_spacing(GTK_BOX(content),12);
 GtkWidget *intro=gtk_label_new("Choose an existing playlist or enter a new name.");
 gtk_label_set_xalign(GTK_LABEL(intro),0);
 gtk_label_set_line_wrap(GTK_LABEL(intro),TRUE);
 gtk_box_pack_start(GTK_BOX(content),intro,FALSE,FALSE,0);
 GtkWidget *combo=gtk_combo_box_text_new();
 gtk_widget_set_hexpand(combo,TRUE);
 int count=0;
 char **lines=g_strsplit(output?output:"","\n",-1);
 for(int k=0;lines[k] && count<200;k++){
  char **fields=g_strsplit(lines[k],"\t",8);
  if(g_strv_length(fields)>=5){
   char *kind=decode_field(fields[0]);
   char *id=decode_field(fields[1]);
   char *title=decode_field(fields[2]);
   if(kind && !strcmp(kind,"playlist") && id && *id &&
      title && *title){
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(combo),id,title);
    count++;
   }
   g_free(kind);g_free(id);g_free(title);
  }
  g_strfreev(fields);
 }
 g_strfreev(lines);
 if(count)gtk_combo_box_set_active(GTK_COMBO_BOX(combo),0);
 gtk_widget_set_sensitive(combo,count>0);
 GtkWidget *existing=gtk_label_new("Existing playlist");
 gtk_label_set_xalign(GTK_LABEL(existing),0);
 gtk_box_pack_start(GTK_BOX(content),existing,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(content),combo,FALSE,FALSE,0);
 GtkWidget *create=gtk_label_new("Or create a playlist");
 gtk_label_set_xalign(GTK_LABEL(create),0);
 gtk_box_pack_start(GTK_BOX(content),create,FALSE,FALSE,0);
 GtkWidget *entry=gtk_entry_new();
 gtk_entry_set_placeholder_text(GTK_ENTRY(entry),"New playlist name (optional)");
 gtk_entry_set_max_length(GTK_ENTRY(entry),100);
 gtk_box_pack_start(GTK_BOX(content),entry,FALSE,FALSE,0);
 gtk_widget_show_all(content);
 if(gtk_dialog_run(GTK_DIALOG(dialog))==GTK_RESPONSE_OK){
  const char *name=gtk_entry_get_text(GTK_ENTRY(entry));
  const char *selected=gtk_combo_box_get_active_id(GTK_COMBO_BOX(combo));
  const char *target=(name && *name)?name:selected;
  const char *action=(name && *name)?"playlist_create":"playlist_add";
  if(target && *target && !strchr(song_id,'|')){
   char *value=g_strdup_printf("%s|%s",target,song_id);
   music_action_start(view,action,value,button,song_id);
   g_free(value);
  }else status_set(view,"Select a playlist or enter a name.");
 }
 gtk_widget_destroy(dialog);
}
static void music_action_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicActionJob *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 gchar *output=NULL;
 GError *error=NULL;
 gboolean done=g_subprocess_communicate_utf8_finish(job->process,result,
                                                    &output,NULL,&error);
 gboolean ok=done && g_subprocess_get_successful(job->process);
 if(view && !view->closing){
  if(job->button && gtk_widget_get_parent(job->button))
   gtk_widget_set_sensitive(job->button,TRUE);
  if(!ok){
   status_set(view,"Could not update Music library. Try again.");
  }else if(!strcmp(job->operation,"playlist_options")){
   music_playlist_dialog(view,job->song_id,output,job->button);
  }else if(!strcmp(job->operation,"like") ||
           !strcmp(job->operation,"unlike")){
   gboolean liked=!strcmp(job->operation,"like");
   if(job->button && gtk_widget_get_parent(job->button)){
    gtk_button_set_image(GTK_BUTTON(job->button),
      gtk_image_new_from_icon_name(liked?"emblem-favorite-symbolic":
                                   "non-starred-symbolic",GTK_ICON_SIZE_BUTTON));
    gtk_widget_set_tooltip_text(job->button,liked?"Unlike song":"Like song");
    g_object_set_data(G_OBJECT(job->button),"music-liked",
                      GINT_TO_POINTER(liked?2:1));
   }
   for(guint i=0;i<view->visible_tracks->len;i++){
    MusicTrack *t=g_ptr_array_index(view->visible_tracks,i);
    if(!g_strcmp0(t->id,job->song_id))t->liked=liked;
   }
   for(guint i=0;i<view->queue->len;i++){
    MusicTrack *t=g_ptr_array_index(view->queue,i);
    if(!g_strcmp0(t->id,job->song_id))t->liked=liked;
   }
   status_set(view,liked?"Added to Liked Songs.":"Removed from Liked Songs.");
  }else{
   status_set(view,"Song added to playlist.");
  }
 }
 g_clear_error(&error);
 g_free(output);
 music_action_free(job);
}
static void music_action_start(MusicView *view,const char *operation,
                               const char *value,GtkWidget *button,
                               const char *song_id){
 if(view->closing || !view->app_password || !view->bound_url ||
    g_strcmp0(view->bound_url,cfg[6])!=0)return;
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  g_free(helper);
  status_set(view,"Music helper is missing.");
  return;
 }
 const char *argv_with_value[]={"/usr/bin/python3",helper,view->bound_url,
                  operation,value,"--format=rows","--auth-format=form",NULL};
 const char *argv_without_value[]={"/usr/bin/python3",helper,view->bound_url,
                  operation,"--format=rows","--auth-format=form",NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(value?argv_with_value:argv_without_value,
      G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
      G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
  g_clear_error(&error);
  status_set(view,"Could not start Music action.");
  return;
 }
 MusicActionJob *job=g_new0(MusicActionJob,1);
 job->root=g_object_ref(view->root);
 job->button=button?g_object_ref(button):NULL;
 job->process=proc;
 job->cancel=g_cancellable_new();
 job->operation=g_strdup(operation);
 job->song_id=g_strdup(song_id?song_id:"");
 char *key=g_uri_escape_string(view->app_password,NULL,FALSE);
 char *user=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
 job->input=g_strdup_printf("api_key=%s&username=%s",key,user);
 wipe_free(key);g_free(user);
 if(button)gtk_widget_set_sensitive(button,FALSE);
 job->deadline=g_timeout_add_seconds(27,music_action_timeout,job);
 g_subprocess_communicate_utf8_async(proc,job->input,job->cancel,
                                     music_action_complete,job);
}
static void music_like_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 GtkWidget *button=GTK_WIDGET(data);
 MusicView *view=g_object_get_data(G_OBJECT(button),"music-view");
 const char *id=g_object_get_data(G_OBJECT(button),"music-id");
 gboolean liked=GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button),"music-liked"))==2;
 if(view && id)music_action_start(view,liked?"unlike":"like",id,button,id);
}
static void music_playlist_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 GtkWidget *button=GTK_WIDGET(data);
 MusicView *view=g_object_get_data(G_OBJECT(button),"music-view");
 const char *id=g_object_get_data(G_OBJECT(button),"music-id");
 if(view && id)music_action_start(view,"playlist_options",NULL,button,id);
}

static void music_add_item(MusicView *view,const char *kind,const char *id,
                           const char *title,const char *artist,
                           const char *cover,const char *album,gboolean liked){
 if(view->grid_mode && (!g_strcmp0(kind,"album") ||
      !g_strcmp0(kind,"artist") || !g_strcmp0(kind,"playlist"))){
  /* Familiar square-art library tiles, not a second navigation model. */
  GtkWidget *card=gtk_button_new();
  gtk_widget_set_name(card,"music-card");
  gtk_style_context_add_class(gtk_widget_get_style_context(card),"now-action");
  GtkWidget *contents=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
  gtk_container_set_border_width(GTK_CONTAINER(contents),7);
  GtkWidget *art=gtk_image_new_from_icon_name("audio-x-generic",GTK_ICON_SIZE_DIALOG);
  gtk_widget_set_size_request(art,128,128);
  gtk_box_pack_start(GTK_BOX(contents),art,FALSE,FALSE,0);
  GtkWidget *caption=gtk_label_new(title);
  gtk_label_set_xalign(GTK_LABEL(caption),0);
  gtk_label_set_ellipsize(GTK_LABEL(caption),PANGO_ELLIPSIZE_END);
  gtk_label_set_max_width_chars(GTK_LABEL(caption),19);
  gtk_box_pack_start(GTK_BOX(contents),caption,FALSE,FALSE,0);
  GtkWidget *subtitle=gtk_label_new(artist && *artist?artist:kind);
  gtk_label_set_xalign(GTK_LABEL(subtitle),0);
  gtk_label_set_ellipsize(GTK_LABEL(subtitle),PANGO_ELLIPSIZE_END);
  gtk_label_set_max_width_chars(GTK_LABEL(subtitle),19);
  gtk_style_context_add_class(gtk_widget_get_style_context(subtitle),"dim-label");
  gtk_box_pack_start(GTK_BOX(contents),subtitle,FALSE,FALSE,0);
  gtk_container_add(GTK_CONTAINER(card),contents);
  gtk_widget_set_size_request(card,150,190);
  g_object_set_data(G_OBJECT(card),"music-view",view);
  g_object_set_data_full(G_OBJECT(card),"music-kind",g_strdup(kind),g_free);
  g_object_set_data_full(G_OBJECT(card),"music-id",g_strdup(id),g_free);
  g_object_set_data_full(G_OBJECT(card),"music-title",g_strdup(title),g_free);
  g_object_set_data_full(G_OBJECT(card),"music-cover",g_strdup(cover),g_free);
  g_signal_connect(card,"clicked",G_CALLBACK(music_item_clicked),card);
  gtk_flow_box_insert(GTK_FLOW_BOX(view->cards),card,-1);
  music_card_art_start(view,cover,art);
  return;
 }
 if(!g_strcmp0(kind,"section")){
  GtkWidget *heading=gtk_label_new(title);
  gtk_widget_set_name(heading,"music-section-title");
  gtk_label_set_xalign(GTK_LABEL(heading),0);
  gtk_widget_set_margin_top(heading,18);
  gtk_widget_set_margin_bottom(heading,7);
  gtk_list_box_insert(GTK_LIST_BOX(view->list),heading,-1);
  return;
 }
 GtkWidget *row=gtk_list_box_row_new();
 GtkWidget *button=gtk_button_new();
 gtk_widget_set_name(button,"music-row");
 gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-action");
 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
 gtk_container_set_border_width(GTK_CONTAINER(content),8);
 gtk_widget_set_hexpand(button,TRUE);
 GtkWidget *primary=gtk_label_new(title);
 gtk_label_set_ellipsize(GTK_LABEL(primary),PANGO_ELLIPSIZE_END);
 gtk_label_set_xalign(GTK_LABEL(primary),0);
 gtk_widget_set_name(primary,"music-row-title");
 gtk_widget_set_hexpand(primary,TRUE);
 gtk_box_pack_start(GTK_BOX(content),primary,FALSE,FALSE,0);
 char *detail;
 if(!g_strcmp0(kind,"song")){
  detail=(album && *album && artist && *artist)?
      g_strdup_printf("%s · %s",artist,album):
      g_strdup(artist && *artist?artist:album && *album?album:"Unknown artist");
 }else{
  detail=g_strdup_printf("%s · %s",
      !g_strcmp0(kind,"artist")?"Artist":
      !g_strcmp0(kind,"catalog_artist")?"Discover artist":
      !g_strcmp0(kind,"catalog_album")?"Discover album":
      !g_strcmp0(kind,"playlist")?"Playlist":"Album",
      artist && *artist?artist:"");
 }
 GtkWidget *secondary=gtk_label_new(detail);
 g_free(detail);
 gtk_label_set_xalign(GTK_LABEL(secondary),0);
 gtk_widget_set_name(secondary,"music-row-detail");
 gtk_label_set_ellipsize(GTK_LABEL(secondary),PANGO_ELLIPSIZE_END);
 gtk_style_context_add_class(gtk_widget_get_style_context(secondary),"dim-label");
 gtk_box_pack_start(GTK_BOX(content),secondary,FALSE,FALSE,0);
 gtk_container_add(GTK_CONTAINER(button),content);
 if(!g_strcmp0(kind,"catalog_album")){
  /* The request is contextual and real: one existing DroppedNeedle POST.
   * No separate queue, target folder or upload dashboard in Music. */
  GtkWidget *line=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
  gtk_box_pack_start(GTK_BOX(line),button,TRUE,TRUE,0);
  GtkWidget *request=gtk_button_new_with_label("Add to Library");
  gtk_style_context_add_class(gtk_widget_get_style_context(request),"now-action");
  g_object_set_data_full(G_OBJECT(request),"music-request-mbid",g_strdup(id),g_free);
  if(g_str_has_suffix(artist?artist:""," · Requested")){
   gtk_button_set_label(GTK_BUTTON(request),"Requested");
   gtk_widget_set_sensitive(request,FALSE);
  }else{
   g_signal_connect(request,"clicked",G_CALLBACK(music_request_album),view);
  }
  gtk_box_pack_end(GTK_BOX(line),request,FALSE,FALSE,0);
  g_hash_table_replace(view->album_buttons,g_strdup(id),request);
  gtk_container_add(GTK_CONTAINER(row),line);
 }else if(!g_strcmp0(kind,"song")){
  GtkWidget *line=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
  gtk_box_pack_start(GTK_BOX(line),button,TRUE,TRUE,0);
  GtkWidget *like=music_icon_button(liked?
      "emblem-favorite-symbolic":"non-starred-symbolic",
      liked?"Unlike song":"Like song");
  gtk_widget_set_name(like,"music-song-action");
  g_object_set_data(G_OBJECT(like),"music-view",view);
  g_object_set_data_full(G_OBJECT(like),"music-id",g_strdup(id),g_free);
  g_object_set_data(G_OBJECT(like),"music-liked",GINT_TO_POINTER(liked?2:1));
  g_signal_connect(like,"clicked",G_CALLBACK(music_like_clicked),like);
  gtk_box_pack_start(GTK_BOX(line),like,FALSE,FALSE,0);
  GtkWidget *add=music_icon_button("list-add-symbolic","Add to playlist");
  gtk_widget_set_name(add,"music-song-action");
  g_object_set_data(G_OBJECT(add),"music-view",view);
  g_object_set_data_full(G_OBJECT(add),"music-id",g_strdup(id),g_free);
  g_signal_connect(add,"clicked",G_CALLBACK(music_playlist_clicked),add);
  gtk_box_pack_start(GTK_BOX(line),add,FALSE,FALSE,0);
  gtk_container_add(GTK_CONTAINER(row),line);
 }else{
  gtk_container_add(GTK_CONTAINER(row),button);
 }
 g_object_set_data(G_OBJECT(button),"music-view",view);
 g_object_set_data_full(G_OBJECT(button),"music-kind",g_strdup(kind),g_free);
 g_object_set_data_full(G_OBJECT(button),"music-id",g_strdup(id),g_free);
 g_object_set_data_full(G_OBJECT(button),"music-title",g_strdup(title),g_free);
 g_object_set_data_full(G_OBJECT(button),"music-cover",g_strdup(cover),g_free);
 if(!g_strcmp0(kind,"song")){
  MusicTrack *song=g_new0(MusicTrack,1);
  song->id=g_strdup(id);
  song->title=g_strdup(title);
  song->artist=g_strdup(artist);
  song->album=g_strdup(album);
  song->liked=liked;
  song->cover_id=g_strdup(cover);
  g_object_set_data(G_OBJECT(button),"music-song-index",
                    GINT_TO_POINTER(view->visible_tracks->len+1));
  g_ptr_array_add(view->visible_tracks,song);
 }
 if(g_str_has_prefix(kind,"catalog_")){
  /* Catalog rows aren't playable before DroppedNeedle imports an album.
   * The separate Add to Library button makes a real authorized REST POST. */
  gtk_widget_set_sensitive(button,FALSE);
  gtk_widget_set_tooltip_text(button,
      "Search result is not in your library yet.");
 }else{
  g_signal_connect(button,"clicked",G_CALLBACK(music_item_clicked),button);
 }
 gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1);
}

static int render_rows(MusicView *view,const char *output,gboolean append){
 if(!append){
  ++view->card_art_serial;
  music_pending_clear(view);
  view->card_art_count=0;
  GList *cards=gtk_container_get_children(GTK_CONTAINER(view->cards));
  for(GList *p=cards;p;p=p->next)gtk_widget_destroy(GTK_WIDGET(p->data));
  g_list_free(cards);
  g_hash_table_remove_all(view->album_buttons);
  g_ptr_array_set_size(view->visible_tracks,0);
  GList *children=gtk_container_get_children(GTK_CONTAINER(view->list));
  for(GList *p=children;p;p=p->next)gtk_widget_destroy(GTK_WIDGET(p->data));
  g_list_free(children);
 }
 if(!output)return 0;
 char **lines=g_strsplit(output,"\n",-1);
 int count=0;
 for(int k=0;lines[k] && count<350;k++){
  if(!*lines[k])continue;
  char **parts=g_strsplit(lines[k],"\t",8);
  guint columns=g_strv_length(parts);
  if(columns==5 || columns==7){
   char *kind=decode_field(parts[0]);
   char *id=decode_field(parts[1]);
   char *title=decode_field(parts[2]);
   char *artist=decode_field(parts[3]);
   char *cover=decode_field(parts[4]);
   char *album=columns==7?decode_field(parts[5]):g_strdup("");
   char *liked=columns==7?decode_field(parts[6]):g_strdup("0");
   if(kind && id && title && artist && cover && album && liked &&
      (!strcmp(kind,"album") || !strcmp(kind,"song") ||
       !strcmp(kind,"artist") || !strcmp(kind,"playlist") ||
       !strcmp(kind,"catalog_album") || !strcmp(kind,"catalog_artist") ||
       !strcmp(kind,"section"))){
    music_add_item(view,kind,id,title,artist,cover,album,!strcmp(liked,"1"));
    ++count;
   }
   g_free(kind);g_free(id);g_free(title);g_free(artist);g_free(cover);
   g_free(album);g_free(liked);
  }
  g_strfreev(parts);
 }
 g_strfreev(lines);
 gtk_widget_show_all(view->list);
 gtk_widget_show_all(view->cards);
 music_card_queue_pump(view);
 return count;
}

static void music_show_empty(MusicView *view,const char *operation){
 const char *message="No items found. Try another search or browse your library.";
 if(!g_strcmp0(operation,"home"))
  message="No music is available yet. Check your library, or open Advanced for imports.";
 else if(!g_strcmp0(operation,"recent"))
  message="No recently played albums yet. Browse Albums or New additions.";
 else if(!g_strcmp0(operation,"liked"))
  message="Nothing in Liked yet. Favorites from your music library will appear here.";
 else if(!g_strcmp0(operation,"discover"))
  message="No music suggestions are available right now.";
 else if(!g_strcmp0(operation,"playlists"))
  message="No playlists yet. Existing server playlists will appear here.";
 GtkWidget *empty=gtk_label_new(message);
 gtk_label_set_line_wrap(GTK_LABEL(empty),TRUE);
 gtk_widget_set_margin_top(empty,22);
 gtk_widget_set_margin_bottom(empty,22);
 gtk_label_set_xalign(GTK_LABEL(empty),0);
 if(view->grid_mode){
  gtk_flow_box_insert(GTK_FLOW_BOX(view->cards),empty,-1);
  gtk_widget_show_all(view->cards);
 }else{
  gtk_list_box_insert(GTK_LIST_BOX(view->list),empty,-1);
  gtk_widget_show_all(view->list);
 }
}

static gboolean query_timeout(gpointer data){
 MusicQuery *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}

static void query_free(MusicQuery *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_object_unref(job->cancel);
 g_object_unref(job->process);
 g_object_unref(job->root);
 wipe_free(job->input);
 g_free(job->operation);
 g_free(job->heading);
 g_free(job);
}

static void query_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicQuery *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 gchar *output=NULL;
 GError *error=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(job->process,result,
                                                &output,NULL,&error);
 if(view && !view->closing){
  view->busy=FALSE;
  if(!ok || !g_subprocess_get_successful(job->process)){
   view->hero_art_serial++;
   if(view->hero_row)gtk_widget_hide(view->hero_row);
   status_set(view,(!g_strcmp0(job->operation,"catalog") ||
                    !g_strcmp0(job->operation,"discover"))
      ? "Discover and requests need an approved device connection."
      : "Music library unavailable. Check server access and Music connection.");
  }else{
   view->grid_mode=(!g_strcmp0(job->operation,"home") ||
                    !g_strcmp0(job->operation,"albums") ||
                    !g_strcmp0(job->operation,"recent") ||
                    !g_strcmp0(job->operation,"new") ||
                    !g_strcmp0(job->operation,"artists") ||
                    !g_strcmp0(job->operation,"playlists"));
   int count=render_rows(view,output,job->append_albums || job->append_songs);
   if(view->grid_mode){
    gtk_widget_show(view->cards_scroll);
    gtk_widget_hide(view->list_scroll);
   }else{
    gtk_widget_hide(view->cards_scroll);
    gtk_widget_show(view->list_scroll);
   }
   if(count==0 && !job->append_albums && !job->append_songs)
    music_show_empty(view,job->operation);
   if(view->shuffle_all){
    if(!g_strcmp0(job->operation,"songs") ||
       !g_strcmp0(job->operation,"random_songs"))gtk_widget_show(view->shuffle_all);
    else gtk_widget_hide(view->shuffle_all);
   }
   if(view->load_more_songs){
    if(!g_strcmp0(job->operation,"songs")){
     view->song_offset=job->offset+count;
     gtk_widget_set_sensitive(view->load_more_songs,TRUE);
     if(count==200 && view->song_offset<=1000000)
      gtk_widget_show(view->load_more_songs);
     else gtk_widget_hide(view->load_more_songs);
    }else gtk_widget_hide(view->load_more_songs);
   }
   if(view->load_more){
    if(!g_strcmp0(job->operation,"albums")){
     view->album_offset=job->offset+count;
     gtk_widget_set_sensitive(view->load_more,TRUE);
     if(count==200 && view->album_offset<=1000000)
      gtk_widget_show(view->load_more);
     else gtk_widget_hide(view->load_more);
    }else gtk_widget_hide(view->load_more);
   }
   if(view->hero_play){
    gboolean playable=(!g_strcmp0(job->operation,"album") ||
                       !g_strcmp0(job->operation,"playlist")) &&
                       view->visible_tracks->len>0;
    gtk_widget_set_sensitive(view->hero_play,playable);
   }
   gtk_label_set_text(GTK_LABEL(view->heading),job->heading);
   char *message=(!g_strcmp0(job->operation,"catalog") ||
                          !g_strcmp0(job->operation,"discover"))
        ? g_strdup_printf("%d music discovery items",count)
        : g_strdup_printf("%d items · Connected to your music library",
            !g_strcmp0(job->operation,"albums")?view->album_offset:count);
   status_set(view,message);
   g_free(message);
   /* Shuffle All uses an authenticated, server-randomized song selection. */
   if(!g_strcmp0(job->operation,"random_songs") &&
      view->visible_tracks->len>0)music_play_visible(view,0);
   if(view->remember_pending){
    view->remember_pending=FALSE;
    /* Credentials are saved only AFTER the OpenSubsonic API accepted them. */
    char *escaped_key=g_uri_escape_string(view->app_password,NULL,FALSE);
    char *escaped_user=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
    char *form=g_strdup_printf("api_key=%s&username=%s",escaped_key,escaped_user);
    wipe_free(escaped_key);
    g_free(escaped_user);
    music_vault_begin(view,"store",form);
    wipe_free(form);
   }
  }
 }
 g_clear_error(&error);
 g_free(output);
 query_free(job);
}

static void query_start(MusicView *view,const char *operation,
                        const char *value,const char *heading){
 if(view->busy || view->closing)return;
 const gboolean append_albums=!g_strcmp0(operation,"albums") && value && *value;
 const gboolean append_songs=!g_strcmp0(operation,"songs") && value && *value;
 const gboolean catalog=!g_strcmp0(operation,"catalog") ||
                        !g_strcmp0(operation,"discover");
 if(!*cfg[6]){
  status_set(view,"Add your Music server URL under NOW Settings.");
  return;
 }
 if(!catalog && (!view->bound_url || g_strcmp0(view->bound_url,cfg[6]))){
  wipe_free(view->app_password);
  view->app_password=NULL;
  status_set(view,"Music server changed. Reconnect with its app password.");
  return;
 }
 if(!catalog && (!view->app_password || !*view->app_password)){
  status_set(view,"Music playback is not connected on this device.");
  return;
 }
 /* Only text search needs a query. Discover is a standalone page:
  * DroppedNeedle GET /discover has no query parameter. */
 if((!g_strcmp0(operation,"search") || !g_strcmp0(operation,"catalog")) &&
    (!value || !*value)){
  status_set(view,"Enter an artist, album, or song to search.");
  return;
 }
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  status_set(view,"Installed Music client helper is missing.");
  g_free(helper);
  return;
 }
 const char *server_url=catalog?cfg[6]:view->bound_url;
 const gchar *argv[]={"/usr/bin/python3",helper,server_url,operation,
                      value && *value?value:NULL,"--format=rows","--auth-format=form",NULL};
 /* Avoid a NULL gap (the helper needs no arbitrary value for browse calls). */
 const gchar *without_value[]={"/usr/bin/python3",helper,server_url,operation,
                              "--format=rows","--auth-format=form",NULL};
 const gchar *const *command=value && *value?argv:without_value;
 GError *error=NULL;
 GSubprocess *process=g_subprocess_newv(command,
    G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
    G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!process){
  status_set(view,"Unable to launch Music browser helper.");
  g_clear_error(&error);
  return;
 }
 char *encoded_user=NULL;
 char *encoded_key=NULL;
 if(!catalog){
  encoded_user=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
  encoded_key=g_uri_escape_string(view->app_password,NULL,FALSE);
 }
 MusicQuery *job=g_new0(MusicQuery,1);
 job->process=process;
 job->root=g_object_ref(view->root);
 job->cancel=g_cancellable_new();
 job->operation=g_strdup(operation);
 job->heading=g_strdup(heading?heading:"Music");
 job->append_albums=append_albums;
 job->append_songs=append_songs;
 job->offset=(append_albums || append_songs)?atoi(value):0;
 if(view->load_more){
  if(!append_albums)gtk_widget_hide(view->load_more);
  else gtk_widget_set_sensitive(view->load_more,FALSE);
 }
 if(view->load_more_songs){
  if(!append_songs)gtk_widget_hide(view->load_more_songs);
  else gtk_widget_set_sensitive(view->load_more_songs,FALSE);
 }
 job->input=catalog?g_strdup(""):g_strdup_printf(
     "api_key=%s&username=%s",encoded_key,encoded_user);
 wipe_free(encoded_key);
 g_free(encoded_user);
 view->busy=TRUE;
 status_set(view,!g_strcmp0(operation,"discover")
      ? "Loading music discoveries..."
      : catalog?"Searching the music catalog...":"Loading your library...");
 job->deadline=g_timeout_add_seconds(27,query_timeout,job);
 g_subprocess_communicate_utf8_async(process,job->input,job->cancel,
                                    query_complete,job);
}


/* GNOME Keyring / KWallet Secret Service work happens off the GTK main loop.
 * It is intentionally separate from the OpenSubsonic network transport. */
typedef struct {
 GtkWidget *root;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
 char *action, *url, *input;
} MusicVault;

static char *keyring_helper_path(void){
 char *music=helper_path();
 char *dir=g_path_get_dirname(music);
 char *keyring=g_build_filename(dir,"music_keyring.py",NULL);
 g_free(dir);
 g_free(music);
 return keyring;
}

static char *form_unescape(const char *encoded){
 if(!encoded || strlen(encoded)>4096)return NULL;
 char *plus=g_strdup(encoded);
 for(char *p=plus;*p;p++)if(*p=='+')*p=' ';
 char *decoded=g_uri_unescape_string(plus,NULL);
 g_free(plus);
 return decoded;
}

/* The keyring stores only "api_key=...&username=..." form data.
 * Parse exactly two fields, never interpret arbitrary keyring text as a URL. */
static gboolean form_unpack(const char *form,char **api_key,char **username){
 *api_key=NULL;
 *username=NULL;
 if(!form || strlen(form)>4096)return FALSE;
 char **fields=g_strsplit(form,"&",3);
 gboolean ok=fields[0] && fields[1] && !fields[2] &&
    g_str_has_prefix(fields[0],"api_key=") &&
    g_str_has_prefix(fields[1],"username=");
 if(ok){
  *api_key=form_unescape(fields[0]+8);
  *username=form_unescape(fields[1]+9);
  ok=*api_key && **api_key && strlen(*api_key)<=1024 &&
     *username && strlen(*username)<=128 &&
     !strchr(*api_key,'\n') && !strchr(*username,'\n');
 }
 if(!ok){
  wipe_free(*api_key);*api_key=NULL;
  wipe_free(*username);*username=NULL;
 }
 g_strfreev(fields);
 return ok;
}

static gboolean vault_timeout(gpointer data){
 MusicVault *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}

static void vault_free(MusicVault *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_object_unref(job->cancel);
 g_object_unref(job->process);
 g_object_unref(job->root);
 wipe_free(job->input);
 g_free(job->action);
 g_free(job->url);
 g_free(job);
}

typedef struct {
 GtkWidget *root;
 GSubprocess *process;
 GCancellable *cancel;
 guint deadline;
 char *server_url;
} MusicEnrollment;

static gboolean music_enroll_timeout(gpointer data){
 MusicEnrollment *job=data;
 job->deadline=0;
 g_cancellable_cancel(job->cancel);
 g_subprocess_force_exit(job->process);
 return G_SOURCE_REMOVE;
}
static void music_enroll_free(MusicEnrollment *job){
 if(job->deadline)g_source_remove(job->deadline);
 g_object_unref(job->cancel);
 g_object_unref(job->process);
 g_object_unref(job->root);
 g_free(job->server_url);
 g_free(job);
}
static void music_enroll_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicEnrollment *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 char *output=NULL;
 GError *error=NULL;
 gboolean done=g_subprocess_communicate_utf8_finish(
     job->process,result,&output,NULL,&error);
 if(view && !view->closing){
  view->auto_enroll_busy=FALSE;
  if(done && g_subprocess_get_successful(job->process) &&
     g_strcmp0(job->server_url,cfg[6])==0 &&
     !g_strcmp0(output,"connected\n")){
   status_set(view,"Music device approved. Opening your library...");
   music_vault_begin(view,"lookup",NULL);
  }else{
   status_set(view,"Music requires owner approval on this host. "
                   "Your existing Games, Video and Downloads are unaffected.");
   gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
  }
 }
 g_free(output);
 g_clear_error(&error);
 music_enroll_free(job);
}
static void music_auto_enroll(MusicView *view){
 if(view->closing || view->auto_enroll_busy ||
    view->auto_enroll_attempted || !*cfg[0] || !*cfg[1] || !*cfg[6])
  return;
 view->auto_enroll_attempted=TRUE;
 char *source=helper_path();
 char *dir=g_path_get_dirname(source);
 char *helper=g_build_filename(dir,"music_device_client.py",NULL);
 g_free(source);g_free(dir);
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  g_free(helper);return;
 }
 const char *argv[]={"/usr/bin/python3",helper,cfg[0],cfg[1],cfg[6],NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
       G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
       G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){g_clear_error(&error);return;}
 MusicEnrollment *job=g_new0(MusicEnrollment,1);
 job->root=g_object_ref(view->root);
 job->process=proc;
 job->cancel=g_cancellable_new();
 job->server_url=g_strdup(cfg[6]);
 job->deadline=g_timeout_add_seconds(75,music_enroll_timeout,job);
 view->auto_enroll_busy=TRUE;
 gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE);
 status_set(view,"Checking approved Music access...");
 g_subprocess_communicate_utf8_async(proc,"",job->cancel,
                                      music_enroll_complete,job);
}

static void vault_complete(GObject *unused,GAsyncResult *result,gpointer data){
 (void)unused;
 MusicVault *job=data;
 MusicView *view=g_object_get_data(G_OBJECT(job->root),"music-view");
 gchar *reply=NULL;
 GError *error=NULL;
 gboolean completed=g_subprocess_communicate_utf8_finish(
                        job->process,result,&reply,NULL,&error);
 int exit_code=completed?g_subprocess_get_exit_status(job->process):-1;
 if(view && !view->closing){
  view->vault_busy=FALSE;
  if(!g_strcmp0(job->action,"lookup")){
   if(g_strcmp0(cfg[6],job->url)==0 &&
      !view->app_password && !view->busy){
    char *key=NULL,*username=NULL;
    if(exit_code==0 && form_unpack(reply,&key,&username)){
     wipe_free(view->app_password);
     view->app_password=key;
     g_free(view->username);
     view->username=username;
     g_free(view->bound_url);
     view->bound_url=g_strdup(job->url);
     gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE);
     query_start(view,"home",NULL,"Music Home");
    }else{
     wipe_free(key);wipe_free(username);
     if(exit_code==3 && !view->auto_enroll_attempted &&
        *cfg[0] && *cfg[1]){
      music_auto_enroll(view);
     }else{
      gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
      status_set(view,exit_code==3
        ? "Ask your server owner to approve Music on this device."
        : "OS keyring unavailable or locked. Check keyring setup.");
     }
    }
   }
  }else if(!g_strcmp0(job->action,"store")){
   if(exit_code==0){
    gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE);
    status_set(view,"Music connected. This device will sign in automatically.");
   }else{
    status_set(view,"Music connected for this session, but device sign-in could not be saved to the OS keyring.");
    gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
   }
  }else if(!g_strcmp0(job->action,"clear")){
   status_set(view,exit_code==0
     ? "Music sign-in removed from this device."
     : "Could not remove Music sign-in; check your OS keyring.");
   gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
  }
 }
 g_clear_error(&error);
 wipe_free(reply);
 vault_free(job);
}

static void music_vault_begin(MusicView *view,const char *action,
                              const char *input){
 if(view->closing || view->vault_busy)return;
 const char *url=!g_strcmp0(action,"lookup")?cfg[6]:
                  (view->bound_url?view->bound_url:cfg[6]);
 if(!url || !*url)return;
 char *helper=keyring_helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  status_set(view,"OS keyring integration is missing; Music sign-in cannot be remembered.");
  gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
  g_free(helper);return;
 }
 const char *argv[]={"/usr/bin/python3",helper,action,url,NULL};
 GError *error=NULL;
 GSubprocess *process=g_subprocess_newv(argv,
   G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
   G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!process){
  status_set(view,"Could not access the OS keyring.");
  gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
  g_clear_error(&error);
  return;
 }
 MusicVault *job=g_new0(MusicVault,1);
 job->root=g_object_ref(view->root);
 job->process=process;
 job->cancel=g_cancellable_new();
 job->action=g_strdup(action);
 job->url=g_strdup(url);
 job->input=g_strdup(input?input:"");
 view->vault_busy=TRUE;
 job->deadline=g_timeout_add_seconds(20,vault_timeout,job);
 g_subprocess_communicate_utf8_async(process,job->input,job->cancel,
                                     vault_complete,job);
}

static void music_opened(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->closing || view->vault_busy || view->busy)return;
 if(!*cfg[6]){
  status_set(view,"Music server is not configured. Set it once in NOW Settings.");
  gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE);
  return;
 }
 if(view->bound_url && !g_strcmp0(view->bound_url,cfg[6]) &&
    view->app_password)return;
 if(view->bound_url && g_strcmp0(view->bound_url,cfg[6])){
  /* Stop streaming before a different server can become selected. */
  music_stop(view);
  /* Credentials are strictly scoped to the originally authorized server. */
  wipe_free(view->app_password);
  view->app_password=NULL;
  g_free(view->bound_url);
  view->bound_url=NULL;
  view->auto_enroll_attempted=FALSE;
 }
 if(view->vault_attempted_url &&
    !g_strcmp0(view->vault_attempted_url,cfg[6]))return;
 g_free(view->vault_attempted_url);
 view->vault_attempted_url=g_strdup(cfg[6]);
 music_vault_begin(view,"lookup",NULL);
}

static void music_forget_device(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->closing || view->vault_busy || view->busy)return;
 music_stop(view);
 view->remember_pending=FALSE;
 wipe_free(view->app_password);view->app_password=NULL;
 g_free(view->vault_attempted_url);view->vault_attempted_url=g_strdup(cfg[6]);
 music_vault_begin(view,"clear",NULL);
}

static void music_nav_selected(MusicView *view,GtkWidget *selected){
 if(!selected || view->active_nav==selected)return;
 if(view->active_nav && GTK_IS_WIDGET(view->active_nav))
  gtk_style_context_remove_class(
     gtk_widget_get_style_context(view->active_nav),"music-active");
 view->active_nav=selected;
 gtk_style_context_add_class(gtk_widget_get_style_context(selected),"music-active");
}
static void music_nav(GtkWidget *button,gpointer data){
 MusicView *view=data;
 if(view->busy || view->closing)return;
 const char *operation=g_object_get_data(G_OBJECT(button),"music-operation");
 const char *heading=g_object_get_data(G_OBJECT(button),"music-heading");
 if(operation){
  music_nav_selected(view,button);
  view->hero_art_serial++;
  if(view->hero_row)gtk_widget_hide(view->hero_row);
  query_start(view,operation,NULL,heading);
 }
}

static void music_focus_search(GtkWidget *unused,gpointer data){
 MusicView *view=data;
 if(unused)music_nav_selected(view,unused);
 if(view->busy || view->closing)return;
 /* Search is a first-class Music destination, not a new admin page. */
 view->hero_art_serial++;
 if(view->hero_row)gtk_widget_hide(view->hero_row);
 if(view->load_more)gtk_widget_hide(view->load_more);
 view->grid_mode=FALSE;
 render_rows(view,"",FALSE);
 gtk_widget_hide(view->cards_scroll);
 gtk_widget_show(view->list_scroll);
 gtk_label_set_text(GTK_LABEL(view->heading),"Search");
 status_set(view,"Search your collection or find new music by artist or album.");
 gtk_widget_grab_focus(view->search);
 gtk_editable_select_region(GTK_EDITABLE(view->search),0,-1);
}

static void music_load_more(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing || view->album_offset<=0 ||
    view->album_offset>1000000)return;
 char *value=g_strdup_printf("%d",view->album_offset);
 query_start(view,"albums",value,"All albums");
 g_free(value);
}

static void music_load_more_songs(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing || view->song_offset<=0 ||
    view->song_offset>1000000)return;
 char *value=g_strdup_printf("%d",view->song_offset);
 query_start(view,"songs",value,"All songs");
 g_free(value);
}
static void music_shuffle_all(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing)return;
 if(view->shuffle_button)
  gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(view->shuffle_button),TRUE);
 query_start(view,"random_songs",NULL,"Shuffle all songs");
}
static void music_search(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing)return;
 const char *value=gtk_entry_get_text(GTK_ENTRY(view->search));
 if(value && *value){
  view->hero_art_serial++;
  if(view->hero_row)gtk_widget_hide(view->hero_row);
  gboolean connected=view->app_password && view->bound_url &&
                       !g_strcmp0(view->bound_url,cfg[6]);
  query_start(view,connected?"search":"catalog",value,
              connected?"Search results":"Music catalog");
 }
}

static void music_retry_access(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->closing || view->auto_enroll_busy || view->busy)return;
 if(view->app_password && view->bound_url &&
    !g_strcmp0(view->bound_url,cfg[6])){
  status_set(view,"This device already has Music playback access.");
  return;
 }
 /* The owner may have approved Music after the initial automatic attempt.
  * Retry the SAME restricted, already enrolled NOW device identity; do not
  * create keys or invent a new pairing flow. */
 view->auto_enroll_attempted=FALSE;
 music_auto_enroll(view);
}

static void music_advanced(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->open_url && *cfg[6])view->open_url(cfg[6]);
 else status_set(view,"Configure your Music server under NOW Settings.");
}
static void music_settings(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->open_settings)view->open_settings(NULL,NULL);
}

static GtkWidget *music_button(const char *text){
 GtkWidget *button=gtk_button_new_with_label(text);
 gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-action");
 gtk_widget_set_halign(button,GTK_ALIGN_FILL);
 return button;
}

GtkWidget *now_music_build(void (*open_url)(const char *),
                           void (*open_settings)(void *, void *),
                           void (*tray_changed)(void)){
 MusicView *view=g_new0(MusicView,1);
 view->open_url=open_url;
 view->open_settings=open_settings;
 view->tray_changed=tray_changed;
 view->visible_tracks=g_ptr_array_new_with_free_func(track_free);
 view->queue=g_ptr_array_new_with_free_func(track_free);
 view->album_buttons=g_hash_table_new_full(g_str_hash,g_str_equal,g_free,NULL);
 view->pending_art=g_queue_new();
 view->queue_index=-1;
 view->volume=75;
 view->playback=now_music_playback_new(music_player_event,view);
 active_music_view=view;
 view->root=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);
 gtk_widget_set_name(view->root,"music-home");
 gtk_container_set_border_width(GTK_CONTAINER(view->root),12);
 g_object_set_data_full(G_OBJECT(view->root),"music-view",view,music_view_free);
 g_signal_connect(view->root,"destroy",G_CALLBACK(music_view_destroy),view);

 GtkWidget *top=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 GtkWidget *title=gtk_label_new("MUSIC");
 gtk_widget_set_halign(title,GTK_ALIGN_START);
 gtk_style_context_add_class(gtk_widget_get_style_context(title),"now-heading");
 gtk_box_pack_start(GTK_BOX(top),title,TRUE,TRUE,0);
 /* Keep rarely needed server management out of the everyday music rail. */
 GtkWidget *advanced=gtk_menu_button_new();
 gtk_button_set_label(GTK_BUTTON(advanced),"More");
 gtk_style_context_add_class(gtk_widget_get_style_context(advanced),"now-action");
 GtkWidget *menu=gtk_menu_new();
 GtkWidget *manage=gtk_menu_item_new_with_label("Advanced · DroppedNeedle");
 g_signal_connect(manage,"activate",G_CALLBACK(music_advanced),view);
 gtk_menu_shell_append(GTK_MENU_SHELL(menu),manage);
 GtkWidget *settings_item=gtk_menu_item_new_with_label("Music settings");
 g_signal_connect(settings_item,"activate",G_CALLBACK(music_settings),view);
 gtk_menu_shell_append(GTK_MENU_SHELL(menu),settings_item);
 GtkWidget *retry_item=gtk_menu_item_new_with_label("Retry Music Access");
 g_signal_connect(retry_item,"activate",G_CALLBACK(music_retry_access),view);
 gtk_menu_shell_append(GTK_MENU_SHELL(menu),retry_item);
 GtkWidget *forget_item=gtk_menu_item_new_with_label("Forget this device");
 g_signal_connect(forget_item,"activate",G_CALLBACK(music_forget_device),view);
 gtk_menu_shell_append(GTK_MENU_SHELL(menu),forget_item);
 gtk_widget_show_all(menu);
 gtk_menu_button_set_popup(GTK_MENU_BUTTON(advanced),menu);
 gtk_box_pack_end(GTK_BOX(top),advanced,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(view->root),top,FALSE,FALSE,0);

 /* A registered NOW device requests Music through its approved SSH identity.
  * Never require an end user to handle a DroppedNeedle provider credential. */
 GtkWidget *connect=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 GtkWidget *connect_hint=gtk_label_new(
     "Music isn't enabled for this device yet. Ask the server owner to approve Music.");
 gtk_label_set_xalign(GTK_LABEL(connect_hint),0);
 gtk_label_set_line_wrap(GTK_LABEL(connect_hint),TRUE);
 gtk_widget_set_hexpand(connect_hint,TRUE);
 gtk_box_pack_start(GTK_BOX(connect),connect_hint,TRUE,TRUE,0);
 GtkWidget *connect_button=music_button("Retry Access");
 g_signal_connect(connect_button,"clicked",G_CALLBACK(music_retry_access),view);
 gtk_box_pack_start(GTK_BOX(connect),connect_button,FALSE,FALSE,0);
 view->connect_panel=gtk_revealer_new();
 gtk_revealer_set_transition_type(GTK_REVEALER(view->connect_panel),
                                  GTK_REVEALER_TRANSITION_TYPE_SLIDE_DOWN);
 gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE);
 gtk_container_add(GTK_CONTAINER(view->connect_panel),connect);
 gtk_box_pack_start(GTK_BOX(view->root),view->connect_panel,FALSE,FALSE,0);

 view->status=gtk_label_new("Checking saved Music connection on this device...");
 gtk_label_set_xalign(GTK_LABEL(view->status),0);
 gtk_label_set_ellipsize(GTK_LABEL(view->status),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(view->root),view->status,FALSE,FALSE,0);

 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 gtk_widget_set_vexpand(content,TRUE);
 gtk_box_pack_start(GTK_BOX(view->root),content,TRUE,TRUE,0);
 GtkWidget *sidebar=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
 gtk_widget_set_name(sidebar,"music-sidebar");
 gtk_widget_set_size_request(sidebar,154,-1);
 /* Established Spotify-style grouping: Home + Search, then
  * Your Library filters. Never put downloads/admin workflow in this rail. */
 /* Your Library is a real, prominent destination: it opens All Songs.
  * Filters beneath it remain regular clickable navigation. */
 const char *ops[]={"home",NULL,"discover","songs","playlists","artists",
                    "albums","liked","recent","new"};
 const char *titles[]={"Home","Search","Discover","YOUR LIBRARY","Playlists",
                       "Artists","Albums","Liked Songs","Recently played","New additions"};
 const char *headings[]={"Music Home","Search","Discover","All songs",
                         "Your playlists","Artists","All albums","Liked music",
                         "Recently played albums","New additions"};
 for(guint i=0;i<G_N_ELEMENTS(ops);i++){
  if(i==8){
   GtkWidget *heading=gtk_label_new("RECENT");
   gtk_widget_set_name(heading,"music-library-label");
   gtk_label_set_xalign(GTK_LABEL(heading),0);
   gtk_widget_set_margin_top(heading,12);
   gtk_box_pack_start(GTK_BOX(sidebar),heading,FALSE,FALSE,0);
  }
  GtkWidget *b=music_button(titles[i]);
  gtk_widget_set_name(b,i==3?"music-library-root":"music-nav");
  GtkWidget *nav_label=gtk_bin_get_child(GTK_BIN(b));
  if(GTK_IS_LABEL(nav_label))gtk_label_set_xalign(GTK_LABEL(nav_label),0);
  if(i==3){
   gtk_widget_set_tooltip_text(b,"Browse all songs in your library");
   gtk_widget_set_margin_top(b,12);
   gtk_button_set_image(GTK_BUTTON(b),
                        gtk_image_new_from_icon_name("folder-music-symbolic",
                                                     GTK_ICON_SIZE_MENU));
   gtk_button_set_always_show_image(GTK_BUTTON(b),TRUE);
  }
  if(ops[i]){
   g_object_set_data(G_OBJECT(b),"music-operation",(gpointer)ops[i]);
   g_object_set_data(G_OBJECT(b),"music-heading",(gpointer)headings[i]);
   g_signal_connect(b,"clicked",G_CALLBACK(music_nav),view);
  }else{
   g_signal_connect(b,"clicked",G_CALLBACK(music_focus_search),view);
  }
  if(i==0)music_nav_selected(view,b);
  gtk_box_pack_start(GTK_BOX(sidebar),b,FALSE,FALSE,0);
 }
 /* The sidebar owns its scrolling, so nine nav actions must not
  * enlarge a 640x500 client or the still-hidden Dashboard stack. */
 GtkWidget *sidebar_scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(sidebar_scroll),
                                 GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_scrolled_window_set_min_content_width(GTK_SCROLLED_WINDOW(sidebar_scroll),154);
 gtk_scrolled_window_set_min_content_height(GTK_SCROLLED_WINDOW(sidebar_scroll),140);
 gtk_widget_set_vexpand(sidebar_scroll,TRUE);
 gtk_container_add(GTK_CONTAINER(sidebar_scroll),sidebar);
 gtk_box_pack_start(GTK_BOX(content),sidebar_scroll,FALSE,TRUE,0);

 GtkWidget *maincol=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
 gtk_widget_set_name(maincol,"music-main");
 gtk_widget_set_hexpand(maincol,TRUE);
 gtk_box_pack_start(GTK_BOX(content),maincol,TRUE,TRUE,0);
 GtkWidget *searchrow=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 view->search=gtk_search_entry_new();
 gtk_entry_set_placeholder_text(GTK_ENTRY(view->search),"Search albums, artists, and tracks...");
 gtk_widget_set_hexpand(view->search,TRUE);
 g_signal_connect(view->search,"activate",G_CALLBACK(music_search),view);
 gtk_box_pack_start(GTK_BOX(searchrow),view->search,TRUE,TRUE,0);
 GtkWidget *search_button=music_button("Search");
 g_signal_connect(search_button,"clicked",G_CALLBACK(music_search),view);
 gtk_box_pack_start(GTK_BOX(searchrow),search_button,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(maincol),searchrow,FALSE,FALSE,0);
 view->heading=gtk_label_new("Music Home");
 gtk_widget_set_name(view->heading,"music-section-title");
 gtk_widget_set_halign(view->heading,GTK_ALIGN_START);
 gtk_box_pack_start(GTK_BOX(maincol),view->heading,FALSE,FALSE,0);
 view->shuffle_all=music_button("Shuffle all");
 g_signal_connect(view->shuffle_all,"clicked",G_CALLBACK(music_shuffle_all),view);
 gtk_widget_set_no_show_all(view->shuffle_all,TRUE);
 gtk_box_pack_start(GTK_BOX(maincol),view->shuffle_all,FALSE,FALSE,0);
 /* Album/artist/playlist art is fetched on demand, not through an
  * unbounded request fan-out for every visible library item. */
 view->hero_row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,12);
 gtk_widget_set_name(view->hero_row,"music-hero");
 view->hero_art=gtk_image_new_from_icon_name("audio-x-generic",GTK_ICON_SIZE_DIALOG);
 gtk_widget_set_size_request(view->hero_art,120,120);
 gtk_box_pack_start(GTK_BOX(view->hero_row),view->hero_art,FALSE,FALSE,0);
 view->hero_title=gtk_label_new("");
 gtk_label_set_xalign(GTK_LABEL(view->hero_title),0);
 gtk_label_set_line_wrap(GTK_LABEL(view->hero_title),TRUE);
 gtk_label_set_ellipsize(GTK_LABEL(view->hero_title),PANGO_ELLIPSIZE_END);
 gtk_widget_set_hexpand(view->hero_title,TRUE);
 gtk_box_pack_start(GTK_BOX(view->hero_row),view->hero_title,TRUE,TRUE,0);
 view->hero_play=music_button("Play");
 gtk_widget_set_sensitive(view->hero_play,FALSE);
 g_signal_connect(view->hero_play,"clicked",G_CALLBACK(music_play_album),view);
 gtk_box_pack_end(GTK_BOX(view->hero_row),view->hero_play,FALSE,FALSE,0);
 gtk_widget_show_all(view->hero_row);
 gtk_widget_set_no_show_all(view->hero_row,TRUE);
 gtk_box_pack_start(GTK_BOX(maincol),view->hero_row,FALSE,FALSE,0);
 view->list_scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(view->list_scroll),
     GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_vexpand(view->list_scroll,TRUE);
 view->list=gtk_list_box_new();
 gtk_widget_set_name(view->list,"music-library");
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(view->list),GTK_SELECTION_NONE);
 gtk_container_add(GTK_CONTAINER(view->list_scroll),view->list);
 gtk_box_pack_start(GTK_BOX(maincol),view->list_scroll,TRUE,TRUE,0);
 view->cards_scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(view->cards_scroll),
     GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_vexpand(view->cards_scroll,TRUE);
 view->cards=gtk_flow_box_new();
 gtk_widget_set_name(view->cards,"music-card-grid");
 gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(view->cards),GTK_SELECTION_NONE);
 gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(view->cards),2);
 gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(view->cards),6);
 gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(view->cards),10);
 gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(view->cards),10);
 gtk_container_set_border_width(GTK_CONTAINER(view->cards),6);
 gtk_container_add(GTK_CONTAINER(view->cards_scroll),view->cards);
 GtkAdjustment *art_scroll=gtk_scrolled_window_get_vadjustment(
                             GTK_SCROLLED_WINDOW(view->cards_scroll));
 g_signal_connect(art_scroll,"value-changed",
                  G_CALLBACK(music_card_scroll_changed),view);
 g_signal_connect(art_scroll,"changed",
                  G_CALLBACK(music_card_scroll_changed),view);
 gtk_widget_set_no_show_all(view->cards_scroll,TRUE);
 gtk_box_pack_start(GTK_BOX(maincol),view->cards_scroll,TRUE,TRUE,0);
 view->load_more=music_button("Load more albums");
 gtk_widget_set_no_show_all(view->load_more,TRUE);
 g_signal_connect(view->load_more,"clicked",G_CALLBACK(music_load_more),view);
 gtk_box_pack_start(GTK_BOX(maincol),view->load_more,FALSE,FALSE,0);
 view->load_more_songs=music_button("Load more songs");
 gtk_widget_set_no_show_all(view->load_more_songs,TRUE);
 g_signal_connect(view->load_more_songs,"clicked",G_CALLBACK(music_load_more_songs),view);
 gtk_box_pack_start(GTK_BOX(maincol),view->load_more_songs,FALSE,FALSE,0);

 /* Persistent bottom player only while NOW has an active local stream.
  * It does not play/control phone audio, or fake a progress bar/seek support. */
 view->player_bar=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);
 GtkWidget *controls=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 gtk_container_set_border_width(GTK_CONTAINER(view->player_bar),7);
 gtk_style_context_add_class(gtk_widget_get_style_context(view->player_bar),
                             "music-player-bar");
 gtk_widget_set_name(view->player_bar,"music-player");
 view->playing_art=gtk_image_new_from_icon_name("audio-x-generic",GTK_ICON_SIZE_SMALL_TOOLBAR);
 gtk_widget_set_size_request(view->playing_art,44,44);
 gtk_box_pack_start(GTK_BOX(controls),view->playing_art,FALSE,FALSE,0);
 GtkWidget *now_playing=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);
 gtk_widget_set_hexpand(now_playing,TRUE);
 view->playing_label=gtk_label_new("");
 gtk_widget_set_name(view->playing_label,"music-now-title");
 gtk_label_set_xalign(GTK_LABEL(view->playing_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(view->playing_label),PANGO_ELLIPSIZE_END);
 gtk_widget_set_hexpand(view->playing_label,TRUE);
 gtk_box_pack_start(GTK_BOX(now_playing),view->playing_label,FALSE,FALSE,0);
 view->playing_artist_label=gtk_label_new("");
 gtk_widget_set_name(view->playing_artist_label,"music-now-artist");
 gtk_label_set_xalign(GTK_LABEL(view->playing_artist_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(view->playing_artist_label),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(now_playing),view->playing_artist_label,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(controls),now_playing,TRUE,TRUE,0);
 view->shuffle_button=gtk_toggle_button_new();
 gtk_button_set_image(GTK_BUTTON(view->shuffle_button),
    gtk_image_new_from_icon_name("media-playlist-shuffle-symbolic",GTK_ICON_SIZE_BUTTON));
 gtk_style_context_add_class(gtk_widget_get_style_context(view->shuffle_button),"music-transport");
 gtk_widget_set_tooltip_text(view->shuffle_button,"Shuffle off");
 gtk_widget_set_size_request(view->shuffle_button,38,38);
 g_signal_connect(view->shuffle_button,"toggled",G_CALLBACK(music_shuffle_clicked),view);
 gtk_box_pack_start(GTK_BOX(controls),view->shuffle_button,FALSE,FALSE,0);
 view->previous_button=music_icon_button("media-skip-backward-symbolic","Previous");
 g_signal_connect(view->previous_button,"clicked",G_CALLBACK(music_prev_clicked),view);
 gtk_box_pack_start(GTK_BOX(controls),view->previous_button,FALSE,FALSE,0);
 view->pause_button=music_icon_button("media-playback-pause-symbolic","Pause");
 gtk_widget_set_name(view->pause_button,"music-primary-play");
 g_signal_connect(view->pause_button,"clicked",G_CALLBACK(music_pause_clicked),view);
 gtk_box_pack_start(GTK_BOX(controls),view->pause_button,FALSE,FALSE,0);
 view->next_button=music_icon_button("media-skip-forward-symbolic","Next");
 g_signal_connect(view->next_button,"clicked",G_CALLBACK(music_next_clicked),view);
 gtk_box_pack_start(GTK_BOX(controls),view->next_button,FALSE,FALSE,0);
 GtkWidget *stop_button=music_icon_button("media-playback-stop-symbolic","Stop");
 g_signal_connect(stop_button,"clicked",G_CALLBACK(music_stop_clicked),view);
 gtk_box_pack_start(GTK_BOX(controls),stop_button,FALSE,FALSE,0);
 /* Local volume only; never changes another user's playback. */

 view->volume_slider=gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL,0,100,1);
 gtk_scale_set_draw_value(GTK_SCALE(view->volume_slider),FALSE);
 gtk_range_set_value(GTK_RANGE(view->volume_slider),view->volume);
 gtk_widget_set_size_request(view->volume_slider,65,-1);
 gtk_widget_set_tooltip_text(view->volume_slider,"This device's music volume");
 g_signal_connect(view->volume_slider,"value-changed",
                  G_CALLBACK(music_volume_changed),view);
 gtk_box_pack_start(GTK_BOX(controls),view->volume_slider,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(view->player_bar),controls,FALSE,FALSE,0);
 GtkWidget *timeline=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 view->seek_slider=gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL,0,1,1);
 gtk_scale_set_draw_value(GTK_SCALE(view->seek_slider),FALSE);
 gtk_widget_set_hexpand(view->seek_slider,TRUE);
 gtk_widget_set_sensitive(view->seek_slider,FALSE);
 gtk_widget_set_tooltip_text(view->seek_slider,"Seek through the current song");
 gtk_widget_add_events(view->seek_slider,GDK_BUTTON_PRESS_MASK|GDK_BUTTON_RELEASE_MASK);
 g_signal_connect(view->seek_slider,"value-changed",
                  G_CALLBACK(music_seek_changed),view);
 g_signal_connect(view->seek_slider,"button-press-event",
                  G_CALLBACK(music_seek_press),view);
 g_signal_connect(view->seek_slider,"button-release-event",
                  G_CALLBACK(music_seek_release),view);
 gtk_box_pack_start(GTK_BOX(timeline),view->seek_slider,TRUE,TRUE,0);
 view->seek_caption=gtk_label_new("0:00 / 0:00");
 gtk_widget_set_size_request(view->seek_caption,100,-1);
 gtk_box_pack_start(GTK_BOX(timeline),view->seek_caption,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(view->player_bar),timeline,FALSE,FALSE,0);
 /* Show children once, then suppress the entire bar from root show_all()
  * until a real playback session becomes active. */
 gtk_widget_show_all(view->player_bar);
 gtk_widget_set_no_show_all(view->player_bar,TRUE);
 gtk_box_pack_end(GTK_BOX(view->root),view->player_bar,FALSE,FALSE,0);
 g_signal_connect(view->root,"map",G_CALLBACK(music_opened),view);
 view->status_timer=g_timeout_add_seconds(15,music_status_tick,view);
 gtk_widget_show_all(view->root);
 gtk_widget_hide(view->hero_row);
 gtk_widget_hide(view->cards_scroll);
 gtk_widget_hide(view->player_bar);
 gtk_widget_hide(view->shuffle_all);
 gtk_widget_hide(view->load_more_songs);
 gtk_widget_hide(view->load_more);
 return view->root;
}
