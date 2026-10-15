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
#include <pthread.h>
#include <limits.h>
#include <dirent.h>
#include <dlfcn.h>
#include <netdb.h>
#include <sys/socket.h>
#include <poll.h>

/* GTK 3 ABI declarations. The build uses installed runtime libraries only. */
typedef void GtkWidget;
typedef void GtkStyleContext;
typedef void GtkCssProvider;
typedef void* gpointer;
typedef int gboolean;
typedef unsigned int guint;
typedef int gint;
typedef unsigned long gulong;
typedef void (*GCallback)(void);
extern void gtk_init(int*,char***);
extern void gtk_main(void);
extern void gtk_main_quit(void);
extern void gtk_widget_hide(void*);
extern gboolean gtk_widget_get_visible(void*);
extern void gtk_window_present(void*);
extern void gtk_window_deiconify(void*);
/* Use StatusNotifierItem via Ayatana AppIndicator when the desktop exposes
 * a watcher. Fall back to the XEmbed-compatible GTK3 status icon otherwise.
 * The pinned XFCE panel launcher is separate from the notification area. */
extern void* gtk_status_icon_new_from_icon_name(const char*);
extern void gtk_status_icon_set_tooltip_text(void*,const char*);
extern void gtk_status_icon_set_visible(void*,gboolean);
extern gboolean gtk_status_icon_is_embedded(void*);
extern void gtk_status_icon_position_menu(void*,int*,int*,gboolean*,void*);
extern GtkWidget* gtk_menu_new(void);
extern GtkWidget* gtk_menu_item_new_with_label(const char*);
extern GtkWidget* gtk_separator_menu_item_new(void);
extern void gtk_menu_shell_append(void*,void*);
extern void gtk_menu_popup(void*,void*,void*,void*,void*,guint,guint);
extern GtkWidget* gtk_window_new(int);
extern void gtk_window_set_title(void*,const char*);
extern gboolean gtk_show_uri_on_window(void*,const char*,guint,void**);
extern void gtk_window_set_default_size(void*,int,int);
extern void gtk_window_set_icon_name(void*,const char*);
extern void gtk_window_set_default_icon_name(const char*);
extern void gtk_window_set_position(void*,int);
extern void gtk_window_set_resizable(void*,gboolean);
extern GtkWidget* gtk_box_new(int,int);
extern GtkWidget* gtk_separator_new(int);
extern GtkWidget* gtk_grid_new(void);
extern GtkWidget* gtk_scrolled_window_new(void*,void*);
extern void gtk_scrolled_window_set_policy(void*,int,int);
extern void gtk_container_add(void*,void*);
extern void gtk_container_set_border_width(void*,guint);
extern void gtk_box_pack_start(void*,void*,gboolean,gboolean,guint);
extern void gtk_box_pack_end(void*,void*,gboolean,gboolean,guint);
extern void gtk_box_reorder_child(void*,void*,gint);
extern void gtk_grid_attach(void*,void*,gint,gint,gint,gint);
extern void gtk_grid_set_row_spacing(void*,guint);
extern void gtk_grid_set_column_spacing(void*,guint);
extern void gtk_grid_set_column_homogeneous(void*,gboolean);
extern GtkWidget* gtk_label_new(const char*);
extern void gtk_label_set_text(void*,const char*);
extern void gtk_label_set_markup(void*,const char*);
extern void gtk_label_set_xalign(void*,float);
extern void gtk_label_set_line_wrap(void*,gboolean);
extern void gtk_label_set_ellipsize(void*,int);
extern GtkWidget* gtk_button_new_with_label(const char*);
extern void gtk_button_set_relief(void*,int);
extern void gtk_widget_set_name(void*,const char*);
extern void gtk_widget_set_size_request(void*,int,int);
extern void gtk_widget_set_hexpand(void*,gboolean);
extern void gtk_widget_set_vexpand(void*,gboolean);
extern void gtk_widget_set_halign(void*,int);
extern void gtk_widget_set_valign(void*,int);
extern void gtk_widget_set_sensitive(void*,gboolean);
extern void gtk_widget_set_margin_top(void*,int);
extern void gtk_widget_set_margin_bottom(void*,int);
extern void gtk_widget_set_margin_start(void*,int);
extern void gtk_widget_set_margin_end(void*,int);
extern void gtk_widget_show_all(void*);
extern void gtk_widget_destroy(void*);
extern GtkStyleContext* gtk_widget_get_style_context(void*);
extern void gtk_style_context_add_class(void*,const char*);
extern GtkCssProvider* gtk_css_provider_new(void);
extern void gtk_css_provider_load_from_data(void*,const char*,long,void**);
extern void gtk_style_context_add_provider_for_screen(void*,void*,guint);
extern void* gdk_screen_get_default(void);
extern gulong g_signal_connect_data(void*,const char*,GCallback,void*,void*,int);
extern guint g_timeout_add(guint,gboolean(*)(void*),void*);
extern guint g_idle_add(gboolean(*)(void*),void*);
extern GtkWidget* gtk_dialog_new_with_buttons(const char*,void*,int,const char*,int,...);
extern GtkWidget* gtk_dialog_get_content_area(void*);
extern GtkWidget* gtk_dialog_add_button(void*,const char*,gint);
extern gint gtk_dialog_run(void*);
extern GtkWidget* gtk_entry_new(void);
extern void gtk_entry_set_text(void*,const char*);
extern void gtk_entry_set_visibility(void*,gboolean);
extern const char* gtk_entry_get_text(void*);
extern void gtk_entry_set_placeholder_text(void*,const char*);
extern GtkWidget* gtk_assistant_new(void);
extern int gtk_assistant_append_page(void*,void*);
extern void gtk_assistant_set_page_title(void*,void*,const char*);
extern void gtk_assistant_set_page_type(void*,void*,int);
extern void gtk_assistant_set_page_complete(void*,void*,gboolean);
extern void gtk_window_set_transient_for(void*,void*);
extern void gtk_window_set_modal(void*,gboolean);
extern void gtk_button_set_label(void*,const char*);
extern void gtk_combo_box_text_remove_all(void*);
extern GtkWidget* gtk_expander_new(const char*);
extern GtkWidget* gtk_combo_box_text_new(void);
extern void gtk_combo_box_text_append_text(void*,const char*);
extern void gtk_combo_box_set_active(void*,gint);
extern gint gtk_combo_box_get_active(void*);
extern void gtk_widget_get_allocation(void*,void*);
extern GtkWidget* gtk_file_chooser_dialog_new(const char*,void*,int,const char*,int,...);
extern char* gtk_file_chooser_get_filename(void*);
extern void g_free(void*);
extern int FcConfigAppFontAddFile(void*,const unsigned char*);
extern void* FcConfigGetCurrent(void);
extern int FcConfigBuildFonts(void*);

extern const unsigned char _binary_inter_ttf_start[], _binary_inter_ttf_end[];
extern const unsigned char _binary_limelight_ttf_start[], _binary_limelight_ttf_end[];

#define RESPONSE_CANCEL -6
#define RESPONSE_OK -5
#define GTK_ORIENTATION_HORIZONTAL 0
#define GTK_ORIENTATION_VERTICAL 1
#define GTK_ALIGN_CENTER 3
#define GTK_STYLE_PROVIDER_PRIORITY_APPLICATION 600
#define BASE ""

static void *tray_icon = NULL;
static void *indicator_library = NULL, *app_indicator = NULL;
static void (*app_indicator_set_status_fn)(void*,int) = NULL;
static void (*app_indicator_set_menu_fn)(void*,void*) = NULL;
static int using_status_notifier = 0;
static int tray_available = 0;

/* Gio's GLib ABI is used only to detect whether a desktop is hosting a
 * StatusNotifierWatcher, avoiding a hidden process with no usable tray. */
