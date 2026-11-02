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

typedef struct {
 char *id, *title, *artist, *cover_id;
} MusicTrack;
static void track_free(gpointer data){
 MusicTrack *t=data;
 if(!t)return;
 g_free(t->id);g_free(t->title);g_free(t->artist);g_free(t->cover_id);g_free(t);
}
static MusicTrack *track_copy(const MusicTrack *source){
 MusicTrack *t=g_new0(MusicTrack,1);
 t->id=g_strdup(source->id);
 t->title=g_strdup(source->title);
 t->artist=g_strdup(source->artist);
 t->cover_id=g_strdup(source->cover_id);
 return t;
}
typedef struct {
 GtkWidget *root, *status, *heading, *list, *user, *password, *search, *connect_panel;
 GtkWidget *player_bar, *playing_label, *pause_button, *previous_button, *next_button;
 GtkWidget *hero_row, *hero_art, *hero_title, *playing_art;
 GPtrArray *visible_tracks, *queue;
 NowMusicPlayback *playback;
 int queue_index;
 gboolean paused;
 char *playing_caption, *pending_cover_id;
 guint64 hero_art_serial, playing_art_serial;
 void (*tray_changed)(void);
 char *username, *app_password, *bound_url, *vault_attempted_url;
 gboolean busy, closing, vault_busy, remember_pending;
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
 char *input;                /* securely wiped on completion */
} MusicQuery;

static MusicView *active_music_view=NULL;
static void music_stop(MusicView *view);
static void music_start_track(MusicView *view,int index);
static void music_art_start(MusicView *view,const char *cover_id,gboolean playing);

static void wipe_free(char *value){
 if(!value)return;
 volatile char *ptr=(volatile char *)value;
 size_t len=strlen(value);
 while(len--)*ptr++=0;
 g_free(value);
}

static void music_view_destroy(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 view->closing=TRUE;
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
 g_free(view->pending_cover_id);
 if(view->visible_tracks)g_ptr_array_unref(view->visible_tracks);
 if(view->queue)g_ptr_array_unref(view->queue);
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
 gtk_label_set_text(GTK_LABEL(view->playing_label),
                    view->playing_caption?view->playing_caption:"Now playing");
 gtk_button_set_label(GTK_BUTTON(view->pause_button),
                      view->paused?"Resume":"Pause");
 gtk_widget_set_sensitive(view->previous_button,TRUE);
 gtk_widget_set_sensitive(view->next_button,
                  view->queue_index+1<(int)view->queue->len);
 gtk_widget_show(view->player_bar);
 music_notify_tray(view);
}
static void music_stop(MusicView *view){
 if(view->playback)now_music_playback_stop(view->playback);
 view->queue_index=-1;
 view->paused=FALSE;
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
 if(!strcmp(event,"ENDED")){
  if(view->queue_index+1<(int)view->queue->len)
   music_start_track(view,view->queue_index+1);
  else music_stop(view);
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
                             view->username,view->app_password,song->id)){
  music_stop(view);
  status_set(view,"Cannot start local audio. Check music helper and mpv installation.");
  return;
 }
 view->queue_index=index;
 view->paused=FALSE;
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
 music_start_track(view,MAX(0,view->queue_index-1));
}
static void music_next_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(!view->playback || !now_music_playback_active(view->playback))return;
 if(view->queue_index+1<(int)view->queue->len)
  music_start_track(view,view->queue_index+1);
 else music_stop(view);
}
static void music_pause_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->playback && now_music_playback_active(view->playback))
  now_music_playback_pause(view->playback,!view->paused);
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
    active_music_view->queue_index+1<(int)active_music_view->queue->len;
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
    job->serial==(job->playing?view->playing_art_serial:view->hero_art_serial) &&
    ok && g_subprocess_get_successful(job->process) && output){
  gsize len=0;
  const guchar *bytes=g_bytes_get_data(output,&len);
  if(len>0 && len<=3*1024*1024){
   GdkPixbufLoader *loader=gdk_pixbuf_loader_new();
   const int pixels=job->playing?44:120;
   gdk_pixbuf_loader_set_size(loader,pixels,pixels);
   gboolean valid=gdk_pixbuf_loader_write(loader,bytes,len,NULL);
   if(valid)valid=gdk_pixbuf_loader_close(loader,NULL);
   if(valid){
    GdkPixbuf *pixbuf=gdk_pixbuf_loader_get_pixbuf(loader);
    if(pixbuf){
     GtkWidget *target=job->playing?view->playing_art:view->hero_art;
     if(target)gtk_image_set_from_pixbuf(GTK_IMAGE(target),pixbuf);
    }
   }
   g_object_unref(loader);
  }
 }
 if(output)g_bytes_unref(output);
 g_clear_error(&error);
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

