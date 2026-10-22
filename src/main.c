#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <signal.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/file.h>
#include <sys/types.h>
#include <time.h>
#include <sys/random.h>
#include <pthread.h>
#include <limits.h>
#include <dirent.h>
#include <dlfcn.h>
#include <netdb.h>
#include <sys/socket.h>
#include <poll.h>
#include "process.h"
#include "presets.h"
#include "config.h"
#include "wolf_pairing.h"
#include "wolf_transport.h"
#include "games_flow.h"
#include "tailscale_async.h"
#include "wizard_network.h"
#include "service_probe.h"
#include "wizard_services.h"
#include "tailscale_install.h"
#include "ssh_authorize.h"
#include "host_metrics.h"
#include "host_job_target.h"
#include "backup_async.h"
#include "tray_prefs.h"
#include "tray_actions.h"
#include "moonlight_install.h"
#include <gtk/gtk.h>
#include <gio/gio.h>
#include <fontconfig/fontconfig.h>

/* Use StatusNotifierItem via Ayatana AppIndicator when the desktop exposes
 * a watcher. Fall back to the XEmbed-compatible GTK3 status icon otherwise.
 * The pinned XFCE panel launcher is separate from the notification area. */

extern const unsigned char _binary_inter_ttf_start[], _binary_inter_ttf_end[];
extern const unsigned char _binary_limelight_ttf_start[], _binary_limelight_ttf_end[];

#define BASE ""

static void *tray_icon = NULL;
static void *indicator_library = NULL, *app_indicator = NULL;
static void (*app_indicator_set_status_fn)(void*,int) = NULL;
static void (*app_indicator_set_menu_fn)(void*,void*) = NULL;
static int using_status_notifier = 0;
static int tray_available = 0;

/* Gio is used only to detect whether a desktop is hosting a
 * StatusNotifierWatcher, avoiding a hidden process with no usable tray. */
static int status_notifier_watcher_present(void){
 GError *error=NULL;
 GDBusConnection *bus=g_bus_get_sync(G_BUS_TYPE_SESSION,NULL,&error);
 if(error){g_error_free(error);error=NULL;}
 if(!bus)return 0;
 GVariant *res=g_dbus_connection_call_sync(bus,"org.freedesktop.DBus","/org/freedesktop/DBus",
   "org.freedesktop.DBus","NameHasOwner",g_variant_new("(s)","org.kde.StatusNotifierWatcher"),
   NULL,0,1500,NULL,&error);
 int found=0;
 if(res){g_variant_get(res,"(b)",&found);g_variant_unref(res);}
 if(error)g_error_free(error);
 g_object_unref(bus);
 return found;
}

static GtkWidget *tray_menu = NULL;
static volatile sig_atomic_t reopen_requested = 0;
static int instance_fd = -1;
static int tray_restoring = 0;
static GtkWidget *win,*indicator,*status_detail,*footer,*grid,*power_grid,*tailscale_label,*games_notice,*games_state,*games_install;
static GtkWidget *model_heading=NULL;
static GtkWidget *metric_cpu,*metric_gpu,*metric_ram,*metric_vram,*metric_network,*metric_vpn,*metric_wolf,*metric_wolf_sessions,*metric_free,*drive_combo;
static GtkWidget *spec_values[8]={0},*spec_status=NULL;
static int specs_inflight=0, wolf_inflight=0;
static GtkWidget *wizard_wolf_label=NULL;
static GtkWidget *active_setup_wizard=NULL;
static char wolf_probe_host[512];
#define MAX_DRIVES NOW_HOST_MAX_DRIVES
/* Mount points reported by the server, not client-side disks. */
typedef NowHostDrive Drive;
static Drive visible_drives[MAX_DRIVES];
static int visible_drive_count=0,drive_combo_updating=0;
static void on_drive_changed(void*,void*);
static char appimage_found[PATH_MAX];
static void tray_build_menu(void);
/* Defer menu replacement until the Settings activation has unwound. */
static gboolean tray_rebuild_after_settings(gpointer unused){(void)unused;tray_build_menu();return G_SOURCE_REMOVE;}
static void say(const char *s);
static int flatpak_has(const char *id);
static void on_games_setup(void*w,void*p);
static void on_wizard(void*w,void*p);
static GtkWidget *tiles[9],*powers[4],*extras_grid;
static int last_columns=0, last_power_columns=0, status_inflight=0, power_inflight=0;
#define ALL_SERVICES_MASK 255u
#define NEW_INSTALL_FEATURED_MASK 207u
#define TRAY_MASK_SETTING 13
static const char *current_model(void){
 return *cfg[12] && !strcmp(cfg[11],cfg[0]) ? cfg[12] : "Server";
}
static void update_model_heading(void){
 if(model_heading)gtk_label_set_text(GTK_LABEL(model_heading),current_model());
}

static const char *CSS =
"* {font-family:'Inter',sans-serif;}"
"window,dialog,assistant,scrolledwindow {background:#101111; color:#ece8e0;}"
"#shell {background:#101111;}"
"#setting {background:#1d201f; border:1px solid #414743;color:#ece8e0;padding:5px 11px;font-size:10px;font-weight:700;min-height:24px;border-radius:2px;}"
"#setting:hover {background:#c47d65;color:#101111;border-color:#c47d65;}"
"#title {font-family:'Inter',sans-serif;font-size:32px;font-weight:900;letter-spacing:-1.4px;color:#ece8e0;}"
"#state {color:#bcb8af;background:#202523;border:1px solid #515b56;padding:7px 10px;font-size:10px;font-weight:800;letter-spacing:.7px;}"
"#state.online {color:#e8c28f;border-color:#c47d65;} #state.offline {color:#e7aca7;border-color:#986967;} #state.pair {color:#e8ce90;border-color:#9b8354;}"
"#detail {font-size:10px;color:#aaa79e;}"
"#rule {background:#75534b;min-height:1px;}"
"#section {font-weight:800;color:#b8b4ac;font-size:11px;letter-spacing:1px;}"
"#metric {background:#171918;border:1px solid #444b46;color:#ece8e0;padding:8px 9px;font-size:12px;font-weight:700;}"
"#drivemetric {background:#171918;border:1px solid #444b46;padding:8px 10px;}"
"#storagehead {font-size:10px;font-weight:800;color:#b8b4ac;}"
"#drivefree {font-size:11px;font-weight:700;color:#ece8e0;}"
"#drivefree.warn {color:#e7aa82;}"
"#drivecombo button {background:#1e211f;color:#ece8e0;border:1px solid #4d5650;border-radius:2px;padding:3px 7px;min-height:25px;font-size:11px;}"
"#drivecombo button:hover {border-color:#c47d65;}"
"#trayorder, #trayorder row {background:#1d211e;color:#ece8e0;}"
"#trayorder row {border-bottom:1px solid #444b46;padding:3px;}"
"#trayorder checkbutton, #trayorder checkbutton check {color:#ece8e0;}"
"#tile {background:#1e211f;color:#ece8e0;border:1px solid #554840;border-radius:2px;padding:6px 8px;font-weight:800;font-size:12px;min-height:43px;border-bottom:2px solid #c47d65;}"
"#tile:hover {background:#b96b5e;color:#101111;} #tile:active {background:#e6aa77;}"
"#power {background:#171918;color:#ece8e0;border:1px solid #59615c;border-radius:2px;padding:6px 6px;font-weight:800;font-size:10px;min-height:30px;}"
"#power:hover {background:#c47d65;color:#101111;}"
"#danger {background:#171918;color:#ddaba5;border:1px solid #9c6b69;border-radius:2px;padding:6px 6px;font-weight:800;font-size:10px;min-height:30px;}"
"#danger:hover {background:#9d3543;color:#fafaf8;}"
"#footer {font-size:11px;color:#b8b4ac;}"
"dialog {background:#151716;} dialog label {color:#ece8e0;font-size:12px;}"
"entry {background:#252a27;color:#ece8e0;border:1px solid #69716a;border-radius:2px;padding:8px;font-size:12px;min-height:25px;}"
"combobox button {background:#222623;color:#ece8e0;border:1px solid #777f77;border-radius:2px;}"
"menu,menuitem {background:#222623;color:#ece8e0;} menuitem:hover {background:#2a9d8f;color:#101111;}"
"#modalheading {font-size:17px;font-weight:800;color:#ece8e0;}"
"#helper {font-size:11px;color:#b8b4ac;}"
"#gameshint {font-size:12px;color:#ece8e0;}"
"#statusmetric {font-size:13px;font-weight:700;color:#c5c7c1;padding:2px 5px;}"
"#statusmetric.good {color:#84d9a7;}"
"#statusmetric.bad {color:#eca29d;}"
"#setupaction, .setupaction {background:#2c322d;color:#ece8e0;border:1px solid #5b665d;border-radius:2px;padding:8px 12px;font-size:11px;font-weight:700;}"
"#setupaction:hover, .setupaction:hover {background:#2a9d8f;color:#101111;}"
"#setupaction label, .setupaction label {color:#ece8e0;font-weight:800;}"
"#setupaction:hover label, .setupaction:hover label {color:#101111;}"
"#note {color:#b8b4ac;font-size:11px;}"
"assistant .sidebar, assistant .sidebar label {background:#1e211f;color:#ece8e0;}"
"assistant button {background:#252a27;color:#ece8e0;}"
"assistant button:hover {background:#2a9d8f;color:#101111;}"
"dialog .dialog-action-area button {background:#252a27;color:#ece8e0;border:1px solid #59615c;padding:8px 14px;}"
"dialog .dialog-action-area button:hover {background:#2a9d8f;color:#101111;}"
"#specname {font-size:11px;color:#b8b4ac;}"
"#specvalue {font-size:12px;color:#ece8e0;font-weight:700;}";
static void safe_copy(char *dest, size_t cap, const char *src) { snprintf(dest,cap,"%s",src?src:""); }
static void mkdir_safe(const char *p) { mkdir(p,0700); }
/* Tray and featured selection are independent bitmasks. */
static unsigned tray_button_mask(void)
{
    return now_tray_parse_mask(cfg[TRAY_MASK_SETTING]);
}
static unsigned featured_mask(void){
 char *end=NULL;errno=0;
 unsigned long value=strtoul(cfg[FEATURED_MASK_SETTING],&end,10);
 if(errno||end==cfg[FEATURED_MASK_SETTING]||*end||value>ALL_SERVICES_MASK)
   return EXISTING_INSTALL_FEATURED_MASK;
 return (unsigned)value;
}
static int config_save(void)
{
    update_model_heading();
    if (!now_config_save()) {
        fprintf(stderr, "Unable to save OptiPlex NOW configuration\n");
        return 0;
    }
    return 1;
}
static void preset_alert(void*parent,const char*title,const char*msg){
 GtkWidget*d=gtk_dialog_new_with_buttons(title,GTK_WINDOW(parent),1,"OK",GTK_RESPONSE_OK,NULL);
 GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));GtkWidget*b=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
 gtk_container_set_border_width(GTK_CONTAINER(b),16);gtk_container_add(GTK_CONTAINER(area),b);
 GtkWidget*l=gtk_label_new(msg);gtk_label_set_line_wrap(GTK_LABEL(l),1);gtk_container_add(GTK_CONTAINER(b),l);
 gtk_widget_show_all(d);gtk_dialog_run(GTK_DIALOG(d));gtk_widget_destroy(d);
}
static int preset_pick(char*out,size_t n,void*parent,int save){
 GtkWidget*d=gtk_file_chooser_dialog_new(save?"Export My OptiPlex":"Import My OptiPlex",GTK_WINDOW(parent),save?1:0,
      "CANCEL",GTK_RESPONSE_CANCEL,save?"SAVE":"OPEN",GTK_RESPONSE_OK,NULL);
 const char*home=getenv("HOME"); if(home&&*home)gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(d),home);
 if(save){
   gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(d),"My-OptiPlex.onp");
   gtk_file_chooser_set_do_overwrite_confirmation(GTK_FILE_CHOOSER(d),1);
 }
 int ok=0; if(gtk_dialog_run(GTK_DIALOG(d))==GTK_RESPONSE_OK){
  char*path=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(d));
  if(path){safe_copy(out,n,path);ok=1;g_free(path);}
 }
 gtk_widget_destroy(d);return ok;
}
/* Prefer a user's existing Moonlight AppImage. No installation is needed. */
static const char *find_appimage(void) {
 if(*cfg[9] && access(cfg[9],X_OK)==0) return cfg[9];
 if(*appimage_found && access(appimage_found,X_OK)==0) return appimage_found;
 const char *home=getenv("HOME");if(!home)return NULL;
 const char *dirs[]={"Applications","AppImages","Downloads","Desktop",".local/bin","bin","",NULL};
 for(int i=0;dirs[i];i++){
  char dir[PATH_MAX];snprintf(dir,sizeof dir,"%s/%s",home,dirs[i]);
  DIR *d=opendir(dir);if(!d)continue;
  struct dirent *e;
  while((e=readdir(d))){
   const char *n=e->d_name;size_t len=strlen(n);
   if(!strcasestr(n,"moonlight") || len<9 || strcasecmp(n+len-9,".AppImage"))continue;
   char path[PATH_MAX];if(snprintf(path,sizeof path,"%s/%s",dir,n)>=(int)sizeof path)continue;
   struct stat st;
   if(stat(path,&st)==0 && S_ISREG(st.st_mode) && access(path,X_OK)==0){
    safe_copy(appimage_found,sizeof appimage_found,path);closedir(d);return appimage_found;
   }
  }
  closedir(d);
 }
 return NULL;
}
static int moonlight_mode(void) {
 if(find_appimage())return 1;
 if(now_program_exists("moonlight"))return 2;
 if(flatpak_has("com.moonlight_stream.Moonlight"))return 3;
 return 0;
}
static const char* moonlight_mode_name(void) {
 const char *names[]={"MOONLIGHT NOT FOUND","MOONLIGHT APPIMAGE READY","MOONLIGHT INSTALLED","MOONLIGHT FLATPAK READY"};
 return names[moonlight_mode()];
}
static void choose_appimage(void) {
 GtkWidget*d=gtk_file_chooser_dialog_new("Choose Moonlight AppImage",GTK_WINDOW(win),0,"CANCEL",GTK_RESPONSE_CANCEL,"USE THIS FILE",GTK_RESPONSE_OK,NULL);
 if(gtk_dialog_run(GTK_DIALOG(d))==GTK_RESPONSE_OK){
  char *path=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(d));
  if(path){
   if(access(path,X_OK)==0){safe_copy(cfg[9],512,path);appimage_found[0]=0;config_save();say("MOONLIGHT APPIMAGE SELECTED");}
   else say("APPIMAGE NOT EXECUTABLE. ENABLE EXECUTE PERMISSION FIRST");
   g_free(path);
  }
 }
 gtk_widget_destroy(d);
}
static int flatpak_has(const char *id) {
 if(!now_program_exists("flatpak"))return 0;
 char out[128];char*args[]={"flatpak","info","--show-ref",(char*)id,NULL};return now_run(args,out,sizeof(out),3)==0;
}
/* Always use the user's default browser, unless they explicitly selected Chrome.
 * A native GTK URI open works across XFCE, KDE and COSMIC when a browser
 * is registered. Try conventional browser commands if no default exists. */
static void browser_open(const char *url) {
 if(strncmp(url,"http://",7)&&strncmp(url,"https://",8))return;
 if(!strcmp(cfg[8],"chrome-flatpak") && flatpak_has("com.google.Chrome")){
   char*args[]={"flatpak","run","com.google.Chrome",(char*)url,NULL};now_launch(args);return;
 }
 if(!strcmp(cfg[8],"chrome") && (now_program_exists("google-chrome-stable")||now_program_exists("google-chrome"))){
   const char *cmd=now_program_exists("google-chrome-stable")?"google-chrome-stable":"google-chrome";
   char*args[]={(char*)cmd,(char*)url,NULL};now_launch(args);return;
 }
 GError *err=NULL;
 if(gtk_show_uri_on_window(GTK_WINDOW(win),url,0,&err))return;
 if(err){g_error_free(err);err=NULL;}
 const char *browsers[]={"brave-browser-nightly","brave-browser","firefox","google-chrome-stable","google-chrome","chromium","chromium-browser"};
 for(unsigned i=0;i<sizeof browsers/sizeof browsers[0];i++){
   if(now_program_exists(browsers[i])){char*args[]={(char*)browsers[i],(char*)url,NULL};now_launch(args);return;}
 }
 const char *flatpak_browsers[]={"com.brave.Browser","org.mozilla.firefox","com.google.Chrome","org.chromium.Chromium"};
 for(unsigned i=0;i<sizeof flatpak_browsers/sizeof flatpak_browsers[0];i++){
   if(flatpak_has(flatpak_browsers[i])){
     char*args[]={"flatpak","run",(char*)flatpak_browsers[i],(char*)url,NULL};now_launch(args);return;
   }
 }
 say("NO WEB BROWSER FOUND. SET A DEFAULT BROWSER IN YOUR DESKTOP SETTINGS");
}

static void set_footer(const char *text) {gtk_label_set_text(GTK_LABEL(footer),text);}
static GtkWidget* label(const char *text,const char *id) {
 GtkWidget*l=gtk_label_new(text);gtk_label_set_xalign(GTK_LABEL(l),0);if(id)gtk_widget_set_name(l,id);return l;
}
static GtkWidget* button(const char *text,const char *id) {
 GtkWidget*b=gtk_button_new_with_label(text);if(id)gtk_widget_set_name(b,id);return b;
}
static void add(GtkWidget*box,GtkWidget*child,int expand) {gtk_box_pack_start(GTK_BOX(box),child,expand,expand,0);}
static void say(const char *s) {if(footer)set_footer(s);}

static int terminal_launch(char *const args[]) {
 if(now_program_exists("xfce4-terminal")){char *argv[24];int i=0;argv[i++]="xfce4-terminal";argv[i++]="--disable-server";argv[i++]="-x";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;now_launch(argv);return 1;}
 if(now_program_exists("mate-terminal")){char *argv[24];int i=0;argv[i++]="mate-terminal";argv[i++]="--";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;now_launch(argv);return 1;}
 if(now_program_exists("gnome-terminal")){char *argv[24];int i=0;argv[i++]="gnome-terminal";argv[i++]="--";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;now_launch(argv);return 1;}
 if(now_program_exists("xterm")){char *argv[24];int i=0;argv[i++]="xterm";argv[i++]="-e";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;now_launch(argv);return 1;}
 say("No terminal found");return 0;
}
static void launch_ssh(int relay) {
 int h=relay?2:0,u=relay?3:1;
 if(!now_valid_host(cfg[h])||!now_valid_user(cfg[u])){say("Check Settings");return;}
 char *args[]={"ssh","-l",cfg[u],cfg[h],NULL};terminal_launch(args);
}
typedef struct {
    GtkWidget *dialog;
    GtkWidget *message;
    GtkWidget *cancel_button;
    GCancellable *cancel;
    gboolean pending;
} SSHAuthorization;

static SSHAuthorization *ssh_authorization = NULL;

static void ssh_authorization_release(SSHAuthorization *state)
{
    if (ssh_authorization == state) {
        ssh_authorization = NULL;
    }
    g_clear_object(&state->cancel);
    g_free(state);
}

static void ssh_authorization_closed(GtkWidget *widget, gpointer data)
{
    (void)widget;
    SSHAuthorization *state = data;
    state->dialog = NULL;
    if (state->cancel) {
        g_cancellable_cancel(state->cancel);
    }
    if (!state->pending) {
        ssh_authorization_release(state);
    }
}

static void ssh_authorization_response(GtkDialog *dialog, gint response, gpointer data)
{
    (void)response;
    (void)data;
    gtk_widget_destroy(GTK_WIDGET(dialog));
}

static void ssh_authorization_done(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    SSHAuthorization *state = data;
    GError *error = NULL;
    gboolean success = now_ssh_authorize_finish(result, &error);
    state->pending = FALSE;

    if (state->dialog) {
        gtk_label_set_text(GTK_LABEL(state->message), success
            ? "SSH ACCESS AUTHORIZED. YOU CAN CONTINUE SETUP."
            : g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)
                ? "SSH AUTHORIZATION CANCELLED."
                : "COULD NOT AUTHORIZE SSH ACCESS. CHECK YOUR SERVER PASSWORD "
                  "OR CONTACT THE SERVER OWNER.");
        gtk_button_set_label(GTK_BUTTON(state->cancel_button), "Close");
    } else {
        ssh_authorization_release(state);
    }
    if (success) {
        say("SERVER ACCESS AUTHORIZED.");
    } else {
        say("SERVER ACCESS NOT AUTHORIZED. RETRY FROM SETUP.");
    }
    g_clear_error(&error);
}