extern void *g_bus_get_sync(int,void*,void**);
extern void *g_dbus_connection_call_sync(void*,const char*,const char*,const char*,const char*,void*,const void*,int,int,void*,void**);
extern void *g_variant_new(const char*,...);
extern void g_variant_get(void*,const char*,...);
extern void g_variant_unref(void*);
extern void g_object_unref(void*);
extern void g_error_free(void*);
static int status_notifier_watcher_present(void){
 void*error=NULL;
 void*bus=g_bus_get_sync(2,NULL,&error);
 if(error){g_error_free(error);error=NULL;}
 if(!bus)return 0;
 void*res=g_dbus_connection_call_sync(bus,"org.freedesktop.DBus","/org/freedesktop/DBus",
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
static GtkWidget *metric_cpu,*metric_gpu,*metric_free,*drive_combo;
static GtkWidget *spec_values[7]={0},*spec_status=NULL;
static int specs_inflight=0, services_inflight=0, wolf_inflight=0;
static GtkWidget *wizard_wolf_label=NULL;
static char wolf_probe_host[512];
static GtkWidget *service_labels[3]={NULL,NULL,NULL};
#define MAX_DRIVES 16
/* Mount points reported by the server, not client-side disks. */
typedef struct {char path[256], size[32], free_space[32], used_percent[16];} Drive;
static Drive visible_drives[MAX_DRIVES];
static int visible_drive_count=0,drive_combo_updating=0;
static void on_drive_changed(void*,void*);
static char appimage_found[PATH_MAX];
static void say(const char *s);
static int flatpak_has(const char *id);
static void on_games_setup(void*w,void*p);
static void on_wizard(void*w,void*p);
static GtkWidget *tiles[8],*powers[4];
static int last_columns=0, last_power_columns=0, status_inflight=0, power_inflight=0;
static char config_path[PATH_MAX];
#define CONFIG_COUNT 13
static const char *keys[]={"host","user","relay","relay_user","wake_command","videos","music","downloads","browser","moonlight_appimage","storage_path","model_host","model_name"};
static const char *defaults[]={"","optiplex","","","","","","","system","","/","",""};
static char cfg[CONFIG_COUNT][512];
static int first_run=0;
static const char *current_model(void){
 return *cfg[12] && !strcmp(cfg[11],cfg[0]) ? cfg[12] : "OptiPlex";
}
static void update_model_heading(void){
 if(model_heading)gtk_label_set_text(model_heading,current_model());
}

static const char *CSS =
"* {font-family:'Inter',sans-serif;}"
"window,dialog,assistant,scrolledwindow {background:#101111; color:#ece8e0;}"
"#shell {background:#101111;}"
"#setting {background:#1d201f; border:1px solid #414743;color:#ece8e0;padding:5px 11px;font-size:10px;font-weight:700;min-height:24px;border-radius:2px;}"
"#setting:hover {background:#2a9d8f;color:#101111;border-color:#2a9d8f;}"
"#title {font-family:'Inter',sans-serif;font-size:32px;font-weight:900;letter-spacing:-1.4px;color:#ece8e0;}"
"#state {color:#bcb8af;background:#202523;border:1px solid #515b56;padding:7px 10px;font-size:10px;font-weight:800;letter-spacing:.7px;}"
"#state.online {color:#a1e2d7;border-color:#2a9d8f;} #state.offline {color:#e7aca7;border-color:#986967;} #state.pair {color:#e8ce90;border-color:#9b8354;}"
"#detail {font-size:10px;color:#aaa79e;}"
"#rule {background:#555e58;min-height:1px;}"
"#section {font-weight:800;color:#b8b4ac;font-size:11px;letter-spacing:1px;}"
"#metric {background:#171918;border:1px solid #444b46;color:#ece8e0;padding:8px 9px;font-size:12px;font-weight:700;}"
"#drivemetric {background:#171918;border:1px solid #444b46;padding:8px 10px;}"
"#storagehead {font-size:10px;font-weight:800;color:#b8b4ac;}"
"#drivefree {font-size:11px;font-weight:700;color:#ece8e0;}"
"#drivefree.warn {color:#e7aa82;}"
"#drivecombo button {background:#1e211f;color:#ece8e0;border:1px solid #4d5650;border-radius:2px;padding:3px 7px;min-height:25px;font-size:11px;}"
"#drivecombo button:hover {border-color:#2a9d8f;}"
"#tile {background:#1e211f;color:#ece8e0;border:1px solid #48534d;border-radius:2px;padding:6px 8px;font-weight:800;font-size:12px;min-height:43px;border-bottom:2px solid #2a9d8f;}"
"#tile:hover {background:#2a9d8f;color:#101111;} #tile:active {background:#86bfb5;}"
"#power {background:#171918;color:#ece8e0;border:1px solid #59615c;border-radius:2px;padding:6px 6px;font-weight:800;font-size:10px;min-height:30px;}"
"#power:hover {background:#2a9d8f;color:#101111;}"
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
static void config_location(void) {
 const char *xdg=getenv("XDG_CONFIG_HOME"); char dir[PATH_MAX];
 snprintf(dir,sizeof dir,"%s",(xdg&&*xdg)?xdg:"");
 if (!*dir) snprintf(dir,sizeof dir,"%s/.config",getenv("HOME")?getenv("HOME"):"/tmp");
 mkdir_safe(dir); size_t len=strlen(dir); if(len+30>=sizeof dir)return;
 strcpy(dir+len,"/optiplex-desk");mkdir_safe(dir);
 snprintf(config_path,sizeof config_path,"%s/config.ini",dir);
}
static void config_load(void) {
 config_location();for(int i=0;i<CONFIG_COUNT;i++)safe_copy(cfg[i],512,defaults[i]);
 FILE*f=fopen(config_path,"r");if(!f){first_run=1;return;}
 char line[1024]; while(fgets(line,sizeof line,f)){
   line[strcspn(line,"\r\n")]=0;char *eq=strchr(line,'=');if(!eq)continue;*eq++=0;
   for(int i=0;i<CONFIG_COUNT;i++)if(!strcmp(line,keys[i])) safe_copy(cfg[i],512,eq);
 }fclose(f);
}
static void config_save(void) {
 update_model_heading();
 FILE*f=fopen(config_path,"w");if(!f)return;fchmod(fileno(f),0600);
 for(int i=0;i<CONFIG_COUNT;i++)fprintf(f,"%s=%s\n",keys[i],cfg[i]);fclose(f);
}
static int valid_host(const char*s) {
 if(!s||!*s||strlen(s)>250)return 0;
 for(;*s;s++)if(!(isalnum((unsigned char)*s)||strchr(".-:_",*s)))return 0;return 1;
}
static int valid_user(const char*s) {
 if(!s||!*s||strlen(s)>100||*s=='-')return 0;
 for(;*s;s++)if(!(isalnum((unsigned char)*s)||strchr("._-",*s)))return 0;return 1;
}

/* A portable connection preset deliberately excludes auth material and local paths.
   Never import/export SSH keys, browser preferences, or Moonlight pairing. */
#define PRESET_COUNT 9
static const int preset_indices[PRESET_COUNT]={0,1,2,3,4,5,6,7,10};
static int safe_wake_path(const char*s){
 if(!s||!*s)return 1;
 if(*s!='/'||strlen(s)>350)return 0;
 for(;*s;s++)if(!(isalnum((unsigned char)*s)||strchr("/_.-",*s)))return 0;
 return 1;
}
static int safe_preset_url(const char*s){
 if(!s||!*s)return 1;
 if(strncmp(s,"https://",8)&&strncmp(s,"http://",7))return 0;
 const char*start=strstr(s,"://")+3;
 if(!*start||strchr(start,'@')||strchr(s,'?')||strchr(s,'#')||strlen(s)>=500)return 0;
 for(;*s;s++)if((unsigned char)*s<=32||(unsigned char)*s>=127)return 0;
 return 1;
}
static int safe_preset_values(char v[CONFIG_COUNT][512]){
 if(!valid_host(v[0])||!valid_user(v[1]))return 0;
 if(*v[2]&&!valid_host(v[2]))return 0;
 if(*v[3]&&!valid_user(v[3]))return 0;
 if(!safe_wake_path(v[4]))return 0;
 for(int i=5;i<=7;i++)if(!safe_preset_url(v[i]))return 0;
 if(*v[10]&&v[10][0]!='/')return 0;
 for(int i=0;i<PRESET_COUNT;i++){
   const char*value=v[preset_indices[i]];
   if(strchr(value,'\n')||strchr(value,'\r')||strlen(value)>=500)return 0;
 }
 return 1;
}
static int preset_read(const char*path,char v[CONFIG_COUNT][512]){
 FILE*f=fopen(path,"r");if(!f)return 0;
 char header[128]; if(!fgets(header,sizeof header,f)||strcmp(header,"# OptiPlex Now server preset v1\n")){fclose(f);return 0;}
 /* Never accept absolute AppImage/browser paths or unrecognized settings. */
 char line[1024];int found_host=0;
 while(fgets(line,sizeof line,f)){
  if(strlen(line)>900||(!strchr(line,'\n')&&!feof(f))){fclose(f);return 0;}
  line[strcspn(line,"\r\n")]=0;
  char *eq=strchr(line,'=');if(!eq){if(*line && *line!='#'){fclose(f);return 0;}continue;}
  *eq++=0;int match=0;
  for(int i=0;i<PRESET_COUNT;i++){
    int j=preset_indices[i];
    if(!strcmp(line,keys[j])){safe_copy(v[j],512,eq);match=1;if(j==0)found_host=1;break;}
  }
  if(!match){fclose(f);return 0;}
 }
 fclose(f);return found_host&&safe_preset_values(v);
}
static int preset_write(const char*path,char v[CONFIG_COUNT][512]){
 if(!safe_preset_values(v))return 0;
 int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);if(fd<0)return 0;
 FILE*f=fdopen(fd,"w");if(!f){close(fd);return 0;}
 int ok=fprintf(f,"# OptiPlex Now server preset v1\n")>0;
 for(int i=0;i<PRESET_COUNT;i++){
  int j=preset_indices[i];
  if(fprintf(f,"%s=%s\n",keys[j],v[j])<0)ok=0;
 }
 if(fclose(f)!=0)ok=0;
 return ok;
}
static void preset_alert(void*parent,const char*title,const char*msg){
 GtkWidget*d=gtk_dialog_new_with_buttons(title,parent,1,"OK",RESPONSE_OK,NULL);
 GtkWidget*area=gtk_dialog_get_content_area(d);GtkWidget*b=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
 gtk_container_set_border_width(b,16);gtk_container_add(area,b);
 GtkWidget*l=gtk_label_new(msg);gtk_label_set_line_wrap(l,1);gtk_container_add(b,l);
 gtk_widget_show_all(d);gtk_dialog_run(d);gtk_widget_destroy(d);
}
static int preset_pick(char*out,size_t n,void*parent,int save){
 GtkWidget*d=gtk_file_chooser_dialog_new(save?"Export My OptiPlex":"Import My OptiPlex",parent,save?1:0,
      "CANCEL",RESPONSE_CANCEL,save?"SAVE":"OPEN",RESPONSE_OK,NULL);
 extern gboolean gtk_file_chooser_set_current_folder(void*,const char*);
 const char*home=getenv("HOME"); if(home&&*home)gtk_file_chooser_set_current_folder(d,home);
 if(save){
   extern void gtk_file_chooser_set_current_name(void*,const char*);
   extern void gtk_file_chooser_set_do_overwrite_confirmation(void*,gboolean);
   gtk_file_chooser_set_current_name(d,"My-OptiPlex.onp");
   gtk_file_chooser_set_do_overwrite_confirmation(d,1);
 }
 int ok=0; if(gtk_dialog_run(d)==RESPONSE_OK){
  char*path=gtk_file_chooser_get_filename(d);
  if(path){safe_copy(out,n,path);ok=1;g_free(path);}
 }
 gtk_widget_destroy(d);return ok;
}
static int run(char *const argv[],char *out,size_t cap,int timeout) {
 if(out&&cap)*out=0; int fd[2];if(pipe(fd))return -1;
 pid_t pid=fork();if(pid<0){close(fd[0]);close(fd[1]);return -1;}
 if(pid==0){close(fd[0]);dup2(fd[1],1);dup2(fd[1],2);close(fd[1]);
   int nullfd=open("/dev/null",O_RDONLY);if(nullfd>=0){dup2(nullfd,0);close(nullfd);}execvp(argv[0],argv);_exit(127);}
 close(fd[1]); fcntl(fd[0],F_SETFL,fcntl(fd[0],F_GETFL)|O_NONBLOCK);
 int status=0,done=0;size_t used=0;long max_ticks=timeout*10;
 for(long n=0;n<max_ticks;n++){
   if(out&&used+1<cap){ssize_t k=read(fd[0],out+used,cap-used-1);if(k>0){used+=(size_t)k;out[used]=0;}}
   pid_t r=waitpid(pid,&status,WNOHANG);if(r==pid){done=1;break;}if(r<0)break;
   usleep(100000);
 }
 if(!done){kill(pid,SIGKILL);waitpid(pid,&status,0);}
 if(out&&used+1<cap){ssize_t k=read(fd[0],out+used,cap-used-1);if(k>0){used+=(size_t)k;out[used]=0;}}
 close(fd[0]);return done&&WIFEXITED(status)?WEXITSTATUS(status):-1;
}
static void launch(char *const argv[]) {
 pid_t pid=fork();if(pid==0){setsid();pid_t nested=fork();if(nested>0)_exit(0);
 int nullfd=open("/dev/null",O_RDWR);if(nullfd>=0){dup2(nullfd,0);dup2(nullfd,1);dup2(nullfd,2);close(nullfd);}
 execvp(argv[0],argv);_exit(127);}if(pid>0)waitpid(pid,NULL,0);
}
static int exists_program(const char*n) {
 if(strchr(n,'/'))return access(n,X_OK)==0;
 const char*path=getenv("PATH");if(!path)return 0;char *dup=strdup(path),*save=NULL;int found=0;
 for(char*p=strtok_r(dup,":",&save);p;p=strtok_r(NULL,":",&save)){
   char file[PATH_MAX];snprintf(file,sizeof file,"%s/%s",p,n);if(access(file,X_OK)==0){found=1;break;}}
 free(dup);return found;
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
 if(exists_program("moonlight"))return 2;
 if(flatpak_has("com.moonlight_stream.Moonlight"))return 3;
 return 0;
}
static const char* moonlight_mode_name(void) {
 const char *names[]={"MOONLIGHT NOT FOUND","MOONLIGHT APPIMAGE READY","MOONLIGHT INSTALLED","MOONLIGHT FLATPAK READY"};
 return names[moonlight_mode()];
}
static void choose_appimage(void) {
 GtkWidget*d=gtk_file_chooser_dialog_new("Choose Moonlight AppImage",win,0,"CANCEL",RESPONSE_CANCEL,"USE THIS FILE",RESPONSE_OK,NULL);
 if(gtk_dialog_run(d)==RESPONSE_OK){
  char *path=gtk_file_chooser_get_filename(d);
  if(path){
   if(access(path,X_OK)==0){safe_copy(cfg[9],512,path);appimage_found[0]=0;config_save();say("MOONLIGHT APPIMAGE SELECTED");}
   else say("APPIMAGE NOT EXECUTABLE. ENABLE EXECUTE PERMISSION FIRST");
   g_free(path);
  }
 }
 gtk_widget_destroy(d);
}
static int flatpak_has(const char *id) {
 if(!exists_program("flatpak"))return 0;
 char out[128];char*args[]={"flatpak","info","--show-ref",(char*)id,NULL};return run(args,out,sizeof(out),3)==0;
}
/* Always use the user's default browser, unless they explicitly selected Chrome.
 * A native GTK URI open works across XFCE, KDE and COSMIC when a browser
 * is registered. Try conventional browser commands if no default exists. */
static void browser_open(const char *url) {
 if(strncmp(url,"http://",7)&&strncmp(url,"https://",8))return;
 if(!strcmp(cfg[8],"chrome-flatpak") && flatpak_has("com.google.Chrome")){
   char*args[]={"flatpak","run","com.google.Chrome",(char*)url,NULL};launch(args);return;
 }
 if(!strcmp(cfg[8],"chrome") && (exists_program("google-chrome-stable")||exists_program("google-chrome"))){
   const char *cmd=exists_program("google-chrome-stable")?"google-chrome-stable":"google-chrome";
   char*args[]={(char*)cmd,(char*)url,NULL};launch(args);return;
 }
 void *err=NULL;
 if(gtk_show_uri_on_window(win,url,0,&err))return;
 if(err){g_error_free(err);err=NULL;}
 const char *browsers[]={"brave-browser-nightly","brave-browser","firefox","google-chrome-stable","google-chrome","chromium","chromium-browser"};
 for(unsigned i=0;i<sizeof browsers/sizeof browsers[0];i++){
   if(exists_program(browsers[i])){char*args[]={(char*)browsers[i],(char*)url,NULL};launch(args);return;}
 }
 const char *flatpak_browsers[]={"com.brave.Browser","org.mozilla.firefox","com.google.Chrome","org.chromium.Chromium"};
 for(unsigned i=0;i<sizeof flatpak_browsers/sizeof flatpak_browsers[0];i++){
   if(flatpak_has(flatpak_browsers[i])){
     char*args[]={"flatpak","run",(char*)flatpak_browsers[i],(char*)url,NULL};launch(args);return;
   }
 }
 say("NO WEB BROWSER FOUND. SET A DEFAULT BROWSER IN YOUR DESKTOP SETTINGS");
}

static void set_footer(const char *text) {gtk_label_set_text(footer,text);}
static GtkWidget* label(const char *text,const char *id) {
 GtkWidget*l=gtk_label_new(text);gtk_label_set_xalign(l,0);if(id)gtk_widget_set_name(l,id);return l;
}
static GtkWidget* button(const char *text,const char *id) {
 GtkWidget*b=gtk_button_new_with_label(text);if(id)gtk_widget_set_name(b,id);return b;
}
static void add(GtkWidget*box,GtkWidget*child,int expand) {gtk_box_pack_start(box,child,expand,expand,0);}
static void say(const char *s) {if(footer)set_footer(s);}

static int terminal_launch(char *const args[]) {
 if(exists_program("xfce4-terminal")){char *argv[24];int i=0;argv[i++]="xfce4-terminal";argv[i++]="--disable-server";argv[i++]="-x";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;launch(argv);return 1;}
 if(exists_program("mate-terminal")){char *argv[24];int i=0;argv[i++]="mate-terminal";argv[i++]="--";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;launch(argv);return 1;}
 if(exists_program("gnome-terminal")){char *argv[24];int i=0;argv[i++]="gnome-terminal";argv[i++]="--";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;launch(argv);return 1;}
 if(exists_program("xterm")){char *argv[24];int i=0;argv[i++]="xterm";argv[i++]="-e";
    for(int j=0;args[j]&&i<23;j++)argv[i++]=args[j];argv[i]=NULL;launch(argv);return 1;}
 say("No terminal found");return 0;
}
static void launch_ssh(int relay) {
 int h=relay?2:0,u=relay?3:1;
 if(!valid_host(cfg[h])||!valid_user(cfg[u])){say("Check Settings");return;}
 char *args[]={"ssh","-l",cfg[u],cfg[h],NULL};terminal_launch(args);
}
static void pair(int relay) {
 int h=relay?2:0,u=relay?3:1;
 if(!valid_host(cfg[h])||!valid_user(cfg[u])){say("Check server / relay settings");return;}
 if(!exists_program("ssh-copy-id")||!exists_program("ssh-keygen")){say("Install openssh-client to pair SSH");return;}
 char sshdir[PATH_MAX],pub[PATH_MAX],private[PATH_MAX];
 snprintf(sshdir,sizeof sshdir,"%s/.ssh",getenv("HOME")?getenv("HOME"):"/tmp");mkdir_safe(sshdir);
 snprintf(pub,sizeof pub,"%s/id_ed25519.pub",sshdir);snprintf(private,sizeof private,"%s/id_ed25519",sshdir);
 if(access(pub,F_OK)!=0){
   if(access(private,F_OK)==0){say("Existing SSH key needs its .pub file");return;}
   char*gen[]={"ssh-keygen","-q","-t","ed25519","-N","","-f",private,NULL};
   if(run(gen,NULL,0,8)!=0){say("Couldn't prepare SSH key");return;}
 }
 char dest[400];snprintf(dest,sizeof dest,"%s@%s",cfg[u],cfg[h]);
 /* Provide a terminal for a one-time remote password prompt. */
 char*args[]={"ssh-copy-id","-i",pub,dest,NULL};
 if(terminal_launch(args))say(relay?"Authorize the relay in the terminal":"Authorize the server in the terminal");
}
static void setup_tailscale(void) {
 if(exists_program("tailscale")){char*args[]={"sudo","tailscale","up",NULL};if(terminal_launch(args))say("Sign in to Tailscale in the opened terminal");}
 else browser_open("https://tailscale.com/download/linux");
}

typedef struct { int type; int success; int tail; char message[300]; char cpu[40],gpu[40],free_space[40]; int drive_count; Drive drives[MAX_DRIVES]; char model[160],source_host[512],source_user[512]; char specs[7][160]; char service_state[3][80]; char service_urls[3][512]; } Result;
static void set_drive_readout(void){
  if(!metric_free)return;
  int n=gtk_combo_box_get_active(drive_combo);
  if(n<0||n>=visible_drive_count){gtk_label_set_text(metric_free,"FREE  --");return;}
  Drive*d=&visible_drives[n];char buf[160];
  if(*d->free_space)snprintf(buf,sizeof buf,"FREE  %s   /   %s",d->free_space,d->size);
  else snprintf(buf,sizeof buf,"NOT MOUNTED");
  gtk_label_set_text(metric_free,buf);
  GtkStyleContext *sty=gtk_widget_get_style_context(metric_free);
  extern void gtk_style_context_remove_class(void*,const char*);
  gtk_style_context_remove_class(sty,"warn");
  if(atoi(d->used_percent)>=90)gtk_style_context_add_class(sty,"warn");
}
static void on_drive_changed(void*w,void*arg){
  (void)w;(void)arg;
  if(drive_combo_updating)return;
  int n=gtk_combo_box_get_active(drive_combo);
  if(n<0||n>=visible_drive_count)return;
  safe_copy(cfg[10],512,visible_drives[n].path);
  config_save();set_drive_readout();
}
static void update_drives(Result*r){
  if(!drive_combo)return;
  if(r->success!=1){gtk_label_set_text(metric_free,"FREE  --");return;}
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
    extern void gtk_combo_box_text_remove_all(void*);
    drive_combo_updating=1;
    gtk_combo_box_text_remove_all(drive_combo);
    for(int i=0;i<visible_drive_count;i++){
      Drive*d=&visible_drives[i];char choice[256];
      const char*name=!strcmp(d->path,"/")?"SYSTEM":strrchr(d->path,'/');
      name=!strcmp(d->path,"/")?name:(name?name+1:d->path);
      snprintf(choice,sizeof choice,"%s   %s",name,d->size);
      gtk_combo_box_text_append_text(drive_combo,choice);
    }
    gtk_combo_box_set_active(drive_combo,visible_drive_count?selected:-1);
    drive_combo_updating=0;
  }
  set_drive_readout();
}

