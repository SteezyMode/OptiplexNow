#include "downloads_flow.h"
#include "downloads_webview.h"
#include "downloads_queue_view.h"
#include "downloads_search_view.h"
#include "downloads_destination_view.h"
#include "presets.h"
#include <gio/gio.h>
#include <string.h>

static GtkWidget *queue_label;
static GtkWidget *queue_view;
static GtkWidget *search_view;
static GtkWidget *destination_view;
static GtkWidget *downloads_subtabs;
static GtkWidget *transfers_tab,*search_tab;
static gboolean queue_has_data;
static GtkWidget *advanced_button;
static GtkWidget *back_button;
static gchar *approved_web_url;
static GtkWidget *queue_stack;
static GtkWidget *view_holder;
static GtkWidget *status_label;
static GtkWidget *vpn_button,*vpn_detail,*vpn_checked,*vpn_account;
static gboolean vpn_inflight;
static GtkWidget *webview;
static gchar *loaded_url;
static gboolean running;
static gboolean manage_running;
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
/* A read-only, owner-authorized Gluetun health/status snapshot.
 * Never label the connection "leak-proof": a healthcheck is not an outage test.
 * No container identifiers, credentials or raw network topology reach GTK. */
typedef struct {
 GSubprocess *proc;
 gchar *host,*user;
} VpnJob;
static void vpn_set_status(const char *label,const char *description,
                           const char *last_checked,gboolean airvpn){
 if(!vpn_button)return;
 gtk_button_set_label(GTK_BUTTON(vpn_button),label);
 gtk_label_set_text(GTK_LABEL(vpn_detail),description);
 gtk_label_set_text(GTK_LABEL(vpn_checked),last_checked);
 if(vpn_account){
   if(airvpn)gtk_widget_show(vpn_account);
   else gtk_widget_hide(vpn_account);
 }
}
static void vpn_finished(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 VpnJob *job=data;
 gchar *output=NULL;
 GError *error=NULL;
 gboolean communicated=g_subprocess_communicate_utf8_finish(
   job->proc,res,&output,NULL,&error);
 if(!g_strcmp0(last_host,job->host) &&
    !g_strcmp0(last_user,job->user)){
   gboolean valid=communicated && g_subprocess_get_successful(job->proc) &&
                  output && strlen(output)<128;
   gchar **fields=valid?g_strsplit(g_strchomp(output),"\t",-1):NULL;
   valid=fields && g_strv_length(fields)==3 &&
         !strcmp(fields[0],"VPN") &&
         (!strcmp(fields[1],"HEALTHY") || !strcmp(fields[1],"UNVERIFIED")) &&
         (!strcmp(fields[2],"airvpn") || !strcmp(fields[2],"other"));
   if(valid){
     gboolean healthy=!strcmp(fields[1],"HEALTHY");
     gboolean airvpn=!strcmp(fields[2],"airvpn");
     GDateTime *now=g_date_time_new_now_local();
     gchar *clock=g_date_time_format(now,"Last checked at %H:%M");
     vpn_set_status(healthy?"VPN: HEALTHY":"VPN: UNVERIFIED",
       healthy?"Gluetun is healthy and qBittorrent shares its network.\n"
               "This is not continuous egress or kill-switch verification.":
               "The VPN-bound downloader could not be confirmed healthy.\n"
               "Do not assume downloads are protected.",
       clock,airvpn);
     g_free(clock);g_date_time_unref(now);
   }else{
     vpn_set_status("VPN: UNKNOWN","VPN status unavailable.\n"
                    "Do not assume downloads are protected.",
                    "Last check failed",FALSE);
   }
   g_strfreev(fields);
 }
 vpn_inflight=FALSE;
 g_clear_error(&error);
 g_free(output);
 g_object_unref(job->proc);
 g_free(job->host);g_free(job->user);g_free(job);
}
static void vpn_refresh(void){
 if(vpn_inflight || !vpn_button || !last_host || !last_user ||
    !now_valid_host(last_host) || !now_valid_user(last_user) ||
    !owner_device_key_exists())return;
 gchar *queue_helper=helper_path();
 gchar *parent=g_path_get_dirname(queue_helper);
 gchar *operations_helper=g_build_filename(parent,"download-operations-client.py",NULL);
 gboolean exists=g_file_test(operations_helper,G_FILE_TEST_IS_REGULAR);
 if(exists){
   const gchar *argv[]={"/usr/bin/python3",operations_helper,last_host,last_user,
                        "vpn",NULL};
   GError *error=NULL;
   GSubprocess *proc=g_subprocess_newv(
        argv,G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
   if(proc){
     VpnJob *job=g_new0(VpnJob,1);
     job->proc=proc;job->host=g_strdup(last_host);job->user=g_strdup(last_user);
     vpn_inflight=TRUE;
     g_subprocess_communicate_utf8_async(proc,NULL,NULL,vpn_finished,job);
   }
   g_clear_error(&error);
 }
 g_free(operations_helper);g_free(parent);g_free(queue_helper);
}
static gboolean vpn_poll(gpointer unused){
 (void)unused;
 if(queue_stack && gtk_widget_get_mapped(queue_stack))vpn_refresh();
 return G_SOURCE_CONTINUE;
}
static void on_vpn_clicked(GtkButton *button,gpointer data){
 (void)data;
 GtkWidget *popover=g_object_get_data(G_OBJECT(button),"now-vpn-popover");
 if(popover)gtk_widget_show_all(popover);
 if(vpn_account && !gtk_widget_get_visible(vpn_account)){
   /* Keep the account link hidden unless the host identified AirVPN. */
   gtk_widget_hide(vpn_account);
 }
 vpn_refresh();
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
 if(accepted && !now_downloads_queue_view_update(queue_view,
        g_strchomp((gchar *)queue_text)))
   accepted=FALSE;
 if(queue_label){
   if(accepted)gtk_label_set_text(GTK_LABEL(queue_label),"Current downloads");
   else gtk_label_set_text(GTK_LABEL(queue_label),
     "Owner service request failed. Check restricted device approval and server/downloads availability. Ordinary SSH and Moonlight pairing are separate.");
   if(!accepted){
     queue_has_data=FALSE;
     now_downloads_queue_view_message(queue_view,"Download queue unavailable.");
     if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
       "DOWNLOADS NOT AVAILABLE — SEE AUTHORIZATION DETAILS BELOW");
   }else if(status_label){
     queue_has_data=TRUE;
     gtk_label_set_text(GTK_LABEL(status_label),"QUEUE UPDATED");
   }
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
 /* Discovery authorizes ONLY an optional in-page Advanced VueTorrent view.
  * Never auto-open that view: the native read-only queue is primary. */
 g_clear_pointer(&approved_web_url,g_free);
 if(pending_web_host && accepted &&
    g_strcmp0(last_host,job->host)==0 &&
    g_strcmp0(last_user,job->user)==0){
   gchar *discovered=NULL;
   if(port>0)
     discovered=strchr(job->host,':') ?
       g_strdup_printf("http://[%s]:%u/",job->host,port) :
       g_strdup_printf("http://%s:%u/",job->host,port);
   const char *target=(discovered &&
      now_downloads_webview_url_allowed(discovered,job->host)) ?
      discovered : pending_web_url;
   if(target && now_downloads_webview_url_allowed(target,job->host))
     approved_web_url=g_strdup(target);
   g_free(discovered);
 }
 if(advanced_button)
   gtk_widget_set_sensitive(advanced_button,approved_web_url!=NULL);
 if(!accepted && webview){
   gtk_container_remove(GTK_CONTAINER(view_holder),webview);
   webview=NULL;
   g_clear_pointer(&loaded_url,g_free);
   gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
 }
 g_clear_pointer(&pending_web_url,g_free);
 g_clear_pointer(&pending_web_host,g_free);
 g_clear_error(&err);g_free(out);
 g_object_unref(job->proc);
 g_free(job->host);g_free(job->user);g_free(job);
}
void now_downloads_refresh(const char *host,const char *user){
 if(!queue_label || running)return;
 g_clear_pointer(&approved_web_url,g_free);
 if(advanced_button)gtk_widget_set_sensitive(advanced_button,FALSE);
 if(queue_stack)
   gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
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
 /* Fixed read-only broker request, with a sanitized native queue protocol. */
 const char *argv[]={"/usr/bin/python3",helper,host,user,"--native",NULL};
 g_clear_pointer(&pending_web_host,g_free);
 g_clear_pointer(&pending_web_url,g_free);
 pending_web_host=g_strdup(host);
 if(last_override && now_downloads_webview_url_allowed(last_override,host))
   pending_web_url=g_strdup(last_override);
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
 gtk_label_set_text(GTK_LABEL(queue_label),"Current downloads");
 if(!queue_has_data)
   now_downloads_queue_view_message(queue_view,"Refreshing approved download queue...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,complete,job);
}
static gboolean refresh_visible_transfers(gpointer unused){
 (void)unused;
 if(queue_stack && downloads_subtabs && last_host && last_user &&
    gtk_widget_get_mapped(queue_stack) && !running &&
    !g_strcmp0(gtk_stack_get_visible_child_name(GTK_STACK(queue_stack)),"queue") &&
    !g_strcmp0(gtk_stack_get_visible_child_name(GTK_STACK(downloads_subtabs)),"transfers"))
   now_downloads_refresh(last_host,last_user);
 return G_SOURCE_CONTINUE;
}
static void update_download_tab_buttons(void){
 if(!downloads_subtabs)return;
 const char *active=gtk_stack_get_visible_child_name(GTK_STACK(downloads_subtabs));
 GtkStyleContext *a=gtk_widget_get_style_context(transfers_tab);
 GtkStyleContext *b=gtk_widget_get_style_context(search_tab);
 if(active && !strcmp(active,"search")){
   gtk_style_context_remove_class(a,"active");
   gtk_style_context_add_class(b,"active");
 }else{
   gtk_style_context_add_class(a,"active");
   gtk_style_context_remove_class(b,"active");
 }
}
static void switch_download_subtab(GtkButton *button,gpointer unused){
 (void)unused;
 if(!downloads_subtabs)return;
 const char *page=g_object_get_data(G_OBJECT(button),"now-download-tab");
 gtk_stack_set_visible_child_name(GTK_STACK(downloads_subtabs),page);
 update_download_tab_buttons();
 if(!strcmp(page,"transfers") && last_host && last_user && !running)
   now_downloads_refresh(last_host,last_user);
}
static void show_queue(GtkWidget *button,gpointer unused){
 (void)button;(void)unused;
 if(!queue_stack)return;
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
 if(back_button)gtk_widget_hide(back_button);
 if(advanced_button)gtk_widget_show(advanced_button);
 if(status_label)gtk_widget_show(status_label);
}
static void show_web(GtkWidget *button,gpointer unused){
 (void)button;(void)unused;
 if(!queue_stack || !approved_web_url || !last_host ||
    !now_downloads_webview_url_allowed(approved_web_url,last_host))return;
 if(!webview){
   webview=now_downloads_webview_new(approved_web_url,last_host);
   if(webview){
     loaded_url=g_strdup(approved_web_url);
     gtk_box_pack_start(GTK_BOX(view_holder),webview,TRUE,TRUE,0);
     gtk_widget_show_all(view_holder);
   }
 }
 if(!webview){
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
     "Advanced WebUI unavailable. Native queue still works; check WebKitGTK.");
   return;
 }
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web");
 if(status_label)gtk_widget_hide(status_label);
 if(advanced_button)gtk_widget_hide(advanced_button);
 if(back_button)gtk_widget_show(back_button);
}
void now_downloads_open(const char *host,const char *user,const char *webui_url){
 if(!queue_stack)return;
 /* A verified, active owner WebView is kept in its GTK stack while other
  * pages are selected. Do not discard login/JS/search state or relaunch the
  * entire page merely because the user switched tabs. */
 gboolean same=g_strcmp0(last_host,host)==0 &&
               g_strcmp0(last_user,user)==0 &&
               g_strcmp0(last_override,webui_url)==0;
 if(search_view){
   gchar *queue_helper=helper_path();
   gchar *parent=g_path_get_dirname(queue_helper);
   gchar *search_helper=g_build_filename(parent,"download-search-client.py",NULL);
   gchar *operations_helper=g_build_filename(parent,"download-operations-client.py",NULL);
   gboolean enrolled=now_valid_host(host) && now_valid_user(user) &&
                     owner_device_key_exists();
   gboolean search_ready=enrolled && g_file_test(search_helper,G_FILE_TEST_IS_REGULAR);
   gboolean picker_ready=enrolled && g_file_test(operations_helper,G_FILE_TEST_IS_REGULAR);
   now_downloads_search_view_configure(search_view,
       search_ready?host:NULL,search_ready?user:NULL,
       search_ready?search_helper:NULL);
   if(destination_view)
     now_downloads_destination_view_configure(destination_view,
       picker_ready?host:NULL,picker_ready?user:NULL,
       picker_ready?operations_helper:NULL);
   g_free(operations_helper);g_free(search_helper);
   g_free(parent);g_free(queue_helper);
 }
 if(same && webview && loaded_url &&
    now_downloads_webview_url_allowed(loaded_url,host)){
   /* Keep the WebKit session alive but show the native queue on entry. */
   show_queue(NULL,NULL);
   if(!running)now_downloads_refresh(host,user);
   vpn_refresh();
   return;
 }
 /* Host identity, SSH user and explicit override are separate from the
  * WebUI session. Only a changed connection invalidates an existing view. */
 if(!same){
   g_clear_pointer(&approved_web_url,g_free);
   if(advanced_button)gtk_widget_set_sensitive(advanced_button,FALSE);
   reconnect_used=FALSE;
   if(reconnect_source){g_source_remove(reconnect_source);reconnect_source=0;}
   g_free(last_host);last_host=g_strdup(host);
   g_free(last_user);last_user=g_strdup(user);
   g_free(last_override);last_override=g_strdup(webui_url);
   vpn_set_status("VPN: UNKNOWN","Checking the selected download host.",
                  "No verification yet",FALSE);
   if(webview){
     gtk_container_remove(GTK_CONTAINER(view_holder),webview);
     webview=NULL;
     g_clear_pointer(&loaded_url,g_free);
   }
 }
 vpn_refresh();
 /* If the initial authorization is still in flight, leave it alone;
  * selecting this tab again must not restart or duplicate the request. */
 if(same && running)return;
 /* A user-initiated revisit immediately retries instead of leaving a
  * previously scheduled one-shot recovery running behind this request. */
 if(reconnect_source){g_source_remove(reconnect_source);reconnect_source=0;}
 show_queue(NULL,NULL);
 g_clear_pointer(&pending_web_url,g_free);
 g_clear_pointer(&pending_web_host,g_free);
 if(now_valid_host(host) && now_valid_user(user)){
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
typedef struct {
 GSubprocess *proc;
 gchar *host,*user,*operation;
} ManageJob;
static void managed_finished(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 ManageJob *job=data;
 gchar *out=NULL;
 GError *error=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(job->proc,res,&out,NULL,&error)
             && g_subprocess_get_successful(job->proc) &&
             out && !strcmp(g_strchomp(out),"MANAGED");
 manage_running=FALSE;
 if(!g_strcmp0(last_host,job->host) && !g_strcmp0(last_user,job->user)){
   if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
       ok?"Torrent action submitted.":"Torrent action failed; retry from Transfers.");
   if(last_host && last_user && !running)now_downloads_refresh(last_host,last_user);
 }
 g_clear_error(&error);g_free(out);
 g_object_unref(job->proc);
 g_free(job->host);g_free(job->user);g_free(job->operation);g_free(job);
}
static void on_transfer_action(const char *operation,const char *torrent_hash,
                               const char *name,gpointer unused){
 (void)name;(void)unused;
 if(manage_running || !last_host || !last_user ||
    !now_valid_host(last_host) || !now_valid_user(last_user) ||
    !owner_device_key_exists() || !operation || !torrent_hash)return;
 gchar *queue_helper=helper_path();
 gchar *directory=g_path_get_dirname(queue_helper);
 gchar *helper=g_build_filename(directory,"download-operations-client.py",NULL);
 if(g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
   const gchar *argv[]={"/usr/bin/python3",helper,last_host,last_user,
                        "manage",operation,torrent_hash,NULL};
   GError *error=NULL;
   GSubprocess *proc=g_subprocess_newv(
        argv,G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
   if(proc){
     ManageJob *job=g_new0(ManageJob,1);
     job->proc=proc;
     job->host=g_strdup(last_host);
     job->user=g_strdup(last_user);
     job->operation=g_strdup(operation);
     manage_running=TRUE;
     if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
                                        "Submitting approved torrent action...");
     g_subprocess_communicate_utf8_async(proc,NULL,NULL,managed_finished,job);
   }else if(status_label)gtk_label_set_text(GTK_LABEL(status_label),
                                           "Unable to submit torrent action.");
   g_clear_error(&error);
 }
 g_free(helper);g_free(directory);g_free(queue_helper);
}
static void on_search_result(const char *magnet,gpointer unused){
 (void)unused;
 if(destination_view)
   now_downloads_destination_view_select(destination_view,magnet);
}
static void on_download_submitted(gpointer unused){
 (void)unused;
 if(last_host && last_user)
   now_downloads_refresh(last_host,last_user);
}
static void on_refresh_clicked(GtkButton *button,gpointer unused){
 (void)button;(void)unused;
 if(last_host && last_user)
   now_downloads_refresh(last_host,last_user);
}
GtkWidget *now_downloads_page(void){
 GtkWidget *root=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 gtk_container_set_border_width(GTK_CONTAINER(root),8);
 GtkWidget *toolbar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 gtk_box_pack_start(GTK_BOX(root),toolbar,FALSE,FALSE,0);
 GtkWidget *title=gtk_label_new("DOWNLOADS");
 gtk_label_set_xalign(GTK_LABEL(title),0);
 gtk_box_pack_start(GTK_BOX(toolbar),title,TRUE,TRUE,0);
 vpn_button=gtk_button_new_with_label("VPN: UNKNOWN");
 gtk_widget_set_name(vpn_button,"vpnstatus");
 gtk_widget_set_tooltip_text(vpn_button,
     "Gluetun health on the approved download host; click for details");
 gtk_box_pack_end(GTK_BOX(toolbar),vpn_button,FALSE,FALSE,0);
 GtkWidget *popover=gtk_popover_new(vpn_button);
 GtkWidget *panel=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
 gtk_container_set_border_width(GTK_CONTAINER(panel),12);
 vpn_detail=gtk_label_new("VPN status not checked.");
 gtk_label_set_line_wrap(GTK_LABEL(vpn_detail),TRUE);
 gtk_label_set_xalign(GTK_LABEL(vpn_detail),0);
 gtk_box_pack_start(GTK_BOX(panel),vpn_detail,FALSE,FALSE,0);
 vpn_checked=gtk_label_new("No verification yet.");
 gtk_label_set_xalign(GTK_LABEL(vpn_checked),0);
 gtk_box_pack_start(GTK_BOX(panel),vpn_checked,FALSE,FALSE,0);
 vpn_account=gtk_link_button_new_with_label(
     "https://airvpn.org/client/","AIRVPN ACCOUNT (EXTERNAL)");
 gtk_widget_set_halign(vpn_account,GTK_ALIGN_START);
 gtk_widget_set_no_show_all(vpn_account,TRUE);
 gtk_widget_hide(vpn_account);
 gtk_box_pack_start(GTK_BOX(panel),vpn_account,FALSE,FALSE,0);
 gtk_container_add(GTK_CONTAINER(popover),panel);
 g_object_set_data_full(G_OBJECT(vpn_button),"now-vpn-popover",
                        g_object_ref_sink(popover),g_object_unref);
 g_signal_connect(vpn_button,"clicked",G_CALLBACK(on_vpn_clicked),NULL);
 g_timeout_add_seconds(60,vpn_poll,NULL);
 GtkWidget *refresh=gtk_button_new_with_label("REFRESH");
 gtk_box_pack_start(GTK_BOX(toolbar),refresh,FALSE,FALSE,0);
 /* Refresh uses only the already-paired host and SSH user. */
 g_signal_connect(refresh,"clicked",G_CALLBACK(on_refresh_clicked),NULL);
 advanced_button=gtk_button_new_with_label("ADVANCED · VUETORRENT");
 gtk_widget_set_sensitive(advanced_button,FALSE);
 gtk_box_pack_start(GTK_BOX(toolbar),advanced_button,FALSE,FALSE,0);
 g_signal_connect(advanced_button,"clicked",G_CALLBACK(show_web),NULL);
 back_button=gtk_button_new_with_label("BACK TO QUEUE");
 gtk_box_pack_start(GTK_BOX(toolbar),back_button,FALSE,FALSE,0);
 g_signal_connect(back_button,"clicked",G_CALLBACK(show_queue),NULL);
 gtk_widget_set_no_show_all(back_button,TRUE);
 gtk_widget_hide(back_button);

 status_label=gtk_label_new("Connect to an approved host to view downloads.");
 gtk_label_set_xalign(GTK_LABEL(status_label),0);
 gtk_label_set_ellipsize(GTK_LABEL(status_label),PANGO_ELLIPSIZE_END);
 gtk_widget_set_no_show_all(status_label,TRUE);
 gtk_box_pack_start(GTK_BOX(root),status_label,FALSE,FALSE,0);
 gtk_widget_show(status_label);

 queue_stack=gtk_stack_new();
 gtk_widget_set_vexpand(queue_stack,TRUE);
 gtk_box_pack_start(GTK_BOX(root),queue_stack,TRUE,TRUE,0);
 view_holder=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);
 gtk_stack_add_named(GTK_STACK(queue_stack),view_holder,"web");

 GtkWidget *body=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 GtkWidget *tabs=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 transfers_tab=gtk_button_new_with_label("TRANSFERS");
 search_tab=gtk_button_new_with_label("SEARCH");
 gtk_widget_set_name(transfers_tab,"downloadsubtab");
 gtk_widget_set_name(search_tab,"downloadsubtab");
 g_object_set_data(G_OBJECT(transfers_tab),"now-download-tab","transfers");
 g_object_set_data(G_OBJECT(search_tab),"now-download-tab","search");
 g_signal_connect(transfers_tab,"clicked",G_CALLBACK(switch_download_subtab),NULL);
 g_signal_connect(search_tab,"clicked",G_CALLBACK(switch_download_subtab),NULL);
 gtk_box_pack_start(GTK_BOX(tabs),transfers_tab,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(tabs),search_tab,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(body),tabs,FALSE,FALSE,0);
 downloads_subtabs=gtk_stack_new();
 gtk_widget_set_vexpand(downloads_subtabs,TRUE);
 gtk_box_pack_start(GTK_BOX(body),downloads_subtabs,TRUE,TRUE,0);
 GtkWidget *transfers=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 queue_label=gtk_label_new("Current downloads");
 gtk_label_set_xalign(GTK_LABEL(queue_label),0);
 gtk_label_set_line_wrap(GTK_LABEL(queue_label),TRUE);
 gtk_box_pack_start(GTK_BOX(transfers),queue_label,FALSE,FALSE,0);
 queue_view=now_downloads_queue_view_new();
 now_downloads_queue_view_on_action(queue_view,on_transfer_action,NULL);
 gtk_box_pack_start(GTK_BOX(transfers),queue_view,TRUE,TRUE,0);
 gtk_stack_add_named(GTK_STACK(downloads_subtabs),transfers,"transfers");
 GtkWidget *search=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 search_view=now_downloads_search_view_new();
 gtk_box_pack_start(GTK_BOX(search),search_view,FALSE,FALSE,0);
 destination_view=now_downloads_destination_view_new();
 gtk_box_pack_start(GTK_BOX(search),destination_view,FALSE,FALSE,0);
 now_downloads_search_view_on_select(search_view,on_search_result,NULL);
 now_downloads_destination_view_on_added(destination_view,on_download_submitted,NULL);
 gtk_stack_add_named(GTK_STACK(downloads_subtabs),search,"search");
 gtk_stack_set_visible_child_name(GTK_STACK(downloads_subtabs),"transfers");
 update_download_tab_buttons();
 gtk_stack_add_named(GTK_STACK(queue_stack),body,"queue");
 gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue");
 g_timeout_add_seconds(3,refresh_visible_transfers,NULL);
 return root;
}