static void pair(int relay)
{
    int host_index = relay ? 2 : 0;
    int user_index = relay ? 3 : 1;
    if (!now_valid_host(cfg[host_index]) || !now_valid_user(cfg[user_index])) {
        say("ENTER THE SERVER ADDRESS AND SSH USER IN SETTINGS.");
        return;
    }
    if (ssh_authorization) {
        say("SSH AUTHORIZATION IS ALREADY IN PROGRESS.");
        return;
    }
    SSHAuthorization *state = g_new0(SSHAuthorization, 1);
    state->cancel = g_cancellable_new();
    state->pending = TRUE;
    ssh_authorization = state;

    GtkWindow *parent = GTK_WINDOW(active_setup_wizard ?
                                   active_setup_wizard : win);
    state->dialog = gtk_dialog_new_with_buttons(
        relay ? "Authorize Wake Relay" : "Authorize Server",
        parent, GTK_DIALOG_MODAL, "Cancel", GTK_RESPONSE_CANCEL, NULL);
    state->cancel_button =
        gtk_dialog_get_widget_for_response(GTK_DIALOG(state->dialog),
                                           GTK_RESPONSE_CANCEL);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(state->dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 20);
    GtkWidget *instructions = gtk_label_new(
        "NOW will install this device's SSH public key into your selected "
        "server account. Approve the host fingerprint if it is correct, "
        "then enter the server account password in the graphical prompt. "
        "The private key stays on this computer.");
    gtk_label_set_line_wrap(GTK_LABEL(instructions), TRUE);
    gtk_box_pack_start(GTK_BOX(area), instructions, FALSE, FALSE, 8);

    state->message = gtk_label_new("CONTACTING SERVER. WAIT FOR THE PASSWORD PROMPT...");
    gtk_label_set_line_wrap(GTK_LABEL(state->message), TRUE);
    gtk_box_pack_start(GTK_BOX(area), state->message, FALSE, FALSE, 8);

    g_signal_connect(state->dialog, "response",
                     G_CALLBACK(ssh_authorization_response), state);
    g_signal_connect(state->dialog, "destroy",
                     G_CALLBACK(ssh_authorization_closed), state);
    gtk_widget_show_all(state->dialog);

    now_ssh_authorize_async(cfg[host_index], cfg[user_index], state->cancel,
                             ssh_authorization_done, state);
}

static gboolean tailscale_install_inflight = FALSE;

static void tailscale_install_done(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    (void)data;
    GError *error = NULL;
    gboolean installed = now_tailscale_install_finish(result, &error);
    tailscale_install_inflight = FALSE;
    if (installed) {
        say("TAILSCALE INSTALLED. SIGN IN THROUGH THE BROWSER.");
        browser_open("http://100.100.100.100/");
    } else {
        say("TAILSCALE INSTALLATION WAS NOT COMPLETED.");
        GtkWidget *notice = gtk_message_dialog_new(
            GTK_WINDOW(active_setup_wizard ? active_setup_wizard : win),
            GTK_DIALOG_MODAL, GTK_MESSAGE_WARNING, GTK_BUTTONS_NONE,
            "Tailscale was not installed");
        gtk_message_dialog_format_secondary_text(
            GTK_MESSAGE_DIALOG(notice),
            "The installation was cancelled or could not finish. "
            "Check that an administrator account and internet access are available. "
            "You can retry from NOW or open Tailscale's official setup guide.");
        gtk_dialog_add_buttons(GTK_DIALOG(notice), "Close", GTK_RESPONSE_CLOSE,
                               "Open setup guide", GTK_RESPONSE_HELP, NULL);
        int action = gtk_dialog_run(GTK_DIALOG(notice));
        gtk_widget_destroy(notice);
        if (action == GTK_RESPONSE_HELP) {
            browser_open("https://tailscale.com/docs/install/linux");
        }
        if (error) {
            g_warning("Tailscale graphical installer failed: %s", error->message);
        }
    }
    g_clear_error(&error);
}

static void setup_tailscale(void)
{
    if (now_program_exists("tailscale")) {
        say("TAILSCALE SETUP OPENS IN YOUR BROWSER.");
        browser_open("http://100.100.100.100/");
        return;
    }
    if (tailscale_install_inflight) {
        say("TAILSCALE INSTALLATION IS ALREADY RUNNING.");
        return;
    }
    if (!now_program_exists("pkexec")) {
        say("GRAPHICAL ADMIN AUTHORIZATION IS MISSING; OPENING TAILSCALE HELP.");
        browser_open("https://tailscale.com/docs/install/linux");
        return;
    }

    GtkWidget *dialog = gtk_message_dialog_new(
        GTK_WINDOW(active_setup_wizard ? active_setup_wizard : win), GTK_DIALOG_MODAL, GTK_MESSAGE_QUESTION, GTK_BUTTONS_NONE,
        "Install Tailscale on this computer?");
    gtk_message_dialog_format_secondary_text(
        GTK_MESSAGE_DIALOG(dialog),
        "NOW will request your administrator password through the desktop "
        "authorization dialog, add Tailscale's official signed package repository "
        "on supported Debian/Ubuntu systems, and install its service. "
        "Existing Tailscale installations are not changed.");
    gtk_dialog_add_buttons(GTK_DIALOG(dialog), "Cancel", GTK_RESPONSE_CANCEL,
                           "Install Tailscale", GTK_RESPONSE_OK, NULL);
    int answer = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
    if (answer != GTK_RESPONSE_OK) {
        return;
    }
    tailscale_install_inflight = TRUE;
    say("INSTALLING TAILSCALE — CONFIRM THE SYSTEM PASSWORD PROMPT.");
    now_tailscale_install_async(tailscale_install_done, NULL);
}

typedef struct { int type; int success; int tail; char message[300]; char cpu[40],gpu[40],cpu_load[40],gpu_load[40],ram_used[40],vram_used[40],vpn_state[80],wolf_state[80],wolf_sessions[80],free_space[40]; int drive_count; Drive drives[MAX_DRIVES]; char model[160]; NowHostJobTarget target; char specs[7][160]; } Result;
static void set_drive_readout(void){
  if(!metric_free)return;
  int n=gtk_combo_box_get_active(GTK_COMBO_BOX(drive_combo));
  if(n<0||n>=visible_drive_count){gtk_label_set_text(GTK_LABEL(metric_free),"FREE  --");return;}
  Drive*d=&visible_drives[n];char buf[160];
  if(*d->free_space)snprintf(buf,sizeof buf,"FREE  %s   /   %s",d->free_space,d->size);
  else snprintf(buf,sizeof buf,"NOT MOUNTED");
  gtk_label_set_text(GTK_LABEL(metric_free),buf);
  GtkStyleContext *sty=gtk_widget_get_style_context(metric_free);
  gtk_style_context_remove_class(GTK_STYLE_CONTEXT(sty),"warn");
  if(atoi(d->used_percent)>=90)gtk_style_context_add_class(GTK_STYLE_CONTEXT(sty),"warn");
}
static void on_drive_changed(void*w,void*arg){
  (void)w;(void)arg;
  if(drive_combo_updating)return;
  int n=gtk_combo_box_get_active(GTK_COMBO_BOX(drive_combo));
  if(n<0||n>=visible_drive_count)return;
  safe_copy(cfg[10],512,visible_drives[n].path);
  config_save();set_drive_readout();
}
static void update_drives(Result*r){
  if(!drive_combo)return;
  if(r->success!=1){gtk_label_set_text(GTK_LABEL(metric_free),"FREE  --");return;}
  /* Do not reset the selection if only disk space values change. */
  int changed=(visible_drive_count!=r->drive_count);
  if(!changed)for(int i=0;i<visible_drive_count;i++){
    if(strcmp(visible_drives[i].path,r->drives[i].path)||strcmp(visible_drives[i].size,r->drives[i].size)){changed=1;break;}
  }
  int selected=0;size_t best=0;
  for(int i=0;i<r->drive_count;i++){
    const char*m=r->drives[i].path;size_t n=strlen(m);
    if(n>best && !strncmp(cfg[10],m,n) && (n==1||cfg[10][n]=='/'||cfg[10][n]==0)){
      selected=i;best=n;
    }
  }
  visible_drive_count=r->drive_count;
  memcpy(visible_drives,r->drives,sizeof visible_drives);
  if(changed){
    drive_combo_updating=1;
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(drive_combo));
    for(int i=0;i<visible_drive_count;i++){
      Drive*d=&visible_drives[i];char choice[256];
      const char*name=!strcmp(d->path,"/")?"SYSTEM":strrchr(d->path,'/');
      name=!strcmp(d->path,"/")?name:(name?name+1:d->path);
      snprintf(choice,sizeof choice,"%s   %s",name,d->size);
      gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(drive_combo),choice);
    }
    gtk_combo_box_set_active(GTK_COMBO_BOX(drive_combo),visible_drive_count?selected:-1);
    drive_combo_updating=0;
  }
  set_drive_readout();
}