static void music_item_clicked(GtkWidget *unused,gpointer data){
 (void)unused;
 GtkWidget *button=GTK_WIDGET(data);
 MusicView *view=g_object_get_data(G_OBJECT(button),"music-view");
 const char *kind=g_object_get_data(G_OBJECT(button),"music-kind");
 const char *id=g_object_get_data(G_OBJECT(button),"music-id");
 const char *title=g_object_get_data(G_OBJECT(button),"music-title");
 if(!view || view->closing || !id || view->busy)return;
 if(!g_strcmp0(kind,"album") || !g_strcmp0(kind,"artist") ||
    !g_strcmp0(kind,"playlist")){
  query_start(view,kind,id,title);
 }else if(!g_strcmp0(kind,"song")){
  int selected=GPOINTER_TO_INT(
                 g_object_get_data(G_OBJECT(button),"music-song-index"))-1;
  if(selected<0 || selected>=(int)view->visible_tracks->len)return;
  g_ptr_array_set_size(view->queue,0);
  for(guint i=0;i<view->visible_tracks->len;i++)
   g_ptr_array_add(view->queue,track_copy(g_ptr_array_index(view->visible_tracks,i)));
  music_start_track(view,selected);
 }
}

static void music_add_item(MusicView *view,const char *kind,const char *id,
                           const char *title,const char *artist){
 GtkWidget *row=gtk_list_box_row_new();
 GtkWidget *button=gtk_button_new();
 gtk_widget_set_name(button,"music-row");
 gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-action");
 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);
 gtk_container_set_border_width(GTK_CONTAINER(content),8);
 GtkWidget *primary=gtk_label_new(title);
 gtk_label_set_ellipsize(GTK_LABEL(primary),PANGO_ELLIPSIZE_END);
 gtk_label_set_xalign(GTK_LABEL(primary),0);
 gtk_box_pack_start(GTK_BOX(content),primary,FALSE,FALSE,0);
 char *detail=g_strdup_printf("%s%s%s",!g_strcmp0(kind,"song")?"Track · ":
                               !g_strcmp0(kind,"artist")?"Artist · ":
                               !g_strcmp0(kind,"playlist")?"Playlist · ":"Album · ",
                               artist && *artist?artist:"",
                               "");
 GtkWidget *secondary=gtk_label_new(detail);
 g_free(detail);
 gtk_label_set_xalign(GTK_LABEL(secondary),0);
 gtk_label_set_ellipsize(GTK_LABEL(secondary),PANGO_ELLIPSIZE_END);
 gtk_style_context_add_class(gtk_widget_get_style_context(secondary),"dim-label");
 gtk_box_pack_start(GTK_BOX(content),secondary,FALSE,FALSE,0);
 gtk_container_add(GTK_CONTAINER(button),content);
 gtk_container_add(GTK_CONTAINER(row),button);
 g_object_set_data(G_OBJECT(button),"music-view",view);
 g_object_set_data_full(G_OBJECT(button),"music-kind",g_strdup(kind),g_free);
 g_object_set_data_full(G_OBJECT(button),"music-id",g_strdup(id),g_free);
 g_object_set_data_full(G_OBJECT(button),"music-title",g_strdup(title),g_free);
 if(!g_strcmp0(kind,"song")){
  MusicTrack *song=g_new0(MusicTrack,1);
  song->id=g_strdup(id);
  song->title=g_strdup(title);
  song->artist=g_strdup(artist);
  g_object_set_data(G_OBJECT(button),"music-song-index",
                    GINT_TO_POINTER(view->visible_tracks->len+1));
  g_ptr_array_add(view->visible_tracks,song);
 }
 g_signal_connect(button,"clicked",G_CALLBACK(music_item_clicked),button);
 gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1);
}

