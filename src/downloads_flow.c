#include "downloads_flow.h"
#include "downloads_webview.h"
#include "presets.h"
#include <gio/gio.h>
#include <string.h>

static GtkWidget *queue_label;
static GtkWidget *queue_stack;
static GtkWidget *view_holder;
static GtkWidget *web_button;
static GtkWidget *status_label;
static GtkWidget *webview;
static gchar *loaded_url;
static gboolean running;
static gchar *last_host;
static gchar *last_user;
static gchar *pending_web_url;
static gchar *pending_web_host;

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
 gboolean accepted=ok && g_subprocess_get_successful(job->proc) &&
                     out && strlen(out)<32768;
 if(queue_label){
   if(accepted)gtk_label_set_text(GTK_LABEL(queue_label),out);
   else gtk_label_set_text(GTK_LABEL(queue_label),"Queue unavailable. Check server connection.");
 }
 running=FALSE;
 if(pending_web_url && accepted &&
    g_strcmp0(last_host,job->host)==0 &&
    g_strcmp0(last_user,job->user)==0 &&
    now_downloads_webview_url_allowed(pending_web_url,pending_web_host)){
   if(!webview){
     webview=now_downloads_webview_new(pending_web_url,pending_web_host);
     if(webview){
       loaded_url=g_strdup(pending_web_url);
       gtk_box_pack_start(GTK_BOX(view_holder),webview,TRUE,TRUE,0);
       gtk_widget_show_all(view_holder);
     }
   }
   gtk_widget_set_sensitive(web_button,webview!=NULL);
   if(webview){
     gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web");
     gtk_label_set_text(GTK_LABEL(status_label),
       "WebUI management uses qBittorrent's separate login and permissions.");
   }else gtk_label_set_text(GTK_LABEL(status_label),
       "WebKitGTK 4.1 is unavailable; the approved read-only queue remains accessible.");
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
   return;
 }
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
   gtk_label_set_text(GTK_LABEL(queue_label),"Downloads helper missing.");
   g_free(helper);return;
 }
 const char *argv[]={"/usr/bin/python3",helper,host,user,NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
   G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
   gtk_label_set_text(GTK_LABEL(queue_label),"Unable to start queue request.");
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
static void show_queue(GtkWidget *button,gpointer unused){
 (void)button;(void)unused;
 if(!queue_stack)return;
 g_clear_pointer(&pending_web_url,g_free);
 g_clear_pointer(&pending_web_host,g_free);
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
 if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
   "Read-only queue from the approved NOW device connection.");
 if(last_host && last_user)now_downloads_refresh(last_host,last_user);
}
static void show_web(GtkWidget *button,gpointer unused){
 (void)button;(void)unused;
 if(!queue_stack || !webview)return;
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web");
 if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
  "WebUI controls use qBittorrent's own login and permissions.");
}
void now_downloads_open(const char *host,const char *user,const char *webui_url){
 g_free(last_host);last_host=g_strdup(host);
 g_free(last_user);last_user=g_strdup(user);
 if(!queue_stack)return;
 /* Recheck the paired owner credential on every entry. Never let an
  * unapproved device load a full-management WebUI just by editing cfg[7]. */
 if(webview){
   gtk_container_remove(GTK_CONTAINER(view_holder),webview);
   webview=NULL;
   g_clear_pointer(&loaded_url,g_free);
 }
 gtk_widget_set_sensitive(web_button,FALSE);
 show_queue(NULL,NULL);
 if(webui_url && now_downloads_webview_url_allowed(webui_url,host)){
   pending_web_url=g_strdup(webui_url);
   pending_web_host=g_strdup(host);
   gtk_label_set_text(GTK_LABEL(status_label),
     "Checking approved owner access before opening qBittorrent...");
 }else{
   gtk_label_set_text(GTK_LABEL(status_label),
     "Set a private, same-server Downloads WebUI URL in Settings to enable management. Read-only queue is available.");
 }
}
GtkWidget *now_downloads_page(void){
 GtkWidget *root=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 gtk_container_set_border_width(GTK_CONTAINER(root),8);
 GtkWidget *toolbar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,5);
 gtk_box_pack_start(GTK_BOX(root),toolbar,FALSE,FALSE,0);
 web_button=gtk_button_new_with_label("VUE TORRENT");
 gtk_widget_set_sensitive(web_button,FALSE);
 gtk_box_pack_start(GTK_BOX(toolbar),web_button,FALSE,FALSE,0);
 g_signal_connect(web_button,"clicked",G_CALLBACK(show_web),NULL);
 GtkWidget *snapshot=gtk_button_new_with_label("QUEUE SNAPSHOT");
 gtk_box_pack_start(GTK_BOX(toolbar),snapshot,FALSE,FALSE,0);
 g_signal_connect(snapshot,"clicked",G_CALLBACK(show_queue),NULL);
 status_label=gtk_label_new("Connecting to approved server...");
 gtk_label_set_xalign(GTK_LABEL(status_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(status_label),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(root),status_label,FALSE,FALSE,0);

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