static gboolean finish_on_main(void *arg) {
 Result*r=arg;
 /* Ignore results from a host that is no longer selected. The worker used
  * the original immutable target, not values subsequently saved in Settings. */
 if(r->type!=8){
   int relay=r->type==1;
   if(!now_host_job_target_matches(&r->target,
                                   relay?cfg[2]:cfg[0],
                                   relay?cfg[3]:cfg[1],
                                   relay?cfg[4]:"")){
     if(r->type==0)status_inflight=0;
     else if(r->type==6)specs_inflight=0;
     else power_inflight=0;
     free(r);return G_SOURCE_REMOVE;
   }
 }else if(strcmp(r->message,*wolf_probe_host?wolf_probe_host:cfg[0])){
   wolf_inflight=0;free(r);return G_SOURCE_REMOVE;
 }
 if(r->type==0){
   if(strcmp(r->target.host,cfg[0])||strcmp(r->target.user,cfg[1])){
     status_inflight=0;free(r);return 0;
   }
   if(r->success==1 && *r->model &&
      (strcmp(cfg[11],r->target.host)||strcmp(cfg[12],r->model))){
     safe_copy(cfg[11],512,r->target.host);safe_copy(cfg[12],512,r->model);config_save();
   }
   update_model_heading();
   const char *s=r->success==1?"● ONLINE":r->success==2?"● PAIR SSH":r->success==3?"● TAILSCALE OFF":"● OFFLINE";
   gtk_label_set_text(GTK_LABEL(indicator),s);
   if(tray_icon){char tip[100];snprintf(tip,sizeof tip,"OptiPlex Now | %s",s+2);gtk_status_icon_set_tooltip_text(GTK_STATUS_ICON(tray_icon),tip);}
   GtkStyleContext*sty=gtk_widget_get_style_context(indicator);
   /* Old classes harmless; remove is available but style is reset below. */
   gtk_style_context_remove_class(GTK_STYLE_CONTEXT(sty),"online");gtk_style_context_remove_class(GTK_STYLE_CONTEXT(sty),"offline");gtk_style_context_remove_class(GTK_STYLE_CONTEXT(sty),"pair");
   gtk_style_context_add_class(GTK_STYLE_CONTEXT(sty),r->success==1?"online":r->success==2?"pair":"offline");
   gtk_label_set_text(GTK_LABEL(status_detail),r->success==1?"":r->message);
   if(metric_cpu){char val[110];snprintf(val,sizeof val,"CPU   %s  %s",*r->cpu_load?r->cpu_load:"--",*r->cpu?r->cpu:"");gtk_label_set_text(GTK_LABEL(metric_cpu),val);}
   if(metric_gpu){char val[110];snprintf(val,sizeof val,"GPU   %s  %s",*r->gpu_load?r->gpu_load:"--",*r->gpu?r->gpu:"");gtk_label_set_text(GTK_LABEL(metric_gpu),val);}
   if(metric_ram){char val[110];snprintf(val,sizeof val,"RAM   %s",*r->ram_used?r->ram_used:"--");gtk_label_set_text(GTK_LABEL(metric_ram),val);}
   if(metric_vram){char val[110];snprintf(val,sizeof val,"VRAM   %s",*r->vram_used?r->vram_used:"--");gtk_label_set_text(GTK_LABEL(metric_vram),val);}
   if(metric_network){gtk_label_set_text(GTK_LABEL(metric_network),r->tail?"TAILSCALE  connected":"TAILSCALE  disconnected");
    GtkStyleContext*cs=gtk_widget_get_style_context(metric_network);gtk_style_context_remove_class(cs,"good");gtk_style_context_remove_class(cs,"bad");
    gtk_style_context_add_class(cs,r->tail?"good":"bad");}
   if(metric_vpn){gtk_label_set_text(GTK_LABEL(metric_vpn),r->success==1?(*r->vpn_state?r->vpn_state:"VPN  UNKNOWN"):"VPN  --");
    GtkStyleContext*cs=gtk_widget_get_style_context(metric_vpn);gtk_style_context_remove_class(cs,"good");gtk_style_context_remove_class(cs,"bad");
    if(r->success==1 && strstr(r->vpn_state,"VPN  HEALTHY"))gtk_style_context_add_class(cs,"good");
    else if(r->success==1 && strstr(r->vpn_state,"VPN  UNHEALTHY"))gtk_style_context_add_class(cs,"bad");}
   if(metric_wolf){gtk_label_set_text(GTK_LABEL(metric_wolf),r->success==1?(*r->wolf_state?r->wolf_state:"WOLF SERVICE  UNKNOWN"):"WOLF SERVICE  --");
    GtkStyleContext*cs=gtk_widget_get_style_context(metric_wolf);gtk_style_context_remove_class(cs,"good");
    if(r->success==1 && strstr(r->wolf_state,"WOLF SERVICE  running"))gtk_style_context_add_class(cs,"good");}
   if(metric_wolf_sessions){gtk_label_set_text(GTK_LABEL(metric_wolf_sessions),r->success==1?(*r->wolf_sessions?r->wolf_sessions:"WOLF DESKTOPS  unknown"):"WOLF DESKTOPS  --");
    GtkStyleContext*cs=gtk_widget_get_style_context(metric_wolf_sessions);gtk_style_context_remove_class(cs,"good");
    if(r->success==1 && strstr(r->wolf_sessions,"WOLF DESKTOPS  ")==r->wolf_sessions && atoi(r->wolf_sessions+strlen("WOLF DESKTOPS  "))>0)gtk_style_context_add_class(cs,"good");}
   update_drives(r);
   if(tailscale_label)gtk_label_set_text(GTK_LABEL(tailscale_label),r->tail?"TAILSCALE CONNECTED":"TAILSCALE NOT CONNECTED");
   status_inflight=0;
 }else if(r->type==8){
    if(wizard_wolf_label)gtk_label_set_text(GTK_LABEL(wizard_wolf_label),r->success?"WOLF REACHABLE":"WOLF NOT DETECTED. YOU CAN STILL CONTINUE");
    wolf_inflight=0;
 }else if(r->type==6){
    if(spec_status)gtk_label_set_text(GTK_LABEL(spec_status),r->success?"LIVE HARDWARE INVENTORY":"SERVER UNAVAILABLE. CHECK SSH / TAILSCALE");
    if(r->success){
      for(int i=0;i<8;i++)if(spec_values[i])gtk_label_set_text(GTK_LABEL(spec_values[i]),*r->specs[i]?r->specs[i]:"NOT AVAILABLE");
    }
    specs_inflight=0;
 }else if(r->type==5){
    if(r->success==1 && !strncmp(r->message,"http://",7)){
      if(games_notice)gtk_label_set_text(GTK_LABEL(games_notice),"OPENING WOLF PIN PAGE");
      browser_open(r->message);
    }else{
      if(games_notice)gtk_label_set_text(GTK_LABEL(games_notice),r->message);
      say(r->message);
    }
    power_inflight=0;
 }else {say(r->message);power_inflight=0;}
 free(r);return 0;
}
static int tcp_reachable(const char *host,const char *port){
 if(!now_valid_host(host))return 0;
 struct addrinfo hints={.ai_family=AF_UNSPEC,.ai_socktype=SOCK_STREAM};
 struct addrinfo *addresses=NULL;
 if(getaddrinfo(host,port,&hints,&addresses))return 0;
 int success=0;
 for(struct addrinfo *a=addresses;a&&!success;a=a->ai_next){
   int fd=socket(a->ai_family,a->ai_socktype,a->ai_protocol);
   if(fd<0)continue;
   int flags=fcntl(fd,F_GETFL,0);
   if(flags<0){close(fd);continue;}
   fcntl(fd,F_SETFL,flags|O_NONBLOCK);
   if(connect(fd,a->ai_addr,a->ai_addrlen)==0)success=1;
   else if(errno==EINPROGRESS){
     struct pollfd pfd={.fd=fd,.events=POLLOUT};
     if(poll(&pfd,1,1800)>0){int e=0;socklen_t len=sizeof e;
       if(getsockopt(fd,SOL_SOCKET,SO_ERROR,&e,&len)==0 && e==0)success=1;}
   }
   close(fd);
 }
 freeaddrinfo(addresses);return success;
}
static void *worker(void*arg){
 Result*r=arg;char out[512]={0};
 if(r->type==0){
   int tailscale_ok=0;
   if (now_program_exists("tailscale")) {
       char *argv[] = {"/usr/bin/python3",
                       "/usr/lib/optiplex-now/tailscale-status.py", NULL};
       tailscale_ok = now_run(argv, out, sizeof out, 6) == 0 &&
                      g_str_has_prefix(out, "CONNECTED");
   }
   r->tail=tailscale_ok;
   if(!now_valid_host(r->target.host)||!now_valid_user(r->target.user)){r->success=0;strcpy(r->message,"CHECK SETTINGS");}
   else {
     /* Fixed, read-only remote telemetry. Mounted physical file systems. */
     const char*cmd=
      "printf 'READY\nMODEL='; cat /sys/class/dmi/id/product_name 2>/dev/null | head -1; "
      "printf 'CPU='; "
      "sensors 2>/dev/null | awk '/Package id 0:/ {print $4; exit}' | tr -d '+\r'; "
      "printf 'GPU='; nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1; "
      "printf 'CPU_LOAD='; awk 'NR==1 {total=0; for(i=2;i<=NF;i++)total+=$i; idle=$5+$6; print total,idle}' /proc/stat | "
      "awk '{a=$1;b=$2; system(\"sleep 0.2\"); getline < \"/proc/stat\"; total=0; for(i=2;i<=NF;i++)total+=$i; idle=$5+$6; if(total>a)printf \"%.0f%%\\n\",100*(1-(idle-b)/(total-a)); else print \"--\"}' ; "
      "printf 'RAM_USED='; awk '/MemTotal:/ {t=$2} /MemAvailable:/ {a=$2} END {if(t>0)printf \"%.1f / %.1f GiB\\n\",(t-a)/1048576,t/1048576}' /proc/meminfo; "
      "printf 'GPU_LOAD='; nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | awk 'NF {print $1\"%\"}'; "
      "printf 'VRAM_USED='; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | awk -F, 'NF>=2 {printf \"%.1f / %.1f GiB\\n\",$1/1024,$2/1024}'; "
      "printf 'VPN_STATUS='; if command -v docker >/dev/null 2>&1; then "
      "vpn_id=$(docker ps -a --format '{{.ID}}|{{.Image}}' 2>/dev/null | awk -F'|' '$2 ~ /(^|\\/)gluetun(:|@|$)/ {print $1; exit}'); "
      "if [ -n \"$vpn_id\" ]; then docker inspect \"$vpn_id\" --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' 2>/dev/null; else echo 'missing|no-healthcheck'; fi | "
      "awk -F'|' '{if($1==\"missing\")print \"VPN  unavailable\"; else if($1!=\"running\")print \"VPN  \" $1; else if($2==\"healthy\")print \"VPN  HEALTHY\"; else if($2==\"unhealthy\")print \"VPN  UNHEALTHY\"; else if($2==\"starting\")print \"VPN  CHECKING\"; else print \"VPN  RUNNING (UNVERIFIED)\"}'; "
      "else echo 'DOCKER UNAVAILABLE'; fi; "
      "printf 'WOLF_STATUS='; if command -v docker >/dev/null 2>&1; then docker inspect wolf --format '{{.State.Status}}' 2>/dev/null | awk 'NF {printf \"WOLF SERVICE  %s\\n\",$1}'; else echo 'DOCKER UNAVAILABLE'; fi; "
      "printf 'WOLF_DESKTOPS='; if command -v docker >/dev/null 2>&1; then "
      "n=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -c '^Wolf.*Desktop_'); "
      "printf 'WOLF DESKTOPS  %s running (not client count)\\n' \"$n\"; "
      "else echo 'DOCKER UNAVAILABLE'; fi; "
      "printf 'DRIVES_BEGIN\n'; "
      "df -hPT -x tmpfs -x devtmpfs -x overlay -x squashfs -x zramfs 2>/dev/null "
      "| awk 'NR>1 && index($1,\"/dev/\")==1 && $7 !~ \"^/(boot|efi|snap)(/|$)\" {print \"DRIVE=\" $7 \"|\" $3 \"|\" $5 \"|\" $6}' ; "
      "printf 'DRIVES_END\n'";
     char stats[8192]={0};
     char *argv[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",r->target.user,r->target.host,cmd,NULL};
     int code=now_run(argv,stats,sizeof stats,9);
     if(code==0&&strstr(stats,"READY")){
       r->success=1;strcpy(r->message,"SERVER REACHABLE");
       now_host_get_metric(r->model,sizeof r->model,stats,"MODEL=");
       now_host_get_metric(r->cpu,sizeof r->cpu,stats,"CPU=");
       now_host_get_metric(r->gpu,sizeof r->gpu,stats,"GPU=");
       now_host_get_metric(r->cpu_load,sizeof r->cpu_load,stats,"CPU_LOAD=");
       now_host_get_metric(r->gpu_load,sizeof r->gpu_load,stats,"GPU_LOAD=");
       now_host_get_metric(r->ram_used,sizeof r->ram_used,stats,"RAM_USED=");
       now_host_get_metric(r->vram_used,sizeof r->vram_used,stats,"VRAM_USED=");
       now_host_get_metric(r->vpn_state,sizeof r->vpn_state,stats,"VPN_STATUS=");
       now_host_get_metric(r->wolf_state,sizeof r->wolf_state,stats,"WOLF_STATUS=");
       now_host_get_metric(r->wolf_sessions,sizeof r->wolf_sessions,stats,"WOLF_DESKTOPS=");
       if(*r->gpu){strncat(r->gpu,"°C",sizeof r->gpu-strlen(r->gpu)-1);}
       r->drive_count = now_host_parse_drives(stats, r->drives, MAX_DRIVES);
     }
     else if(strstr(stats,"Permission denied")||strstr(stats,"Host key verification")) {r->success=2;strcpy(r->message,"AUTHORIZE SSH IN SETTINGS");}
     else if(!tailscale_ok){r->success=3;strcpy(r->message,"CHECK TAILSCALE");}
     else{r->success=0;strcpy(r->message,"SERVER UNREACHABLE");}
   }
 }else if(r->type==8){
   r->success=tcp_reachable(r->message,"47989") || tcp_reachable(r->message,"47984");
 }else if(r->type==6){
   if(now_valid_host(r->target.host)&&now_valid_user(r->target.user)){
     /* Read-only hardware inventory. No root privileges and no hardcoded specifications. */
     const char*cmd=
      "printf 'MODEL='; cat /sys/class/dmi/id/product_name 2>/dev/null | head -1; "
      "printf 'CPU_MODEL='; sed -n 's/^[[:space:]]*model name[[:space:]]*:[[:space:]]*//p' /proc/cpuinfo | head -1; "
      "printf 'GPU_MODEL='; gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1); "
      "if [ -z \"$gpu\" ]; then gpu=$(nvidia-smi -L 2>/dev/null | head -1 | sed 's/^GPU [0-9][0-9]*: //;s/ (UUID:.*$//'); fi; printf '%s\\n' \"$gpu\"; "
      "printf 'VRAM='; nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1; "
      "printf 'RAM='; awk '/MemTotal:/ {printf \"%.1f GiB\\n\",$2/1048576}' /proc/meminfo; "
      "printf 'OS='; . /etc/os-release; printf '%s\\n' \"$PRETTY_NAME\"; "
      "printf 'DRIVER='; nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1";
     char stats[8192]={0};
     char *argv[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",r->target.user,r->target.host,(char*)cmd,NULL};
     if(now_run(argv,stats,sizeof stats,10)==0 && strstr(stats,"MODEL=")){
       const char *keys[]={"MODEL=","CPU_MODEL=","GPU_MODEL=","VRAM=","RAM=","OS=","DRIVER="};
       for(int i=0;i<7;i++)now_host_get_metric(r->specs[i],sizeof r->specs[i],stats,keys[i]);
       r->success=1;
     }
   }
 }else if(r->type==5){
   if(!now_valid_host(r->target.host)||!now_valid_user(r->target.user)) {strcpy(r->message,"CHECK SERVER SETTINGS");}
   else {
     char *args[]={"ssh","-o","BatchMode=yes","-o","ConnectTimeout=5","-o","StrictHostKeyChecking=yes",
         "-l",r->target.user,r->target.host,
         "docker logs --since 10m wolf 2>&1 | grep -oE 'http[^[:space:]]+/pin/#[0-9A-Fa-f]+' | tail -1",NULL};
     char logline[4096]={0};int c=now_run(args,logline,sizeof(logline),9);
     char *hash=strstr(logline,"/pin/#");
     if(c==0&&hash){
       hash+=6;char token[90];int i=0;
       while(isxdigit((unsigned char)hash[i])&&i<80){token[i]=hash[i];i++;}
       token[i]=0;
       if(i>=6){snprintf(r->message,sizeof r->message,"http://%s:47989/pin/#%s",r->target.host,token);r->success=1;}
       else strcpy(r->message,"INVALID WOLF PIN LINK");
     }else strcpy(r->message,"START PAIR WOLF FIRST, THEN RETRY");
   }
 }else {
   int kind=r->type-1; int relay=kind==0;
   if(!now_valid_host(r->target.host)||!now_valid_user(r->target.user)){strcpy(r->message,"Invalid host or user. Check Settings.");}
   else {
     char*arg[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",r->target.user,r->target.host,NULL,NULL};
     char command[1024];
     if(relay) {
       if(!*r->target.wake_path||!now_safe_wake_path(r->target.wake_path)){strcpy(r->message,"Set a valid relay wake script in Settings");goto done;}
       snprintf(command,sizeof command,"%s",r->target.wake_path);
     }else{
       const char*actions[]={"suspend","reboot","poweroff"};
       snprintf(command,sizeof command,"sudo -n /usr/bin/systemctl %s",actions[kind-1]);
     }
     arg[12]=command;
     int code=now_run(arg,out,sizeof out,14);
     if(code==0){r->success=1;strcpy(r->message,relay?"WAKE SENT":"POWER COMMAND SENT");}
     else if ((kind==1||kind==2||kind==3) && (strstr(out,"Connection to")||strstr(out,"closed"))) {r->success=1;strcpy(r->message,"POWER COMMAND SENT");}
     else {r->success=0;snprintf(r->message,sizeof r->message,"%s",*out?out:"COMMAND FAILED. CHECK SSH / SUDO");
       r->message[strcspn(r->message,"\r\n")]=0;}
   }
 }
 done:g_idle_add(finish_on_main,r);return NULL;
}
static void begin_job(int type) {
 if(type==0&&status_inflight)return;
 if(type==6&&specs_inflight)return;
 if(type==8&&wolf_inflight)return;
 if(type!=0&&type!=6&&type!=8&&power_inflight)return;
 if(type==0)status_inflight=1;else if(type==6)specs_inflight=1;else if(type==8)wolf_inflight=1;else power_inflight=1;
 Result*r=calloc(1,sizeof* r);
 int relay=type==1;
 if(r)r->type=type;
 if(!r || !now_host_job_target_capture(&r->target,
                relay?cfg[2]:cfg[0],relay?cfg[3]:cfg[1],
                relay?cfg[4]:"")){
   free(r);
   if(type==0)status_inflight=0;else if(type==6)specs_inflight=0;
   else if(type==8)wolf_inflight=0;else power_inflight=0;
   return;
 }
 if(type==8)safe_copy(r->message,sizeof r->message,*wolf_probe_host?wolf_probe_host:cfg[0]);
 pthread_t t; if(pthread_create(&t,NULL,worker,r)==0)pthread_detach(t);else{free(r);if(type==0)status_inflight=0;else if(type==6)specs_inflight=0;else if(type==8)wolf_inflight=0;else power_inflight=0;}
}
static gboolean periodic(void*unused){(void)unused;begin_job(0);return 1;}
static void refresh(void){gtk_label_set_text(GTK_LABEL(indicator),"● CHECKING");begin_job(0);}
static void on_power(void*widget,void*data){(void)widget;int n=(int)(long)data;
 if(n>0){const char*names[]={"","Sleep","Restart","Shut down"};
   GtkWidget*d=gtk_dialog_new_with_buttons("Confirm",GTK_WINDOW(win),1,"CANCEL",GTK_RESPONSE_CANCEL,"CONFIRM",GTK_RESPONSE_OK,NULL);
   GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));char msg[128];snprintf(msg,sizeof msg,"%s server?",names[n]);
   GtkWidget*l=label(msg,"modalheading");gtk_widget_set_margin_start(l,22);gtk_widget_set_margin_end(l,22);
   gtk_widget_set_margin_top(l,16);gtk_widget_set_margin_bottom(l,12);add(area,l,0);gtk_widget_show_all(d);
   int resp=gtk_dialog_run(GTK_DIALOG(d));gtk_widget_destroy(d);if(resp!=GTK_RESPONSE_OK)return;
 }
 say("SENDING POWER COMMAND");begin_job(n+1);
}
static int has_moonlight(void) {return moonlight_mode()!=0;}
static void open_moonlight(void){
 int mode=moonlight_mode();
 if(mode==1){char*args[]={(char*)find_appimage(),NULL};now_launch(args);say("MOONLIGHT APPIMAGE OPENED");}
 else if(mode==2){char*args[]={"moonlight",NULL};now_launch(args);say("MOONLIGHT OPENED");}
 else if(mode==3){char*args[]={"flatpak","run","com.moonlight_stream.Moonlight",NULL};now_launch(args);say("MOONLIGHT OPENED");}
 else say("CHOOSE AN APPIMAGE OR INSTALL MOONLIGHT IN GAMES SETUP");
}
/* Directly connect the selected Moonlight client to the Steam application on Wolf.
 * Moonlight Qt supports: moonlight stream HOST APP. Preferences and pairing
 * are read from its own existing profile, preserving hardware decoding. */
static void launch_wolf_app(const char *app){
 if(!has_moonlight()){on_games_setup(NULL,NULL);return;}
 if(!now_valid_host(cfg[0])){say("SET SERVER IN SETTINGS");open_moonlight();return;}
 int mode=moonlight_mode();
 if(mode==1){char *args[]={(char*)find_appimage(),"stream",cfg[0],(char*)app,NULL};now_launch(args);}
 else if(mode==2){char *args[]={"moonlight","stream",cfg[0],(char*)app,NULL};now_launch(args);}
 else {char *args[]={"flatpak","run","com.moonlight_stream.Moonlight","stream",cfg[0],(char*)app,NULL};now_launch(args);}
 say("MOONLIGHT LAUNCHED — STREAM STATUS NOT VERIFIED");
}
/*
 * Games P0: the MacBook physically verified owner-only Steam lifecycle.
 * GTK must now use the separate restricted device key, not the old direct
 * moonlight-profile-id Steam app or the administrative SSH credentials.
 * This is a source-only alpha handoff; the reference host still denies Start.
 */
#define NOW_GAMES_HELPER "/usr/lib/optiplex-now/owner-games-client.py"
typedef struct {
 gboolean running;
 gboolean opening_ui;
 gboolean stopping;
 guint poll_id;
 gint64 deadline;
 GCancellable *cancel;
 char host[512];
 char user[512];
} ManagedGamesFlow;
static ManagedGamesFlow managed_games={0};
static void managed_games_send(const char *action);

static void managed_games_message(const char *message){
 say(message);
 if(games_notice)gtk_label_set_text(GTK_LABEL(games_notice),message);
}
static void managed_games_finish(const char *message){
 if(managed_games.poll_id){
  g_source_remove(managed_games.poll_id);
  managed_games.poll_id=0;
 }
 g_clear_object(&managed_games.cancel);
 managed_games.running=FALSE;
 managed_games_message(message);
}
static gboolean managed_games_poll(gpointer data){
 (void)data;
 managed_games.poll_id=0;
 if(managed_games.running)managed_games_send("status");
 return G_SOURCE_REMOVE;
}
static void managed_games_reply(GObject *source,GAsyncResult *result,gpointer data){
 (void)source;
 const char *action=data;
 NowGamesReply answer=NOW_GAMES_BUSY;
 GError *error=NULL;
 gboolean ok=now_games_request_finish(result,&answer,&error);
 if(error)g_error_free(error);
 if(!managed_games.running)return;
 if(!ok){
  managed_games_finish(managed_games.stopping?
    "STEAM STOP UNCONFIRMED. CHECK HOST STATUS BEFORE RETRY":
    "GAMES HOST REFUSED OR UNAVAILABLE. NO DIRECT STEAM FALLBACK");
  return;
 }
 if(managed_games.stopping){
  managed_games_finish(answer==NOW_GAMES_IDLE?
    "STEAM LOBBY STOP CONFIRMED":
    "STEAM STOP NOT CONFIRMED. CHECK HOST STATUS");
  return;
 }
 if(strcmp(action,"start")==0){
  managed_games_finish(answer==NOW_GAMES_JOINED?
    "OWNER STEAM JOINED. CONTINUE IN MOONLIGHT":
    "STEAM LAUNCH NOT CONFIRMED. CHECK GAMES STATUS");
  return;
 }
 if(answer==NOW_GAMES_WOLF_UI_CONNECTED){
  managed_games_message("OWNER DEVICE AUTHORIZED. REQUESTING STEAM...");
  managed_games_send("start");
  return;
 }
 if(answer==NOW_GAMES_NEEDS_WOLF_UI){
  if(g_get_monotonic_time()>=managed_games.deadline){
   managed_games_finish("WOLF UI DID NOT CONNECT. NO STEAM LAUNCH ATTEMPTED");
   return;
  }
  if(!managed_games.opening_ui){
   managed_games.opening_ui=TRUE;
   managed_games_message("OPENING MOONLIGHT WOLF UI");
   launch_wolf_app("Wolf UI");
  }
  managed_games_message("WAITING FOR AUTHENTICATED WOLF UI STREAM");
  managed_games.poll_id=g_timeout_add_seconds(3,managed_games_poll,NULL);
  return;
 }
 if(answer==NOW_GAMES_IN_USE){
  managed_games_finish("OWNER STEAM ALREADY IN USE. CHECK SESSION BEFORE RETRY");
 }else if(answer==NOW_GAMES_BUSY){
  managed_games_finish("WOLF BUSY WITH ANOTHER SESSION. NO STEAM LAUNCH");
 }else{
  managed_games_finish("UNEXPECTED GAMES STATUS. NO STEAM LAUNCH");
 }
}
static void managed_games_send(const char *action){
 if(!managed_games.running || !managed_games.cancel)return;
 now_games_request_async(NOW_GAMES_HELPER,action,managed_games.host,
                         managed_games.user,managed_games.cancel,
                         managed_games_reply,(gpointer)action);
}
static void managed_games_begin(gboolean stop){
 if(managed_games.running){
  managed_games_message("GAMES REQUEST ALREADY IN PROGRESS");
  return;
 }
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){
  managed_games_message("SET SERVER AND SSH USER IN SETTINGS");
  return;
 }
 if(access(NOW_GAMES_HELPER,R_OK)!=0){
  managed_games_message("MANAGED GAMES CLIENT MISSING. UPDATE NOW INSTALLER");
  return;
 }
 char *key=g_build_filename(g_get_home_dir(),".local","share",
   "optiplex-now","games-client","id_ed25519",NULL);
 gboolean has_key=g_file_test(key,G_FILE_TEST_IS_REGULAR);
 g_free(key);
 if(!has_key){
  managed_games_message("THIS DEVICE NEEDS OWNER GAMES APPROVAL");
  return;
 }
 if(!stop && !has_moonlight()){on_games_setup(NULL,NULL);return;}
 memset(&managed_games,0,sizeof managed_games);
 managed_games.running=TRUE;
 managed_games.stopping=stop;
 managed_games.cancel=g_cancellable_new();
 managed_games.deadline=g_get_monotonic_time()+90*G_USEC_PER_SEC;
 g_strlcpy(managed_games.host,cfg[0],sizeof managed_games.host);
 g_strlcpy(managed_games.user,cfg[1],sizeof managed_games.user);
 managed_games_message(stop?"REQUESTING GUARDED OWNER STEAM STOP":
  "CHECKING APPROVED GAMES CONNECTION...");
 managed_games_send(stop?"stop":"status");
}
static void on_managed_games_stop(void *widget,void *data){
 (void)widget;(void)data;
 if(managed_games.running){
  managed_games_message("GAMES REQUEST IN PROGRESS. RETRY WHEN FINISHED");
  return;
 }
 GtkWidget *dialog=gtk_message_dialog_new(GTK_WINDOW(win),GTK_DIALOG_MODAL,
  GTK_MESSAGE_WARNING,GTK_BUTTONS_NONE,
  "Stop the owner's current Steam session?");
 gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
  "This may close a running game. Stop only the session you own.");
 gtk_dialog_add_buttons(GTK_DIALOG(dialog),"Cancel",GTK_RESPONSE_CANCEL,
                        "Stop Steam",GTK_RESPONSE_OK,NULL);
 int response=gtk_dialog_run(GTK_DIALOG(dialog));
 gtk_widget_destroy(dialog);
 if(response==GTK_RESPONSE_OK)managed_games_begin(TRUE);
}
static void launch_steam(void){managed_games_begin(FALSE);}
static void launch_desktop(void){launch_wolf_app("OptiPlex Studio Desktop");}
static void launch_torrents(void){
 if(!*cfg[7] || !now_safe_preset_url(cfg[7])){say("SET DOWNLOADS URL IN SETTINGS");return;}
 browser_open(cfg[7]);
}
typedef struct {
    GtkWidget *dialog;
    GtkWidget *status;
    GCancellable *cancel;
    guint timeout_id;
    gboolean finished;
} MoonlightInstallUI;

static MoonlightInstallUI *moonlight_install_ui = NULL;

static gboolean moonlight_install_timeout(gpointer data)
{
    MoonlightInstallUI *state = data;
    state->timeout_id = 0;
    g_cancellable_cancel(state->cancel);
    if (state->dialog) {
        gtk_label_set_text(GTK_LABEL(state->status),
                           "INSTALLATION TIMED OUT. STOPPING...");
    }
    return G_SOURCE_REMOVE;
}

static void moonlight_install_destroy(GtkWidget *widget, gpointer data)
{
    (void)widget;
    MoonlightInstallUI *state = data;
    state->dialog = NULL;
    state->status = NULL;
    if (!state->finished) {
        g_cancellable_cancel(state->cancel);
    }
}

static void moonlight_install_response(GtkDialog *dialog, gint response,
                                        gpointer data)
{
    (void)response;
    MoonlightInstallUI *state = data;
    if (state->finished) {
        gtk_widget_destroy(GTK_WIDGET(dialog));
        return;
    }
    gtk_widget_destroy(GTK_WIDGET(dialog)); /* also cancels the active worker */
}

static void moonlight_install_done(GObject *source, GAsyncResult *result,
                                    gpointer data)
{
    (void)source;
    MoonlightInstallUI *state = data;
    GError *error = NULL;
    gboolean installed = now_moonlight_install_finish(result, &error);
    state->finished = TRUE;
    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
        state->timeout_id = 0;
    }

    const char *message = "MOONLIGHT INSTALLED. OPEN IT TO PAIR WITH WOLF.";
    if (!installed) {
        message = g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)
            ? "MOONLIGHT INSTALLATION CANCELLED."
            : "MOONLIGHT COULD NOT BE INSTALLED. CHECK YOUR CONNECTION AND FLATPAK.";
    }
    say(message);
    if (games_notice) {
        gtk_label_set_text(GTK_LABEL(games_notice), message);
    }
    if (games_install) {
        gtk_widget_set_sensitive(games_install, TRUE);
        gtk_button_set_label(GTK_BUTTON(games_install),
                             installed ? "OPEN MOONLIGHT" : "INSTALL MOONLIGHT");
    }
    if (state->dialog) {
        gtk_label_set_text(GTK_LABEL(state->status), message);
        GtkWidget *button = gtk_dialog_get_widget_for_response(
            GTK_DIALOG(state->dialog), GTK_RESPONSE_CANCEL);
        if (button) {
            gtk_button_set_label(GTK_BUTTON(button), "Close");
        }
    }
    g_clear_error(&error);
    g_clear_object(&state->cancel);
    moonlight_install_ui = NULL;
    if (!state->dialog) {
        g_free(state);
    }
}

static void moonlight_install_dialog_destroy(GtkWidget *widget, gpointer data)
{
    MoonlightInstallUI *state = data;
    moonlight_install_destroy(widget, data);
    if (state->finished) {
        g_free(state);
    }
}

