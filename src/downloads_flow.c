#include "downloads_flow.h"
#include "downloads_webview.h"
#include "presets.h"
#include <gio/gio.h>
#include <string.h>

static GtkWidget *queue_label;
static GtkWidget *queue_stack;
static GtkWidget *view_holder;
static GtkWidget *status_label;
static GtkWidget *webview;
static gchar *loaded_url;
static gboolean running;
static gchar *last_host;
static gchar *last_user;
static gchar *last_override;
static gchar *pending_web_url;
static gchar *pending_web_host;
/* One bounded, read-only recovery after a transient first-open SSH failure.
 * Owner approval errors still fail closed; never retry state-changing work. */
static guint reconnect_source;
static gboolean reconnect_used;
static gboolean reconnect_once(gpointer unused){
 (void)unused;
 reconnect_source=0;
 if(!queue_stack || !gtk_widget_get_mapped(queue_stack) ||
    !last_host || !last_user || webview)return G_SOURCE_REMOVE;
 now_downloads_open(last_host,last_user,last_override);
 return G_SOURCE_REMOVE;
}

/* Local credential presence is not server authorization; it is a quick,
 * no-network diagnostic for fresh Linux accounts. The trusted host still
 * checks the restricted key and its owner-device grant on every request. */
static gboolean owner_device_key_exists(void){
 gchar *path=g_build_filename(g_get_home_dir(),".local","share",
   "optiplex-now","games-client","id_ed25519",NULL);
 gboolean present=g_file_test(path,G_FILE_TEST_IS_REGULAR);
 g_free(path);
 return present;
}

typedef struct {
 GSubprocess *proc;
 gchar *host;
 gchar *user;
} QueueJob;

