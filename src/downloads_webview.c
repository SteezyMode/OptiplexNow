/* Optional in-window qBittorrent WebUI renderer.
 * No WebKit compile/link dependency: Debian installs without a browser engine
 * continue to use the owner's authenticated read-only queue.
 * NEVER attempt localhost bypass, inject auth cookies, or publish proxy ports.
 */
#include "downloads_webview.h"
#include <gio/gio.h>
#include <dlfcn.h>
#include <string.h>

typedef struct {
 GtkWidget *(*new_view)(void);
 void (*load_uri)(gpointer, const gchar *);
 gpointer (*nav_request)(gpointer);
 const gchar *(*request_uri)(gpointer);
 void (*decision_ignore)(gpointer);
 gpointer (*get_context)(gpointer);
 void (*cancel_download)(gpointer);
} BrowserAPI;
static BrowserAPI api;
static gboolean loader_checked;
static gboolean browser_available;

static gboolean load_browser(void) {
 if(loader_checked)return browser_available;
 loader_checked=TRUE;
 void *lib=dlopen("libwebkit2gtk-4.1.so.0",RTLD_NOW|RTLD_LOCAL);
 if(!lib)return FALSE;
 #define LOOKUP(field,symbol) do { \
  void *found=dlsym(lib,symbol); \
  if(!found)return FALSE; \
  memcpy(&api.field,&found,sizeof(found)); \
 } while(0)
 LOOKUP(new_view,"webkit_web_view_new");
 LOOKUP(load_uri,"webkit_web_view_load_uri");
 LOOKUP(nav_request,"webkit_navigation_policy_decision_get_request");
 LOOKUP(request_uri,"webkit_uri_request_get_uri");
 LOOKUP(decision_ignore,"webkit_policy_decision_ignore");
 LOOKUP(get_context,"webkit_web_view_get_context");
 LOOKUP(cancel_download,"webkit_download_cancel");
 #undef LOOKUP
 browser_available=TRUE;
 return TRUE;
}

/* HTTP only for numeric private LAN/Tailscale addresses (WireGuard provides
 * transport encryption on the Tailnet). DNS and public endpoints require TLS.
 * This is intentionally narrower than the generic configurable browser URL. */
static gboolean private_ip(const char *name) {
 if(!name)return FALSE;
 GInetAddress *ip=g_inet_address_new_from_string(name);
 if(!ip)return FALSE;
 gboolean ok=FALSE;
 if(g_inet_address_get_family(ip)==G_SOCKET_FAMILY_IPV4){
  const guint8 *b=g_inet_address_to_bytes(ip);
  ok=(b[0]==10) || (b[0]==172 && b[1]>=16 && b[1]<=31) ||
      (b[0]==192 && b[1]==168) ||
      (b[0]==100 && b[1]>=64 && b[1]<=127) ||
      (b[0]==127);
 }else{
  ok=g_inet_address_get_is_loopback(ip) ||
     g_inet_address_get_is_site_local(ip);
 }
 g_object_unref(ip);
 return ok;
}

gboolean now_downloads_webview_url_allowed(const char *url,
                                            const char *approved_host) {
 if(!url || !approved_host || !*url || !*approved_host ||
    strlen(url)>1024 || strlen(approved_host)>253)return FALSE;
 GError *error=NULL;
 GUri *uri=g_uri_parse(url,G_URI_FLAGS_NONE,&error);
 if(error){g_error_free(error);return FALSE;}
 if(!uri)return FALSE;
 const char *scheme=g_uri_get_scheme(uri);
 const char *host=g_uri_get_host(uri);
 gboolean valid=host && !g_ascii_strcasecmp(host,approved_host) &&
   !g_uri_get_userinfo(uri) &&
   scheme && (!g_ascii_strcasecmp(scheme,"https") ||
              (!g_ascii_strcasecmp(scheme,"http") && private_ip(host))) &&
   !g_uri_get_query(uri);
 if(valid){
   int port=g_uri_get_port(uri);
   if(port==0 || port>65535)valid=FALSE;
 }
 g_uri_unref(uri);
 return valid;
}
typedef struct {
 GUri *origin;
} ViewPolicy;
static gboolean allowed_same_origin(ViewPolicy *policy,const char *url){
 if(!url)return FALSE;
 GUri *uri=g_uri_parse(url,G_URI_FLAGS_NONE,NULL);
 if(!uri)return FALSE;
 const char *a=g_uri_get_host(uri),*b=g_uri_get_host(policy->origin);
 const char *as=g_uri_get_scheme(uri),*bs=g_uri_get_scheme(policy->origin);
 int ap=g_uri_get_port(uri),bp=g_uri_get_port(policy->origin);
 if(ap<0)ap=!g_ascii_strcasecmp(as?as:"","https")?443:80;
 if(bp<0)bp=!g_ascii_strcasecmp(bs?bs:"","https")?443:80;
 gboolean ok=a&&b&&as&&bs&&!g_ascii_strcasecmp(a,b)&&
   !g_ascii_strcasecmp(as,bs)&&ap==bp&&!g_uri_get_userinfo(uri);
 g_uri_unref(uri);
 return ok;
}
/* WebKitPolicyDecisionType: NAVIGATION_ACTION 0, NEW_WINDOW_ACTION 1,
 * RESPONSE 2. Deny popups and cross-origin main frame navigation. */
static gboolean decide_policy(gpointer view,gpointer decision,gint type,
                               gpointer user_data){
 (void)view;
 ViewPolicy *policy=user_data;
 if(type==1){
  api.decision_ignore(decision);
  return TRUE;
 }
 if(type!=0)return FALSE;
 gpointer request=api.nav_request(decision);
 const char *url=request?api.request_uri(request):NULL;
 if(!allowed_same_origin(policy,url)){
  api.decision_ignore(decision);
  return TRUE;
 }
 return FALSE;
}
static void download_started(gpointer context,gpointer download,gpointer data){
 (void)context;(void)data;
 /* Downloading actual files via the WebView is outside this owner-only
  * manager pilot. Prevent unexpected file writes or navigation escapes. */
 api.cancel_download(download);
}
static void free_policy(gpointer data,GClosure *closure){
 (void)closure;
 ViewPolicy *p=data;
 if(p->origin)g_uri_unref(p->origin);
 g_free(p);
}
GtkWidget *now_downloads_webview_new(const char *url,const char *approved_host){
 if(!now_downloads_webview_url_allowed(url,approved_host) ||
    !load_browser())return NULL;
 GtkWidget *view=api.new_view();
 if(!view)return NULL;
 ViewPolicy *policy=g_new0(ViewPolicy,1);
 policy->origin=g_uri_parse(url,G_URI_FLAGS_NONE,NULL);
 g_signal_connect_data(view,"decide-policy",G_CALLBACK(decide_policy),
                       policy,free_policy,0);
 gpointer context=api.get_context(view);
 if(context){
   g_signal_handlers_disconnect_by_func(context,G_CALLBACK(download_started),NULL);
   g_signal_connect(context,"download-started",
                    G_CALLBACK(download_started),NULL);
 }
 api.load_uri(view,url);
 return view;
}