static void install_moonlight(void)
{
    if (moonlight_install_ui) {
        say("MOONLIGHT INSTALLATION IS ALREADY IN PROGRESS.");
        return;
    }
    if (!now_program_exists("flatpak")) {
        say("FLATPAK IS REQUIRED. INSTALL FLATPAK OR USE A MOONLIGHT APPIMAGE.");
        if (games_notice) {
            gtk_label_set_text(GTK_LABEL(games_notice),
                               "INSTALL FLATPAK OR CHOOSE A MOONLIGHT APPIMAGE.");
        }
        return;
    }
    GtkWidget *parent = games_install ? gtk_widget_get_toplevel(games_install)
                                     : active_setup_wizard;
    if (!parent || !GTK_IS_WINDOW(parent)) {
        parent = win;
    }
    GtkWidget *confirmation = gtk_message_dialog_new(
        GTK_WINDOW(parent), GTK_DIALOG_MODAL, GTK_MESSAGE_QUESTION,
        GTK_BUTTONS_NONE, "Install Moonlight on this computer?");
    gtk_message_dialog_format_secondary_text(
        GTK_MESSAGE_DIALOG(confirmation),
        "OptiPlex NOW will add the official Flathub remote if needed and "
        "install Moonlight for your Linux account. It may download "
        "Moonlight and runtime dependencies. No administrator password "
        "or terminal is required.");
    gtk_dialog_add_buttons(GTK_DIALOG(confirmation), "Cancel",
                           GTK_RESPONSE_CANCEL, "Install Moonlight",
                           GTK_RESPONSE_OK, NULL);
    gtk_dialog_set_default_response(GTK_DIALOG(confirmation), GTK_RESPONSE_CANCEL);
    int response = gtk_dialog_run(GTK_DIALOG(confirmation));
    gtk_widget_destroy(confirmation);
    if (response != GTK_RESPONSE_OK) {
        return;
    }

    MoonlightInstallUI *state = g_new0(MoonlightInstallUI, 1);
    state->cancel = g_cancellable_new();
    moonlight_install_ui = state;
    state->dialog = gtk_dialog_new_with_buttons(
        "Installing Moonlight", GTK_WINDOW(parent), GTK_DIALOG_MODAL,
        "Cancel installation", GTK_RESPONSE_CANCEL, NULL);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(state->dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 20);
    state->status = gtk_label_new(
        "INSTALLING MOONLIGHT FROM FLATHUB. THIS MAY TAKE SEVERAL MINUTES.");
    gtk_label_set_line_wrap(GTK_LABEL(state->status), TRUE);
    gtk_box_pack_start(GTK_BOX(area), state->status, FALSE, FALSE, 12);
    g_signal_connect(state->dialog, "response",
                     G_CALLBACK(moonlight_install_response), state);
    g_signal_connect(state->dialog, "destroy",
                     G_CALLBACK(moonlight_install_dialog_destroy), state);
    gtk_widget_show_all(state->dialog);
    if (games_install) {
        gtk_widget_set_sensitive(games_install, FALSE);
    }
    say("INSTALLING MOONLIGHT...");
    state->timeout_id = g_timeout_add_seconds(900, moonlight_install_timeout, state);
    now_moonlight_install_async(state->cancel, moonlight_install_done, state);
}
/* The bridge is host-local behind trusted SSH. Never block GTK while querying it. */
typedef struct {
    GtkWidget *dialog;
    GtkWidget *clients;
    GtkWidget *pin_entry;
    GtkWidget *status;
    GtkWidget *refresh_button;
    GtkWidget *authorize_button;
    GCancellable *cancellable;
    guint timeout_id;
    guint auto_refresh_id;
    gint64 auto_refresh_deadline;
    gboolean busy;
    gboolean closed;
    gboolean pairing;
    char host[512];
    char user[512];
    NowWolfPending pending[NOW_WOLF_MAX_PENDING];
    int count;
} WolfPairUI;

static void wolf_ui_free(WolfPairUI *state)
{
    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
    }
    if (state->auto_refresh_id) {
        g_source_remove(state->auto_refresh_id);
    }
    g_clear_object(&state->cancellable);
    g_free(state);
}

static void wolf_ui_close(WolfPairUI *state)
{
    if (state->closed) {
        return;
    }
    state->closed = TRUE;
    if (state->auto_refresh_id) {
        g_source_remove(state->auto_refresh_id);
        state->auto_refresh_id = 0;
    }
    if (state->cancellable) {
        g_cancellable_cancel(state->cancellable);
    }
    gtk_widget_destroy(state->dialog);

    /* An outstanding GTask still owns a pointer to this state. */
    if (!state->busy) {
        wolf_ui_free(state);
    }
}

static gboolean wolf_ui_timeout(gpointer data)
{
    WolfPairUI *state = data;
    state->timeout_id = 0;
    if (!state->closed && state->cancellable) {
        g_cancellable_cancel(state->cancellable);
    }
    return G_SOURCE_REMOVE;
}

static void wolf_ui_finished(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    WolfPairUI *state = data;
    GError *error = NULL;
    char *reply = now_wolf_request_finish(result, &error);
    gboolean pairing = state->pairing;

    state->busy = FALSE;
    if (state->timeout_id) {
        g_source_remove(state->timeout_id);
        state->timeout_id = 0;
    }
    g_clear_object(&state->cancellable);

    if (state->closed) {
        g_free(reply);
        g_clear_error(&error);
        wolf_ui_free(state);
        return;
    }

    gtk_widget_set_sensitive(state->refresh_button, TRUE);
    gtk_widget_set_sensitive(state->authorize_button, TRUE);

    if (!reply) {
        gtk_label_set_text(GTK_LABEL(state->status),
            g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)
            ? "Pairing request timed out or was cancelled. Refresh and retry."
            : "Cannot reach pairing helper. Check SSH access and the host helper.");
        if (pairing) {
            state->count = 0;
            gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->clients));
        }
        g_clear_error(&error);
        return;
    }

    if (!pairing) {
        state->count = now_wolf_parse_pending(reply, state->pending,
                                               NOW_WOLF_MAX_PENDING);
        if (state->count < 0) {
            state->count = 0;
            gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->clients));
            gtk_label_set_text(GTK_LABEL(state->status),
                "Invalid or ambiguous pending clients. Refresh to retry.");
        } else {
            /* A refreshed index can refer to a different client. Clear old
             * selection and require approval of the current candidate list. */
            GtkComboBox *combo = GTK_COMBO_BOX(state->clients);
            gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->clients));
            for (int i = 0; i < state->count; i++) {
                gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(state->clients),
                                                state->pending[i].client_ip);
            }
            if (state->count == 1) {
                gtk_combo_box_set_active(combo, 0);
            } else {
                gtk_combo_box_set_active(combo, -1);
            }
            if (state->count && state->auto_refresh_id) {
                g_source_remove(state->auto_refresh_id);
                state->auto_refresh_id = 0;
            }
            gtk_label_set_text(GTK_LABEL(state->status), state->count
                ? "Select the intended Moonlight device, then authorize."
                : "Waiting for Moonlight device. Searching automatically...");
        }
    } else {
        /* The Python SSH bridge validates the host's success response and
         * exits nonzero if authorization failed. Do not parse JSON by substring. */
        gtk_entry_set_text(GTK_ENTRY(state->pin_entry), "");
        g_free(reply);
        say("MOONLIGHT PAIRED");
        wolf_ui_close(state);
        return;
    }
    g_free(reply);
}

static void wolf_ui_start(WolfPairUI *state, const char *action, const char *payload)
{
    if (state->closed || state->busy) {
        return;
    }
    state->busy = TRUE;
    state->pairing = strcmp(action, "pair") == 0;
    state->cancellable = g_cancellable_new();
    gtk_widget_set_sensitive(state->refresh_button, FALSE);
    gtk_widget_set_sensitive(state->authorize_button, FALSE);
    gtk_label_set_text(GTK_LABEL(state->status),
        state->pairing ? "Authorizing selected client..." : "Finding pending Moonlight clients...");

    state->timeout_id = g_timeout_add_seconds(20, wolf_ui_timeout, state);
    now_wolf_request_async("/usr/lib/optiplex-now/wolf-pair-client.py",
                           action, state->host, state->user, payload,
                           state->cancellable, wolf_ui_finished, state);
}

/* Poll only while awaiting a candidate, for at most three minutes. Requests
 * are serialized by wolf_ui_start and approval always requires the owner. */
static gboolean wolf_ui_auto_refresh(gpointer data)
{
    WolfPairUI *state = data;
    if (state->closed) {
        state->auto_refresh_id = 0;
        return G_SOURCE_REMOVE;
    }
    if (g_get_monotonic_time() >= state->auto_refresh_deadline) {
        state->auto_refresh_id = 0;
        if (!state->busy && state->count == 0) {
            gtk_label_set_text(GTK_LABEL(state->status),
                "No client found. Use Refresh Now to search again.");
        }
        return G_SOURCE_REMOVE;
    }
    if (!state->busy && state->count == 0) {
        wolf_ui_start(state, "pending-text", NULL);
    }
    return G_SOURCE_CONTINUE;
}

static void wolf_ui_response(GtkDialog *dialog, gint response, gpointer data)
{
    (void)dialog;
    WolfPairUI *state = data;
    if (response != 1 && response != GTK_RESPONSE_OK) {
        wolf_ui_close(state);
        return;
    }
    if (state->busy || state->closed) {
        return;
    }

    if (response == 1) {
        state->count = 0;
        gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(state->clients));
        wolf_ui_start(state, "pending-text", NULL);
        return;
    }

    int selected = gtk_combo_box_get_active(GTK_COMBO_BOX(state->clients));
    const char *pin = gtk_entry_get_text(GTK_ENTRY(state->pin_entry));
    char payload[256] = {0};
    if (selected < 0 || selected >= state->count ||
        !now_wolf_make_pair_payload(&state->pending[selected], pin,
                                    payload, sizeof payload)) {
        gtk_label_set_text(GTK_LABEL(state->status),
                           "Select a valid pending Moonlight device.");
        return;
    }

    wolf_ui_start(state, "pair", payload);
    memset(payload, 0, sizeof payload);
}

static void wolf_pair_dialog(const char *generated_pin, GtkWindow *parent)
{
    WolfPairUI *state = g_new0(WolfPairUI, 1);
    g_strlcpy(state->host, cfg[0], sizeof state->host);
    g_strlcpy(state->user, cfg[1], sizeof state->user);

    GtkWidget *dialog = gtk_dialog_new_with_buttons(
        "Connect to Game Host", parent ? parent : GTK_WINDOW(win), GTK_DIALOG_MODAL,
        "Cancel", GTK_RESPONSE_CANCEL, "Refresh Now", 1,
        "Authorize Device", GTK_RESPONSE_OK, NULL);
    state->dialog = dialog;
    state->refresh_button = gtk_dialog_get_widget_for_response(GTK_DIALOG(dialog), 1);
    state->authorize_button =
        gtk_dialog_get_widget_for_response(GTK_DIALOG(dialog), GTK_RESPONSE_OK);

    GtkWidget *content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget *hint = gtk_label_new(
        "NOW is searching for this device. Select it when it appears and "
        "approve it here. Refresh Now is available if needed.");
    gtk_label_set_line_wrap(GTK_LABEL(hint), TRUE);
    gtk_box_pack_start(GTK_BOX(content), hint, FALSE, FALSE, 8);

    state->clients = gtk_combo_box_text_new();
    gtk_box_pack_start(GTK_BOX(content), state->clients, FALSE, FALSE, 6);
    state->pin_entry = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(state->pin_entry), generated_pin);
    gtk_editable_set_editable(GTK_EDITABLE(state->pin_entry), FALSE);
    gtk_box_pack_start(GTK_BOX(content), state->pin_entry, FALSE, FALSE, 6);
    state->status = gtk_label_new("Waiting for pairing request.");
    gtk_label_set_line_wrap(GTK_LABEL(state->status), TRUE);
    gtk_box_pack_start(GTK_BOX(content), state->status, FALSE, FALSE, 6);

    g_signal_connect(dialog, "response", G_CALLBACK(wolf_ui_response), state);
    /* Temporary pairing dialog only: avoid being buried behind Moonlight's
     * PIN window. The hint ends as soon as pairing is approved or cancelled. */
    gtk_window_set_keep_above(GTK_WINDOW(dialog), TRUE);
    gtk_widget_show_all(dialog);
    gtk_window_present(GTK_WINDOW(dialog));
    state->auto_refresh_deadline = g_get_monotonic_time() + 3 * 60 * G_USEC_PER_SEC;
    state->auto_refresh_id = g_timeout_add_seconds(3, wolf_ui_auto_refresh, state);
    wolf_ui_start(state, "pending-text", NULL);
}
static void pair_wolf(GtkWidget *origin){
 if(!has_moonlight()){say("INSTALL MOONLIGHT FIRST");return;}
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){say("SET SERVER IN SETTINGS");return;}
 unsigned int random_value=0;
 if(getrandom(&random_value,sizeof random_value,0)!=(ssize_t)sizeof random_value){say("CANNOT GENERATE PAIRING PIN");return;}
 char pin[5];snprintf(pin,sizeof pin,"%04u",random_value%10000);
 const char*appimage=find_appimage();
 const gchar*native[]={"moonlight","pair",cfg[0],"--pin",pin,NULL};
 const gchar*portable[]={appimage,"pair",cfg[0],"--pin",pin,NULL};
 const gchar*flat[]={"flatpak","run","com.moonlight_stream.Moonlight","pair",cfg[0],"--pin",pin,NULL};
 int mode=moonlight_mode();
 const gchar*const*args=mode==1?portable:mode==2?native:flat;
 GError*error=NULL;
 GSubprocess*process=g_subprocess_newv(args,G_SUBPROCESS_FLAGS_STDOUT_SILENCE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 if(!process){g_clear_error(&error);say("MOONLIGHT PAIRING COULD NOT START");memset(pin,0,sizeof pin);return;}
 say("MOONLIGHT PAIRING STARTED");
 GtkWidget *toplevel = origin ? gtk_widget_get_toplevel(origin) : win;
 wolf_pair_dialog(pin, GTK_IS_WINDOW(toplevel) ? GTK_WINDOW(toplevel) : GTK_WINDOW(win));
 memset(pin,0,sizeof pin);
 /* Leave Moonlight alive long enough to finish the certificate exchange after Wolf approves. */
 g_object_unref(process);
}
static void on_games_action(void*w,void*arg){
 int resp=(int)(long)arg;
 if(resp==101){if(has_moonlight())open_moonlight();else install_moonlight();}
 else if(resp==102)open_moonlight();
 else if(resp==105)choose_appimage();
 else if(resp==103)pair_wolf(w);
 else if(resp==104){
   if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){
     if(games_notice)gtk_label_set_text(GTK_LABEL(games_notice),"CHECK SERVER SETTINGS");
   }else{
     if(games_notice)gtk_label_set_text(GTK_LABEL(games_notice),"LOOKING FOR WOLF PAIRING PAGE");
     begin_job(5);
   }
 }
 if(games_state)gtk_label_set_text(GTK_LABEL(games_state),moonlight_mode_name());
 if(games_install){gtk_button_set_label(GTK_BUTTON(games_install),has_moonlight()?"OPEN MOONLIGHT":"INSTALL MOONLIGHT");}
}
/* Only reached after an explicit confirmation. SSH/sudo authenticate in a
 * terminal; credentials never enter launcher configuration or shell arguments. */
static void on_restart_streaming(void *w, void *parent) {
 (void)w;
 void *owner=parent?parent:win;
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){
   preset_alert(owner,"Server settings needed","Set the host and SSH user in Settings first.");return;
 }
 GtkWidget*d=gtk_dialog_new_with_buttons("Restart streaming service?",GTK_WINDOW(owner),1,
   "Cancel",GTK_RESPONSE_CANCEL,"Restart streaming",GTK_RESPONSE_OK,NULL);
 gtk_dialog_set_default_response(GTK_DIALOG(d),GTK_RESPONSE_CANCEL);
 GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));
 GtkWidget*msg=gtk_label_new("This will disconnect active streaming sessions.\nSave your game first. The server itself will stay on.");
 gtk_container_set_border_width(GTK_CONTAINER(area),20);gtk_label_set_line_wrap(GTK_LABEL(msg),1);gtk_container_add(GTK_CONTAINER(area),msg);
 gtk_widget_show_all(d);int response=gtk_dialog_run(GTK_DIALOG(d));gtk_widget_destroy(d);
 if(response!=GTK_RESPONSE_OK)return;
 char *args[]={"/usr/lib/optiplex-now/restart-streaming",cfg[0],cfg[1],NULL};
 if(terminal_launch(args))say("Streaming restart opened in terminal. Check its result before reconnecting.");
 else preset_alert(owner,"Terminal unavailable","Install a supported terminal to authenticate the streaming restart.");
}

static void on_games_setup(void*w,void*p){(void)w;
 GtkWidget*d=gtk_dialog_new_with_buttons("Games",GTK_WINDOW(p?p:win),1,"CLOSE",GTK_RESPONSE_CANCEL,NULL);
 gtk_window_set_default_size(GTK_WINDOW(d),440,290);
 GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));
 GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,11);
 gtk_container_set_border_width(GTK_CONTAINER(col),20);add(area,col,0);
 add(col,label("MOONLIGHT + WOLF","modalheading"),0);
 games_state=label(moonlight_mode_name(),"gameshint");add(col,games_state,0);
 GtkWidget*address=label("","helper");char text[600];snprintf(text,sizeof text,"WOLF HOST   %s",*cfg[0]?cfg[0]:"SET SERVER IP IN SETTINGS");gtk_label_set_text(GTK_LABEL(address),text);add(col,address,0);
 add(col,label("Games requires an approved device key. Owner Steam opens through Wolf UI.","helper"),0);
 GtkWidget*row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);add(col,row,0);
 games_install=button(has_moonlight()?"OPEN MOONLIGHT":"INSTALL MOONLIGHT","setupaction");
 g_signal_connect_data(games_install,"clicked",(GCallback)on_games_action,(void*)(long)101,NULL,0);add(row,games_install,1);
 GtkWidget*choose=button("USE APPIMAGE","setupaction");
 g_signal_connect_data(choose,"clicked",(GCallback)on_games_action,(void*)(long)105,NULL,0);add(col,choose,0);
 GtkWidget*pairbutton=button("CONNECT TO GAME HOST","setupaction");
 g_signal_connect_data(pairbutton,"clicked",(GCallback)on_games_action,(void*)(long)103,NULL,0);add(row,pairbutton,1);
 GtkWidget*pin=button("OPEN WOLF PIN","setupaction");
 g_signal_connect_data(pin,"clicked",(GCallback)on_games_action,(void*)(long)104,NULL,0);add(col,pin,0);
 GtkWidget*restart=button("Restart streaming service…","setupaction");
 g_signal_connect_data(restart,"clicked",(GCallback)on_restart_streaming,d,NULL,0);add(col,restart,0);
 GtkWidget*stop=button("STOP OWNER STEAM (CONFIRM)","setupaction");
 g_signal_connect_data(stop,"clicked",(GCallback)on_managed_games_stop,NULL,NULL,0);add(col,stop,0);
 games_notice=label("","gameshint");add(col,games_notice,0);
 gtk_widget_show_all(d);gtk_dialog_run(GTK_DIALOG(d));
 games_notice=NULL;games_state=NULL;games_install=NULL;gtk_widget_destroy(d);
}
/* COSMIC Files may launch in Home when supplied a remote SFTP URI.
 * Mount it through GVFS first, then hand COSMIC an actual local FUSE path.
 * Traditional GTK and KDE file managers can still accept their SFTP URIs. */
static void open_remote_files(void){
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){say("SET SERVER AND SSH USER IN SETTINGS");return;}
 if(now_program_exists("cosmic-files")){
   const char*helper="/usr/lib/optiplex-now/open-remote-files";
   if(access(helper,X_OK)!=0){
      say("FILES HELPER MISSING. REINSTALL OPTIPLEX NOW");return;
   }
   char*args[]={(char*)helper,cfg[0],cfg[1],NULL};
   now_launch(args);say("CONNECTING TO SERVER FILES");return;
 }
 char url[640];snprintf(url,sizeof url,"sftp://%s@%s/",cfg[1],cfg[0]);
 const char*managers[]={"thunar","nemo","nautilus","dolphin","caja","pcmanfm"};
 for(unsigned i=0;i<sizeof managers/sizeof managers[0];i++){
   if(now_program_exists(managers[i])){
      char*args[]={(char*)managers[i],url,NULL};now_launch(args);say("OPENING SERVER FILES");return;
   }
 }
 if(now_program_exists("gio")){char*args[]={"gio","open",url,NULL};now_launch(args);say("OPENING SFTP LOCATION");return;}
 say("NO SFTP-CAPABLE FILE MANAGER FOUND");
}
static void open_web_gaming_path(const char*suffix){
  if(!*cfg[16] || !now_safe_preset_url(cfg[16])){say("SET WEB GAMING URL IN SETTINGS");return;}
  size_t n=strlen(cfg[16]);while(n>0 && cfg[16][n-1]=='/')n--;
  char url[768];
  if(snprintf(url,sizeof url,"%.*s%s",(int)n,cfg[16],suffix)>=(int)sizeof url){say("WEB GAMING URL TOO LONG");return;}
  browser_open(url);
}
static void on_web_gaming_settings(void*w,void*p){(void)w;(void)p;open_web_gaming_path("/settings");}
/* Opens a deliberately interactive, SSH-backed server maintenance menu.
 * The client has no Docker privileges and does not manage Wolf itself. */
static void on_web_gaming_maintenance(void*w,void*p){
 (void)w;(void)p;
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){say("SET SERVER AND SSH USER IN SETTINGS");return;}
 const char*helper="/usr/lib/optiplex-now/web-gaming-maintenance";
 if(access(helper,X_OK)!=0){say("WEB MAINTENANCE HELPER MISSING. REINSTALL OPTIPLEX NOW");return;}
 char*args[]={(char*)helper,cfg[0],cfg[1],NULL};
 if(terminal_launch(args))say("WEB MAINTENANCE OPENED IN TERMINAL. SERVER HELPER REQUIRED.");
 else preset_alert(win,"Maintenance unavailable","No terminal emulator found. Install a terminal and retry.");
}
static void on_web_gaming_admin(void*w,void*p){
 (void)w;(void)p;
 if(!now_valid_host(cfg[0])||!now_valid_user(cfg[1])){say("SET SERVER AND SSH USER IN SETTINGS");return;}
 const char*helper="/usr/lib/optiplex-now/open-web-gaming-admin";
 if(access(helper,X_OK)!=0){say("WEB ADMIN HELPER MISSING. REINSTALL OPTIPLEX NOW");return;}
 char*args[]={(char*)helper,cfg[0],cfg[1],NULL};
 now_launch(args);
 say("OPENING WEB GAMING ADMIN VIA SSH");
}
/* Open WebUI is the Bruiser front end; Ollama and SearXNG remain separate.
 * Default to the user's configured host, not a machine-specific fixed IP. */