static char *helper_path(void){
 char *exe=g_file_read_link("/proc/self/exe",NULL);
 if(!exe)return g_strdup("/usr/lib/optiplex-now/download-queue-client.py");
 char *bin=g_path_get_dirname(exe);
 char *usr=g_path_get_dirname(bin);
 char *name=g_path_get_basename(usr);
 char *path;
 if(!strcmp(name,"usr") && strcmp(usr,"/usr")){
   char *root=g_path_get_dirname(usr);
   path=g_build_filename(root,"usr","lib","optiplex-now","download-queue-client.py",NULL);
   g_free(root);
 }else path=g_strdup("/usr/lib/optiplex-now/download-queue-client.py");
 g_free(exe);g_free(bin);g_free(usr);g_free(name);
 return path;
}
static void complete(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 QueueJob *job=data;
 char *out=NULL;
 GError *err=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(job->proc,res,&out,NULL,&err);
 /* Never consume an earlier host's response after settings change. Reissue
  * one request for the currently selected approved device instead. */
 if(g_strcmp0(last_host,job->host)!=0 ||
    g_strcmp0(last_user,job->user)!=0){
   running=FALSE;
   g_clear_error(&err);g_free(out);
   g_object_unref(job->proc);
   g_free(job->host);g_free(job->user);g_free(job);
   if(last_host && last_user)now_downloads_refresh(last_host,last_user);
   return;
 }
 gboolean accepted=ok && g_subprocess_get_successful(job->proc) &&
                     out && strlen(out)<32768;
 guint port=0;
 const char *queue_text=out;
 if(accepted){
   if(!g_str_has_prefix(out,"WEBUI_PORT="))accepted=FALSE;
   else{
     const char *endline=strchr(out,'\n');
     char *parsed_end=NULL;
     gint64 value=g_ascii_strtoll(out+strlen("WEBUI_PORT="),&parsed_end,10);
     if(!endline || parsed_end!=endline || value<0 || value>65535 ||
        (value!=0 && value<1024))accepted=FALSE;
     else{
       port=(guint)value;
       queue_text=endline+1;
     }
   }
 }
 if(queue_label){
   if(accepted)gtk_label_set_text(GTK_LABEL(queue_label),queue_text);
   else gtk_label_set_text(GTK_LABEL(queue_label),
     "Owner service request failed. Check restricted device approval and server/downloads availability. Ordinary SSH and Moonlight pairing are separate.");
   if(!accepted && status_label)gtk_label_set_text(GTK_LABEL(status_label),
     "DOWNLOADS NOT AVAILABLE — SEE AUTHORIZATION DETAILS BELOW");
 }
 running=FALSE;
 if(!accepted && pending_web_host && !reconnect_used && !reconnect_source){
   /* Network/Tailscale can become ready just after application startup.
    * Make one delayed, bounded, read-only retry, never an endless poll. */
   reconnect_used=TRUE;
   reconnect_source=g_timeout_add_seconds(4,reconnect_once,NULL);
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
     "DOWNLOADS UNAVAILABLE — RETRYING CONNECTION ONCE");
 }
 if(pending_web_host && accepted &&
    g_strcmp0(last_host,job->host)==0 &&
    g_strcmp0(last_user,job->user)==0){
   /* The host supplied the port through the existing authenticated owner
    * queue request. The host address comes ONLY from the paired NOW config. */
   char *discovered=NULL;
   if(port>0){
     discovered=strchr(job->host,':') ?
       g_strdup_printf("http://[%s]:%u/",job->host,port) :
       g_strdup_printf("http://%s:%u/",job->host,port);
   }
   const char *target=(discovered &&
      now_downloads_webview_url_allowed(discovered,job->host)) ?
      discovered : pending_web_url;
   if(target && now_downloads_webview_url_allowed(target,job->host)){
     webview=now_downloads_webview_new(target,job->host);
     if(webview){
       loaded_url=g_strdup(target);
       gtk_box_pack_start(GTK_BOX(view_holder),webview,TRUE,TRUE,0);
       gtk_widget_show_all(view_holder);
     }
   }
   if(webview){
     gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web");
     gtk_widget_hide(status_label);
   }else{
     gtk_widget_show(status_label);
     gtk_label_set_text(GTK_LABEL(status_label),
       "WebUI unavailable. Read-only queue works; check optional WebKitGTK and approved host.");
   }
   g_free(discovered);
 }
 g_clear_pointer(&pending_web_url,g_free);
 g_clear_pointer(&pending_web_host,g_free);
 g_clear_error(&err);g_free(out);
 g_object_unref(job->proc);
 g_free(job->host);g_free(job->user);g_free(job);
}
void now_downloads_refresh(const char *host,const char *user){
 if(!queue_label || running)return;
 if(!now_valid_host(host) || !now_valid_user(user)){
   gtk_label_set_text(GTK_LABEL(queue_label),"Connect an approved NOW host in Settings.");
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),"SERVER NOT CONFIGURED");
   return;
 }
 if(!owner_device_key_exists()){
   gtk_label_set_text(GTK_LABEL(queue_label),
     "This Linux profile lacks a restricted NOW owner-service key. NOW-managed Games and protected Downloads require host approval. Wolf pairing separately permits access to Wolf-published apps; it does not grant NOW host-service access.");
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
     "OWNER DEVICE NOT ENROLLED — SEE DETAILS BELOW");
   return;
 }
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
   gtk_label_set_text(GTK_LABEL(queue_label),"Downloads helper missing.");
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),"DOWNLOADS COMPONENT MISSING");
   g_free(helper);return;
 }
 const char *argv[]={"/usr/bin/python3",helper,host,user,"--with-port",NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
   G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
   gtk_label_set_text(GTK_LABEL(queue_label),"Unable to start queue request.");
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),"DOWNLOADS CHECK FAILED");
   g_clear_error(&error);return;
 }
 QueueJob *job=g_new0(QueueJob,1);
 job->proc=proc;
 job->host=g_strdup(host);
 job->user=g_strdup(user);
 running=TRUE;
 gtk_label_set_text(GTK_LABEL(queue_label),"Reading authorized download queue...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,complete,job);
}
static void show_web(GtkWidget *button,gpointer unused){
 (void)button;(void)unused;
 if(!queue_stack || !webview)return;
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web");
 if(status_label)gtk_widget_hide(status_label);
}
void now_downloads_open(const char *host,const char *user,const char *webui_url){
 if(!queue_stack)return;
 /* A verified, active owner WebView is kept in its GTK stack while other
  * pages are selected. Do not discard login/JS/search state or relaunch the
  * entire page merely because the user switched tabs. */
 gboolean same=g_strcmp0(last_host,host)==0 &&
               g_strcmp0(last_user,user)==0 &&
               g_strcmp0(last_override,webui_url)==0;
 if(same && webview && loaded_url &&
    now_downloads_webview_url_allowed(loaded_url,host)){
   show_web(NULL,NULL);
   return;
 }
 /* Host identity, SSH user and explicit override are separate from the
  * WebUI session. Only a changed connection invalidates an existing view. */
 if(!same){
   reconnect_used=FALSE;
   if(reconnect_source){g_source_remove(reconnect_source);reconnect_source=0;}
   g_free(last_host);last_host=g_strdup(host);
   g_free(last_user);last_user=g_strdup(user);
   g_free(last_override);last_override=g_strdup(webui_url);
   if(webview){
     gtk_container_remove(GTK_CONTAINER(view_holder),webview);
     webview=NULL;
     g_clear_pointer(&loaded_url,g_free);
   }
 }
 /* If the initial authorization is still in flight, leave it alone;
  * selecting this tab again must not restart or duplicate the request. */
 if(same && running)return;
 /* A user-initiated revisit immediately retries instead of leaving a
  * previously scheduled one-shot recovery running behind this request. */
 if(reconnect_source){g_source_remove(reconnect_source);reconnect_source=0;}
 gtk_widget_show(status_label);
 g_clear_pointer(&pending_web_url,g_free);
 g_clear_pointer(&pending_web_host,g_free);
 if(now_valid_host(host) && now_valid_user(user)){
   pending_web_host=g_strdup(host);
   if(webui_url && now_downloads_webview_url_allowed(webui_url,host))
     pending_web_url=g_strdup(webui_url);
   gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
   gtk_label_set_text(GTK_LABEL(status_label),
     "Discovering VPN-bound downloader through approved server...");
   now_downloads_refresh(host,user);
 }else{
   gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
   gtk_label_set_text(GTK_LABEL(status_label),
     "Connect an approved server to discover downloads.");
 }
}
GtkWidget *now_downloads_page(void){
 GtkWidget *root=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 gtk_container_set_border_width(GTK_CONTAINER(root),8);
 /* A successfully loaded VueTorrent uses the whole page. The read-only
  * queue remains an automatic fallback when the embedded UI is unavailable. */
 status_label=gtk_label_new("Connecting to approved server...");
 gtk_label_set_xalign(GTK_LABEL(status_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(status_label),PANGO_ELLIPSIZE_END);
 /* Suppress the informational row entirely while VueTorrent is open,
  * including on gtk_widget_show_all after tray restore or page changes. */
 gtk_widget_set_no_show_all(status_label,TRUE);
 gtk_box_pack_start(GTK_BOX(root),status_label,FALSE,FALSE,0);
 gtk_widget_show(status_label);

 queue_stack=gtk_stack_new();
 gtk_widget_set_vexpand(queue_stack,TRUE);
 gtk_box_pack_start(GTK_BOX(root),queue_stack,TRUE,TRUE,0);
 view_holder=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);
 gtk_stack_add_named(GTK_STACK(queue_stack),view_holder,"web");
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);
 GtkWidget *body=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);
 gtk_container_set_border_width(GTK_CONTAINER(body),12);
 gtk_container_add(GTK_CONTAINER(scroll),body);
 queue_label=gtk_label_new("Select Downloads to inspect the approved server.");
 gtk_label_set_selectable(GTK_LABEL(queue_label),TRUE);
 gtk_label_set_xalign(GTK_LABEL(queue_label),0);
 gtk_label_set_yalign(GTK_LABEL(queue_label),0);
 gtk_label_set_line_wrap(GTK_LABEL(queue_label),TRUE);
 gtk_box_pack_start(GTK_BOX(body),queue_label,FALSE,FALSE,0);
 gtk_stack_add_named(GTK_STACK(queue_stack),scroll,"queue");
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
 return root;
}
