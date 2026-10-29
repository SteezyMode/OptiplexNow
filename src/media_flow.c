#include <gtk/gtk.h>
#include <gio/gio.h>
#include <string.h>
#include "config.h"
#include "presets.h"
#include "media_flow.h"
#include "media_endpoint_token.h"

static void (*now_media_status_cb)(const char *);
static void (*now_media_open_cb)(const char *);
static void (*now_media_in_app_cb)(const char *);
static const char *now_media_host(void){ return cfg[0]; }
static const char *now_media_user(void){ return cfg[1]; }
static const char *now_media_fallback(void){ return cfg[5]; }
static void now_media_say(const char *text){ if(now_media_status_cb)now_media_status_cb(text); }
static void now_media_browser_open(const char *url){ if(now_media_open_cb)now_media_open_cb(url); }
void now_media_bind(void (*status)(const char *),void (*open)(const char *),
                    void (*in_app)(const char *)){
 now_media_status_cb=status;now_media_open_cb=open;now_media_in_app_cb=in_app;
}

/* Videos discovers a strictly bounded endpoint through restricted owner SSH.
 * A media helper cannot dictate a hostname, credentials or arbitrary URL. */
typedef struct {
 GSubprocess *process;
 char *host;
 gboolean embedded;
} MediaDiscovery;

static gboolean media_discovery_running=FALSE;

static char *media_helper_path(void){
 char *exe=g_file_read_link("/proc/self/exe",NULL);
 if(!exe)return g_strdup("/usr/lib/optiplex-now/media-discover.py");
 char *bin=g_path_get_dirname(exe);
 char *usr=g_path_get_dirname(bin);
 char *name=g_path_get_basename(usr);
 char *path;
 if(!strcmp(name,"usr") && strcmp(usr,"/usr")){
  char *root=g_path_get_dirname(usr);
  path=g_build_filename(root,"usr","lib","optiplex-now","media-discover.py",NULL);
  g_free(root);
 }else path=g_strdup("/usr/lib/optiplex-now/media-discover.py");
 g_free(name);g_free(usr);g_free(bin);g_free(exe);
 return path;
}

static void media_discovery_complete(GObject *unused,GAsyncResult *res,gpointer userdata){
 (void)unused;
 MediaDiscovery *job=userdata;
 gchar *reply=NULL;
 GError *error=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(
   job->process,res,&reply,NULL,&error);
 media_discovery_running=FALSE;
 gchar *url=NULL;
 if(ok && g_subprocess_get_successful(job->process) &&
    g_strcmp0(job->host,now_media_host())==0 &&
    now_valid_host(job->host))
   url=now_media_url_from_token(job->host,reply);
 if(url){
  now_media_say(job->embedded?"OPENING JELLYFIN IN NOW":"OPENING VERIFIED JELLYFIN");
  if(job->embedded && now_media_in_app_cb)now_media_in_app_cb(url);
  else now_media_browser_open(url);
 }else if(*now_media_fallback() && now_safe_preset_url(now_media_fallback())){
  /* Explicit legacy override remains functional when automatic discovery
   * is unavailable. Never open an address from the SSH response. */
  now_media_say("DISCOVERY UNAVAILABLE. USING SAVED VIDEOS URL");
  if(job->embedded && now_media_in_app_cb)now_media_in_app_cb(now_media_fallback());
  else now_media_browser_open(now_media_fallback());
 }else{
  now_media_say("JELLYFIN NOT VERIFIED. CHECK SERVER CONNECTION OR MEDIA SETUP");
 }
 g_free(url);
 g_clear_error(&error);
 g_free(reply);
 g_object_unref(job->process);
 g_free(job->host);
 g_free(job);
}
static void now_media_open_target(gboolean embedded){
 if(media_discovery_running){now_media_say("CHECKING JELLYFIN CONNECTION");return;}
 if(!now_valid_host(now_media_host()) || !now_valid_user(now_media_user())){
  if(*now_media_fallback() && now_safe_preset_url(now_media_fallback())){
    if(embedded && now_media_in_app_cb)now_media_in_app_cb(now_media_fallback());
    else now_media_browser_open(now_media_fallback());
  }else now_media_say("CONNECT AN AUTHORIZED HOST IN SETTINGS");
  return;
 }
 char *helper=media_helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
  if(*now_media_fallback() && now_safe_preset_url(now_media_fallback())){
    if(embedded && now_media_in_app_cb)now_media_in_app_cb(now_media_fallback());
    else now_media_browser_open(now_media_fallback());
  }else now_media_say("JELLYFIN DISCOVERY HELPER MISSING");
  g_free(helper);return;
 }
 const gchar *argv[]={"/usr/bin/python3",helper,now_media_host(),now_media_user(),NULL};
 GError *error=NULL;
 GSubprocess *process=g_subprocess_newv(argv,
    G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,
    &error);
 g_free(helper);
 if(!process){
  g_clear_error(&error);
  now_media_say("UNABLE TO CHECK JELLYFIN");
  return;
 }
 MediaDiscovery *job=g_new0(MediaDiscovery,1);
 job->process=process;
 job->host=g_strdup(now_media_host());
 job->embedded=embedded;
 media_discovery_running=TRUE;
 now_media_say("DISCOVERING JELLYFIN THROUGH AUTHORIZED HOST...");
 g_subprocess_communicate_utf8_async(process,NULL,NULL,
                                     media_discovery_complete,job);
}


void now_media_open_videos(void){now_media_open_target(FALSE);}
void now_media_open_videos_in_app(void){now_media_open_target(TRUE);}