static int bruiser_url(char *out,size_t cap,int admin){
 char base[640];
 if(*cfg[14]){
   if(!now_safe_preset_url(cfg[14]))return 0;
   safe_copy(base,sizeof base,cfg[14]);
 }else{
   if(!now_valid_host(cfg[0]))return 0;
   snprintf(base,sizeof base,"http://%s:3000",cfg[0]);
 }
 size_t n=strlen(base);
 while(n>0&&base[n-1]=='/')base[--n]=0;
 if(admin)snprintf(out,cap,"%s/admin/settings",base);
 else safe_copy(out,cap,base);
 return 1;
}
static void on_bruiser_ai(void*w,void*p){
 (void)w;(void)p;
 char url[720];
 if(!bruiser_url(url,sizeof url,0)){say("SET SERVER OR BRUISER URL IN SETTINGS");return;}
 browser_open(url);
}
static void on_bruiser_admin(void*w,void*p){
 (void)w;(void)p;
 char url[720];
 if(!bruiser_url(url,sizeof url,1)){say("SET SERVER OR BRUISER URL IN SETTINGS");return;}
 browser_open(url);
 say("BRUISER ADMIN REQUIRES OPEN WEBUI ADMIN ACCOUNT");
}
static void on_tile(void*widget,void*data){(void)widget;int n=(int)(long)data;
 if(n==0){
   if(has_moonlight())launch_steam();else on_games_setup(NULL,NULL);
 }else if(n==1||n==2){int ix=n==1?5:6;if(!*cfg[ix]){say("ADD URL IN SETTINGS");return;}browser_open(cfg[ix]);}
 else if(n==4)launch_torrents();
 else if(n==3)open_remote_files();
 else if(n==5)launch_ssh(0);
 else if(n==6)launch_desktop();
 else if(n==7)open_web_gaming_path("/?launch=steam");
 else if(n==8)on_bruiser_ai(NULL,NULL);
 
}
static void reflow(int width) {
 int cols=width>=600?4:2;
 int pcols=width>=560?4:2;
 if(cols==last_columns && pcols==last_power_columns)return;
 if(cols!=last_columns){
   last_columns=cols;
   /* Move each action to exactly one section without destroying its widget. */
   for(int i=0;i<8;i++){
     g_object_ref(tiles[i]);
     void*parent=gtk_widget_get_parent(tiles[i]);
     if(parent)gtk_container_remove(GTK_CONTAINER(parent),tiles[i]);
   }
   unsigned featured=featured_mask();int primary=0,other=0;
   for(int i=0;i<8;i++){
     int chosen=(featured&(1u<<i))!=0;
     int pos=chosen?primary++:other++;
     gtk_grid_attach(GTK_GRID(chosen?grid:extras_grid),tiles[i],pos%cols,pos/cols,1,1);
     g_object_unref(tiles[i]);
   }
   gtk_widget_show_all(grid);
   gtk_widget_show_all(extras_grid);
 }
 if(pcols!=last_power_columns){
   last_power_columns=pcols;
   for(int i=0;i<4;i++){g_object_ref(powers[i]);if(gtk_widget_get_parent(powers[i]))gtk_container_remove(GTK_CONTAINER(power_grid),powers[i]);}
   for(int i=0;i<4;i++){gtk_grid_attach(GTK_GRID(power_grid),powers[i],i%pcols,i/pcols,1,1);g_object_unref(powers[i]);}
   gtk_widget_show_all(power_grid);
 }
}
static void on_size(void*widget,void*allocation,void*unused) {
 (void)widget;(void)unused;
 /* GtkAllocation layout: x,y,width,height */
 const int *bounds=(const int*)allocation;int w=bounds[2];
 if(w>0)reflow(w);
}
/* Single instance: selecting the normal app launcher while running in the
 * tray brings the existing window back, rather than adding a second icon. */
static void request_reopen(int signo){ (void)signo; reopen_requested=1; }
static int claim_instance(void){
 char path[PATH_MAX];
 const char *runtime=getenv("XDG_RUNTIME_DIR");
 int n;
 if(runtime && *runtime){
   n=snprintf(path,sizeof path,"%s/optiplex-now.lock",runtime);
 }else{
   const char *home=getenv("HOME");
   char cache[PATH_MAX];
   n=snprintf(cache,sizeof cache,"%s/.cache",home?home:"/tmp");
   if(n<0 || (size_t)n>=sizeof cache){
     fprintf(stderr,"Instance cache path is too long\n");
     return -1;
   }
   if(mkdir(cache,0700)!=0 && errno!=EEXIST){
     fprintf(stderr,"Could not create instance cache: %s\n",strerror(errno));
     return -1;
   }
   n=snprintf(path,sizeof path,"%s/optiplex-now.lock",cache);
 }
 if(n<0 || (size_t)n>=sizeof path){
   fprintf(stderr,"Instance lock path is too long\n");
   return -1;
 }
 instance_fd=open(path,O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
 if(instance_fd<0){
   fprintf(stderr,"Could not open instance lock: %s\n",strerror(errno));
   return -1;
 }
 struct stat st;
 if(fstat(instance_fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_uid!=geteuid()){
   fprintf(stderr,"Instance lock must be a regular file owned by this user\n");
   goto lock_error;
 }
 if(flock(instance_fd,LOCK_EX|LOCK_NB)!=0){
   if(errno!=EWOULDBLOCK && errno!=EAGAIN){
     fprintf(stderr,"Could not acquire instance lock: %s\n",strerror(errno));
     goto lock_error;
   }
   char buf[64]={0};
   if(lseek(instance_fd,0,SEEK_SET)>=0){
     ssize_t got=read(instance_fd,buf,sizeof(buf)-1);
     if(got>0){
       char *end=NULL;
       errno=0;
       long pid=strtol(buf,&end,10);
       if(errno==0 && end!=buf && (*end=='\n' || *end=='\0') && pid>1 && pid<=INT_MAX)
         kill((pid_t)pid,SIGUSR1);
     }
   }
   close(instance_fd);
   instance_fd=-1;
   return 0;
 }
 struct sigaction sa={0};
 sa.sa_handler=request_reopen;
 sigemptyset(&sa.sa_mask);
 if(sigaction(SIGUSR1,&sa,NULL)!=0){
   fprintf(stderr,"Could not install reopen signal handler: %s\n",strerror(errno));
   goto lock_error;
 }
 char buf[64];
 n=snprintf(buf,sizeof buf,"%ld\n",(long)getpid());
 if(n<0 || (size_t)n>=sizeof buf || ftruncate(instance_fd,0)!=0 ||
    lseek(instance_fd,0,SEEK_SET)<0){
   fprintf(stderr,"Could not prepare instance PID file: %s\n",strerror(errno));
   goto lock_error;
 }
 size_t written=0;
 while(written<(size_t)n){
   ssize_t k=write(instance_fd,buf+written,(size_t)n-written);
   if(k<0 && errno==EINTR)continue;
   if(k<=0){
     fprintf(stderr,"Could not write instance PID: %s\n",strerror(errno));
     goto lock_error;
   }
   written+=(size_t)k;
 }
 return 1;
lock_error:
 close(instance_fd);
 instance_fd=-1;
 return -1;
}
static gboolean tray_finish_restore(void *unused){
 (void)unused;
 if(win){
   gtk_window_deiconify(GTK_WINDOW(win));
   gtk_widget_show_all(win);
   gtk_window_present(GTK_WINDOW(win));
 }
 tray_restoring=0;
 return 0;
}
static void tray_show_window(void){
 if(!win)return;
 tray_restoring=1;
 /* On XFCE, hidden maximized/fullscreen windows can reopen as an unresizable
  * screen-filling surface. The tray is a normal-window restore action. */
 gtk_window_unfullscreen(GTK_WINDOW(win));
 gtk_window_unmaximize(GTK_WINDOW(win));
 gtk_window_set_resizable(GTK_WINDOW(win),TRUE);
 gtk_window_deiconify(GTK_WINDOW(win));gtk_widget_show_all(win);gtk_window_present(GTK_WINDOW(win));
 /* Some XFCE window managers send the iconified-state event after restore.
  * Present a second time once that event has been processed. */
 g_timeout_add(140,tray_finish_restore,NULL);
}
static gboolean reopen_check(void *unused){
 (void)unused;if(reopen_requested){reopen_requested=0;tray_show_window();}return 1;
}
/* Don't leave an invisible process behind if the desktop has no tray. */
static gboolean can_minimize_to_tray(void){return using_status_notifier ? tray_available : (tray_icon && gtk_status_icon_is_embedded(GTK_STATUS_ICON(tray_icon)));}
static gboolean close_to_tray(void *widget,void*event,void*unused){
 (void)widget;(void)event;(void)unused;
 if(can_minimize_to_tray()){gtk_widget_hide(win);return 1;}
 return 0;
}
/* This matches GdkEventWindowState on GTK3. */
typedef struct {int type;void*window;signed char send_event;int changed_mask;int new_window_state;} TrayWindowStateEvent;
static gboolean minimize_to_tray(void *widget,void*event,void*unused){
 (void)widget;(void)unused;
 const TrayWindowStateEvent *e=event;
 if(e && !tray_restoring && (e->changed_mask & 2) && (e->new_window_state & 2) && can_minimize_to_tray()){
   gtk_widget_hide(win);
 }
 return 0;
}
static void on_window_destroy(void*widget,void*unused){(void)widget;(void)unused;gtk_main_quit();}

typedef struct { GtkWidget* inputs[8]; int relay; GtkWidget*parent; } PairContext;
static void on_pair_click(void*w,void*p){
 (void)w; PairContext*c=p;
 for(int i=0;i<5;i++){
   const char*v=gtk_entry_get_text(GTK_ENTRY(c->inputs[i]));
   if(strchr(v,'\n')||strchr(v,'\r'))return;
   safe_copy(cfg[i],512,v);
 }
 config_save();pair(c->relay);
}
static void on_games_setup_from_settings(void*w,void*p){
 PairContext*c=p;
 for(int i=0;i<5;i++){
   const char*v=gtk_entry_get_text(GTK_ENTRY(c->inputs[i]));
   if(strchr(v,'\n')||strchr(v,'\r'))return;
   safe_copy(cfg[i],512,v);
 }
 config_save();on_games_setup(w,c->parent);
}
static void on_tail(void*w,void*p){(void)w;(void)p;setup_tailscale();}
/* Host review runs in its own small GTK process; no changes to client state. */
static void on_server_readiness(void *w,void *p)
{
 (void)w;(void)p;
 gchar *argv[]={"/usr/lib/optiplex-now/now-host-setup",NULL};
 GError *error=NULL;
 if(!g_spawn_async(NULL,argv,NULL,G_SPAWN_DEFAULT,NULL,NULL,NULL,&error)){
   if(error)g_error_free(error);
   preset_alert(win,"Server setup unavailable",
       "Read-only host setup is not installed. Install the latest NOW test package.");
 }
}

static void on_system_info(void*w,void*p){
 (void)w;(void)p;
 GtkWidget*d=gtk_dialog_new_with_buttons("System Info",GTK_WINDOW(win),1,"CLOSE",GTK_RESPONSE_CANCEL,NULL);
 gtk_window_set_default_size(GTK_WINDOW(d),490,390);
 GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));
 GtkWidget*box=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);gtk_container_set_border_width(GTK_CONTAINER(box),20);add(area,box,1);
 add(box,label("SYSTEM INFO","modalheading"),0);
 spec_status=label("READING HARDWARE...","helper");add(box,spec_status,0);
 GtkWidget*rows=gtk_grid_new();gtk_grid_set_row_spacing(GTK_GRID(rows),13);gtk_grid_set_column_spacing(GTK_GRID(rows),18);add(box,rows,1);
 const char*names[]={"MODEL","PROCESSOR","GRAPHICS","VIDEO MEMORY","SYSTEM RAM","OPERATING SYSTEM","NVIDIA DRIVER"};
 for(int i=0;i<7;i++){
   GtkWidget*name=label(names[i],"specname");gtk_widget_set_size_request(name,135,-1);gtk_grid_attach(GTK_GRID(rows),name,0,i,1,1);
   spec_values[i]=label("...","specvalue");gtk_label_set_ellipsize(GTK_LABEL(spec_values[i]),3);gtk_widget_set_hexpand(spec_values[i],1);
   gtk_grid_attach(GTK_GRID(rows),spec_values[i],1,i,1,1);
 }
 gtk_widget_show_all(d);begin_job(6);gtk_dialog_run(GTK_DIALOG(d));
 for(int i=0;i<7;i++)spec_values[i]=NULL;
 spec_status=NULL;gtk_widget_destroy(d);
}

typedef struct {GtkWidget*parent,*fields[8],*disk;} PresetExportContext;
static void export_preset(void*w,void*p){
 (void)w;PresetExportContext*c=p;char v[CONFIG_COUNT][512];
 for(int i=0;i<CONFIG_COUNT;i++)safe_copy(v[i],512,cfg[i]);
 for(int i=0;i<8;i++)safe_copy(v[i],512,gtk_entry_get_text(GTK_ENTRY(c->fields[i])));
 safe_copy(v[10],512,gtk_entry_get_text(GTK_ENTRY(c->disk)));
 if(!now_preset_values_valid(v)){
  preset_alert(c->parent,"Preset not saved","Check server, relay, URL, and wake script fields. Presets cannot contain URL passwords or tokens.");return;
 }
 char path[PATH_MAX];if(!preset_pick(path,sizeof path,c->parent,1))return;
 if(now_preset_write(path,v,keys))preset_alert(c->parent,"Preset saved","Share this file only with devices you trust. Pair each device separately.");
 else preset_alert(c->parent,"Preset not saved","Could not write preset file.");
}
/* Full trusted-device backup. Passphrase never appears in process arguments. */
#define BACKUP_BINARY "/usr/lib/optiplex-now/optiplex-now-backup"
static int backup_pick(char*out,size_t n,void*parent,int save){
 GtkWidget*d=gtk_file_chooser_dialog_new(save?"Export Full Backup":"Restore Full Backup",GTK_WINDOW(parent),save?1:0,
  "CANCEL",GTK_RESPONSE_CANCEL,save?"SAVE":"OPEN",GTK_RESPONSE_OK,NULL);
 const char*home=getenv("HOME");
 if(home&&*home)gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(d),home);
 if(save){
  gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(d),"My-OptiPlex-full.onb");
  gtk_file_chooser_set_do_overwrite_confirmation(GTK_FILE_CHOOSER(d),1);
 }
 int ok=0;
 if(gtk_dialog_run(GTK_DIALOG(d))==GTK_RESPONSE_OK){char*path=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(d));if(path){safe_copy(out,n,path);ok=1;g_free(path);}}
 gtk_widget_destroy(d);return ok;
}
static int backup_password(void*parent,int restore,char*out,size_t n){
 GtkWidget*d=gtk_dialog_new_with_buttons(restore?"Unlock Backup":"Encrypt Backup",GTK_WINDOW(parent),1,
                                      "CANCEL",GTK_RESPONSE_CANCEL,restore?"RESTORE":"ENCRYPT",GTK_RESPONSE_OK,NULL);
 GtkWidget*box=gtk_dialog_get_content_area(GTK_DIALOG(d));GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,10);
 gtk_container_set_border_width(GTK_CONTAINER(col),18);add(box,col,0);
 GtkWidget*note=label(restore?"Your SSH key and Moonlight pairing may be replaced. Use only on a trusted PC.":
   "Contains SSH credentials and Moonlight pairing. Keep this file private.","helper");
 gtk_label_set_line_wrap(GTK_LABEL(note),1);add(col,note,0);
 GtkWidget*password=gtk_entry_new();gtk_entry_set_visibility(GTK_ENTRY(password),0);
 gtk_entry_set_placeholder_text(GTK_ENTRY(password),"Backup password (12+ characters)");add(col,password,0);
 GtkWidget*again=NULL;
 if(!restore){again=gtk_entry_new();gtk_entry_set_visibility(GTK_ENTRY(again),0);
  gtk_entry_set_placeholder_text(GTK_ENTRY(again),"Confirm password");add(col,again,0);}
 gtk_widget_show_all(d);int ok=0;
 if(gtk_dialog_run(GTK_DIALOG(d))==GTK_RESPONSE_OK){
  const char*pass=gtk_entry_get_text(GTK_ENTRY(password));
  const char*confirm=again?gtk_entry_get_text(GTK_ENTRY(again)):pass;
  size_t z=strlen(pass);
  if(z>=12&&z<n&&!strcmp(pass,confirm)){memcpy(out,pass,z+1);ok=1;}
  else preset_alert(d,"Invalid password","Use at least 12 characters. Both passwords must match.");
 }
 gtk_widget_destroy(d);return ok;
}
/* Restore must finish without interruption. The existing archive helper replaces
 * identity files individually, so forced cancellation could leave partial state.
 * Run it asynchronously under an uncloseable modal progress dialog instead. */
typedef struct {
    GtkWidget *dialog;
    gboolean completed;
    gboolean success;
    GError *error;
} BackupProgress;

static gboolean backup_progress_ignore_close(GtkWidget *widget,
                                               GdkEvent *event, gpointer data)
{
    (void)widget;
    (void)event;
    (void)data;
    return TRUE;
}

static void backup_progress_finished(GObject *source, GAsyncResult *result,
                                      gpointer data)
{
    (void)source;
    BackupProgress *progress = data;
    progress->success = now_backup_run_finish(result, &progress->error);
    progress->completed = TRUE;
    if (progress->dialog) {
        gtk_dialog_response(GTK_DIALOG(progress->dialog), GTK_RESPONSE_ACCEPT);
    } else {
        g_clear_error(&progress->error);
        g_free(progress);
    }
}

static int backup_progress_run(void *parent, int restore, const char *path,
                               const char *password)
{
    GtkWidget *dialog = gtk_dialog_new_with_buttons(
        restore ? "Restoring encrypted backup" : "Saving encrypted backup",
        GTK_WINDOW(parent), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        NULL);
    gtk_window_set_deletable(GTK_WINDOW(dialog), FALSE);
    g_signal_connect(dialog, "delete-event",
                     G_CALLBACK(backup_progress_ignore_close), NULL);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget *col = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_container_set_border_width(GTK_CONTAINER(col), 18);
    GtkWidget *spinner = gtk_spinner_new();
    GtkWidget *message = gtk_label_new(
        restore ? "Restoring settings and device identity. Do not close NOW." :
                  "Encrypting device settings and pairing identity. Do not close NOW.");
    gtk_label_set_line_wrap(GTK_LABEL(message), TRUE);
    gtk_container_add(GTK_CONTAINER(area), col);
    add(col, spinner, 0);
    add(col, message, 1);

    BackupProgress *progress = g_new0(BackupProgress, 1);
    progress->dialog = dialog;
    gtk_widget_show_all(dialog);
    gtk_spinner_start(GTK_SPINNER(spinner));
    now_backup_run_async(BACKUP_BINARY, restore, path, password,
                         backup_progress_finished, progress);
    gtk_dialog_run(GTK_DIALOG(dialog));
    /* Parent destruction can dismiss the dialog without completing the job.
     * Keep the state alive for its completion callback in that unusual case. */
    progress->dialog = NULL;
    gtk_widget_destroy(dialog);
    if (!progress->completed)
        return -1;
    int rc = progress->success ? 0 :
        (g_error_matches(progress->error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND) ?
         -2 : -1);
    g_clear_error(&progress->error);
    g_free(progress);
    return rc;
}