static gboolean finish_on_main(void *arg) {
 Result*r=arg; if(r->type==0){
   if(strcmp(r->source_host,cfg[0])||strcmp(r->source_user,cfg[1])){
     status_inflight=0;free(r);return 0;
   }
   if(r->success==1 && *r->model &&
      (strcmp(cfg[11],r->source_host)||strcmp(cfg[12],r->model))){
     safe_copy(cfg[11],512,r->source_host);safe_copy(cfg[12],512,r->model);config_save();
   }
   update_model_heading();
   const char *s=r->success==1?"● ONLINE":r->success==2?"● PAIR SSH":r->success==3?"● TAILSCALE OFF":"● OFFLINE";
   gtk_label_set_text(indicator,s);
   if(tray_icon){char tip[100];snprintf(tip,sizeof tip,"OptiPlex Now | %s",s+2);gtk_status_icon_set_tooltip_text(tray_icon,tip);}
   GtkStyleContext*sty=gtk_widget_get_style_context(indicator);
   /* Old classes harmless; remove is available but style is reset below. */
   extern void gtk_style_context_remove_class(void*,const char*);
   gtk_style_context_remove_class(sty,"online");gtk_style_context_remove_class(sty,"offline");gtk_style_context_remove_class(sty,"pair");
   gtk_style_context_add_class(sty,r->success==1?"online":r->success==2?"pair":"offline");
   gtk_label_set_text(status_detail,r->success==1?"":r->message);
   if(metric_cpu){char val[70];snprintf(val,sizeof val,"CPU   %s",*r->cpu?r->cpu:"--");gtk_label_set_text(metric_cpu,val);}
   if(metric_gpu){char val[70];snprintf(val,sizeof val,"GPU   %s",*r->gpu?r->gpu:"--");gtk_label_set_text(metric_gpu,val);}
   update_drives(r);
   if(tailscale_label)gtk_label_set_text(tailscale_label,r->tail?"TAILSCALE CONNECTED":"TAILSCALE NOT CONNECTED");
   status_inflight=0;
 }else if(r->type==7){
    for(int i=0;i<3;i++)if(service_labels[i])gtk_label_set_text(service_labels[i],r->service_state[i]);
    services_inflight=0;
 }else if(r->type==8){
    if(wizard_wolf_label)gtk_label_set_text(wizard_wolf_label,r->success?"WOLF REACHABLE":"WOLF NOT DETECTED. YOU CAN STILL CONTINUE");
    wolf_inflight=0;
 }else if(r->type==6){
    if(spec_status)gtk_label_set_text(spec_status,r->success?"LIVE HARDWARE INVENTORY":"SERVER UNAVAILABLE. CHECK SSH / TAILSCALE");
    if(r->success){
      for(int i=0;i<7;i++)if(spec_values[i])gtk_label_set_text(spec_values[i],*r->specs[i]?r->specs[i]:"NOT AVAILABLE");
    }
    specs_inflight=0;
 }else if(r->type==5){
    if(r->success==1 && !strncmp(r->message,"http://",7)){
      if(games_notice)gtk_label_set_text(games_notice,"OPENING WOLF PIN PAGE");
      browser_open(r->message);
    }else{
      if(games_notice)gtk_label_set_text(games_notice,r->message);
      say(r->message);
    }
    power_inflight=0;
 }else {say(r->message);power_inflight=0;}
 free(r);return 0;
}
static int safe_disk_path(const char *s){
 if(!s||*s!='/'||strlen(s)>350)return 0;
 for(;*s;s++)if(!(isalnum((unsigned char)*s)||strchr("/_.-",*s)))return 0;
 return 1;
}
/* Keep mounted data drives in the selector, not recovery or OS support volumes.
   Apply locally too, so changing the remote df filter cannot expose these rows. */
