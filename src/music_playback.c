/* Async, per-session music playback boundary for NOW.
 * A dedicated Python helper authenticates to OpenSubsonic by POST, streams
 * only audio bytes to local mpv, and accepts PAUSE/RESUME/STOP via stdin.
 * Passwords never appear in subprocess argv, URLs, persistent files, or mpv.
 */
#include "music_playback.h"
#include "music_helper_paths.h"
#include <gio/gio.h>
#include <string.h>
#include <stdio.h>
#include <signal.h>

struct NowMusicPlayback {
 gint refs;
 gboolean closing;
 struct MusicJob *current; /* owns one reference */
 NowMusicPlaybackEvent notify;
 void *user_data;
};
typedef struct MusicJob {
 gint refs;
 NowMusicPlayback *owner; /* holds manager alive through asynchronous jobs */
 GSubprocess *proc;
 GDataInputStream *events;
 GCancellable *cancel;
 gboolean stopped;
} MusicJob;

static void secure_free(char *s) {
 if(!s)return;
 volatile char *p=(volatile char *)s;
 size_t n=strlen(s);
 while(n--)*p++=0;
 g_free(s);
}
static NowMusicPlayback *manager_ref(NowMusicPlayback *m){
 g_atomic_int_inc(&m->refs);return m;
}
static void manager_unref(NowMusicPlayback *m){
 if(g_atomic_int_dec_and_test(&m->refs))g_free(m);
}
static MusicJob *job_ref(MusicJob *j){
 g_atomic_int_inc(&j->refs);return j;
}
static void job_unref(MusicJob *j){
 if(!g_atomic_int_dec_and_test(&j->refs))return;
 g_clear_object(&j->cancel);
 g_clear_object(&j->events);
 g_clear_object(&j->proc);
 manager_unref(j->owner);
 g_free(j);
}
static void job_stop(MusicJob *j){
 if(j->stopped)return;
 j->stopped=TRUE;
 /* Kill only THIS local playback worker; the helper sets Linux
  * parent-death SIGTERM on mpv so no decoder survives a forced close. */
 g_cancellable_cancel(j->cancel);
 if(j->proc && !g_subprocess_get_if_exited(j->proc))
   g_subprocess_force_exit(j->proc);
}
static void detach_current(NowMusicPlayback *m,MusicJob *j,gboolean force){
 if(m->current!=j)return;
 m->current=NULL;
 if(force)job_stop(j);
 job_unref(j);
}
static void notify_event(MusicJob *j,const char *event){
 NowMusicPlayback *m=j->owner;
 if(m->closing || m->current!=j || !m->notify)return;
 gboolean terminal=!g_strcmp0(event,"ENDED") ||
                   !g_strcmp0(event,"ERROR") ||
                   !g_strcmp0(event,"STOPPED");
 if(terminal){
  /* Callers may start the next track in this callback. Detach first to
   * prevent a terminal event from destroying a new session. */
  detach_current(m,j,FALSE);
 }
 m->notify(event,m->user_data);
}
static void read_event(MusicJob *j);
static void event_read_complete(GObject *source,GAsyncResult *result,gpointer user){
 (void)source;
 MusicJob *j=user;
 GError *error=NULL;
 gsize length=0;
 char *line=g_data_input_stream_read_line_finish(j->events,result,&length,&error);
 if(!j->stopped && j->owner->current==j) {
  if(!line){
   if(error && g_error_matches(error,G_IO_ERROR,G_IO_ERROR_CANCELLED)){
    /* Cancellation is expected on a deliberate user stop. */
   }else notify_event(j,"ERROR");
  }else if(length<80){
   if(!strcmp(line,"BUFFERING")||!strcmp(line,"PLAYING")||
      !strcmp(line,"PAUSED")||!strcmp(line,"ENDED")||
      !strcmp(line,"STOPPED")||!strcmp(line,"ERROR")||
      !strcmp(line,"SEEK_UNAVAILABLE"))
    notify_event(j,line);
   else if(g_str_has_prefix(line,"POSITION ")){
    unsigned position=0,duration=0;
    char extra=0;
    /* Reject malformed or injected worker lines before handing to GTK. */
    if(sscanf(line,"POSITION %u %u %c",&position,&duration,&extra)==2 &&
       duration>0 && duration<=604800 && position<=duration)
     notify_event(j,line);
   }
  }
  if(line && !j->stopped && j->owner->current==j)
   read_event(j);
 }
 g_clear_error(&error);
 g_free(line);
 job_unref(j);
}
static void read_event(MusicJob *j){
 g_data_input_stream_read_line_async(
   j->events,G_PRIORITY_DEFAULT,j->cancel,
   event_read_complete,job_ref(j));
}
static void wait_finished(GObject *source,GAsyncResult *result,gpointer user){
 (void)source;
 MusicJob *j=user;
 GError *error=NULL;
 gboolean waited=g_subprocess_wait_finish(j->proc,result,&error);
 if(waited && !j->stopped && !j->owner->closing &&
    !g_subprocess_get_successful(j->proc)){
  /* Log process result only. No URL, track identifier, or credentials. */
  if(g_subprocess_get_if_signaled(j->proc))
   g_warning("Music playback helper ended on signal %d",
             g_subprocess_get_term_sig(j->proc));
  else if(g_subprocess_get_if_exited(j->proc))
   g_warning("Music playback helper exited with status %d",
             g_subprocess_get_exit_status(j->proc));
 }
 if(j->owner->current==j && !j->stopped){
  /* A helper disappearing without ENDED/ERROR is not a working session. */
  notify_event(j,waited&&g_subprocess_get_successful(j->proc)?"ENDED":"ERROR");
 }
 g_clear_error(&error);
 job_unref(j);
}
static char *helper_path(void){
 return now_music_helper_path(NOW_MUSIC_HELPER_PLAYER);
}
NowMusicPlayback *now_music_playback_new(NowMusicPlaybackEvent cb,void *data){
 /* GLib before 2.82 does not suppress SIGPIPE for GSubprocess pipes.
  * The music helper can exit between spawn and a credential/PAUSE/SEEK
  * write. Without this, the kernel may terminate the entire GTK app,
  * instead of letting GOutputStream return a normal broken-pipe error.
  * Match modern GLib's process-wide behavior; the worker uses its own
  * Python subprocess with normal SIGPIPE defaults. */
#ifdef SIGPIPE
 signal(SIGPIPE,SIG_IGN);
#endif
 NowMusicPlayback *m=g_new0(NowMusicPlayback,1);
 m->refs=1;
 m->notify=cb;
 m->user_data=data;
 return m;
}
gboolean now_music_playback_start(NowMusicPlayback *m,const char *server,
                         const char *username,const char *key,const char *id,
                         int initial_volume){
 if(!m || m->closing || !server || !*server ||
    !key || !*key || !id || !*id || strlen(id)>512 ||
    initial_volume<0 || initial_volume>100)
  return FALSE;
 now_music_playback_stop(m);
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  g_free(helper);return FALSE;
 }
 char *volume_arg=g_strdup_printf("%d",initial_volume);
 const gchar *argv[]={"/usr/bin/python3",helper,server,id,volume_arg,NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
   G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_PIPE|
   G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 g_free(volume_arg);
 if(!proc){
  g_clear_error(&error);
  return FALSE;
 }
 char *encoded=g_uri_escape_string(key,NULL,FALSE);
 char *user=g_uri_escape_string(username?username:"",NULL,FALSE);
 char *line=g_strdup_printf("api_key=%s&username=%s\n",encoded,user);
 secure_free(encoded);
 g_free(user);
 GOutputStream *input=g_subprocess_get_stdin_pipe(proc);
 gsize written=0;
 gboolean delivered=g_output_stream_write_all(input,line,strlen(line),
                                                 &written,NULL,&error);
 secure_free(line);
 if(!delivered){
  g_subprocess_force_exit(proc);
  g_object_unref(proc);
  g_clear_error(&error);
  return FALSE;
 }
 MusicJob *j=g_new0(MusicJob,1);
 j->refs=1;
 j->owner=manager_ref(m);
 j->proc=proc;
 j->events=g_data_input_stream_new(g_subprocess_get_stdout_pipe(proc));
 j->cancel=g_cancellable_new();
 m->current=j;
 read_event(j);
 /* Uncancellable wait always reaps a killed/failed local helper. */
 g_subprocess_wait_async(proc,NULL,wait_finished,job_ref(j));
 return TRUE;
}
void now_music_playback_pause(NowMusicPlayback *m,gboolean paused){
 if(!m || m->closing || !m->current)return;
 GOutputStream *out=g_subprocess_get_stdin_pipe(m->current->proc);
 const char *cmd=paused?"PAUSE\n":"RESUME\n";
 gsize written=0;
 GError *error=NULL;
 if(!g_output_stream_write_all(out,cmd,strlen(cmd),
                               &written,NULL,&error)){
  /* A dead player cannot be shown as paused/playing. */
  MusicJob *j=m->current;
  job_ref(j);
  notify_event(j,"ERROR");
  job_unref(j);
 }
 g_clear_error(&error);
}
void now_music_playback_volume(NowMusicPlayback *m,int level){
 if(!m || m->closing || !m->current || level<0 || level>100)return;
 GOutputStream *out=g_subprocess_get_stdin_pipe(m->current->proc);
 char *command=g_strdup_printf("VOLUME %d\n",level);
 gsize written=0;
 GError *error=NULL;
 gboolean ok=g_output_stream_write_all(out,command,strlen(command),
                                        &written,NULL,&error);
 g_free(command);
 if(!ok){
  MusicJob *j=m->current;
  job_ref(j);
  notify_event(j,"ERROR");
  job_unref(j);
 }
 g_clear_error(&error);
}
void now_music_playback_seek(NowMusicPlayback *m,int seconds){
 if(!m || m->closing || !m->current || seconds<0 || seconds>604800)return;
 GOutputStream *out=g_subprocess_get_stdin_pipe(m->current->proc);
 char *line=g_strdup_printf("SEEK %d\n",seconds);
 gsize written=0;
 GError *error=NULL;
 gboolean sent=g_output_stream_write_all(out,line,strlen(line),
                                          &written,NULL,&error);
 g_free(line);
 if(!sent){
  MusicJob *j=m->current;
  job_ref(j);
  notify_event(j,"ERROR");
  job_unref(j);
 }
 g_clear_error(&error);
}
void now_music_playback_stop(NowMusicPlayback *m){
 if(!m || !m->current)return;
 MusicJob *j=m->current;
 detach_current(m,j,TRUE);
}
gboolean now_music_playback_active(const NowMusicPlayback *m){
 return m && !m->closing && m->current!=NULL;
}
void now_music_playback_free(NowMusicPlayback *m){
 if(!m)return;
 m->closing=TRUE;
 m->notify=NULL;
 m->user_data=NULL;
 now_music_playback_stop(m);
 manager_unref(m);
}