static int full_backup_ui(void*parent,int restore){
 if(restore){
  GtkWidget*d=gtk_dialog_new_with_buttons("Confirm Restore",GTK_WINDOW(parent),1,"CANCEL",GTK_RESPONSE_CANCEL,"CONTINUE",GTK_RESPONSE_OK,NULL);
  GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));
  GtkWidget*n=label("Restore may replace SSH keys, Moonlight settings and OptiPlex preferences.\nOnly restore on a computer you own and trust.","helper");
  gtk_label_set_line_wrap(GTK_LABEL(n),1);gtk_container_set_border_width(GTK_CONTAINER(area),16);add(area,n,0);
  gtk_widget_show_all(d);int result=gtk_dialog_run(GTK_DIALOG(d));gtk_widget_destroy(d);if(result!=GTK_RESPONSE_OK)return 0;
 }
 char path[PATH_MAX];if(!backup_pick(path,sizeof path,parent,!restore))return 0;
 char pw[2048]={0};if(!backup_password(parent,restore,pw,sizeof pw))return 0;
 /* Passphrase is duplicated only for the subprocess stdin and wiped here. */
 int rc=backup_progress_run(parent,restore,path,pw);explicit_bzero(pw,sizeof pw);
 if(rc==0){
  if(restore){now_config_load();last_columns=-1;GtkAllocation dimensions={0};gtk_widget_get_allocation(win,&dimensions);reflow(dimensions.width>0?dimensions.width:660);tray_build_menu();refresh();preset_alert(parent,"Backup restored","Settings restored. Restart Moonlight to load its pairing data. Tailscale still requires sign-in on this device.");}
  else preset_alert(parent,"Backup saved","Encrypted backup saved. Keep your password safe and only restore on a trusted computer.");
 }else preset_alert(parent,"Backup failed",rc==-2?"Backup helper is missing. Reinstall OptiPlex Now.":
       "Backup failed. Check file, password, and permissions. No settings were intentionally reset.");
 return rc==0;
}
static void export_full_backup(void*w,void*p){(void)w;full_backup_ui(p?p:win,0);}
static void restore_full_backup(void*w,void*p){(void)w;void*parent=p?p:win;if(full_backup_ui(parent,1) && p)gtk_dialog_response(GTK_DIALOG(parent),GTK_RESPONSE_CANCEL);}
static void settings_open_page(GtkWidget *button,gpointer unused){
 (void)unused;
 GtkStack *stack=GTK_STACK(g_object_get_data(G_OBJECT(button),"settings-stack"));
 const char *page=g_object_get_data(G_OBJECT(button),"settings-page");
 if(stack&&page)gtk_stack_set_visible_child_name(stack,page);
}
static GtkWidget *settings_page(GtkWidget *stack,const char *name){
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);
 gtk_container_set_border_width(GTK_CONTAINER(content),14);
 gtk_container_add(GTK_CONTAINER(scroll),content);
 gtk_stack_add_named(GTK_STACK(stack),scroll,name);
 return content;
}
static void settings_link(GtkWidget *container,GtkWidget *stack,const char *caption,const char *page){
 GtkWidget *b=button(caption,"setupaction");
 g_object_set_data(G_OBJECT(b),"settings-stack",stack);
 g_object_set_data(G_OBJECT(b),"settings-page",(gpointer)page);
 g_signal_connect(b,"clicked",G_CALLBACK(settings_open_page),NULL);
 add(container,b,0);
}
/* XFCE-style list ordering: move the existing row, preserving its checkboxes. */
static void tray_order_move(GtkWidget *button,gpointer direction_ptr){
 GtkWidget *row=gtk_widget_get_ancestor(button,GTK_TYPE_LIST_BOX_ROW);
 if(!row)return;
 GtkListBox *list=GTK_LIST_BOX(gtk_widget_get_parent(row));
 int from=gtk_list_box_row_get_index(GTK_LIST_BOX_ROW(row));
 int delta=GPOINTER_TO_INT(direction_ptr);
 int to=from+delta;
 if(to<0 || to>=8)return;
 g_object_ref(row);
 gtk_container_remove(GTK_CONTAINER(list),row);
 gtk_list_box_insert(list,row,to);
 g_object_unref(row);
 gtk_widget_show_all(GTK_WIDGET(list));
}
static void on_settings(void*w,void*p){(void)w;(void)p;
 GtkWidget*d=gtk_dialog_new_with_buttons("OptiPlex Now | Settings",GTK_WINDOW(win),1,"CANCEL",GTK_RESPONSE_CANCEL,"SAVE",GTK_RESPONSE_OK,NULL);
 /* A single resizable dialog with internal navigation; suitable for 1024x768. */
 gtk_window_set_default_size(GTK_WINDOW(d),680,550);
 GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));
 GtkWidget*stack=gtk_stack_new();
 gtk_stack_set_transition_type(GTK_STACK(stack),GTK_STACK_TRANSITION_TYPE_SLIDE_LEFT_RIGHT);
 gtk_widget_set_vexpand(stack,TRUE);
 add(area,stack,1);
 GtkWidget*home=settings_page(stack,"home");
 settings_link(home,stack,"GAMING & STREAMING  ›","gaming");
 settings_link(home,stack,"APPEARANCE & TRAY  ›","preferences");
 
 add(home,label("SETUP & MAINTENANCE","modalheading"),0);
 settings_link(home,stack,"CONNECTIONS & SERVER  ›","connection");
 GtkWidget*connection=settings_page(stack,"connection");
 GtkWidget*gaming=settings_page(stack,"gaming");
 GtkWidget*preferences=settings_page(stack,"preferences");
 GtkWidget*pages[]={connection,gaming,preferences};
 for(int k=0;k<3;k++)settings_link(pages[k],stack,"‹ BACK TO SETTINGS","home");
 GtkWidget*col=connection;
 add(col,label("CONNECTION","modalheading"),0);
 GtkWidget*guided=button("SETUP WIZARD","setupaction");g_signal_connect_data(guided,"clicked",(GCallback)on_wizard,NULL,NULL,0);add(col,guided,0);
 add(col,label("HOST SETUP (READ-ONLY)","modalheading"),0);
 GtkWidget*host_review=button("CHECK THIS PC FOR SERVER SETUP","setupaction");
 g_signal_connect(host_review,"clicked",G_CALLBACK(on_server_readiness),NULL);
 add(col,host_review,0);
 add(col,label("Checks hardware and installation blockers. Does not install or restart services.","helper"),0);
 tailscale_label=label("CHECKING TAILSCALE","helper");add(col,tailscale_label,0);
 GtkWidget*gt=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(gt),10);gtk_grid_set_row_spacing(GTK_GRID(gt),7);add(col,gt,0);
 GtkWidget*advanced_grid=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(advanced_grid),10);gtk_grid_set_row_spacing(GTK_GRID(advanced_grid),7);
 GtkWidget*advanced=gtk_expander_new("ADVANCED SETTINGS");gtk_container_add(GTK_CONTAINER(advanced),advanced_grid);
 const char*names[]={"Server IP","SSH user","Wake relay IP","Relay SSH user","Wake command","Videos URL","Music URL","Downloads URL"};
 GtkWidget*fields[8];
 for(int i=0;i<8;i++){
  GtkWidget*l=label(names[i],NULL);gtk_widget_set_size_request(l,110,-1);
  GtkWidget*dest=(i<2||i>=5)?gt:advanced_grid;int row=i<2?i:i>=5?i-3:i-2;
  gtk_grid_attach(GTK_GRID(dest),l,0,row,1,1);
  fields[i]=gtk_entry_new();gtk_entry_set_text(GTK_ENTRY(fields[i]),cfg[i]);gtk_widget_set_hexpand(fields[i],1);gtk_grid_attach(GTK_GRID(dest),fields[i],1,row,1,1);
 }
 GtkWidget*disklabel=label("Downloads disk",NULL);
 GtkWidget*diskentry=gtk_entry_new();gtk_entry_set_text(GTK_ENTRY(diskentry),cfg[10]);gtk_widget_set_hexpand(diskentry,1);
 gtk_grid_attach(GTK_GRID(advanced_grid),disklabel,0,7,1,1);gtk_grid_attach(GTK_GRID(advanced_grid),diskentry,1,7,1,1);
 GtkWidget*combo=gtk_combo_box_text_new();const char*opts[]={"Default browser (automatic)","System default","Chrome Flatpak","Chrome native"};
 for(int i=0;i<4;i++)gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo),opts[i]);
 int which=!strcmp(cfg[8],"system")?1:!strcmp(cfg[8],"chrome-flatpak")?2:!strcmp(cfg[8],"chrome")?3:0;
 gtk_combo_box_set_active(GTK_COMBO_BOX(combo),which);
 gtk_grid_attach(GTK_GRID(advanced_grid),label("Browser",NULL),0,6,1,1);
 gtk_grid_attach(GTK_GRID(advanced_grid),combo,1,6,1,1);
 GtkWidget*actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 GtkWidget*t=button("TAILSCALE","setupaction");g_signal_connect_data(t,"clicked",(GCallback)on_tail,NULL,NULL,0);add(actions,t,1);
 PairContext server_context={.relay=0},relay_context={.relay=1};
 for(int i=0;i<8;i++){server_context.inputs[i]=fields[i];relay_context.inputs[i]=fields[i];}
 server_context.parent=d;relay_context.parent=d;
 GtkWidget*s=button("PAIR SERVER","setupaction");g_signal_connect_data(s,"clicked",(GCallback)on_pair_click,&server_context,NULL,0);add(actions,s,1);
 GtkWidget*r=button("PAIR RELAY","setupaction");g_signal_connect_data(r,"clicked",(GCallback)on_pair_click,&relay_context,NULL,0);add(actions,r,1);
 add(col,actions,0);
 col=gaming;
 add(col,label("STREAMING","modalheading"),0);
 GtkWidget*games=button("STREAMING SETUP (MOONLIGHT + WOLF)","setupaction");
 g_signal_connect_data(games,"clicked",(GCallback)on_games_setup_from_settings,&server_context,NULL,0);add(col,games,0);
 add(col,label("WEB GAMING URL (OPTIONAL)","helper"),0);
 GtkWidget*web_url_entry=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(web_url_entry),"https://your-streaming-host.example");
 gtk_entry_set_text(GTK_ENTRY(web_url_entry),cfg[16]);add(col,web_url_entry,0);
 GtkWidget*websettings=button("WEB GAMING SETTINGS","setupaction");
 g_signal_connect_data(websettings,"clicked",(GCallback)on_web_gaming_settings,NULL,NULL,0);add(col,websettings,0);
 GtkWidget*webadmin=button("WEB GAMING ADMIN","setupaction");
 g_signal_connect_data(webadmin,"clicked",(GCallback)on_web_gaming_admin,NULL,NULL,0);add(col,webadmin,0);
 col=preferences;
 add(col,label("DESKTOP SHORTCUT NAME","modalheading"),0);
 add(col,label("Caption after Desktop | in tray. Does not rename Wolf itself.","helper"),0);
 char desktop_label[128];now_tray_desktop_caption(desktop_label,sizeof desktop_label);
 GtkWidget*desktop_caption_entry=gtk_entry_new();
 gtk_entry_set_max_length(GTK_ENTRY(desktop_caption_entry),48);
 gtk_entry_set_text(GTK_ENTRY(desktop_caption_entry),desktop_label);
 add(col,desktop_caption_entry,0);
 add(col,label("SHORTCUTS","modalheading"),0);
 add(col,label("Featured services appear above; the rest stay in Additional Services. Tray is independent.","helper"),0);
 GtkWidget*featured_checks[8],*tray_checks[8];
 GtkWidget*order_list=gtk_list_box_new();
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(order_list),GTK_SELECTION_NONE);
 gtk_widget_set_name(order_list,"trayorder");
 int current_order[8];now_tray_order_load(current_order);
 GtkWidget*headers=gtk_grid_new();
 gtk_grid_set_column_spacing(GTK_GRID(headers),12);
 const char*head_names[]={"SERVICE","PRIMARY","TRAY","MOVE"};
 int widths[]={128,72,52,84};
 for(int h=0;h<4;h++){
  GtkWidget*heading=label(head_names[h],"storagehead");
  gtk_widget_set_size_request(heading,widths[h],-1);
  gtk_label_set_xalign(GTK_LABEL(heading),h==0?0.0f:0.5f);
  gtk_grid_attach(GTK_GRID(headers),heading,h,0,1,1);
 }
 add(col,headers,0);

 unsigned fm=featured_mask(),tm=tray_button_mask();
 for(int n=0;n<8;n++){
   int i=current_order[n];
   GtkWidget*row=gtk_list_box_row_new();
   g_object_set_data(G_OBJECT(row),"service-id",GINT_TO_POINTER(i+1));
   GtkWidget*line=gtk_grid_new();
   gtk_grid_set_column_spacing(GTK_GRID(line),12);
   gtk_container_add(GTK_CONTAINER(row),line);
   GtkWidget*name=label(now_tray_service_name(i),NULL);
   gtk_widget_set_size_request(name,128,-1);
   gtk_label_set_xalign(GTK_LABEL(name),0);
   gtk_grid_attach(GTK_GRID(line),name,0,0,1,1);
   featured_checks[i]=gtk_check_button_new();
   tray_checks[i]=gtk_check_button_new();
   gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(featured_checks[i]),(fm&(1u<<i))!=0);
   gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(tray_checks[i]),(tm&(1u<<i))!=0);
   GtkWidget*primary_box=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,0);
   GtkWidget*tray_box=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,0);
   gtk_widget_set_size_request(primary_box,72,-1);
   gtk_widget_set_size_request(tray_box,52,-1);
   gtk_box_pack_start(GTK_BOX(primary_box),featured_checks[i],TRUE,FALSE,0);
   gtk_box_pack_start(GTK_BOX(tray_box),tray_checks[i],TRUE,FALSE,0);
   gtk_grid_attach(GTK_GRID(line),primary_box,1,0,1,1);
   gtk_grid_attach(GTK_GRID(line),tray_box,2,0,1,1);
   GtkWidget*arrows=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,3);
   gtk_widget_set_size_request(arrows,84,-1);
   gtk_box_set_homogeneous(GTK_BOX(arrows),TRUE);
   GtkWidget*up=button("↑","setting"),*down=button("↓","setting");
   g_signal_connect(up,"clicked",G_CALLBACK(tray_order_move),GINT_TO_POINTER(-1));
   g_signal_connect(down,"clicked",G_CALLBACK(tray_order_move),GINT_TO_POINTER(1));
   add(arrows,up,0);add(arrows,down,0);
   gtk_grid_attach(GTK_GRID(line),arrows,3,0,1,1);
   gtk_list_box_insert(GTK_LIST_BOX(order_list),row,-1);
 }
 add(col,order_list,0);
 col=connection;
 add(col,label("UPDATES & MAINTENANCE","modalheading"),0);
 GtkWidget*webmaint=button("WEB GAMING MAINTENANCE","setupaction");
 g_signal_connect_data(webmaint,"clicked",(GCallback)on_web_gaming_maintenance,NULL,NULL,0);add(col,webmaint,0);
 add(col,advanced,0);
 PresetExportContext export_context={.parent=d,.disk=diskentry};
 for(int i=0;i<8;i++)export_context.fields[i]=fields[i];
 GtkWidget*export_btn=button("EXPORT MY OPTIPLEX","setupaction");
 g_signal_connect_data(export_btn,"clicked",(GCallback)export_preset,&export_context,NULL,0);add(col,export_btn,0);
  GtkWidget*full_export=button("EXPORT FULL BACKUP","setupaction");
 g_signal_connect_data(full_export,"clicked",(GCallback)export_full_backup,d,NULL,0);add(col,full_export,0);
 GtkWidget*full_import=button("RESTORE FULL BACKUP","setupaction");
 g_signal_connect_data(full_import,"clicked",(GCallback)restore_full_backup,d,NULL,0);add(col,full_import,0);

 GtkWidget*hint=label("Preset has addresses, never passwords or SSH keys.","helper");add(col,hint,0);
 gtk_widget_show_all(d);
 gtk_stack_set_visible_child_name(GTK_STACK(stack),"home");
 int resp=gtk_dialog_run(GTK_DIALOG(d));
 if(resp==GTK_RESPONSE_OK){
   for(int i=0;i<8;i++){const char*v=gtk_entry_get_text(GTK_ENTRY(fields[i]));if(strchr(v,'\n')||strchr(v,'\r'))continue;safe_copy(cfg[i],512,v);}
   const char*browsers[]={"auto","system","chrome-flatpak","chrome"};int choice=gtk_combo_box_get_active(GTK_COMBO_BOX(combo));
   const char*disk=gtk_entry_get_text(GTK_ENTRY(diskentry));
   if(now_host_safe_disk_path(disk)) safe_copy(cfg[10],512,disk);
   safe_copy(cfg[8],512,browsers[choice>=0&&choice<4?choice:0]);
        unsigned selected=0,featured=0;
    for(int i=0;i<8;i++){
      if(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(tray_checks[i])))selected|=1u<<i;
      if(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(featured_checks[i])))featured|=1u<<i;
    }
    snprintf(cfg[TRAY_MASK_SETTING],512,"%u",selected);
    snprintf(cfg[FEATURED_MASK_SETTING],512,"%u",featured);
    const char*new_caption=gtk_entry_get_text(GTK_ENTRY(desktop_caption_entry));
    if(*new_caption && !strchr(new_caption,'\n') && !strchr(new_caption,'\r'))
      now_tray_desktop_caption_save(new_caption);
    int ordered[8];
    for(int n=0;n<8;n++){
      GtkListBoxRow*row=gtk_list_box_get_row_at_index(GTK_LIST_BOX(order_list),n);
      ordered[n]=row?GPOINTER_TO_INT(g_object_get_data(G_OBJECT(row),"service-id"))-1:n;
    }
    now_tray_order_save(ordered);
    const char*web_url=gtk_entry_get_text(GTK_ENTRY(web_url_entry));
    if(now_safe_preset_url(web_url))safe_copy(cfg[16],512,web_url);
    else say("INVALID WEB GAMING URL; PREVIOUS VALUE RETAINED");
    config_save();/* Never destroy the activating tray menu from its own callback. */
    g_timeout_add(200,tray_rebuild_after_settings,NULL);
    last_columns=-1;GtkAllocation dimensions={0};gtk_widget_get_allocation(win,&dimensions);
    reflow(dimensions.width>0?dimensions.width:660);
    say("SETTINGS SAVED");refresh();
 }
 tailscale_label=NULL;gtk_widget_destroy(d);
}
/* Setup assistant. Client pairing is explicit and uses the user's own credentials. */
typedef struct {
    GtkWidget *assistant, *server_page, *games_page, *services_page, *finish_page;
    GtkWidget *host, *user, *relay, *relayuser, *wake;
    GtkWidget *ts_state, *game_state, *wolf_state, *notice, *preset_notice;
    GtkWidget *find_button, *tailscale_button, *service_check_button;
    GtkWidget *service_inputs[3], *service_labels[3];
    char checked_urls[NOW_SERVICE_PROBE_COUNT][NOW_SERVICE_PROBE_URL_MAX];
    char staged[CONFIG_COUNT][512];
    int preset_loaded, closing, references;
    guint tailscale_poll_id;
    NowWizardNetwork *network;
    NowServiceProbe *service_probe;
} Wizard;

static void wizard_unref(Wizard *wizard)
{
    if (--wizard->references == 0) {
        free(wizard);
    }
}
static void wizard_validate(void*w,void*p){
 (void)w;Wizard*c=p;
 int ok=now_valid_host(gtk_entry_get_text(GTK_ENTRY(c->host)))&&now_valid_user(gtk_entry_get_text(GTK_ENTRY(c->user)));
 gtk_assistant_set_page_complete(GTK_ASSISTANT(c->assistant),c->server_page,ok);
 gtk_label_set_text(GTK_LABEL(c->notice),"");
}
static void wizard_save(Wizard*c){
 const char*values[]={gtk_entry_get_text(GTK_ENTRY(c->host)),gtk_entry_get_text(GTK_ENTRY(c->user)),
                      gtk_entry_get_text(GTK_ENTRY(c->relay)),gtk_entry_get_text(GTK_ENTRY(c->relayuser)),gtk_entry_get_text(GTK_ENTRY(c->wake))};
 int server_valid=now_valid_host(values[0])&&now_valid_user(values[1]);
 for(int i=0;i<5;i++){
   if(strchr(values[i],'\n')||strchr(values[i],'\r'))server_valid=0;
 }
 if(server_valid){
   for(int i=0;i<5;i++)safe_copy(cfg[i],512,values[i]);
   if(c->preset_loaded){
     safe_copy(cfg[10],512,c->staged[10]);
     safe_copy(cfg[14],512,c->staged[14]);
     safe_copy(cfg[16],512,c->staged[16]);
   }
 }

 /* Media URLs must survive leaving Services even if server/SSH identity is
  * incomplete. An invalid optional service must not block valid ones. */
 const char *urls[3];
 for(int i=0;i<3;i++){
   urls[i]=c->service_inputs[i]?
      gtk_entry_get_text(GTK_ENTRY(c->service_inputs[i])):NULL;
 }
 unsigned invalid_urls=now_wizard_store_services(cfg,urls);
 if(!config_save()){
   gtk_label_set_text(GTK_LABEL(c->notice),"UNABLE TO SAVE SETTINGS");
   say("SETTINGS COULD NOT BE SAVED");
 }else if(invalid_urls){
   for(int i=0;i<3;i++)if((invalid_urls&(1u<<i))&&c->service_labels[i]){
     gtk_label_set_text(GTK_LABEL(c->service_labels[i]),"INVALID URL. PREVIOUS VALUE RETAINED");
   }
   gtk_label_set_text(GTK_LABEL(c->notice),"VALID SERVICE URLS SAVED. INVALID URLS RETAINED");
   say("INVALID SERVICE URL. OTHER URLS SAVED");
 }else if(!server_valid){
   gtk_label_set_text(GTK_LABEL(c->notice),"SERVICE URLS SAVED. SERVER DETAILS INCOMPLETE");
 }else{
   gtk_label_set_text(GTK_LABEL(c->notice),"SAVED");
 }
}
static void wizard_network_result(gpointer context, NowWizardNetworkKind kind,
                                  const char *reply, const GError *error);