static int system_mount(const char *path) {
 if(!path || path[0]!='/')return 1;
 if(!strcmp(path,"/"))return 0;
 const char *p=path;
 while(*p){
   while(*p=='/')p++;
   if(!*p)break;
   const char *end=strchr(p,'/');size_t n=end?(size_t)(end-p):strlen(p);
   if((n>=8 && strcasestr(p,"recovery") && (size_t)(strcasestr(p,"recovery")-p)<n) ||
      (n==4 && !strncasecmp(p,"boot",4)) ||
      (n==3 && !strncasecmp(p,"efi",3)) ||
      (n==4 && !strncasecmp(p,"snap",4)))return 1;
   if(!end)break;
   p=end+1;
 }
 if(!strncmp(path,"/run/",5)||!strncmp(path,"/dev/",5)||
    !strncmp(path,"/proc/",6)||!strncmp(path,"/sys/",5))return 1;
 return 0;
}
static void get_metric(char *dst,size_t n,const char *output,const char *key){
 const char *at=output;
 while((at=strstr(at,key)) && at!=output && at[-1]!='\n')at+=strlen(key);
 if(!at)return;
 at+=strlen(key);size_t j=0;
 while(*at && *at!='\n' && *at!='\r' && j+1<n){
  if(isprint((unsigned char)*at)) dst[j++]=*at;
  at++;
 }
 dst[j]=0;
}
static int tcp_reachable(const char *host,const char *port){
 if(!valid_host(host))return 0;
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
   if(exists_program("tailscale")) {char *argv[]={"tailscale","ip","-4",NULL};tailscale_ok=run(argv,out,sizeof out,5)==0 && strstr(out,"100.")!=NULL;}
   r->tail=tailscale_ok;
   if(!valid_host(r->source_host)||!valid_user(r->source_user)){r->success=0;strcpy(r->message,"CHECK SETTINGS");}
   else {
     /* Fixed, read-only remote telemetry. Mounted physical file systems. */
     const char*cmd=
      "printf 'READY\nMODEL='; cat /sys/class/dmi/id/product_name 2>/dev/null | head -1; "
      "printf 'CPU='; "
      "sensors 2>/dev/null | awk '/Package id 0:/ {print $4; exit}' | tr -d '+\r'; "
      "printf 'GPU='; nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1; "
      "printf 'DRIVES_BEGIN\n'; "
      "df -hPT -x tmpfs -x devtmpfs -x overlay -x squashfs -x zramfs 2>/dev/null "
      "| awk 'NR>1 && index($1,\"/dev/\")==1 && $7 !~ \"^/(boot|efi|snap)(/|$)\" {print \"DRIVE=\" $7 \"|\" $3 \"|\" $5 \"|\" $6}' ; "
      "printf 'DRIVES_END\n'";
     char stats[8192]={0};
     char *argv[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=accept-new","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",r->source_user,r->source_host,cmd,NULL};
     int code=run(argv,stats,sizeof stats,9);
     if(code==0&&strstr(stats,"READY")){
       r->success=1;strcpy(r->message,"SERVER REACHABLE");
       get_metric(r->model,sizeof r->model,stats,"MODEL=");
       get_metric(r->cpu,sizeof r->cpu,stats,"CPU=");
       get_metric(r->gpu,sizeof r->gpu,stats,"GPU=");
       if(*r->gpu){strncat(r->gpu,"°C",sizeof r->gpu-strlen(r->gpu)-1);}
       const char*line=stats;
       while((line=strstr(line,"DRIVE=")) && r->drive_count<MAX_DRIVES){
         line+=6;
         const char*e=strchr(line,'\n');if(!e)break;
         char row[512];size_t len=(size_t)(e-line);
         if(len>=sizeof row){line=e;continue;}
         memcpy(row,line,len);row[len]=0;
         char *parts[4]={0},*cursor=row;
         for(int j=0;j<4;j++){
           parts[j]=cursor;
           if(j<3){char *bar=strchr(cursor,'|');if(!bar){parts[0]=NULL;break;}*bar=0;cursor=bar+1;}
         }
         if(parts[0] && safe_disk_path(parts[0]) && !system_mount(parts[0])){
           Drive*d=&r->drives[r->drive_count++];
           safe_copy(d->path,sizeof d->path,parts[0]);
           safe_copy(d->size,sizeof d->size,parts[1]);
           safe_copy(d->free_space,sizeof d->free_space,parts[2]);
           safe_copy(d->used_percent,sizeof d->used_percent,parts[3]);
         }
         line=e;
       }
     }
     else if(strstr(stats,"Permission denied")||strstr(stats,"Host key verification")) {r->success=2;strcpy(r->message,"AUTHORIZE SSH IN SETTINGS");}
     else if(!tailscale_ok){r->success=3;strcpy(r->message,"CHECK TAILSCALE");}
     else{r->success=0;strcpy(r->message,"SERVER UNREACHABLE");}
   }
 }else if(r->type==7){
   for(int i=0;i<3;i++){
      const char*url=r->service_urls[i];
      if(!*url){safe_copy(r->service_state[i],sizeof r->service_state[i],"NOT SET UP");continue;}
      if((strncmp(url,"https://",8)&&strncmp(url,"http://",7))||!exists_program("curl")){
        safe_copy(r->service_state[i],sizeof r->service_state[i],"NOT CHECKED");continue;
      }
      char http[128]={0};
      char*argv[]={"curl","--silent","--show-error","--location","--max-time","3","--connect-timeout","2","--output","/dev/null","--write-out","%{http_code}",(char*)url,NULL};
      int rc=run(argv,http,sizeof http,5);
      int code=atoi(http);
      safe_copy(r->service_state[i],sizeof r->service_state[i],rc==0 && code>=200&&code<500?"RESPONDING":"UNREACHABLE");
   }
 }else if(r->type==8){
   r->success=tcp_reachable(r->message,"47989") || tcp_reachable(r->message,"47984");
 }else if(r->type==6){
   if(valid_host(cfg[0])&&valid_user(cfg[1])){
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
     char *argv[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=accept-new","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",cfg[1],cfg[0],(char*)cmd,NULL};
     if(run(argv,stats,sizeof stats,10)==0 && strstr(stats,"MODEL=")){
       const char *keys[]={"MODEL=","CPU_MODEL=","GPU_MODEL=","VRAM=","RAM=","OS=","DRIVER="};
       for(int i=0;i<7;i++)get_metric(r->specs[i],sizeof r->specs[i],stats,keys[i]);
       r->success=1;
     }
   }
 }else if(r->type==5){
   if(!valid_host(cfg[0])||!valid_user(cfg[1])) {strcpy(r->message,"CHECK SERVER SETTINGS");}
   else {
     char *args[]={"ssh","-o","BatchMode=yes","-o","ConnectTimeout=5","-o","StrictHostKeyChecking=accept-new",
         "-l",cfg[1],cfg[0],
         "docker logs --since 10m wolf 2>&1 | grep -oE 'http[^[:space:]]+/pin/#[0-9A-Fa-f]+' | tail -1",NULL};
     char logline[4096]={0};int c=run(args,logline,sizeof(logline),9);
     char *hash=strstr(logline,"/pin/#");
     if(c==0&&hash){
       hash+=6;char token[90];int i=0;
       while(isxdigit((unsigned char)hash[i])&&i<80){token[i]=hash[i];i++;}
       token[i]=0;
       if(i>=6){snprintf(r->message,sizeof r->message,"http://%s:47989/pin/#%s",cfg[0],token);r->success=1;}
       else strcpy(r->message,"INVALID WOLF PIN LINK");
     }else strcpy(r->message,"START PAIR WOLF FIRST, THEN RETRY");
   }
 }else {
   int kind=r->type-1; int relay=kind==0;int h=relay?2:0,u=relay?3:1;
   if(!valid_host(cfg[h])||!valid_user(cfg[u])){strcpy(r->message,"Invalid host or user. Check Settings.");}
   else {
     char*arg[]={"ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=accept-new","-o","ConnectTimeout=4","-o","ConnectionAttempts=1","-l",cfg[u],cfg[h],NULL,NULL};
     char command[1024];
     if(relay) {
       if(!*cfg[4]||!safe_wake_path(cfg[4])){strcpy(r->message,"Set a valid relay wake script in Settings");goto done;}
       snprintf(command,sizeof command,"%s",cfg[4]);
     }else{
       const char*actions[]={"suspend","reboot","poweroff"};
       snprintf(command,sizeof command,"sudo -n /usr/bin/systemctl %s",actions[kind-1]);
     }
     arg[12]=command;
     int code=run(arg,out,sizeof out,14);
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
 if(type==7&&services_inflight)return;
 if(type==8&&wolf_inflight)return;
 if(type!=0&&type!=6&&type!=7&&type!=8&&power_inflight)return;
 if(type==0)status_inflight=1;else if(type==6)specs_inflight=1;else if(type==7)services_inflight=1;else if(type==8)wolf_inflight=1;else power_inflight=1;
 Result*r=calloc(1,sizeof* r);r->type=type;
 if(type==8)safe_copy(r->message,sizeof r->message,*wolf_probe_host?wolf_probe_host:cfg[0]);
 if(type==7)for(int i=0;i<3;i++)safe_copy(r->service_urls[i],sizeof r->service_urls[i],cfg[5+i]);
 safe_copy(r->source_host,sizeof r->source_host,cfg[0]);
 safe_copy(r->source_user,sizeof r->source_user,cfg[1]);
 pthread_t t; if(pthread_create(&t,NULL,worker,r)==0)pthread_detach(t);else{free(r);if(type==0)status_inflight=0;else if(type==6)specs_inflight=0;else if(type==7)services_inflight=0;else if(type==8)wolf_inflight=0;else power_inflight=0;}
}
static gboolean periodic(void*unused){(void)unused;begin_job(0);return 1;}
static void refresh(void){gtk_label_set_text(indicator,"● CHECKING");begin_job(0);}
static void on_power(void*widget,void*data){(void)widget;int n=(int)(long)data;
 if(n>0){const char*names[]={"","Sleep","Restart","Shut down"};
   GtkWidget*d=gtk_dialog_new_with_buttons("Confirm",win,1,"CANCEL",RESPONSE_CANCEL,"CONFIRM",RESPONSE_OK,NULL);
   GtkWidget*area=gtk_dialog_get_content_area(d);char msg[128];snprintf(msg,sizeof msg,"%s OptiPlex?",names[n]);
   GtkWidget*l=label(msg,"modalheading");gtk_widget_set_margin_start(l,22);gtk_widget_set_margin_end(l,22);
   gtk_widget_set_margin_top(l,16);gtk_widget_set_margin_bottom(l,12);add(area,l,0);gtk_widget_show_all(d);
   int resp=gtk_dialog_run(d);gtk_widget_destroy(d);if(resp!=RESPONSE_OK)return;
 }
 say("SENDING POWER COMMAND");begin_job(n+1);
}
static int has_moonlight(void) {return moonlight_mode()!=0;}
static void open_moonlight(void){
 int mode=moonlight_mode();
 if(mode==1){char*args[]={(char*)find_appimage(),NULL};launch(args);say("MOONLIGHT APPIMAGE OPENED");}
 else if(mode==2){char*args[]={"moonlight",NULL};launch(args);say("MOONLIGHT OPENED");}
 else if(mode==3){char*args[]={"flatpak","run","com.moonlight_stream.Moonlight",NULL};launch(args);say("MOONLIGHT OPENED");}
 else say("CHOOSE AN APPIMAGE OR INSTALL MOONLIGHT IN GAMES SETUP");
}
/* Directly connect the selected Moonlight client to the Steam application on Wolf.
 * Moonlight Qt supports: moonlight stream HOST APP. Preferences and pairing
 * are read from its own existing profile, preserving hardware decoding. */
static void launch_wolf_app(const char *app){
 if(!has_moonlight()){on_games_setup(NULL,NULL);return;}
 if(!valid_host(cfg[0])){say("SET SERVER IN SETTINGS");open_moonlight();return;}
 int mode=moonlight_mode();
 if(mode==1){char *args[]={(char*)find_appimage(),"stream",cfg[0],(char*)app,NULL};launch(args);}
 else if(mode==2){char *args[]={"moonlight","stream",cfg[0],(char*)app,NULL};launch(args);}
 else {char *args[]={"flatpak","run","com.moonlight_stream.Moonlight","stream",cfg[0],(char*)app,NULL};launch(args);}
 say("CONNECTING TO WOLF");
}
static void launch_steam(void){launch_wolf_app("Steam");}
static void launch_desktop(void){launch_wolf_app("XFCE");}
static void launch_torrents(void){
 if(!valid_host(cfg[0])){say("SET SERVER IN SETTINGS");return;}
 char url[700];snprintf(url,sizeof url,"http://%s:8085",cfg[0]);
 browser_open(url);
}
static void install_moonlight(void){
 if(!exists_program("flatpak")){
   say("FLATPAK IS REQUIRED TO INSTALL MOONLIGHT");
   if(games_notice)gtk_label_set_text(games_notice,"FLATPAK IS REQUIRED TO INSTALL MOONLIGHT");
   return;
 }
 /* The action is explicitly user initiated. Flatpak asks to install the remote and package. */
 char*args[]={"sh","-c","flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo && flatpak install --user flathub com.moonlight_stream.Moonlight; printf '\\nPress Enter to close...'; read _",NULL};
 if(terminal_launch(args)){
   say("COMPLETE INSTALLATION IN THE TERMINAL");
   if(games_notice)gtk_label_set_text(games_notice,"COMPLETE INSTALLATION IN THE TERMINAL");
 }
}
static void pair_wolf(void){
 if(!has_moonlight()){say("INSTALL MOONLIGHT FIRST");return;}
 if(!valid_host(cfg[0])){say("SET SERVER IN SETTINGS");return;}
 char *native[]={"moonlight","pair",cfg[0],NULL};
 char *appimage[]={(char*)find_appimage(),"pair",cfg[0],NULL};
 char *flat[]={"flatpak","run","com.moonlight_stream.Moonlight","pair",cfg[0],NULL};
 int mode=moonlight_mode();
 if(terminal_launch(mode==1?appimage:mode==2?native:flat)){
   say("ENTER THE PIN ON WOLF'S PAIRING PAGE");
   if(games_notice)gtk_label_set_text(games_notice,"AFTER PAIRING STARTS, CLICK OPEN WOLF PIN");
 }
}
static void on_games_action(void*w,void*arg){(void)w;
 int resp=(int)(long)arg;
 if(resp==101){if(has_moonlight())open_moonlight();else install_moonlight();}
 else if(resp==102)open_moonlight();
 else if(resp==105)choose_appimage();
 else if(resp==103)pair_wolf();
 else if(resp==104){
   if(!valid_host(cfg[0])||!valid_user(cfg[1])){
     if(games_notice)gtk_label_set_text(games_notice,"CHECK SERVER SETTINGS");
   }else{
     if(games_notice)gtk_label_set_text(games_notice,"LOOKING FOR WOLF PAIRING PAGE");
     begin_job(5);
   }
 }
 if(games_state)gtk_label_set_text(games_state,moonlight_mode_name());
 if(games_install){extern void gtk_button_set_label(void*,const char*);gtk_button_set_label(games_install,has_moonlight()?"OPEN MOONLIGHT":"INSTALL MOONLIGHT");}
}
/* Only reached after an explicit confirmation. SSH/sudo authenticate in a
 * terminal; credentials never enter launcher configuration or shell arguments. */
static void on_restart_streaming(void *w, void *parent) {
 (void)w;
 void *owner=parent?parent:win;
 if(!valid_host(cfg[0])||!valid_user(cfg[1])){
   preset_alert(owner,"Server settings needed","Set the OptiPlex host and SSH user in Settings first.");return;
 }
 GtkWidget*d=gtk_dialog_new_with_buttons("Restart streaming service?",owner,1,
   "Cancel",RESPONSE_CANCEL,"Restart streaming",RESPONSE_OK,NULL);
 extern void gtk_dialog_set_default_response(void*,gint);
 gtk_dialog_set_default_response(d,RESPONSE_CANCEL);
 GtkWidget*area=gtk_dialog_get_content_area(d);
 GtkWidget*msg=gtk_label_new("This will disconnect active streaming sessions.\nSave your game first. The OptiPlex itself will stay on.");
 gtk_container_set_border_width(area,20);gtk_label_set_line_wrap(msg,1);gtk_container_add(area,msg);
 gtk_widget_show_all(d);int response=gtk_dialog_run(d);gtk_widget_destroy(d);
 if(response!=RESPONSE_OK)return;
 char *args[]={"/usr/lib/optiplex-now/restart-streaming",cfg[0],cfg[1],NULL};
 if(terminal_launch(args))say("Streaming restart opened in terminal. Check its result before reconnecting.");
 else preset_alert(owner,"Terminal unavailable","Install a supported terminal to authenticate the streaming restart.");
}

static void on_games_setup(void*w,void*p){(void)w;
 GtkWidget*d=gtk_dialog_new_with_buttons("Games",p?p:win,1,"CLOSE",RESPONSE_CANCEL,NULL);
 gtk_window_set_default_size(d,440,290);
 GtkWidget*area=gtk_dialog_get_content_area(d);
 GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,11);
 gtk_container_set_border_width(col,20);add(area,col,0);
 add(col,label("MOONLIGHT + WOLF","modalheading"),0);
 games_state=label(moonlight_mode_name(),"gameshint");add(col,games_state,0);
 GtkWidget*address=label("","helper");char text[600];snprintf(text,sizeof text,"WOLF HOST   %s",*cfg[0]?cfg[0]:"SET SERVER IP IN SETTINGS");gtk_label_set_text(address,text);add(col,address,0);
 add(col,label("Games launches Steam directly. Open Moonlight here for setup.","helper"),0);
 GtkWidget*row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);add(col,row,0);
 games_install=button(has_moonlight()?"OPEN MOONLIGHT":"INSTALL MOONLIGHT","setupaction");
 g_signal_connect_data(games_install,"clicked",(GCallback)on_games_action,(void*)(long)101,NULL,0);add(row,games_install,1);
 GtkWidget*choose=button("USE APPIMAGE","setupaction");
 g_signal_connect_data(choose,"clicked",(GCallback)on_games_action,(void*)(long)105,NULL,0);add(col,choose,0);
 GtkWidget*pairbutton=button("PAIR WOLF","setupaction");
 g_signal_connect_data(pairbutton,"clicked",(GCallback)on_games_action,(void*)(long)103,NULL,0);add(row,pairbutton,1);
 GtkWidget*pin=button("OPEN WOLF PIN","setupaction");
 g_signal_connect_data(pin,"clicked",(GCallback)on_games_action,(void*)(long)104,NULL,0);add(col,pin,0);
 GtkWidget*restart=button("Restart streaming service…","setupaction");
 g_signal_connect_data(restart,"clicked",(GCallback)on_restart_streaming,d,NULL,0);add(col,restart,0);
 games_notice=label("","gameshint");add(col,games_notice,0);
 gtk_widget_show_all(d);gtk_dialog_run(d);
 games_notice=NULL;games_state=NULL;games_install=NULL;gtk_widget_destroy(d);
}
/* COSMIC Files may launch in Home when supplied a remote SFTP URI.
 * Mount it through GVFS first, then hand COSMIC an actual local FUSE path.
 * Traditional GTK and KDE file managers can still accept their SFTP URIs. */
static void open_remote_files(void){
 if(!valid_host(cfg[0])||!valid_user(cfg[1])){say("SET SERVER AND SSH USER IN SETTINGS");return;}
 if(exists_program("cosmic-files")){
   const char*helper="/usr/lib/optiplex-now/open-remote-files";
   if(access(helper,X_OK)!=0){
      say("FILES HELPER MISSING. REINSTALL OPTIPLEX NOW");return;
   }
   char*args[]={(char*)helper,cfg[0],cfg[1],NULL};
   launch(args);say("CONNECTING TO SERVER FILES");return;
 }
 char url[640];snprintf(url,sizeof url,"sftp://%s@%s/",cfg[1],cfg[0]);
 const char*managers[]={"thunar","nemo","nautilus","dolphin","caja","pcmanfm"};
 for(unsigned i=0;i<sizeof managers/sizeof managers[0];i++){
   if(exists_program(managers[i])){
      char*args[]={(char*)managers[i],url,NULL};launch(args);say("OPENING SERVER FILES");return;
   }
 }
 if(exists_program("gio")){char*args[]={"gio","open",url,NULL};launch(args);say("OPENING SFTP LOCATION");return;}
 say("NO SFTP-CAPABLE FILE MANAGER FOUND");
}
static void on_tile(void*widget,void*data){(void)widget;int n=(int)(long)data;
 if(n==0){
   if(has_moonlight())launch_steam();else on_games_setup(NULL,NULL);
 }else if(n==1||n==2||n==4){int ix=n==1?5:n==2?6:7;if(!*cfg[ix]){say("ADD URL IN SETTINGS");return;}browser_open(cfg[ix]);}
 else if(n==3)open_remote_files();
 else if(n==5)launch_ssh(0);
 else if(n==6)launch_desktop();
 else if(n==7)launch_torrents();
}
static void reflow(int width) {
 int cols=width>=600?4:2;
 int pcols=width>=560?4:2;
 if(cols==last_columns && pcols==last_power_columns)return;
 extern void gtk_container_remove(void*,void*);
 extern void g_object_ref(void*), g_object_unref(void*);
 extern void* gtk_widget_get_parent(void*);
 if(cols!=last_columns){
   last_columns=cols;
   for(int i=0;i<8;i++){g_object_ref(tiles[i]);if(gtk_widget_get_parent(tiles[i]))gtk_container_remove(grid,tiles[i]);}
   for(int i=0;i<8;i++){gtk_grid_attach(grid,tiles[i],i%cols,i/cols,1,1);g_object_unref(tiles[i]);}
   gtk_widget_show_all(grid);
 }
 if(pcols!=last_power_columns){
   last_power_columns=pcols;
   for(int i=0;i<4;i++){g_object_ref(powers[i]);if(gtk_widget_get_parent(powers[i]))gtk_container_remove(power_grid,powers[i]);}
   for(int i=0;i<4;i++){gtk_grid_attach(power_grid,powers[i],i%pcols,i/pcols,1,1);g_object_unref(powers[i]);}
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
 char path[PATH_MAX];const char *runtime=getenv("XDG_RUNTIME_DIR");
 if(runtime && *runtime){snprintf(path,sizeof path,"%s/optiplex-now.lock",runtime);}
 else {
   const char*home=getenv("HOME");char cache[PATH_MAX];
   snprintf(cache,sizeof cache,"%s/.cache",home?home:"/tmp");mkdir_safe(cache);
   snprintf(path,sizeof path,"%s/optiplex-now.lock",cache);
 }
 instance_fd=open(path,O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
 if(instance_fd<0) {fprintf(stderr,"Could not open instance lock: %s\n",strerror(errno));return 1;}
 if(flock(instance_fd,LOCK_EX|LOCK_NB)!=0){
   char buf[64]={0};lseek(instance_fd,0,SEEK_SET);
   ssize_t n=read(instance_fd,buf,sizeof(buf)-1);if(n>0){
     long pid=strtol(buf,NULL,10);if(pid>1 && pid<=INT_MAX)kill((pid_t)pid,SIGUSR1);
   }
   close(instance_fd);instance_fd=-1;return 0;
 }
 ftruncate(instance_fd,0);lseek(instance_fd,0,SEEK_SET);
 char buf[64];int n=snprintf(buf,sizeof buf,"%ld\n",(long)getpid());write(instance_fd,buf,n);
 struct sigaction sa={0};sa.sa_handler=request_reopen;sigemptyset(&sa.sa_mask);
 sigaction(SIGUSR1,&sa,NULL);
 return 1;
}
static gboolean tray_finish_restore(void *unused){
 (void)unused;
 if(win){gtk_window_deiconify(win);gtk_widget_show_all(win);gtk_window_present(win);}
 tray_restoring=0;
 return 0;
}
static void tray_show_window(void){
 if(!win)return;
 tray_restoring=1;
 gtk_window_deiconify(win);gtk_widget_show_all(win);gtk_window_present(win);
 /* Some XFCE window managers send the iconified-state event after restore.
  * Present a second time once that event has been processed. */
 g_timeout_add(140,tray_finish_restore,NULL);
}
static gboolean reopen_check(void *unused){
 (void)unused;if(reopen_requested){reopen_requested=0;tray_show_window();}return 1;
}
/* Don't leave an invisible process behind if the desktop has no tray. */
static gboolean can_minimize_to_tray(void){return using_status_notifier ? tray_available : (tray_icon && gtk_status_icon_is_embedded(tray_icon));}
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
   const char*v=gtk_entry_get_text(c->inputs[i]);
   if(strchr(v,'\n')||strchr(v,'\r'))return;
   safe_copy(cfg[i],512,v);
 }
 config_save();pair(c->relay);
}
static void on_games_setup_from_settings(void*w,void*p){
 PairContext*c=p;
 for(int i=0;i<5;i++){
   const char*v=gtk_entry_get_text(c->inputs[i]);
   if(strchr(v,'\n')||strchr(v,'\r'))return;
   safe_copy(cfg[i],512,v);
 }
 config_save();on_games_setup(w,c->parent);
}
static void on_tail(void*w,void*p){(void)w;(void)p;setup_tailscale();}
static void on_system_info(void*w,void*p){
 (void)w;(void)p;
 GtkWidget*d=gtk_dialog_new_with_buttons("System Info",win,1,"CLOSE",RESPONSE_CANCEL,NULL);
 gtk_window_set_default_size(d,490,390);
 GtkWidget*area=gtk_dialog_get_content_area(d);
 GtkWidget*box=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);gtk_container_set_border_width(box,20);add(area,box,1);
 add(box,label("SYSTEM INFO","modalheading"),0);
 spec_status=label("READING HARDWARE...","helper");add(box,spec_status,0);
 GtkWidget*rows=gtk_grid_new();gtk_grid_set_row_spacing(rows,13);gtk_grid_set_column_spacing(rows,18);add(box,rows,1);
 const char*names[]={"MODEL","PROCESSOR","GRAPHICS","VIDEO MEMORY","SYSTEM RAM","OPERATING SYSTEM","NVIDIA DRIVER"};
 for(int i=0;i<7;i++){
   GtkWidget*name=label(names[i],"specname");gtk_widget_set_size_request(name,135,-1);gtk_grid_attach(rows,name,0,i,1,1);
   spec_values[i]=label("...","specvalue");gtk_label_set_ellipsize(spec_values[i],3);gtk_widget_set_hexpand(spec_values[i],1);
   gtk_grid_attach(rows,spec_values[i],1,i,1,1);
 }
 gtk_widget_show_all(d);begin_job(6);gtk_dialog_run(d);
 for(int i=0;i<7;i++)spec_values[i]=NULL;
 spec_status=NULL;gtk_widget_destroy(d);
}