static int render_rows(MusicView *view,const char *output){
 g_ptr_array_set_size(view->visible_tracks,0);
 GList *children=gtk_container_get_children(GTK_CONTAINER(view->list));
 for(GList *p=children;p;p=p->next)gtk_widget_destroy(GTK_WIDGET(p->data));
 g_list_free(children);
 if(!output)return 0;
 char **lines=g_strsplit(output,"\n",-1);
 int count=0;
 for(int k=0;lines[k] && count<350;k++){
  if(!*lines[k])continue;
  char **parts=g_strsplit(lines[k],"\t",5);
  if(g_strv_length(parts)==4){
   char *kind=decode_field(parts[0]);
   char *id=decode_field(parts[1]);
   char *title=decode_field(parts[2]);
   char *artist=decode_field(parts[3]);
   if(kind && id && title && artist &&
      (!strcmp(kind,"album") || !strcmp(kind,"song") ||
       !strcmp(kind,"artist") || !strcmp(kind,"playlist"))){
    music_add_item(view,kind,id,title,artist);
    ++count;
   }
   g_free(kind);g_free(id);g_free(title);g_free(artist);
  }
  g_strfreev(parts);
 }
 g_strfreev(lines);
 gtk_widget_show_all(view->list);
 return count;
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
   status_set(view,"Music library unavailable. Check URL, app password, and server access.");
  }else{
   int count=render_rows(view,output);
   gtk_label_set_text(GTK_LABEL(view->heading),job->heading);
   char *message=g_strdup_printf("%d items · Connected to your music library",count);
   status_set(view,message);
   g_free(message);
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
 if(!*cfg[6]){
  status_set(view,"Add your Music server URL under NOW Settings.");
  return;
 }
 if(!view->bound_url || g_strcmp0(view->bound_url,cfg[6])){
  wipe_free(view->app_password);
  view->app_password=NULL;
  status_set(view,"Music server changed. Reconnect with its app password.");
  return;
 }
 if(!view->app_password || !*view->app_password){
  status_set(view,"Enter your OpenSubsonic app password and connect first.");
  return;
 }
 if(!g_strcmp0(operation,"search") && (!value || !*value)){
  status_set(view,"Enter an artist, album, or song to search.");
  return;
 }
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  status_set(view,"Installed Music client helper is missing.");
  g_free(helper);
  return;
 }
 const gchar *argv[]={"/usr/bin/python3",helper,view->bound_url,operation,
                      value && *value?value:NULL,"--format=rows","--auth-format=form",NULL};
 /* Avoid a NULL gap (the helper needs no arbitrary value for browse calls). */
 const gchar *without_value[]={"/usr/bin/python3",helper,view->bound_url,operation,
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
 char *encoded_user=g_uri_escape_string(view->username?view->username:"",NULL,FALSE);
 char *encoded_key=g_uri_escape_string(view->app_password,NULL,FALSE);
 MusicQuery *job=g_new0(MusicQuery,1);
 job->process=process;
 job->root=g_object_ref(view->root);
 job->cancel=g_cancellable_new();
 job->operation=g_strdup(operation);
 job->heading=g_strdup(heading?heading:"Music");
 job->input=g_strdup_printf("api_key=%s&username=%s",encoded_key,encoded_user);
 wipe_free(encoded_key);
 g_free(encoded_user);
 view->busy=TRUE;
 status_set(view,"Loading music library...");
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
     query_start(view,"home",NULL,"Recently played albums");
    }else{
     wipe_free(key);wipe_free(username);
     gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE);
     status_set(view,exit_code==3
       ? "Connect your music library once; this device will remember you."
       : "OS keyring unavailable or locked. Check keyring setup to enable automatic sign-in.");
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
 if(view->closing || view->vault_busy || view->busy || !*cfg[6])return;
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