static gboolean wizard_tailscale_poll(gpointer data)
{
    Wizard *wizard = data;
    if (!wizard->assistant || wizard->closing ||
        !gtk_widget_get_visible(wizard->assistant)) {
        return G_SOURCE_CONTINUE;
    }
    if (tailscale_install_inflight) {
        gtk_label_set_text(GTK_LABEL(wizard->ts_state),
                           "INSTALLING TAILSCALE — APPROVE THE SYSTEM PASSWORD PROMPT");
        return G_SOURCE_CONTINUE;
    }
    if (!now_wizard_network_busy(wizard->network, NOW_WIZARD_NET_STATUS)) {
        now_wizard_network_start(
            wizard->network, NOW_WIZARD_NET_STATUS,
            "/usr/lib/optiplex-now/tailscale-status.py");
    }
    return G_SOURCE_CONTINUE;
}
static void wizard_service_check(void*w,void*p);
static void wizard_prepare(void*a,void*page,void*p){
 (void)a;Wizard*c=p;
 /* Moving past Services is an explicit Continue action. Commit the entered
  * URLs now, even if the user closes the final summary without clicking Apply. */
 if(page==c->finish_page)wizard_save(c);
 wizard_tailscale_poll(c);
 if(c->game_state)gtk_label_set_text(GTK_LABEL(c->game_state),moonlight_mode_name());
 if(page==c->services_page)wizard_service_check(NULL,c);
 if(page==c->games_page){
   if(c->wolf_state)gtk_label_set_text(GTK_LABEL(c->wolf_state),"CHECKING WOLF CONNECTION...");
   /* Use the address entered in the wizard without saving partial settings. */
   safe_copy(wolf_probe_host,sizeof wolf_probe_host,gtk_entry_get_text(GTK_ENTRY(c->host)));
   /* The server may stream even if its pairing page is unavailable; do not block setup. */
   begin_job(8);
 }
}
static void picker_selection_changed(void *combo,void *accept){
 gtk_widget_set_sensitive(accept,gtk_combo_box_get_active(GTK_COMBO_BOX(combo))>=0);
}
static void wizard_network_result(gpointer context, NowWizardNetworkKind kind,
                                  const char *reply, const GError *error)
{
    Wizard *wizard = context;
    /* Nested GTK dialogs may destroy the assistant. Keep Wizard valid
     * until this handler returns, independently from the network job. */
    wizard->references++;
    if (wizard->closing || !wizard->assistant) {
        wizard_unref(wizard);
        return;
    }
    if (kind == NOW_WIZARD_NET_STATUS) {
        const char *message = "TAILSCALE STATUS UNAVAILABLE — CHECK CONNECTION";
        const char *action = "CONNECT TAILSCALE";
        if (error && g_error_matches(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT)) {
            message = "TAILSCALE CHECK TIMED OUT — RETRY CONNECTION";
        } else if (!error && reply) {
            char *status = g_strstrip(g_strdup(reply));
            if (g_strcmp0(status, "CONNECTED") == 0) {
                message = "TAILSCALE CONNECTED — CONTINUE TO SERVER";
                action = "TAILSCALE CONNECTED";
            } else if (g_strcmp0(status, "NOT_INSTALLED") == 0) {
                message = "TAILSCALE NOT INSTALLED — INSTALL TO CONTINUE";
                action = "INSTALL TAILSCALE";
            } else if (g_strcmp0(status, "SIGN_IN") == 0) {
                message = "TAILSCALE NEEDS SIGN-IN — CONNECT TAILSCALE";
            } else if (g_strcmp0(status, "NOT_CONNECTED") == 0) {
                message = "TAILSCALE DISCONNECTED — CONNECT TAILSCALE";
            }
            g_free(status);
        }
        gtk_label_set_text(GTK_LABEL(wizard->ts_state), message);
        gtk_button_set_label(GTK_BUTTON(wizard->tailscale_button), action);
        wizard_unref(wizard);
        return;
    }
    if (kind != NOW_WIZARD_NET_DISCOVERY) {
        wizard_unref(wizard);
        return;
    }

    gtk_widget_set_sensitive(wizard->find_button, TRUE);
    int current_page = gtk_assistant_get_current_page(GTK_ASSISTANT(wizard->assistant));
    GtkWidget *current = gtk_assistant_get_nth_page(
        GTK_ASSISTANT(wizard->assistant), current_page);
    if (current != wizard->server_page) {
        wizard_unref(wizard);
        return;
    }

    NowTailscaleServer servers[NOW_TAILSCALE_MAX_SERVERS] = {0};
    int count = (!error && reply)
        ? now_tailscale_parse_servers(reply, servers, NOW_TAILSCALE_MAX_SERVERS)
        : -1;
    if (count <= 0) {
        const char *message = count == 0
            ? "NO OTHER DEVICES FOUND — ENTER SERVER ADDRESS MANUALLY"
            : (error && g_error_matches(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT))
                ? "SERVER SEARCH TIMED OUT — RETRY OR ENTER ADDRESS"
                : "COULD NOT LIST DEVICES — CHECK TAILSCALE OR ENTER ADDRESS";
        gtk_label_set_text(GTK_LABEL(wizard->notice), message);
        wizard_unref(wizard);
        return;
    }
    gtk_label_set_text(GTK_LABEL(wizard->notice), "SELECT THE INTENDED HOST");

    GtkWidget *dialog = gtk_dialog_new_with_buttons(
        "Choose your server", GTK_WINDOW(wizard->assistant), GTK_DIALOG_MODAL,
        "Cancel", GTK_RESPONSE_CANCEL, NULL);
    GtkWidget *accept = gtk_dialog_add_button(GTK_DIALOG(dialog),
                                              "Use this device", GTK_RESPONSE_OK);
    gtk_widget_set_sensitive(accept, FALSE);
    GtkWidget *area = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(area), 18);
    GtkWidget *column = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    add(area, column, 0);
    GtkWidget *hint = label("Select the computer running your server.\n"
        "Being on Tailscale does not authorize SSH or Wolf.", "helper");
    gtk_label_set_line_wrap(GTK_LABEL(hint), TRUE);
    add(column, hint, 0);
    GtkWidget *combo = gtk_combo_box_text_new();
    add(column, combo, 0);
    for (int i = 0; i < count; i++) {
        gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo), servers[i].label);
    }
    g_signal_connect_data(combo, "changed",
                          (GCallback)picker_selection_changed, accept, NULL, 0);
    gtk_widget_show_all(dialog);
    int response = gtk_dialog_run(GTK_DIALOG(dialog));
    int selected = gtk_combo_box_get_active(GTK_COMBO_BOX(combo));
    if (response == GTK_RESPONSE_OK && selected >= 0 && selected < count &&
        wizard->assistant && !wizard->closing) {
        gtk_entry_set_text(GTK_ENTRY(wizard->host), servers[selected].address);
        gtk_label_set_text(GTK_LABEL(wizard->notice),
            "ADDRESS FILLED. CONFIRM THE SSH USER, THEN CONTINUE.");
    }
    gtk_widget_destroy(dialog);
    wizard_unref(wizard);
}

static void find_server(Wizard *wizard)
{
    if (wizard->closing || !wizard->assistant ||
        now_wizard_network_busy(wizard->network, NOW_WIZARD_NET_DISCOVERY)) {
        return;
    }
    gtk_widget_set_sensitive(wizard->find_button, FALSE);
    gtk_label_set_text(GTK_LABEL(wizard->notice), "FINDING TAILSCALE DEVICES...");
    if (!now_wizard_network_start(
        wizard->network, NOW_WIZARD_NET_DISCOVERY,
        "/usr/lib/optiplex-now/find-servers.py")) {
        gtk_widget_set_sensitive(wizard->find_button, TRUE);
        gtk_label_set_text(GTK_LABEL(wizard->notice), "SERVER SEARCH FAILED TO START");
    }
}
static void wizard_action(void*w,void*p){
 Wizard*c=p;
 const char*n=gtk_widget_get_name(w);if(!n)n="";
 if(!strcmp(n,"w_keep")){gtk_widget_destroy(c->assistant);return;}
 else if(!strcmp(n,"w_restore")){if(full_backup_ui(c->assistant,1))gtk_widget_destroy(c->assistant);return;}
 if(!strcmp(n,"w_import")){
    char path[PATH_MAX];if(!preset_pick(path,sizeof path,c->assistant,0))return;
    char v[CONFIG_COUNT][512];
    for(int i=0;i<CONFIG_COUNT;i++)safe_copy(v[i],512,c->staged[i]);
    if(!now_preset_read(path,v,keys)){
       gtk_label_set_text(GTK_LABEL(c->preset_notice),"INVALID PRESET. NO CHANGES MADE.");return;
    }
    for(int i=0;i<CONFIG_COUNT;i++)safe_copy(c->staged[i],512,v[i]);
    c->preset_loaded=1;
    gtk_entry_set_text(GTK_ENTRY(c->host),v[0]);gtk_entry_set_text(GTK_ENTRY(c->user),v[1]);
    gtk_entry_set_text(GTK_ENTRY(c->relay),v[2]);gtk_entry_set_text(GTK_ENTRY(c->relayuser),v[3]);gtk_entry_set_text(GTK_ENTRY(c->wake),v[4]);
    for(int i=0;i<3;i++){
       gtk_entry_set_text(GTK_ENTRY(c->service_inputs[i]),v[5+i]);
       if(c->service_labels[i])gtk_label_set_text(GTK_LABEL(c->service_labels[i]),*v[5+i]?"READY TO CHECK":"NOT CONFIGURED");
    }
    gtk_label_set_text(GTK_LABEL(c->preset_notice),"PRESET LOADED. SERVICES WILL BE CHECKED AUTOMATICALLY.");
    return;
 }
 if(!strcmp(n,"w_pair")||!strcmp(n,"w_relay")||!strcmp(n,"w_wolf")||!strcmp(n,"w_wolfpin"))wizard_save(c);
 if(!strcmp(n,"w_find"))find_server(c);
 else if(!strcmp(n,"w_ts"))setup_tailscale();
 else if(!strcmp(n,"w_ts_signup"))browser_open("https://login.tailscale.com/start");
 else if(!strcmp(n,"w_pair"))pair(0);
 else if(!strcmp(n,"w_relay"))pair(1);
 else if(!strcmp(n,"w_moonlight")){if(has_moonlight())open_moonlight();else install_moonlight();}
 else if(!strcmp(n,"w_appimage"))choose_appimage();
 else if(!strcmp(n,"w_wolf"))pair_wolf(w);
 else if(!strcmp(n,"w_wolfpin"))begin_job(5);
 else if(!strcmp(n,"w_future")){
   GtkWidget*d=gtk_dialog_new_with_buttons("New Server",GTK_WINDOW(c->assistant),1,"CLOSE",GTK_RESPONSE_CANCEL,NULL);
   GtkWidget*area=gtk_dialog_get_content_area(GTK_DIALOG(d));GtkWidget*box=gtk_box_new(GTK_ORIENTATION_VERTICAL,10);
   gtk_container_set_border_width(GTK_CONTAINER(box),20);add(area,box,0);
   add(box,label("NEW SERVER SETUP","modalheading"),0);
   GtkWidget*l=label("Automated server provisioning is not included yet.\nFor now, install Tailscale and SSH on the new server,\nthen use this wizard to connect.","helper");
   gtk_label_set_line_wrap(GTK_LABEL(l),1);add(box,l,0);
   gtk_widget_show_all(d);gtk_dialog_run(GTK_DIALOG(d));gtk_widget_destroy(d);
 }
 if(c->game_state)gtk_label_set_text(GTK_LABEL(c->game_state),moonlight_mode_name());
}
static GtkWidget*wizard_button(Wizard*c,GtkWidget*page,const char*title,const char*id){
 GtkWidget*b=button(title,"setupaction");gtk_widget_set_name(b,id);gtk_style_context_add_class(GTK_STYLE_CONTEXT(gtk_widget_get_style_context(b)),"setupaction");
 g_signal_connect_data(b,"clicked",(GCallback)wizard_action,c,NULL,0);add(page,b,0);return b;
}
static gboolean destroy_wizard_idle(void*w){gtk_widget_destroy(w);return 0;}
static void wizard_end(void*w,void*p){Wizard*c=p;if(c->closing)return;c->closing=1;wizard_save(c);refresh();g_idle_add(destroy_wizard_idle,w);}
static void wizard_cancel(void*w,void*p){Wizard*c=p;if(c->closing)return;c->closing=1;g_idle_add(destroy_wizard_idle,w);}
static void wizard_service_result(
    gpointer context, const NowServiceProbeEntry entries[NOW_SERVICE_PROBE_COUNT],
    const GError *error)
{
    Wizard *wizard = context;
    wizard->references++;
    if (!wizard->closing && wizard->assistant) {
        for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; ++index) {
            const char *current = gtk_entry_get_text(
                GTK_ENTRY(wizard->service_inputs[index]));
            const char *state = "UNREACHABLE";
            if (strcmp(current, wizard->checked_urls[index]) != 0) {
                state = "URL CHANGED — CHECK AGAIN";
            } else if (error) {
                state = g_error_matches(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT)
                    ? "TIMED OUT — RETRY" : "CHECK FAILED — RETRY";
            } else if (entries) {
                state = entries[index].state;
            }
            gtk_label_set_text(GTK_LABEL(wizard->service_labels[index]), state);
        }
        gtk_widget_set_sensitive(wizard->service_check_button, TRUE);
    }
    wizard_unref(wizard);
}

static void wizard_service_check(void *widget, void *data)
{
    (void)widget;
    Wizard *wizard = data;
    if (wizard->closing || !wizard->assistant ||
        now_service_probe_busy(wizard->service_probe)) {
        return;
    }
    const char *urls[NOW_SERVICE_PROBE_COUNT];
    for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; ++index) {
        urls[index] = gtk_entry_get_text(GTK_ENTRY(wizard->service_inputs[index]));
        if (!now_safe_preset_url(urls[index])) {
            gtk_label_set_text(GTK_LABEL(wizard->service_labels[index]),
                               "INVALID URL — CORRECT TO CHECK");
            return;
        }
    }
    for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; ++index) {
        safe_copy(wizard->checked_urls[index],
                  sizeof wizard->checked_urls[index], urls[index]);
        gtk_label_set_text(GTK_LABEL(wizard->service_labels[index]), "CHECKING...");
    }
    gtk_widget_set_sensitive(wizard->service_check_button, FALSE);
    if (!now_service_probe_start(wizard->service_probe, urls)) {
        gtk_widget_set_sensitive(wizard->service_check_button, TRUE);
        for (int index = 0; index < NOW_SERVICE_PROBE_COUNT; ++index) {
            gtk_label_set_text(GTK_LABEL(wizard->service_labels[index]),
                               "COULD NOT START CHECK — RETRY");
        }
    }
}
static void wizard_destroy(void *widget, void *data)
{
    if (active_setup_wizard == widget) {
        active_setup_wizard = NULL;
    }
    Wizard *wizard = data;
    wizard->closing = 1;
    wizard->assistant = NULL;
    if (wizard->tailscale_poll_id) {
        g_source_remove(wizard->tailscale_poll_id);
        wizard->tailscale_poll_id = 0;
    }
    now_wizard_network_close(wizard->network);
    wizard->network = NULL;
    now_service_probe_close(wizard->service_probe);
    wizard->service_probe = NULL;
    wizard_wolf_label = NULL;
    wizard_unref(wizard);
}
static void on_wizard(void*w,void*p){(void)w;(void)p;
 if (active_setup_wizard) {
     gtk_window_present(GTK_WINDOW(active_setup_wizard));
     return;
 }
 Wizard*c=calloc(1,sizeof *c);if(!c)return;
 c->references=1;
 c->network=now_wizard_network_new(wizard_network_result,c,9000);
 if(!c->network){free(c);return;}
 c->service_probe=now_service_probe_new(wizard_service_result,c,16000);
 if(!c->service_probe){now_wizard_network_close(c->network);free(c);return;}
 for(int i=0;i<CONFIG_COUNT;i++)safe_copy(c->staged[i],512,cfg[i]);
 GtkWidget*a=gtk_assistant_new();c->assistant=a;
 active_setup_wizard=a;
 gtk_window_set_title(GTK_WINDOW(a),"OptiPlex Now | Setup");gtk_window_set_default_size(GTK_WINDOW(a),710,480);
 gtk_window_set_transient_for(GTK_WINDOW(a),GTK_WINDOW(win));gtk_window_set_modal(GTK_WINDOW(a),1);
 /* Page 1: keep existing device setup. No credentials or pairings are reset. */
 GtkWidget*one=gtk_box_new(GTK_ORIENTATION_VERTICAL,14);gtk_container_set_border_width(GTK_CONTAINER(one),24);
 add(one,label("CONNECT THIS DEVICE","modalheading"),0);
 c->ts_state=label("CHECKING TAILSCALE","gameshint");add(one,c->ts_state,0);
 c->tailscale_button=wizard_button(c,one,"CONNECT TAILSCALE","w_ts");
 wizard_button(c,one,"NEW TO TAILSCALE? CREATE ACCOUNT ↗","w_ts_signup");
 add(one,label("Connection status updates automatically after sign-in.","helper"),0);
 wizard_button(c,one,"IMPORT MY OPTIPLEX","w_import");
 wizard_button(c,one,"RESTORE FULL BACKUP (TRUSTED PC)","w_restore");
 c->preset_notice=label("","helper");add(one,c->preset_notice,0);
 if(!first_run&&*cfg[0]){
    add(one,label("EXISTING CONNECTION FOUND","helper"),0);
    wizard_button(c,one,"KEEP EXISTING SETUP","w_keep");
 }
 c->tailscale_poll_id=g_timeout_add_seconds(5,wizard_tailscale_poll,c);
 gtk_assistant_append_page(GTK_ASSISTANT(a),one);gtk_assistant_set_page_title(GTK_ASSISTANT(a),one,"TAILSCALE");gtk_assistant_set_page_type(GTK_ASSISTANT(a),one,1);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),one,1);
 /* Page 2: choose your server. All values are prefilled from saved configuration. */
 GtkWidget*two=gtk_box_new(GTK_ORIENTATION_VERTICAL,13);c->server_page=two;gtk_container_set_border_width(GTK_CONTAINER(two),24);
 add(two,label("FIND YOUR SERVER","modalheading"),0);
 c->find_button=wizard_button(c,two,"FIND SERVER ON TAILSCALE","w_find");
 add(two,label("SERVER ADDRESS — CHOOSE ABOVE OR ENTER MANUALLY","helper"),0);
 c->host=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(c->host),"Tailscale IP or hostname");gtk_entry_set_text(GTK_ENTRY(c->host),cfg[0]);add(two,c->host,0);
 add(two,label("SSH USER","helper"),0);
 c->user=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(c->user),"SSH username");gtk_entry_set_text(GTK_ENTRY(c->user),cfg[1]);add(two,c->user,0);
 g_signal_connect_data(c->host,"changed",(GCallback)wizard_validate,c,NULL,0);
 g_signal_connect_data(c->user,"changed",(GCallback)wizard_validate,c,NULL,0);
 c->notice=label("","helper");add(two,c->notice,0);
 wizard_button(c,two,"NEW SERVER SETUP (PLANNED)","w_future");
 gtk_assistant_append_page(GTK_ASSISTANT(a),two);gtk_assistant_set_page_title(GTK_ASSISTANT(a),two,"SERVER");gtk_assistant_set_page_type(GTK_ASSISTANT(a),two,0);wizard_validate(NULL,c);
 /* Page 3: pair SSH keys once. Relay is optional. */
 GtkWidget*three=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);gtk_container_set_border_width(GTK_CONTAINER(three),22);
 add(three,label("SECURE ACCESS","modalheading"),0);
 add(three,label("Existing SSH keys are reused.","helper"),0);
 wizard_button(c,three,"AUTHORIZE SSH KEY","w_pair");
 GtkWidget*wake_options=gtk_expander_new("WAKE OPTIONS (OPTIONAL)");
 GtkWidget*wake_fields=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);
 gtk_container_set_border_width(GTK_CONTAINER(wake_fields),12);
 gtk_container_add(GTK_CONTAINER(wake_options),wake_fields);
 add(three,wake_options,0);
 c->relay=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(c->relay),"Relay Tailscale IP");gtk_entry_set_text(GTK_ENTRY(c->relay),cfg[2]);add(wake_fields,c->relay,0);
 c->relayuser=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(c->relayuser),"Relay SSH user");gtk_entry_set_text(GTK_ENTRY(c->relayuser),cfg[3]);add(wake_fields,c->relayuser,0);
 c->wake=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(c->wake),"Wake script on relay");gtk_entry_set_text(GTK_ENTRY(c->wake),cfg[4]);add(wake_fields,c->wake,0);
 wizard_button(c,wake_fields,"AUTHORIZE RELAY KEY","w_relay");
 gtk_assistant_append_page(GTK_ASSISTANT(a),three);gtk_assistant_set_page_title(GTK_ASSISTANT(a),three,"ACCESS");gtk_assistant_set_page_type(GTK_ASSISTANT(a),three,0);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),three,1);
 /* Page 4: reuse the existing installed Moonlight, including AppImages. */
 GtkWidget*four=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);gtk_container_set_border_width(GTK_CONTAINER(four),24);
 add(four,label("CONNECT TO GAME HOST","modalheading"),0);
 add(four,label("Connect once during setup, then play from Games.","helper"),0);
 c->game_state=label(moonlight_mode_name(),"gameshint");add(four,c->game_state,0);
 c->wolf_state=label("CHECKING WOLF...","gameshint");wizard_wolf_label=c->wolf_state;add(four,c->wolf_state,0);
 c->games_page=four;
 wizard_button(c,four,"OPEN / INSTALL MOONLIGHT","w_moonlight");
 wizard_button(c,four,"SELECT APPIMAGE","w_appimage");
 wizard_button(c,four,"CONNECT TO GAME HOST","w_wolf");
 wizard_button(c,four,"ADVANCED PAIRING HELP","w_wolfpin");
 gtk_assistant_append_page(GTK_ASSISTANT(a),four);gtk_assistant_set_page_title(GTK_ASSISTANT(a),four,"GAMES");gtk_assistant_set_page_type(GTK_ASSISTANT(a),four,0);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),four,1);
 /* Page 5: let a fresh installation actually configure each service.
  * Do not claim the server's Wolf stream is missing merely because a URL
  * wasn't configured locally. */
 GtkWidget*five=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);c->services_page=five;gtk_container_set_border_width(GTK_CONTAINER(five),20);
 add(five,label("SERVICES","modalheading"),0);
 add(five,label("Addresses from your preset are checked automatically.","helper"),0);
 const char*names[]={"VIDEOS URL","MUSIC URL","DOWNLOADS URL"};
 GtkWidget*rows=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(rows),9);gtk_grid_set_row_spacing(GTK_GRID(rows),11);add(five,rows,0);
 for(int i=0;i<3;i++){
   gtk_grid_attach(GTK_GRID(rows),label(names[i],"specname"),0,i,1,1);
   c->service_inputs[i]=gtk_entry_new();gtk_widget_set_hexpand(c->service_inputs[i],1);
   gtk_entry_set_text(GTK_ENTRY(c->service_inputs[i]),c->staged[i+5]);
   gtk_grid_attach(GTK_GRID(rows),c->service_inputs[i],1,i,1,1);
   c->service_labels[i]=label(*c->staged[i+5]?"NOT CHECKED":"ADD URL","specvalue");
   gtk_grid_attach(GTK_GRID(rows),c->service_labels[i],2,i,1,1);
 }
 c->service_check_button=button("CHECK SERVICES","setupaction");g_signal_connect_data(c->service_check_button,"clicked",(GCallback)wizard_service_check,c,NULL,0);add(five,c->service_check_button,0);
 gtk_assistant_append_page(GTK_ASSISTANT(a),five);gtk_assistant_set_page_title(GTK_ASSISTANT(a),five,"SERVICES");gtk_assistant_set_page_type(GTK_ASSISTANT(a),five,0);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),five,1);
 /* Page 6: nothing else needed for existing clients. */
 GtkWidget*six=gtk_box_new(GTK_ORIENTATION_VERTICAL,15);c->finish_page=six;gtk_container_set_border_width(GTK_CONTAINER(six),24);
 add(six,label("READY","modalheading"),0);
 add(six,label("Saved settings carry over between updates.","helper"),0);
 add(six,label("Open System Info from the dashboard for live hardware details.","helper"),0);
 gtk_assistant_append_page(GTK_ASSISTANT(a),six);gtk_assistant_set_page_title(GTK_ASSISTANT(a),six,"FINISH");gtk_assistant_set_page_type(GTK_ASSISTANT(a),six,2);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),six,1);
 g_signal_connect_data(a,"prepare",(GCallback)wizard_prepare,c,NULL,0);
 g_signal_connect_data(a,"apply",(GCallback)wizard_end,c,NULL,0);
 g_signal_connect_data(a,"cancel",(GCallback)wizard_cancel,c,NULL,0);
 g_signal_connect_data(a,"close",(GCallback)wizard_end,c,NULL,0);
 g_signal_connect_data(a,"destroy",(GCallback)wizard_destroy,c,NULL,0);
 gtk_widget_show_all(a);
 wizard_tailscale_poll(c);
}
static gboolean first_setup(void*unused) { on_wizard(NULL,unused);return 0; }

