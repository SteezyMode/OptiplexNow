/* Optional Bruiser Music native library browser (pre-player vertical slice).
 * The goal is a familiar first-party library UI without copying DroppedNeedle
 * admin pages or storing its administrator credentials. All requests are async.
 * Playback is intentionally not claimed until stream/queue/tray tests pass.
 */
#define _GNU_SOURCE
#include "ui_music.h"
#include "config.h"
#include <gio/gio.h>
#include <string.h>

typedef struct {
 GtkWidget *root, *status, *heading, *list, *user, *password, *search;
 char *username, *app_password;
 gboolean busy, closing;
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
 wipe_free(view->app_password);
 view->app_password=NULL;
}

static void music_view_free(gpointer data){
 MusicView *view=data;
 wipe_free(view->app_password);
 g_free(view->username);
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
 }else{
  status_set(view,"Track playback is the next integration stage. Library browsing is available now.");
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
 g_signal_connect(button,"clicked",G_CALLBACK(music_item_clicked),button);
 gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1);
}

static int render_rows(MusicView *view,const char *output){
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
 const gchar *argv[]={"/usr/bin/python3",helper,cfg[6],operation,
                      value && *value?value:NULL,"--format=rows","--auth-format=form",NULL};
 /* Avoid a NULL gap (the helper needs no arbitrary value for browse calls). */
 const gchar *without_value[]={"/usr/bin/python3",helper,cfg[6],operation,
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

static void music_connect(GtkWidget *unused,gpointer data){
 (void)unused;
 MusicView *view=data;
 if(view->busy || view->closing)return;
 const char *entered=gtk_entry_get_text(GTK_ENTRY(view->password));
 if(!entered || !*entered){
  status_set(view,"Enter your user app password from DroppedNeedle.");
  return;
 }
 wipe_free(view->app_password);
 view->app_password=g_strdup(entered);
 g_free(view->username);
 view->username=g_strdup(gtk_entry_get_text(GTK_ENTRY(view->user)));
 gtk_entry_set_text(GTK_ENTRY(view->password),"");
 query_start(view,"albums",NULL,"Your albums");
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
                           void (*open_settings)(void *, void *)){
 MusicView *view=g_new0(MusicView,1);
 view->open_url=open_url;
 view->open_settings=open_settings;
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
 gtk_box_pack_start(GTK_BOX(view->root),connect,FALSE,FALSE,0);

 view->status=gtk_label_new("Connect with a dedicated music app password. Nothing is saved to disk.");
 gtk_label_set_xalign(GTK_LABEL(view->status),0);
 gtk_label_set_ellipsize(GTK_LABEL(view->status),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(view->root),view->status,FALSE,FALSE,0);

 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 gtk_widget_set_vexpand(content,TRUE);
 gtk_box_pack_start(GTK_BOX(view->root),content,TRUE,TRUE,0);
 GtkWidget *sidebar=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
 gtk_widget_set_size_request(sidebar,100,-1);
 for(int i=0;i<3;i++){
  const char *ops[]={"albums","artists","playlists"};
  const char *titles[]={"Albums","Artists","Playlists"};
  GtkWidget *b=music_button(titles[i]);
  g_object_set_data(G_OBJECT(b),"music-operation",(gpointer)ops[i]);
  g_object_set_data(G_OBJECT(b),"music-heading",(gpointer)titles[i]);
  g_signal_connect(b,"clicked",G_CALLBACK(music_nav),view);
  gtk_box_pack_start(GTK_BOX(sidebar),b,FALSE,FALSE,0);
 }
 GtkWidget *settings=music_button("Settings");
 g_signal_connect(settings,"clicked",G_CALLBACK(music_settings),view);
 gtk_box_pack_end(GTK_BOX(sidebar),settings,FALSE,FALSE,0);
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
 view->heading=gtk_label_new("Your library");
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
 gtk_widget_show_all(view->root);
 return view->root;
}