static void music_connect(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing)return;
 const char *entered=gtk_entry_get_text(GTK_ENTRY(view->password));
 if(!entered || !*entered){
  status_set(view,"Enter your user app password from DroppedNeedle.");
  return;
 }
 if(!*cfg[6]){
  status_set(view,"Add your Music server URL under NOW Settings.");
  return;
 }
 g_free(view->bound_url);
 view->bound_url=g_strdup(cfg[6]);
 g_free(view->vault_attempted_url);
 view->vault_attempted_url=g_strdup(cfg[6]);
 wipe_free(view->app_password);
 view->app_password=g_strdup(entered);
 g_free(view->username);
 view->username=g_strdup(gtk_entry_get_text(GTK_ENTRY(view->user)));
 gtk_entry_set_text(GTK_ENTRY(view->password),"");
 view->remember_pending=TRUE;
 query_start(view,"home",NULL,"Recently played albums");
}

static void music_nav(GtkWidget *button,gpointer data){
 MusicView *view=data;
 const char *operation=g_object_get_data(G_OBJECT(button),"music-operation");
 const char *heading=g_object_get_data(G_OBJECT(button),"music-heading");
 if(operation)query_start(view,operation,NULL,heading);
}

static void music_search(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 const char *value=gtk_entry_get_text(GTK_ENTRY(view->search));
 if(value && *value)query_start(view,"search",value,"Search results");
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
 view->queue_index=-1;
 view->playback=now_music_playback_new(music_player_event,view);
 active_music_view=view;
 view->root=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);
 gtk_container_set_border_width(GTK_CONTAINER(view->root),12);
 g_object_set_data_full(G_OBJECT(view->root),"music-view",view,music_view_free);
 g_signal_connect(view->root,"destroy",G_CALLBACK(music_view_destroy),view);

 GtkWidget *top=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 GtkWidget *title=gtk_label_new("MUSIC");
 gtk_widget_set_halign(title,GTK_ALIGN_START);
 gtk_style_context_add_class(gtk_widget_get_style_context(title),"now-heading");
 gtk_box_pack_start(GTK_BOX(top),title,TRUE,TRUE,0);
 GtkWidget *advanced=music_button("Advanced · DroppedNeedle ↗");
 g_signal_connect(advanced,"clicked",G_CALLBACK(music_advanced),view);
 gtk_box_pack_end(GTK_BOX(top),advanced,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(view->root),top,FALSE,FALSE,0);

 GtkWidget *connect=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 view->user=gtk_entry_new();
 gtk_entry_set_placeholder_text(GTK_ENTRY(view->user),"Username (optional)");
 gtk_widget_set_size_request(view->user,125,-1);
 gtk_box_pack_start(GTK_BOX(connect),view->user,FALSE,FALSE,0);
 view->password=gtk_entry_new();
 gtk_entry_set_visibility(GTK_ENTRY(view->password),FALSE);
 gtk_entry_set_placeholder_text(GTK_ENTRY(view->password),"OpenSubsonic app password");
 gtk_widget_set_hexpand(view->password,TRUE);
 gtk_box_pack_start(GTK_BOX(connect),view->password,TRUE,TRUE,0);
 GtkWidget *connect_button=music_button("Connect");
 g_signal_connect(connect_button,"clicked",G_CALLBACK(music_connect),view);
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
 gtk_widget_set_size_request(sidebar,135,-1);
 /* Familiar, functional library destinations: no unsupported
  * recommendation placeholders or hidden DroppedNeedle admin controls. */
 const char *ops[]={"home","albums","recent","new","liked","artists","playlists"};
 const char *titles[]={"Home","Albums","Recently played",
                       "New additions","Liked","Artists","Playlists"};
 const char *headings[]={"Recently played albums","All albums","Recently played albums",
                         "New additions","Liked music","Artists","Your playlists"};
 for(guint i=0;i<G_N_ELEMENTS(ops);i++){
  GtkWidget *b=music_button(titles[i]);
  g_object_set_data(G_OBJECT(b),"music-operation",(gpointer)ops[i]);
  g_object_set_data(G_OBJECT(b),"music-heading",(gpointer)headings[i]);
  g_signal_connect(b,"clicked",G_CALLBACK(music_nav),view);
  gtk_box_pack_start(GTK_BOX(sidebar),b,FALSE,FALSE,0);
 }
 GtkWidget *settings=music_button("Settings");
 g_signal_connect(settings,"clicked",G_CALLBACK(music_settings),view);
 gtk_box_pack_end(GTK_BOX(sidebar),settings,FALSE,FALSE,0);
 GtkWidget *forget=music_button("Forget this device");
 g_signal_connect(forget,"clicked",G_CALLBACK(music_forget_device),view);
 gtk_box_pack_end(GTK_BOX(sidebar),forget,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(content),sidebar,FALSE,FALSE,0);

 GtkWidget *maincol=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
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
 view->heading=gtk_label_new("Recently played albums");
 gtk_widget_set_halign(view->heading,GTK_ALIGN_START);
 gtk_box_pack_start(GTK_BOX(maincol),view->heading,FALSE,FALSE,0);
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
     GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_vexpand(scroll,TRUE);
 view->list=gtk_list_box_new();
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(view->list),GTK_SELECTION_NONE);
 gtk_container_add(GTK_CONTAINER(scroll),view->list);
 gtk_box_pack_start(GTK_BOX(maincol),scroll,TRUE,TRUE,0);

 /* Persistent bottom player only while NOW has an active local stream.
  * It does not play/control phone audio, or fake a progress bar/seek support. */
 view->player_bar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 gtk_container_set_border_width(GTK_CONTAINER(view->player_bar),7);
 gtk_style_context_add_class(gtk_widget_get_style_context(view->player_bar),
                             "music-player-bar");
 view->playing_label=gtk_label_new("");
 gtk_label_set_xalign(GTK_LABEL(view->playing_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(view->playing_label),PANGO_ELLIPSIZE_END);
 gtk_widget_set_hexpand(view->playing_label,TRUE);
 gtk_box_pack_start(GTK_BOX(view->player_bar),view->playing_label,TRUE,TRUE,0);
 view->previous_button=music_button("Previous");
 g_signal_connect(view->previous_button,"clicked",
                  G_CALLBACK(music_prev_clicked),view);
 gtk_box_pack_start(GTK_BOX(view->player_bar),
                    view->previous_button,FALSE,FALSE,0);
 view->pause_button=music_button("Pause");
 g_signal_connect(view->pause_button,"clicked",
                  G_CALLBACK(music_pause_clicked),view);
 gtk_box_pack_start(GTK_BOX(view->player_bar),
                    view->pause_button,FALSE,FALSE,0);
 view->next_button=music_button("Next");
 g_signal_connect(view->next_button,"clicked",
                  G_CALLBACK(music_next_clicked),view);
 gtk_box_pack_start(GTK_BOX(view->player_bar),
                    view->next_button,FALSE,FALSE,0);
 GtkWidget *stop_button=music_button("Stop");
 g_signal_connect(stop_button,"clicked",
                  G_CALLBACK(music_stop_clicked),view);
 gtk_box_pack_start(GTK_BOX(view->player_bar),stop_button,FALSE,FALSE,0);
 /* Show children once, then suppress the entire bar from root show_all()
  * until a real playback session becomes active. */
 gtk_widget_show_all(view->player_bar);
 gtk_widget_set_no_show_all(view->player_bar,TRUE);
 gtk_box_pack_end(GTK_BOX(view->root),view->player_bar,FALSE,FALSE,0);
 g_signal_connect(view->root,"map",G_CALLBACK(music_opened),view);
 gtk_widget_show_all(view->root);
 gtk_widget_hide(view->player_bar);
 return view->root;
}