static void fonts_register(void) {
 char path[PATH_MAX],file[PATH_MAX];const char *home=getenv("HOME");if(!home)home="/tmp";
 const char *cache=getenv("XDG_CACHE_HOME");
 if(cache&&*cache)snprintf(path,sizeof path,"%s",cache);
 else snprintf(path,sizeof path,"%s/.cache",home);
 mkdir_safe(path);strncat(path,"/optiplex-desk",sizeof path-strlen(path)-1);mkdir_safe(path);
 const unsigned char *beg[]={_binary_inter_ttf_start,_binary_limelight_ttf_start};
 const unsigned char *end[]={_binary_inter_ttf_end,_binary_limelight_ttf_end};
 const char *names[]={"Inter-Variable.ttf","Limelight-Regular.ttf"};
 for(int i=0;i<2;i++){
   snprintf(file,sizeof file,"%s/%s",path,names[i]);size_t len=(size_t)(end[i]-beg[i]);
   struct stat st;if(stat(file,&st)!=0||(size_t)st.st_size!=len){
     FILE*f=fopen(file,"wb");if(f){fwrite(beg[i],1,len,f);fclose(f);chmod(file,0600);}}
   FcConfigAppFontAddFile(FcConfigGetCurrent(),(const unsigned char*)file);
 }
 FcConfigBuildFonts(FcConfigGetCurrent());
}
static void tray_quit(void *w,void *data){
 (void)w;(void)data;
 if(tray_icon)gtk_status_icon_set_visible(GTK_STATUS_ICON(tray_icon),0);
 if(app_indicator && app_indicator_set_status_fn)app_indicator_set_status_fn(app_indicator,0);
 gtk_main_quit();
}
static void tray_toggle(void *icon,void *data){
 (void)icon;(void)data;
 if(gtk_widget_get_visible(win))gtk_widget_hide(win);
 else tray_show_window();
}
static void tray_dispatch_show(void *context)
{
    (void)context;
    tray_show_window();
}

static void tray_dispatch_settings(void *context)
{
    (void)context;
    on_settings(NULL, NULL);
}

static void tray_dispatch_system_info(void *context)
{
    (void)context;
    on_system_info(NULL, NULL);
}

static void tray_dispatch_quit(void *context)
{
    (void)context;
    tray_quit(NULL, NULL);
}

static void tray_dispatch_restart(void *context)
{
    (void)context;
    on_restart_streaming(NULL, NULL);
}

static void tray_dispatch_service(void *context, int index)
{
    (void)context;
    on_tile(NULL, (void *)(long)index);
}

static int tray_dispatch_moonlight_available(void *context)
{
    (void)context;
    return has_moonlight();
}

static void tray_action(void *widget, void *data)
{
    (void)widget;
    static const NowTrayActions handlers = {
        .show_window = tray_dispatch_show,
        .open_settings = tray_dispatch_settings,
        .open_system_info = tray_dispatch_system_info,
        .quit = tray_dispatch_quit,
        .restart_streaming = tray_dispatch_restart,
        .launch_service = tray_dispatch_service,
        .moonlight_available = tray_dispatch_moonlight_available
    };
    (void)now_tray_dispatch_action(GPOINTER_TO_INT(data), &handlers, NULL);
}
static void tray_menu_item(const char*caption,int action){
 GtkWidget *item=gtk_menu_item_new_with_label(caption);
 g_signal_connect_data(item,"activate",(GCallback)tray_action,(void*)(long)action,NULL,0);
 gtk_menu_shell_append(GTK_MENU_SHELL(tray_menu),item);
}
static void tray_separator(void){
 GtkWidget*item=gtk_separator_menu_item_new();gtk_menu_shell_append(GTK_MENU_SHELL(tray_menu),item);
}
static void tray_popup(void *icon,guint button,guint when,void *data){
 (void)data;
 gtk_menu_popup(GTK_MENU(tray_menu),NULL,NULL,(void*)gtk_status_icon_position_menu,icon,button,when);
}
static void tray_build_menu(void){
 GtkWidget*old=tray_menu;
 tray_menu=gtk_menu_new();
 tray_menu_item("Open OptiPlex Now",NOW_TRAY_OPEN_WINDOW);
 unsigned mask=tray_button_mask();
 if(mask){
  tray_separator();
  char desktop[128];
  now_tray_desktop_caption(desktop, sizeof desktop);
  int order[NOW_TRAY_ACTIONS];
  now_tray_order_load(order);
  for (int position = 0; position < NOW_TRAY_ACTIONS; ++position) {
      int action = order[position];
      if (!(mask & (1u << action))) {
          continue;
      }
      /* Standard menu items work with GTK and AppIndicator/DBusMenu. */
      char caption[256];
      if (!now_tray_service_caption(action, desktop, caption, sizeof caption)) {
          continue;
      }
      GtkWidget *item = gtk_menu_item_new_with_label(caption);
      g_signal_connect_data(item, "activate", (GCallback)tray_action,
                            (void *)(long)action, NULL, 0);
      gtk_menu_shell_append(GTK_MENU_SHELL(tray_menu), item);
  }
 }
 tray_separator();
 tray_menu_item("Restart streaming service…",NOW_TRAY_RESTART_STREAMING);
 tray_separator();
 tray_menu_item("System Info",NOW_TRAY_OPEN_SYSTEM_INFO);
 tray_menu_item("Settings",NOW_TRAY_OPEN_SETTINGS);
 tray_separator();tray_menu_item("Quit",NOW_TRAY_QUIT);
 gtk_widget_show_all(tray_menu);
 if(app_indicator && app_indicator_set_menu_fn)app_indicator_set_menu_fn(app_indicator,tray_menu);
 if(old)gtk_widget_destroy(old);
}
static void tray_initialize(void){
 tray_build_menu();
 /* Only publish an SNI icon when a desktop is actually listening for it. */
 if(status_notifier_watcher_present()){
   indicator_library=dlopen("libayatana-appindicator3.so.1",RTLD_LAZY|RTLD_LOCAL);
   if(!indicator_library)indicator_library=dlopen("libappindicator3.so.1",RTLD_LAZY|RTLD_LOCAL);
   if(indicator_library){
     void*(*new_indicator)(const char*,const char*,int)=dlsym(indicator_library,"app_indicator_new");
     app_indicator_set_status_fn=dlsym(indicator_library,"app_indicator_set_status");
     app_indicator_set_menu_fn=dlsym(indicator_library,"app_indicator_set_menu");
     void (*set_indicator_title)(void*,const char*)=dlsym(indicator_library,"app_indicator_set_title");
     if(new_indicator && app_indicator_set_status_fn && app_indicator_set_menu_fn){
       app_indicator=new_indicator("optiplex-now","optiplex-now-tray",0);
       if(app_indicator){
         if(set_indicator_title)set_indicator_title(app_indicator,"OptiPlex Now");
         app_indicator_set_menu_fn(app_indicator,tray_menu);
         app_indicator_set_status_fn(app_indicator,1); /* ACTIVE */
         using_status_notifier=1;
         tray_available=1;
         return;
       }
     }
     dlclose(indicator_library);
     indicator_library=NULL;
   }
 }
 /* XFCE Notification Area and desktops without an SNI host. */
 tray_icon=gtk_status_icon_new_from_icon_name("optiplex-now-tray");
 gtk_status_icon_set_tooltip_text(GTK_STATUS_ICON(tray_icon),"OptiPlex Now");
 g_signal_connect_data(tray_icon,"activate",(GCallback)tray_toggle,NULL,NULL,0);
 g_signal_connect_data(tray_icon,"popup-menu",(GCallback)tray_popup,NULL,NULL,0);
 gtk_status_icon_set_visible(GTK_STATUS_ICON(tray_icon),1);
}

static gboolean initial_tray_check(void *unused){
 (void)unused;
 /* Show the window rather than leave an unreachable background process. */
 if(!can_minimize_to_tray())tray_show_window();
 return 0;
}
int main(int argc,char**argv) {
 int start_in_tray=0;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--start-in-tray")){
   start_in_tray=1;
   for(int j=i;j<argc-1;j++)argv[j]=argv[j+1];
   argc--;i--;
  }
 }
 int instance_result=claim_instance();
 if(instance_result<=0)return instance_result==0?0:1;
 fonts_register();gtk_init(&argc,&argv);gtk_window_set_default_icon_name("optiplex-now");now_config_load();
 GtkCssProvider*cp=gtk_css_provider_new();gtk_css_provider_load_from_data(GTK_CSS_PROVIDER(cp),CSS,-1,NULL);
 gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),GTK_STYLE_PROVIDER(cp),GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
 /* Give the dashboard enough height for server controls on normal displays.
   Bound it to the monitor's usable area so older laptops and projectors can
   still access everything through the existing scrolled container. */
  int initial_width = 900;
  int initial_height = 620;
  GdkDisplay *display = gdk_display_get_default();
  if (display) {
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    if (!monitor && gdk_display_get_n_monitors(display) > 0) {
      monitor = gdk_display_get_monitor(display, 0);
    }
    if (monitor) {
      GdkRectangle workarea;
      gdk_monitor_get_workarea(monitor, &workarea);
      /* Preserve the roomy ultrawide desktop layout tested by CI.
       * Prefer a smaller normal window on 1366x768 notebook screens. */
      if (workarea.width >= 1920 && workarea.height >= 900) {
        initial_width = MIN(1100, MAX(400, workarea.width - 96));
        initial_height = MIN(720, MAX(340, workarea.height - 120));
      } else {
        initial_width = MIN(900, MAX(400, workarea.width - 96));
        initial_height = MIN(620, MAX(340, workarea.height - 120));
      }
    }
  }
  win=gtk_window_new(GTK_WINDOW_TOPLEVEL);
  gtk_window_set_title(GTK_WINDOW(win),"OptiPlex Now");
  gtk_window_set_default_size(GTK_WINDOW(win),initial_width,initial_height);
  gtk_window_set_resizable(GTK_WINDOW(win),TRUE);
 gtk_window_set_icon_name(GTK_WINDOW(win),"optiplex-now");gtk_window_set_position(GTK_WINDOW(win),1);
 g_signal_connect_data(win,"destroy",(GCallback)on_window_destroy,NULL,NULL,0);
 g_signal_connect_data(win,"delete-event",(GCallback)close_to_tray,NULL,NULL,0);
 g_signal_connect_data(win,"window-state-event",(GCallback)minimize_to_tray,NULL,NULL,0);
 g_signal_connect_data(win,"size-allocate",(GCallback)on_size,NULL,NULL,0);
 GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(sc),GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);
 /* The stack's wider pages must scroll, not set an enormous window minimum. */
 gtk_scrolled_window_set_min_content_width(GTK_SCROLLED_WINDOW(sc),320);
 gtk_scrolled_window_set_min_content_height(GTK_SCROLLED_WINDOW(sc),280);
 gtk_container_add(GTK_CONTAINER(win),sc);
 GtkWidget*main_pages=gtk_stack_new();
 gtk_stack_set_transition_type(GTK_STACK(main_pages),GTK_STACK_TRANSITION_TYPE_SLIDE_LEFT_RIGHT);
 gtk_container_add(GTK_CONTAINER(sc),main_pages);
 GtkWidget*shell=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(shell,"shell");
 gtk_stack_add_named(GTK_STACK(main_pages),shell,"dashboard");
 GtkWidget*body=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);gtk_container_set_border_width(GTK_CONTAINER(body),14);add(shell,body,1);
 GtkWidget*head=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,15);add(body,head,0);
 GtkWidget*brandcol=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_hexpand(brandcol,1);add(head,brandcol,1);
 model_heading=label(current_model(),"title");
 gtk_label_set_ellipsize(GTK_LABEL(model_heading),3);
 gtk_label_set_max_width_chars(GTK_LABEL(model_heading),22);
 add(brandcol,model_heading,0);
 GtkWidget*right=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);gtk_widget_set_valign(right,GTK_ALIGN_CENTER);add(head,right,0);
 GtkWidget*tools=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);add(right,tools,0);
 indicator=label("● CHECKING","state");add(tools,indicator,0);
 GtkWidget*sys=button("SYSTEM INFO","setting");g_signal_connect_data(sys,"clicked",(GCallback)on_system_info,NULL,NULL,0);add(tools,sys,0);
 GtkWidget*sett=button("SETTINGS","setting");g_signal_connect_data(sett,"clicked",(GCallback)on_settings,NULL,NULL,0);add(tools,sett,0);
 status_detail=label("","detail");add(right,status_detail,0);
 GtkWidget*rule=gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);gtk_widget_set_name(rule,"rule");gtk_widget_set_size_request(rule,-1,1);add(body,rule,0);
 GtkWidget*metrics=gtk_grid_new();gtk_grid_set_column_homogeneous(GTK_GRID(metrics),1);gtk_grid_set_column_spacing(GTK_GRID(metrics),8);add(body,metrics,0);
 metric_cpu=label("CPU   --","metric");metric_gpu=label("GPU   --","metric");
 gtk_grid_attach(GTK_GRID(metrics),metric_cpu,0,0,1,1);gtk_grid_attach(GTK_GRID(metrics),metric_gpu,1,0,1,1);
  metric_ram=label("RAM   --","metric");metric_vram=label("VRAM   --","metric");
  gtk_grid_attach(GTK_GRID(metrics),metric_ram,0,1,1,1);gtk_grid_attach(GTK_GRID(metrics),metric_vram,1,1,1,1);
 GtkWidget*diskbox=gtk_box_new(GTK_ORIENTATION_VERTICAL,3);gtk_widget_set_name(diskbox,"drivemetric");
 GtkWidget*diskhead=label("STORAGE","storagehead");add(diskbox,diskhead,0);
 drive_combo=gtk_combo_box_text_new();gtk_widget_set_name(drive_combo,"drivecombo");gtk_widget_set_hexpand(drive_combo,1);
 gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(drive_combo),"Checking drives...");gtk_combo_box_set_active(GTK_COMBO_BOX(drive_combo),0);
 g_signal_connect_data(drive_combo,"changed",(GCallback)on_drive_changed,NULL,NULL,0);add(diskbox,drive_combo,0);
 metric_free=label("FREE  --","drivefree");add(diskbox,metric_free,0);
 gtk_grid_attach(GTK_GRID(metrics),diskbox,2,0,1,2);
  metric_network=label("TAILSCALE  --","statusmetric");add(body,metric_network,0);
  metric_vpn=label("VPN  --","statusmetric");add(body,metric_vpn,0);
  metric_wolf=label("WOLF SERVICE  --","statusmetric");add(body,metric_wolf,0);
  metric_wolf_sessions=label("WOLF DESKTOPS  --","statusmetric");add(body,metric_wolf_sessions,0);
 /* The dashboard prioritizes host state. Launchers live on Software page. */
 GtkWidget*software=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);
 GtkWidget*software_scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(software_scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_container_add(GTK_CONTAINER(software_scroll),software);
 gtk_stack_add_named(GTK_STACK(main_pages),software_scroll,"software");
 settings_link(tools,main_pages,"SOFTWARE","software");
 settings_link(software,main_pages,"‹ DASHBOARD","dashboard");
 add(software,label("SOFTWARE","section"),0);
 grid=gtk_grid_new();gtk_grid_set_column_homogeneous(GTK_GRID(grid),1);gtk_grid_set_row_spacing(GTK_GRID(grid),7);gtk_grid_set_column_spacing(GTK_GRID(grid),7);
 gtk_widget_set_hexpand(grid,1);add(software,grid,0);
 GtkWidget*extras=gtk_expander_new("ADDITIONAL SERVICES");add(software,extras,0);
 extras_grid=gtk_grid_new();gtk_grid_set_column_homogeneous(GTK_GRID(extras_grid),1);
 gtk_grid_set_row_spacing(GTK_GRID(extras_grid),7);gtk_grid_set_column_spacing(GTK_GRID(extras_grid),7);
 gtk_widget_set_hexpand(extras_grid,1);gtk_container_add(GTK_CONTAINER(extras),extras_grid);
 const char *names[]={"GAMES","VIDEOS","MUSIC","FILES","DOWNLOADS","TERMINAL","DESKTOP","WEB GAMING"};
 for(int i=0;i<8;i++){tiles[i]=button(names[i],"tile");g_signal_connect_data(tiles[i],"clicked",(GCallback)on_tile,(void*)(long)i,NULL,0);}
 GtkWidget*sec=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);add(sec,label("SERVER POWER","section"),1);add(body,sec,0);
 power_grid=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(power_grid),7);gtk_grid_set_row_spacing(GTK_GRID(power_grid),7);
 gtk_grid_set_column_homogeneous(GTK_GRID(power_grid),1);add(body,power_grid,0);
 const char*pow_names[]={"WAKE","SLEEP","RESTART","SHUTDOWN"};
 for(int i=0;i<4;i++){powers[i]=button(pow_names[i],i==3?"danger":"power");g_signal_connect_data(powers[i],"clicked",(GCallback)on_power,(void*)(long)i,NULL,0);}
 footer=label("","footer");add(body,footer,0);
 reflow(initial_width);
 /* Initialize the tray before showing the window to avoid login flicker. */
 tray_initialize();
 if(!start_in_tray || first_run)gtk_widget_show_all(win);
 else g_timeout_add(1800,initial_tray_check,NULL);
 g_timeout_add(300,reopen_check,NULL);
 g_timeout_add(15000,periodic,NULL);refresh();
 if(first_run)g_idle_add(first_setup,NULL); /* first run setup */
 gtk_main();return 0;
}