typedef struct {GtkWidget*parent,*fields[8],*disk;} PresetExportContext;
static void export_preset(void*w,void*p){
 (void)w;PresetExportContext*c=p;char v[CONFIG_COUNT][512];
 for(int i=0;i<CONFIG_COUNT;i++)safe_copy(v[i],512,cfg[i]);
 for(int i=0;i<8;i++)safe_copy(v[i],512,gtk_entry_get_text(c->fields[i]));
 safe_copy(v[10],512,gtk_entry_get_text(c->disk));
 if(!safe_preset_values(v)){
  preset_alert(c->parent,"Preset not saved","Check server, relay, URL, and wake script fields. Presets cannot contain URL passwords or tokens.");return;
 }
 char path[PATH_MAX];if(!preset_pick(path,sizeof path,c->parent,1))return;
 if(preset_write(path,v))preset_alert(c->parent,"Preset saved","Share this file only with devices you trust. Pair each device separately.");
 else preset_alert(c->parent,"Preset not saved","Could not write preset file.");
}
/* Full trusted-device backup. Passphrase never appears in process arguments. */
#define BACKUP_BINARY "/usr/lib/optiplex-now/optiplex-now-backup"
static int backup_pick(char*out,size_t n,void*parent,int save){
 GtkWidget*d=gtk_file_chooser_dialog_new(save?"Export Full Backup":"Restore Full Backup",parent,save?1:0,
  "CANCEL",RESPONSE_CANCEL,save?"SAVE":"OPEN",RESPONSE_OK,NULL);
 const char*home=getenv("HOME");
 extern gboolean gtk_file_chooser_set_current_folder(void*,const char*);
 if(home&&*home)gtk_file_chooser_set_current_folder(d,home);
 if(save){
  extern void gtk_file_chooser_set_current_name(void*,const char*);
  extern void gtk_file_chooser_set_do_overwrite_confirmation(void*,gboolean);
  gtk_file_chooser_set_current_name(d,"My-OptiPlex-full.onb");
  gtk_file_chooser_set_do_overwrite_confirmation(d,1);
 }
 int ok=0;
 if(gtk_dialog_run(d)==RESPONSE_OK){char*path=gtk_file_chooser_get_filename(d);if(path){safe_copy(out,n,path);ok=1;g_free(path);}}
 gtk_widget_destroy(d);return ok;
}
static int backup_password(void*parent,int restore,char*out,size_t n){
 GtkWidget*d=gtk_dialog_new_with_buttons(restore?"Unlock Backup":"Encrypt Backup",parent,1,
                                      "CANCEL",RESPONSE_CANCEL,restore?"RESTORE":"ENCRYPT",RESPONSE_OK,NULL);
 GtkWidget*box=gtk_dialog_get_content_area(d);GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,10);
 gtk_container_set_border_width(col,18);add(box,col,0);
 GtkWidget*note=label(restore?"Your SSH key and Moonlight pairing may be replaced. Use only on a trusted PC.":
   "Contains SSH credentials and Moonlight pairing. Keep this file private.","helper");
 gtk_label_set_line_wrap(note,1);add(col,note,0);
 GtkWidget*password=gtk_entry_new();gtk_entry_set_visibility(password,0);
 gtk_entry_set_placeholder_text(password,"Backup password (12+ characters)");add(col,password,0);
 GtkWidget*again=NULL;
 if(!restore){again=gtk_entry_new();gtk_entry_set_visibility(again,0);
  gtk_entry_set_placeholder_text(again,"Confirm password");add(col,again,0);}
 gtk_widget_show_all(d);int ok=0;
 if(gtk_dialog_run(d)==RESPONSE_OK){
  const char*pass=gtk_entry_get_text(password);
  const char*confirm=again?gtk_entry_get_text(again):pass;
  size_t z=strlen(pass);
  if(z>=12&&z<n&&!strcmp(pass,confirm)){memcpy(out,pass,z+1);ok=1;}
  else preset_alert(d,"Invalid password","Use at least 12 characters. Both passwords must match.");
 }
 gtk_widget_destroy(d);return ok;
}
static int backup_execute(int restore,const char*path,const char*password){
 if(access(BACKUP_BINARY,X_OK)!=0)return -2;
 int pipefd[2];if(pipe(pipefd)!=0)return -1;
 pid_t pid=fork();
 if(pid<0){close(pipefd[0]);close(pipefd[1]);return -1;}
 if(pid==0){
  close(pipefd[1]);dup2(pipefd[0],STDIN_FILENO);close(pipefd[0]);
  int fd=open("/dev/null",O_WRONLY);if(fd>=0){dup2(fd,STDOUT_FILENO);dup2(fd,STDERR_FILENO);close(fd);}
  execl(BACKUP_BINARY,"optiplex-now-backup",restore?"restore":"export",path,(char*)NULL);
  _exit(127);
 }
 close(pipefd[0]);size_t len=strlen(password);int ok=1;
 if(write(pipefd[1],password,len)!=(ssize_t)len||write(pipefd[1],"\n",1)!=1)ok=0;
 close(pipefd[1]);int status=0;if(waitpid(pid,&status,0)<0)return -1;
 return ok&&WIFEXITED(status)&&WEXITSTATUS(status)==0?0:-1;
}
static int full_backup_ui(void*parent,int restore){
 if(restore){
  GtkWidget*d=gtk_dialog_new_with_buttons("Confirm Restore",parent,1,"CANCEL",RESPONSE_CANCEL,"CONTINUE",RESPONSE_OK,NULL);
  GtkWidget*area=gtk_dialog_get_content_area(d);
  GtkWidget*n=label("Restore may replace SSH keys, Moonlight settings and OptiPlex preferences.\nOnly restore on a computer you own and trust.","helper");
  gtk_label_set_line_wrap(n,1);gtk_container_set_border_width(area,16);add(area,n,0);
  gtk_widget_show_all(d);int result=gtk_dialog_run(d);gtk_widget_destroy(d);if(result!=RESPONSE_OK)return 0;
 }
 char path[PATH_MAX];if(!backup_pick(path,sizeof path,parent,!restore))return 0;
 char pw[2048]={0};if(!backup_password(parent,restore,pw,sizeof pw))return 0;
 int rc=backup_execute(restore,path,pw);explicit_bzero(pw,sizeof pw);
 if(rc==0){
  if(restore){config_load();refresh();preset_alert(parent,"Backup restored","Settings restored. Restart Moonlight to load its pairing data. Tailscale still requires sign-in on this device.");}
  else preset_alert(parent,"Backup saved","Encrypted backup saved. Keep your password safe and only restore on a trusted computer.");
 }else preset_alert(parent,"Backup failed",rc==-2?"Backup helper is missing. Reinstall OptiPlex Now.":
       "Backup failed. Check file, password, and permissions. No settings were intentionally reset.");
 return rc==0;
}
static void export_full_backup(void*w,void*p){(void)w;full_backup_ui(p?p:win,0);}
static void restore_full_backup(void*w,void*p){(void)w;extern void gtk_dialog_response(void*,gint);void*parent=p?p:win;if(full_backup_ui(parent,1) && p)gtk_dialog_response(parent,RESPONSE_CANCEL);}
static void on_settings(void*w,void*p){(void)w;(void)p;
 GtkWidget*d=gtk_dialog_new_with_buttons("OptiPlex Now | Settings",win,1,"CANCEL",RESPONSE_CANCEL,"SAVE",RESPONSE_OK,NULL);
 gtk_window_set_default_size(d,510,440);
 GtkWidget*area=gtk_dialog_get_content_area(d);
 GtkWidget*scroll=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy(scroll,1,1);gtk_widget_set_vexpand(scroll,1);add(area,scroll,1);
 GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,13);gtk_container_set_border_width(col,18);gtk_container_add(scroll,col);
 add(col,label("CONNECTION","modalheading"),0);
 GtkWidget*guided=button("SETUP WIZARD","setupaction");g_signal_connect_data(guided,"clicked",(GCallback)on_wizard,NULL,NULL,0);add(col,guided,0);
 tailscale_label=label("CHECKING TAILSCALE","helper");add(col,tailscale_label,0);
 GtkWidget*gt=gtk_grid_new();gtk_grid_set_column_spacing(gt,10);gtk_grid_set_row_spacing(gt,7);add(col,gt,0);
 GtkWidget*advanced_grid=gtk_grid_new();gtk_grid_set_column_spacing(advanced_grid,10);gtk_grid_set_row_spacing(advanced_grid,7);
 GtkWidget*advanced=gtk_expander_new("ADVANCED SETTINGS");gtk_container_add(advanced,advanced_grid);
 const char*names[]={"Server IP","SSH user","Wake relay IP","Relay SSH user","Wake command","Videos URL","Music URL","Downloads URL"};
 GtkWidget*fields[8];
 for(int i=0;i<8;i++){
  GtkWidget*l=label(names[i],NULL);gtk_widget_set_size_request(l,110,-1);
  GtkWidget*dest=(i<2||i>=5)?gt:advanced_grid;int row=i<2?i:i>=5?i-3:i-2;
  gtk_grid_attach(dest,l,0,row,1,1);
  fields[i]=gtk_entry_new();gtk_entry_set_text(fields[i],cfg[i]);gtk_widget_set_hexpand(fields[i],1);gtk_grid_attach(dest,fields[i],1,row,1,1);
 }
 GtkWidget*disklabel=label("Downloads disk",NULL);
 GtkWidget*diskentry=gtk_entry_new();gtk_entry_set_text(diskentry,cfg[10]);gtk_widget_set_hexpand(diskentry,1);
 gtk_grid_attach(advanced_grid,disklabel,0,7,1,1);gtk_grid_attach(advanced_grid,diskentry,1,7,1,1);
 GtkWidget*combo=gtk_combo_box_text_new();const char*opts[]={"Default browser (automatic)","System default","Chrome Flatpak","Chrome native"};
 for(int i=0;i<4;i++)gtk_combo_box_text_append_text(combo,opts[i]);
 int which=!strcmp(cfg[8],"system")?1:!strcmp(cfg[8],"chrome-flatpak")?2:!strcmp(cfg[8],"chrome")?3:0;
 gtk_combo_box_set_active(combo,which);
 gtk_grid_attach(advanced_grid,label("Browser",NULL),0,6,1,1);
 gtk_grid_attach(advanced_grid,combo,1,6,1,1);
 GtkWidget*actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 GtkWidget*t=button("TAILSCALE","setupaction");g_signal_connect_data(t,"clicked",(GCallback)on_tail,NULL,NULL,0);add(actions,t,1);
 PairContext server_context={.relay=0},relay_context={.relay=1};
 for(int i=0;i<8;i++){server_context.inputs[i]=fields[i];relay_context.inputs[i]=fields[i];}
 server_context.parent=d;relay_context.parent=d;
 GtkWidget*s=button("PAIR SERVER","setupaction");g_signal_connect_data(s,"clicked",(GCallback)on_pair_click,&server_context,NULL,0);add(actions,s,1);
 GtkWidget*r=button("PAIR RELAY","setupaction");g_signal_connect_data(r,"clicked",(GCallback)on_pair_click,&relay_context,NULL,0);add(actions,r,1);
 add(col,actions,0);
 GtkWidget*games=button("GAMES SETUP","setupaction");
 g_signal_connect_data(games,"clicked",(GCallback)on_games_setup_from_settings,&server_context,NULL,0);add(col,games,0);
 add(col,advanced,0);
 PresetExportContext export_context={.parent=d,.disk=diskentry};
 for(int i=0;i<8;i++)export_context.fields[i]=fields[i];
 GtkWidget*export_btn=button("EXPORT MY OPTIPLEX","setupaction");
 g_signal_connect_data(export_btn,"clicked",(GCallback)export_preset,&export_context,NULL,0);add(col,export_btn,0);
 gtk_box_reorder_child(col,export_btn,2);
 GtkWidget*full_export=button("EXPORT FULL BACKUP","setupaction");
 g_signal_connect_data(full_export,"clicked",(GCallback)export_full_backup,d,NULL,0);add(col,full_export,0);
 GtkWidget*full_import=button("RESTORE FULL BACKUP","setupaction");
 g_signal_connect_data(full_import,"clicked",(GCallback)restore_full_backup,d,NULL,0);add(col,full_import,0);

 GtkWidget*hint=label("Preset has addresses, never passwords or SSH keys.","helper");add(col,hint,0);
 gtk_widget_show_all(d);
 int resp=gtk_dialog_run(d);
 if(resp==RESPONSE_OK){
   for(int i=0;i<8;i++){const char*v=gtk_entry_get_text(fields[i]);if(strchr(v,'\n')||strchr(v,'\r'))continue;safe_copy(cfg[i],512,v);}
   const char*browsers[]={"auto","system","chrome-flatpak","chrome"};int choice=gtk_combo_box_get_active(combo);
   const char*disk=gtk_entry_get_text(diskentry);
   if(safe_disk_path(disk)) safe_copy(cfg[10],512,disk);
   safe_copy(cfg[8],512,browsers[choice>=0&&choice<4?choice:0]);config_save();say("SETTINGS SAVED");refresh();
 }
 tailscale_label=NULL;gtk_widget_destroy(d);
}
/* Setup assistant. Client pairing is explicit and uses the user's own credentials. */
typedef struct {GtkWidget *assistant,*server_page,*games_page,*services_page,*host,*user,*relay,*relayuser,*wake,*ts_state,*game_state,*wolf_state,*notice,*preset_notice,*service_inputs[3]; char staged[CONFIG_COUNT][512]; int preset_loaded,closing; } Wizard;
static void wizard_validate(void*w,void*p){
 (void)w;Wizard*c=p;
 int ok=valid_host(gtk_entry_get_text(c->host))&&valid_user(gtk_entry_get_text(c->user));
 gtk_assistant_set_page_complete(c->assistant,c->server_page,ok);
 gtk_label_set_text(c->notice,"");
}
static void wizard_save(Wizard*c){
 const char*values[]={gtk_entry_get_text(c->host),gtk_entry_get_text(c->user),
                      gtk_entry_get_text(c->relay),gtk_entry_get_text(c->relayuser),gtk_entry_get_text(c->wake)};
 if(!valid_host(values[0])||!valid_user(values[1])){
   return;
 }
 for(int i=0;i<5;i++){
   if(strchr(values[i],'\n')||strchr(values[i],'\r'))return;
   safe_copy(cfg[i],512,values[i]);
 }
 if(c->preset_loaded)safe_copy(cfg[10],512,c->staged[10]);
 for(int i=0;i<3;i++)if(c->service_inputs[i]){
   const char *url=gtk_entry_get_text(c->service_inputs[i]);
   if(safe_preset_url(url))safe_copy(cfg[5+i],512,url);
 }
 /* For a fresh installation, make basic services follow the selected server. */
 if(!*cfg[6])snprintf(cfg[6],512,"http://%s:8688",cfg[0]);
 if(!*cfg[7])snprintf(cfg[7],512,"http://%s:8085",cfg[0]);
 config_save();gtk_label_set_text(c->notice,"SAVED");
}
static void wizard_service_check(void*w,void*p);
static void wizard_prepare(void*a,void*page,void*p){
 (void)a;(void)page;Wizard*c=p;
 char text[160];
 if(exists_program("tailscale")){
   char out[128]={0};char*args[]={"tailscale","ip","-4",NULL};
   if(run(args,out,sizeof out,4)==0 && strstr(out,"100."))snprintf(text,sizeof text,"TAILSCALE CONNECTED");
   else snprintf(text,sizeof text,"TAILSCALE NOT CONNECTED");
 }else snprintf(text,sizeof text,"TAILSCALE NOT INSTALLED");
 gtk_label_set_text(c->ts_state,text);
 if(c->game_state)gtk_label_set_text(c->game_state,moonlight_mode_name());
 if(page==c->services_page)wizard_service_check(NULL,c);
 if(page==c->games_page){
   if(c->wolf_state)gtk_label_set_text(c->wolf_state,"CHECKING WOLF CONNECTION...");
   /* Use the address entered in the wizard without saving partial settings. */
   safe_copy(wolf_probe_host,sizeof wolf_probe_host,gtk_entry_get_text(c->host));
   /* The server may stream even if its pairing page is unavailable; do not block setup. */
   begin_job(8);
 }
}
static void picker_selection_changed(void *combo,void *accept){
 gtk_widget_set_sensitive(accept,gtk_combo_box_get_active(combo)>=0);
}
static void find_server(Wizard*c){
 char output[65536]={0};
 char *args[]={"/usr/bin/python3","/usr/lib/optiplex-now/find-servers.py",NULL};
 if(run(args,output,sizeof output,6)!=0){
   preset_alert(c->assistant,"Find server",*output?output:"Could not list devices. Check Tailscale, or enter an address manually.");return;
 }
 GtkWidget*d=gtk_dialog_new_with_buttons("Choose your server",c->assistant,1,"Cancel",RESPONSE_CANCEL,NULL);
 GtkWidget*accept=gtk_dialog_add_button(d,"Use this device",RESPONSE_OK);
 gtk_widget_set_sensitive(accept,0);
 GtkWidget*area=gtk_dialog_get_content_area(d);gtk_container_set_border_width(area,18);
 GtkWidget*col=gtk_box_new(GTK_ORIENTATION_VERTICAL,10);add(area,col,0);
 GtkWidget*hint=label("Choose the computer running your server.\nThese are your Tailscale devices; SSH and Wolf are checked separately.","helper");
 gtk_label_set_line_wrap(hint,1);add(col,hint,0);
 GtkWidget*combo=gtk_combo_box_text_new();add(col,combo,0);
 char addresses[200][256];int count=0;char *save=NULL;
 for(char*line=strtok_r(output,"\n",&save);line&&count<200;line=strtok_r(NULL,"\n",&save)){
   char*tab=strchr(line,'\t');if(!tab)continue;*tab++=0;
   if(!valid_host(line))continue;
   safe_copy(addresses[count++],256,line);gtk_combo_box_text_append_text(combo,tab);
 }
 g_signal_connect_data(combo,"changed",(GCallback)picker_selection_changed,accept,NULL,0);
 gtk_widget_show_all(d);
 int response=gtk_dialog_run(d),selected=gtk_combo_box_get_active(combo);
 if(response==RESPONSE_OK && selected>=0 && selected<count){
   gtk_entry_set_text(c->host,addresses[selected]);
   gtk_label_set_text(c->notice,"ADDRESS FILLED. CONFIRM THE SSH USER, THEN CONTINUE.");
 }
 gtk_widget_destroy(d);
}
static void wizard_action(void*w,void*p){
 Wizard*c=p;
 extern const char* gtk_widget_get_name(void*);
 const char*n=gtk_widget_get_name(w);if(!n)n="";
 if(!strcmp(n,"w_keep")){gtk_widget_destroy(c->assistant);return;}
 else if(!strcmp(n,"w_restore")){if(full_backup_ui(c->assistant,1))gtk_widget_destroy(c->assistant);return;}
 if(!strcmp(n,"w_import")){
    char path[PATH_MAX];if(!preset_pick(path,sizeof path,c->assistant,0))return;
    char v[CONFIG_COUNT][512];
    for(int i=0;i<CONFIG_COUNT;i++)safe_copy(v[i],512,c->staged[i]);
    if(!preset_read(path,v)){
       gtk_label_set_text(c->preset_notice,"INVALID PRESET. NO CHANGES MADE.");return;
    }
    for(int i=0;i<CONFIG_COUNT;i++)safe_copy(c->staged[i],512,v[i]);
    c->preset_loaded=1;
    gtk_entry_set_text(c->host,v[0]);gtk_entry_set_text(c->user,v[1]);
    gtk_entry_set_text(c->relay,v[2]);gtk_entry_set_text(c->relayuser,v[3]);gtk_entry_set_text(c->wake,v[4]);
    for(int i=0;i<3;i++){
       gtk_entry_set_text(c->service_inputs[i],v[5+i]);
       if(service_labels[i])gtk_label_set_text(service_labels[i],*v[5+i]?"READY TO CHECK":"NOT CONFIGURED");
    }
    gtk_label_set_text(c->preset_notice,"PRESET LOADED. SERVICES WILL BE CHECKED AUTOMATICALLY.");
    return;
 }
 if(!strcmp(n,"w_pair")||!strcmp(n,"w_relay")||!strcmp(n,"w_wolf")||!strcmp(n,"w_wolfpin"))wizard_save(c);
 if(!strcmp(n,"w_find"))find_server(c);
 else if(!strcmp(n,"w_ts"))setup_tailscale();
 else if(!strcmp(n,"w_pair"))pair(0);
 else if(!strcmp(n,"w_relay"))pair(1);
 else if(!strcmp(n,"w_moonlight")){if(has_moonlight())open_moonlight();else install_moonlight();}
 else if(!strcmp(n,"w_appimage"))choose_appimage();
 else if(!strcmp(n,"w_wolf"))pair_wolf();
 else if(!strcmp(n,"w_wolfpin"))begin_job(5);
 else if(!strcmp(n,"w_profile")){
   char *args[]={"sudo","python3","/usr/lib/optiplex-now/server-profile.py",NULL};
   terminal_launch(args);
 }
 else if(!strcmp(n,"w_future")){
   GtkWidget*d=gtk_dialog_new_with_buttons("New Server",c->assistant,1,"CLOSE",RESPONSE_CANCEL,NULL);
   GtkWidget*area=gtk_dialog_get_content_area(d);GtkWidget*box=gtk_box_new(GTK_ORIENTATION_VERTICAL,10);
   gtk_container_set_border_width(box,20);add(area,box,0);
   add(box,label("NEW SERVER SETUP","modalheading"),0);
   GtkWidget*l=label("Automated server provisioning is not included yet.\nFor now, install Tailscale and SSH on the new server,\nthen use this wizard to connect.","helper");
   gtk_label_set_line_wrap(l,1);add(box,l,0);
   gtk_widget_show_all(d);gtk_dialog_run(d);gtk_widget_destroy(d);
 }
 if(c->game_state)gtk_label_set_text(c->game_state,moonlight_mode_name());
}
static GtkWidget*wizard_button(Wizard*c,GtkWidget*page,const char*title,const char*id){
 GtkWidget*b=button(title,"setupaction");gtk_widget_set_name(b,id);gtk_style_context_add_class(gtk_widget_get_style_context(b),"setupaction");
 g_signal_connect_data(b,"clicked",(GCallback)wizard_action,c,NULL,0);add(page,b,0);return b;
}
static gboolean destroy_wizard_idle(void*w){gtk_widget_destroy(w);return 0;}
static void wizard_end(void*w,void*p){Wizard*c=p;if(c->closing)return;c->closing=1;wizard_save(c);refresh();g_idle_add(destroy_wizard_idle,w);}
static void wizard_cancel(void*w,void*p){Wizard*c=p;if(c->closing)return;c->closing=1;g_idle_add(destroy_wizard_idle,w);}
static void wizard_service_check(void*w,void*p){
 (void)w;Wizard*c=p;
 if(services_inflight)return;
 Result*r=calloc(1,sizeof *r);if(!r)return;
 r->type=7;
 for(int i=0;i<3;i++){
   const char*url=gtk_entry_get_text(c->service_inputs[i]);
   if(!safe_preset_url(url)){gtk_label_set_text(service_labels[i],"INVALID URL");free(r);return;}
   safe_copy(r->service_urls[i],sizeof r->service_urls[i],url);
   gtk_label_set_text(service_labels[i],"CHECKING...");
 }
 services_inflight=1;pthread_t t;
 if(pthread_create(&t,NULL,worker,r)==0)pthread_detach(t);
 else {services_inflight=0;free(r);}
}
static void wizard_destroy(void*w,void*p){(void)w;wizard_wolf_label=NULL;for(int i=0;i<3;i++)service_labels[i]=NULL;free(p);}
static void on_wizard(void*w,void*p){(void)w;(void)p;
 Wizard*c=calloc(1,sizeof *c);if(!c)return;
 for(int i=0;i<CONFIG_COUNT;i++)safe_copy(c->staged[i],512,cfg[i]);
 GtkWidget*a=gtk_assistant_new();c->assistant=a;
 gtk_window_set_title(a,"OptiPlex Now | Setup");gtk_window_set_default_size(a,710,480);
 gtk_window_set_transient_for(a,win);gtk_window_set_modal(a,1);
 /* Page 1: keep existing device setup. No credentials or pairings are reset. */
 GtkWidget*one=gtk_box_new(GTK_ORIENTATION_VERTICAL,14);gtk_container_set_border_width(one,24);
 add(one,label("CONNECT THIS DEVICE","modalheading"),0);
 c->ts_state=label("CHECKING TAILSCALE","gameshint");add(one,c->ts_state,0);
 wizard_button(c,one,"CONNECT TAILSCALE","w_ts");
 wizard_button(c,one,"IMPORT MY OPTIPLEX","w_import");
 wizard_button(c,one,"RESTORE FULL BACKUP (TRUSTED PC)","w_restore");
 c->preset_notice=label("","helper");add(one,c->preset_notice,0);
 if(!first_run&&*cfg[0]){
    add(one,label("EXISTING CONNECTION FOUND","helper"),0);
    wizard_button(c,one,"KEEP EXISTING SETUP","w_keep");
 }
 gtk_assistant_append_page(a,one);gtk_assistant_set_page_title(a,one,"TAILSCALE");gtk_assistant_set_page_type(a,one,1);gtk_assistant_set_page_complete(a,one,1);
 /* Page 2: choose your server. All values are prefilled from saved configuration. */
 GtkWidget*two=gtk_box_new(GTK_ORIENTATION_VERTICAL,13);c->server_page=two;gtk_container_set_border_width(two,24);
 add(two,label("FIND YOUR SERVER","modalheading"),0);
 wizard_button(c,two,"FIND SERVER ON TAILSCALE","w_find");
 add(two,label("SERVER ADDRESS — CHOOSE ABOVE OR ENTER MANUALLY","helper"),0);
 c->host=gtk_entry_new();gtk_entry_set_placeholder_text(c->host,"Tailscale IP or hostname");gtk_entry_set_text(c->host,cfg[0]);add(two,c->host,0);
 add(two,label("SSH USER","helper"),0);
 c->user=gtk_entry_new();gtk_entry_set_placeholder_text(c->user,"optiplex");gtk_entry_set_text(c->user,cfg[1]);add(two,c->user,0);
 g_signal_connect_data(c->host,"changed",(GCallback)wizard_validate,c,NULL,0);
 g_signal_connect_data(c->user,"changed",(GCallback)wizard_validate,c,NULL,0);
 c->notice=label("","helper");add(two,c->notice,0);
 wizard_button(c,two,"MUSIC SERVER PROFILES (THIS PC)","w_profile");
 wizard_button(c,two,"NEW SERVER SETUP (PLANNED)","w_future");
 gtk_assistant_append_page(a,two);gtk_assistant_set_page_title(a,two,"SERVER");gtk_assistant_set_page_type(a,two,0);wizard_validate(NULL,c);
 /* Page 3: pair SSH keys once. Relay is optional. */
 GtkWidget*three=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);gtk_container_set_border_width(three,22);
 add(three,label("SECURE ACCESS","modalheading"),0);
 add(three,label("Existing SSH keys are reused.","helper"),0);
 wizard_button(c,three,"AUTHORIZE SSH KEY","w_pair");
 add(three,label("WAKE RELAY (OPTIONAL)","helper"),0);
 c->relay=gtk_entry_new();gtk_entry_set_placeholder_text(c->relay,"Relay Tailscale IP");gtk_entry_set_text(c->relay,cfg[2]);add(three,c->relay,0);
 c->relayuser=gtk_entry_new();gtk_entry_set_placeholder_text(c->relayuser,"Relay SSH user");gtk_entry_set_text(c->relayuser,cfg[3]);add(three,c->relayuser,0);
 c->wake=gtk_entry_new();gtk_entry_set_placeholder_text(c->wake,"Wake script on relay");gtk_entry_set_text(c->wake,cfg[4]);add(three,c->wake,0);
 wizard_button(c,three,"AUTHORIZE RELAY KEY","w_relay");
 gtk_assistant_append_page(a,three);gtk_assistant_set_page_title(a,three,"ACCESS");gtk_assistant_set_page_type(a,three,0);gtk_assistant_set_page_complete(a,three,1);
 /* Page 4: reuse the existing installed Moonlight, including AppImages. */
 GtkWidget*four=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);gtk_container_set_border_width(four,24);
 add(four,label("GAMES","modalheading"),0);
 c->game_state=label(moonlight_mode_name(),"gameshint");add(four,c->game_state,0);
 c->wolf_state=label("CHECKING WOLF...","gameshint");wizard_wolf_label=c->wolf_state;add(four,c->wolf_state,0);
 c->games_page=four;
 wizard_button(c,four,"OPEN / INSTALL MOONLIGHT","w_moonlight");
 wizard_button(c,four,"SELECT APPIMAGE","w_appimage");
 wizard_button(c,four,"PAIR WOLF","w_wolf");
 wizard_button(c,four,"OPEN WOLF PIN","w_wolfpin");
 gtk_assistant_append_page(a,four);gtk_assistant_set_page_title(a,four,"GAMES");gtk_assistant_set_page_type(a,four,0);gtk_assistant_set_page_complete(a,four,1);
 /* Page 5: let a fresh installation actually configure each service.
  * Do not claim the server's Wolf stream is missing merely because a URL
  * wasn't configured locally. */
 GtkWidget*five=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);c->services_page=five;gtk_container_set_border_width(five,20);
 add(five,label("SERVICES","modalheading"),0);
 add(five,label("Addresses from your preset are checked automatically.","helper"),0);
 const char*names[]={"VIDEOS URL","MUSIC URL","DOWNLOADS URL"};
 GtkWidget*rows=gtk_grid_new();gtk_grid_set_column_spacing(rows,9);gtk_grid_set_row_spacing(rows,11);add(five,rows,0);
 for(int i=0;i<3;i++){
   gtk_grid_attach(rows,label(names[i],"specname"),0,i,1,1);
   c->service_inputs[i]=gtk_entry_new();gtk_widget_set_hexpand(c->service_inputs[i],1);
   gtk_entry_set_text(c->service_inputs[i],c->staged[i+5]);
   gtk_grid_attach(rows,c->service_inputs[i],1,i,1,1);
   service_labels[i]=label(*c->staged[i+5]?"NOT CHECKED":"ADD URL","specvalue");
   gtk_grid_attach(rows,service_labels[i],2,i,1,1);
 }
 GtkWidget*check=button("CHECK SERVICES","setupaction");g_signal_connect_data(check,"clicked",(GCallback)wizard_service_check,c,NULL,0);add(five,check,0);
 gtk_assistant_append_page(a,five);gtk_assistant_set_page_title(a,five,"SERVICES");gtk_assistant_set_page_type(a,five,0);gtk_assistant_set_page_complete(a,five,1);
 /* Page 6: nothing else needed for existing clients. */
 GtkWidget*six=gtk_box_new(GTK_ORIENTATION_VERTICAL,15);gtk_container_set_border_width(six,24);
 add(six,label("READY","modalheading"),0);
 add(six,label("Saved settings carry over between updates.","helper"),0);
 add(six,label("Open System Info from the dashboard for live hardware details.","helper"),0);
 gtk_assistant_append_page(a,six);gtk_assistant_set_page_title(a,six,"FINISH");gtk_assistant_set_page_type(a,six,2);gtk_assistant_set_page_complete(a,six,1);
 g_signal_connect_data(a,"prepare",(GCallback)wizard_prepare,c,NULL,0);
 g_signal_connect_data(a,"apply",(GCallback)wizard_end,c,NULL,0);
 g_signal_connect_data(a,"cancel",(GCallback)wizard_cancel,c,NULL,0);
 g_signal_connect_data(a,"close",(GCallback)wizard_end,c,NULL,0);
 g_signal_connect_data(a,"destroy",(GCallback)wizard_destroy,c,NULL,0);
 gtk_widget_show_all(a);
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
 if(tray_icon)gtk_status_icon_set_visible(tray_icon,0);
 if(app_indicator && app_indicator_set_status_fn)app_indicator_set_status_fn(app_indicator,0);
 gtk_main_quit();
}
static void tray_toggle(void *icon,void *data){
 (void)icon;(void)data;
 if(gtk_widget_get_visible(win))gtk_widget_hide(win);
 else tray_show_window();
}
static void tray_action(void *widget,void *data){
 (void)widget;
 int action=(int)(long)data;
 if(action==10)tray_show_window();
 else if(action==11){tray_show_window();on_settings(NULL,NULL);}
 else if(action==12){tray_show_window();on_system_info(NULL,NULL);}
 else if(action==13)tray_quit(NULL,NULL);
 else if(action==14)on_restart_streaming(NULL,NULL);
 else {
   if(action==0 && !has_moonlight())tray_show_window();
   on_tile(NULL,(void*)(long)action);
 }
}
static void tray_menu_item(const char*caption,int action){
 GtkWidget *item=gtk_menu_item_new_with_label(caption);
 g_signal_connect_data(item,"activate",(GCallback)tray_action,(void*)(long)action,NULL,0);
 gtk_menu_shell_append(tray_menu,item);
}
static void tray_separator(void){
 GtkWidget*item=gtk_separator_menu_item_new();gtk_menu_shell_append(tray_menu,item);
}
static void tray_popup(void *icon,guint button,guint when,void *data){
 (void)data;
 gtk_menu_popup(tray_menu,NULL,NULL,(void*)gtk_status_icon_position_menu,icon,button,when);
}
static void tray_initialize(void){
 tray_menu=gtk_menu_new();
 tray_menu_item("Open OptiPlex Now",10);tray_separator();
 tray_menu_item("Games  |  Steam",0);
 tray_menu_item("Desktop  |  XFCE",6);
 tray_menu_item("Torrents  |  VueTorrent",7);
 tray_menu_item("Videos",1);
 tray_menu_item("Music",2);
 tray_menu_item("Files",3);
 tray_menu_item("Downloads",4);
 tray_menu_item("Terminal",5);
 tray_separator();
 tray_menu_item("Restart streaming service…",14);
 tray_separator();
 tray_menu_item("System Info",12);
 tray_menu_item("Settings",11);
 tray_separator();tray_menu_item("Quit",13);
 gtk_widget_show_all(tray_menu);

 /* Only publish an SNI icon when a desktop is actually listening for it. */
 if(status_notifier_watcher_present()){
   indicator_library=dlopen("libayatana-appindicator3.so.1",RTLD_LAZY|RTLD_LOCAL);
   if(!indicator_library)indicator_library=dlopen("libappindicator3.so.1",RTLD_LAZY|RTLD_LOCAL);
   if(indicator_library){
     void*(*new_indicator)(const char*,const char*,int)=dlsym(indicator_library,"app_indicator_new");
     app_indicator_set_status_fn=dlsym(indicator_library,"app_indicator_set_status");
     app_indicator_set_menu_fn=dlsym(indicator_library,"app_indicator_set_menu");
     if(new_indicator && app_indicator_set_status_fn && app_indicator_set_menu_fn){
       app_indicator=new_indicator("optiplex-now","optiplex-now-tray",0);
       if(app_indicator){
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
 gtk_status_icon_set_tooltip_text(tray_icon,"OptiPlex Now");
 g_signal_connect_data(tray_icon,"activate",(GCallback)tray_toggle,NULL,NULL,0);
 g_signal_connect_data(tray_icon,"popup-menu",(GCallback)tray_popup,NULL,NULL,0);
 gtk_status_icon_set_visible(tray_icon,1);
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
 if(!claim_instance())return 0;
 fonts_register();gtk_init(&argc,&argv);gtk_window_set_default_icon_name("optiplex-now");config_load();
 GtkCssProvider*cp=gtk_css_provider_new();gtk_css_provider_load_from_data(cp,CSS,-1,NULL);
 gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),cp,GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
 win=gtk_window_new(0);gtk_window_set_title(win,"OptiPlex Now");gtk_window_set_default_size(win,660,505);
 gtk_window_set_icon_name(win,"optiplex-now");gtk_window_set_position(win,1);
 g_signal_connect_data(win,"destroy",(GCallback)on_window_destroy,NULL,NULL,0);
 g_signal_connect_data(win,"delete-event",(GCallback)close_to_tray,NULL,NULL,0);
 g_signal_connect_data(win,"window-state-event",(GCallback)minimize_to_tray,NULL,NULL,0);
 g_signal_connect_data(win,"size-allocate",(GCallback)on_size,NULL,NULL,0);
 GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy(sc,1,1);gtk_container_add(win,sc);
 GtkWidget*shell=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(shell,"shell");gtk_container_add(sc,shell);
 GtkWidget*body=gtk_box_new(GTK_ORIENTATION_VERTICAL,9);gtk_container_set_border_width(body,14);add(shell,body,1);
 GtkWidget*head=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,15);add(body,head,0);
 GtkWidget*brandcol=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_hexpand(brandcol,1);add(head,brandcol,1);
 model_heading=label(current_model(),"title");
 gtk_label_set_ellipsize(model_heading,3);
 extern void gtk_label_set_max_width_chars(void*,int);
 gtk_label_set_max_width_chars(model_heading,22);
 add(brandcol,model_heading,0);
 GtkWidget*right=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);gtk_widget_set_valign(right,GTK_ALIGN_CENTER);add(head,right,0);
 GtkWidget*tools=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);add(right,tools,0);
 indicator=label("● CHECKING","state");add(tools,indicator,0);
 GtkWidget*sys=button("SYSTEM INFO","setting");g_signal_connect_data(sys,"clicked",(GCallback)on_system_info,NULL,NULL,0);add(tools,sys,0);
 GtkWidget*sett=button("SETTINGS","setting");g_signal_connect_data(sett,"clicked",(GCallback)on_settings,NULL,NULL,0);add(tools,sett,0);
 status_detail=label("","detail");add(right,status_detail,0);
 GtkWidget*rule=gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);gtk_widget_set_name(rule,"rule");gtk_widget_set_size_request(rule,-1,1);add(body,rule,0);
 GtkWidget*metrics=gtk_grid_new();gtk_grid_set_column_homogeneous(metrics,1);gtk_grid_set_column_spacing(metrics,8);add(body,metrics,0);
 metric_cpu=label("CPU   --","metric");metric_gpu=label("GPU   --","metric");
 gtk_grid_attach(metrics,metric_cpu,0,0,1,1);gtk_grid_attach(metrics,metric_gpu,1,0,1,1);
 GtkWidget*diskbox=gtk_box_new(GTK_ORIENTATION_VERTICAL,3);gtk_widget_set_name(diskbox,"drivemetric");
 GtkWidget*diskhead=label("STORAGE","storagehead");add(diskbox,diskhead,0);
 drive_combo=gtk_combo_box_text_new();gtk_widget_set_name(drive_combo,"drivecombo");gtk_widget_set_hexpand(drive_combo,1);
 gtk_combo_box_text_append_text(drive_combo,"Checking drives...");gtk_combo_box_set_active(drive_combo,0);
 g_signal_connect_data(drive_combo,"changed",(GCallback)on_drive_changed,NULL,NULL,0);add(diskbox,drive_combo,0);
 metric_free=label("FREE  --","drivefree");add(diskbox,metric_free,0);
 gtk_grid_attach(metrics,diskbox,2,0,1,1);
 grid=gtk_grid_new();gtk_grid_set_column_homogeneous(grid,1);gtk_grid_set_row_spacing(grid,7);gtk_grid_set_column_spacing(grid,7);
 gtk_widget_set_hexpand(grid,1);add(body,grid,0);
 const char *names[]={"GAMES","VIDEOS","MUSIC","FILES","DOWNLOADS","TERMINAL","DESKTOP","TORRENTS"};
 for(int i=0;i<8;i++){tiles[i]=button(names[i],"tile");g_signal_connect_data(tiles[i],"clicked",(GCallback)on_tile,(void*)(long)i,NULL,0);}
 GtkWidget*sec=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);add(sec,label("POWER","section"),1);add(body,sec,0);
 power_grid=gtk_grid_new();gtk_grid_set_column_spacing(power_grid,7);gtk_grid_set_row_spacing(power_grid,7);
 gtk_grid_set_column_homogeneous(power_grid,1);add(body,power_grid,0);
 const char*pow_names[]={"WAKE","SLEEP","RESTART","SHUTDOWN"};
 for(int i=0;i<4;i++){powers[i]=button(pow_names[i],i==3?"danger":"power");g_signal_connect_data(powers[i],"clicked",(GCallback)on_power,(void*)(long)i,NULL,0);}
 footer=label("","footer");add(body,footer,0);
 reflow(660);
 /* Initialize the tray before showing the window to avoid login flicker. */
 tray_initialize();
 if(!start_in_tray || first_run)gtk_widget_show_all(win);
 else g_timeout_add(1800,initial_tray_check,NULL);
 g_timeout_add(300,reopen_check,NULL);
 g_timeout_add(15000,periodic,NULL);refresh();
 if(first_run)g_idle_add(first_setup,NULL); /* first run setup */
 gtk_main();return 0;
}
