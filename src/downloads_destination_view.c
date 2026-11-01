/* Inline, owner-only folder browser and explicit Add. No shell, passwords,
 * direct WebUI endpoint, extra window, host absolute path or media organizer.
 * Each browse/add is revalidated by the restricted host-side owner broker.
 */
#include "downloads_destination_view.h"
#include <gio/gio.h>
#include <glib/gstdio.h>
#include <string.h>

typedef struct {
 gchar *host,*user,*root,*relative;
} SavedPlace;
typedef struct {
 GtkWidget *view,*roots,*folders,*folder_scroll,*filter,*path,*status,*up,*add;
 GtkWidget *new_folder,*places_combo,*pin_place;
 gchar *host,*user,*helper,*root,*relative,*magnet,*pending_folder;
 GPtrArray *places,*recents;
 gboolean running,loading_roots,loading_places,folder_valid,auto_pin_created;
 void (*on_added)(gpointer);
 gpointer added_data;
} Picker;
typedef struct {
 GtkWidget *view;
 GSubprocess *proc;
 gchar *host,*user,*root,*relative;
 char action;
} Job;
static Picker *state(GtkWidget *view){
 return view?g_object_get_data(G_OBJECT(view),"now-destination-state"):NULL;
}
static void free_place(gpointer data){
 SavedPlace *p=data;
 if(p){g_free(p->host);g_free(p->user);
       g_free(p->root);g_free(p->relative);g_free(p);}
}
static void free_state(gpointer data){
 Picker *s=data;
 g_free(s->host);g_free(s->user);g_free(s->helper);
 g_free(s->root);g_free(s->relative);g_free(s->magnet);
 g_free(s->pending_folder);
 if(s->places)g_ptr_array_unref(s->places);
 if(s->recents)g_ptr_array_unref(s->recents);
 g_free(s);
}
static void clear_folder_buttons(Picker *s){
 GList *children=gtk_container_get_children(GTK_CONTAINER(s->folders));
 for(GList *at=children;at;at=at->next)
   gtk_widget_destroy(GTK_WIDGET(at->data));
 g_list_free(children);
}
/* Filter only already-authorized folder names; nothing typed here is sent
 * to the server, and a match is still revalidated on the host when opened. */
static void filter_folder_buttons(Picker *s){
 if(!s || !s->filter || !s->folders)return;
 const char *query=gtk_entry_get_text(GTK_ENTRY(s->filter));
 gchar *needle=g_utf8_casefold(query,-1);
 GList *buttons=gtk_container_get_children(GTK_CONTAINER(s->folders));
 for(GList *it=buttons;it;it=it->next){
   GtkWidget *button=GTK_WIDGET(it->data);
   const char *name=gtk_button_get_label(GTK_BUTTON(button));
   gchar *folded=g_utf8_casefold(name?name:"",-1);
   gtk_widget_set_visible(button,!*needle || strstr(folded,needle)!=NULL);
   g_free(folded);
 }
 g_list_free(buttons);g_free(needle);
}
static void on_filter_changed(GtkEditable *entry,gpointer data){
 (void)entry;
 Picker *s=state(GTK_WIDGET(data));
 filter_folder_buttons(s);
 if(s && s->folder_scroll){
   GtkAdjustment *adj=gtk_scrolled_window_get_vadjustment(
                         GTK_SCROLLED_WINDOW(s->folder_scroll));
   if(adj)gtk_adjustment_set_value(adj,gtk_adjustment_get_lower(adj));
 }
}
static gboolean safe_name(const char *s){
 if(!s || !*s || !g_utf8_validate(s,-1,NULL) ||
    g_utf8_strlen(s,-1)>160 || strchr(s,'/') ||
    !strcmp(s,".") || !strcmp(s,".."))return FALSE;
 for(const unsigned char *p=(const unsigned char *)s;*p;p++)
   if(*p<32 || *p==127)return FALSE;
 return TRUE;
}
static gboolean safe_root(const char *value){
 if(!value || !*value || strlen(value)>32 ||
    !(value[0]>='a' && value[0]<='z'))return FALSE;
 for(const unsigned char *p=(const unsigned char *)value;*p;p++)
   if(!g_ascii_islower(*p) && !g_ascii_isdigit(*p) &&
      *p!='_' && *p!='-')return FALSE;
 return TRUE;
}
static gboolean safe_relative(const char *value){
 if(!value || strlen(value)>512)return FALSE;
 if(!*value)return TRUE;
 gchar **parts=g_strsplit(value,"/",-1);
 gboolean ok=TRUE;
 for(guint i=0;parts[i];i++)
   if(i>=12 || !safe_name(parts[i])){ok=FALSE;break;}
 g_strfreev(parts);
 return ok;
}
/* Saved places are bookmarks scoped to this client's approved root IDs and
 * relative folders, never raw host paths. Every use re-runs owner browse. */
#define MAX_SAVED_PLACES 24
#define MAX_RECENT_PLACES 8
static gboolean valid_bookmark_host(const gchar *host){
 if(!host || !*host || strlen(host)>253 || host[0]=='-')return FALSE;
 for(const gchar *p=host;*p;p++)
   if(!g_ascii_isalnum(*p) && *p!='.' && *p!=':' && *p!='-')
     return FALSE;
 return TRUE;
}
static gboolean valid_bookmark_user(const gchar *user){
 if(!user || !*user || strlen(user)>32 ||
    !(g_ascii_isalpha(user[0]) || user[0]=='_'))return FALSE;
 for(const gchar *p=user;*p;p++)
   if(!g_ascii_isalnum(*p) && *p!='_' && *p!='-')return FALSE;
 return TRUE;
}
static gboolean same_server(Picker *s,SavedPlace *p){
 return p && !g_strcmp0(s->host,p->host) &&
             !g_strcmp0(s->user,p->user);
}
static gchar *places_path(void){
 return g_build_filename(g_get_user_config_dir(),"optiplex-now",
                         "download-places.ini",NULL);
}
static void refresh_place_choices(Picker *s){
 s->loading_places=TRUE;
 gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(s->places_combo));
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->places_combo),"",
                           "★ FAVORITES / ↺ RECENT LOCATIONS");
 for(guint kind=0;kind<2;kind++){
   GPtrArray *items=kind==0?s->places:s->recents;
   for(guint i=0;i<items->len;i++){
     SavedPlace *p=g_ptr_array_index(items,i);
     if(!same_server(s,p))continue;
     gchar *label=g_strdup_printf("%s  %s / %s",
          kind==0?"★ Favorite":"↺ Recent",p->root,
          *p->relative?p->relative:"(root)");
     gchar *id=g_strdup_printf("%c%u",kind==0?'f':'r',i);
     gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->places_combo),id,label);
     g_free(id);g_free(label);
   }
 }
 gtk_combo_box_set_active(GTK_COMBO_BOX(s->places_combo),0);
 s->loading_places=FALSE;
}
static gboolean store_places(Picker *s){
 gchar *file=places_path();
 gchar *directory=g_path_get_dirname(file);
 gboolean ok=FALSE;
 if(g_mkdir_with_parents(directory,0700)==0){
   GKeyFile *data=g_key_file_new();
   for(guint kind=0;kind<2;kind++){
     GPtrArray *items=kind==0?s->places:s->recents;
     for(guint i=0;i<items->len;i++){
       SavedPlace *p=g_ptr_array_index(items,i);
       gchar *group=g_strdup_printf("%s%u",kind==0?"place":"recent",i);
       g_key_file_set_string(data,group,"host",p->host);
       g_key_file_set_string(data,group,"user",p->user);
       g_key_file_set_string(data,group,"root",p->root);
       g_key_file_set_string(data,group,"relative",p->relative);
       g_free(group);
     }
   }
   gsize size=0;
   gchar *raw=g_key_file_to_data(data,&size,NULL);
   if(raw && size<=32768)
     ok=g_file_set_contents(file,raw,size,NULL);
   g_free(raw);g_key_file_unref(data);
 }
 g_free(directory);g_free(file);
 return ok;
}
static void load_places(Picker *s){
 gchar *file=places_path(),*raw=NULL;
 gsize size=0;
 if(g_file_get_contents(file,&raw,&size,NULL) && size<=32768){
   GKeyFile *data=g_key_file_new();
   if(g_key_file_load_from_data(data,raw,size,G_KEY_FILE_NONE,NULL)){
     for(guint kind=0;kind<2;kind++){
       GPtrArray *items=kind==0?s->places:s->recents;
       guint bound=kind==0?MAX_SAVED_PLACES:MAX_RECENT_PLACES;
       for(guint i=0;i<bound;i++){
         gchar *group=g_strdup_printf("%s%u",kind==0?"place":"recent",i);
         gchar *host=g_key_file_get_string(data,group,"host",NULL);
         gchar *user=g_key_file_get_string(data,group,"user",NULL);
         gchar *root=g_key_file_get_string(data,group,"root",NULL);
         gchar *relative=g_key_file_get_string(data,group,"relative",NULL);
         if(valid_bookmark_host(host) && valid_bookmark_user(user) &&
            safe_root(root) && safe_relative(relative)){
           SavedPlace *p=g_new0(SavedPlace,1);
           p->host=g_strdup(host);p->user=g_strdup(user);
           p->root=g_strdup(root);p->relative=g_strdup(relative);
           g_ptr_array_add(items,p);
         }
         g_free(host);g_free(user);g_free(root);g_free(relative);g_free(group);
       }
     }
   }
   g_key_file_unref(data);
 }
 g_free(raw);g_free(file);
 refresh_place_choices(s);
}
static gboolean remember_current_place(Picker *s){
 if(!s || !s->folder_valid || !valid_bookmark_host(s->host) ||
    !valid_bookmark_user(s->user) || !safe_root(s->root) ||
    !safe_relative(s->relative))return FALSE;
 for(guint i=0;i<s->places->len;i++){
   SavedPlace *p=g_ptr_array_index(s->places,i);
   if(same_server(s,p) && !strcmp(p->root,s->root) &&
      !strcmp(p->relative,s->relative))
     return TRUE;
 }
 if(s->places->len>=MAX_SAVED_PLACES)return FALSE;
 SavedPlace *p=g_new0(SavedPlace,1);
 p->host=g_strdup(s->host);p->user=g_strdup(s->user);
 p->root=g_strdup(s->root);p->relative=g_strdup(s->relative);
 g_ptr_array_add(s->places,p);
 refresh_place_choices(s);
 return store_places(s);
}
static gint current_favorite(Picker *s){
 if(!s || !s->root || !s->relative)return -1;
 for(guint i=0;i<s->places->len;i++){
   SavedPlace *p=g_ptr_array_index(s->places,i);
   if(same_server(s,p) && !strcmp(p->root,s->root) &&
      !strcmp(p->relative,s->relative))return (gint)i;
 }
 return -1;
}
static gboolean record_recent_place(Picker *s){
 /* Only a successfully submitted torrent becomes Recent. No default. */
 if(!s || !valid_bookmark_host(s->host) || !valid_bookmark_user(s->user) ||
    !safe_root(s->root) || !safe_relative(s->relative))return FALSE;
 for(guint i=0;i<s->recents->len;i++){
   SavedPlace *p=g_ptr_array_index(s->recents,i);
   if(same_server(s,p) && !strcmp(p->root,s->root) &&
      !strcmp(p->relative,s->relative)){
     g_ptr_array_remove_index(s->recents,i);
     break;
   }
 }
 SavedPlace *p=g_new0(SavedPlace,1);
 p->host=g_strdup(s->host);p->user=g_strdup(s->user);
 p->root=g_strdup(s->root);p->relative=g_strdup(s->relative);
 g_ptr_array_insert(s->recents,0,p);
 while(s->recents->len>MAX_RECENT_PLACES)
   g_ptr_array_remove_index(s->recents,s->recents->len-1);
 refresh_place_choices(s);
 return store_places(s);
}
static gboolean has_places_for_host(Picker *s){
 for(guint kind=0;kind<2;kind++){
   GPtrArray *items=kind==0?s->places:s->recents;
   for(guint i=0;i<items->len;i++)
     if(same_server(s,g_ptr_array_index(items,i)))return TRUE;
 }
 return FALSE;
}
static void button_states(Picker *s){
 gtk_widget_set_sensitive(s->add,!s->running && s->folder_valid &&
                          s->magnet && s->root);
 gtk_widget_set_sensitive(s->up,!s->running && s->relative && *s->relative);
 gtk_widget_set_sensitive(s->roots,!s->running);
 gtk_widget_set_sensitive(s->new_folder,!s->running && s->folder_valid);
 gtk_widget_set_sensitive(s->pin_place,!s->running && s->folder_valid);
 gtk_button_set_label(GTK_BUTTON(s->pin_place),
                      current_favorite(s)>=0?"★ Favorited":"☆ Favorite");
 gtk_widget_set_sensitive(s->places_combo,!s->running && has_places_for_host(s));
}
static void start(Picker *s,char action);
static void on_save_place(GtkButton *unused,gpointer data){
 (void)unused;
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->running || !s->folder_valid)return;
 gint old=current_favorite(s);
 gboolean ok=FALSE;
 if(old>=0){
   g_ptr_array_remove_index(s->places,(guint)old);
   refresh_place_choices(s);
   ok=store_places(s);
 }else ok=remember_current_place(s);
 gtk_label_set_text(GTK_LABEL(s->status),ok ?
   (old>=0?"Favorite removed.":"Location saved to Favorites.") :
   "Unable to change Favorites. Check local permissions or limit.");
 button_states(s);
}
static void on_place_selected(GtkComboBox *combo,gpointer data){
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->loading_places || s->running)return;
 const gchar *id=gtk_combo_box_get_active_id(combo);
 if(!id || (id[0]!='f' && id[0]!='r')){button_states(s);return;}
 GPtrArray *items=id[0]=='f'?s->places:s->recents;
 gchar *end=NULL;
 guint64 index=g_ascii_strtoull(id+1,&end,10);
 if(!end || *end || index>=items->len)return;
 SavedPlace *place=g_ptr_array_index(items,(guint)index);
 if(!same_server(s,place) || !safe_root(place->root) ||
    !safe_relative(place->relative))return;
 s->loading_roots=TRUE;
 gboolean available=gtk_combo_box_set_active_id(GTK_COMBO_BOX(s->roots),place->root);
 s->loading_roots=FALSE;
 if(!available){
   gtk_label_set_text(GTK_LABEL(s->status),
      "Saved drive is no longer approved for downloads.");
   button_states(s);return;
 }
 g_free(s->root);s->root=g_strdup(place->root);
 g_free(s->relative);s->relative=g_strdup(place->relative);
 start(s,'b'); /* Always revalidate through owner broker. */
}
static void on_new_folder(GtkButton *unused,gpointer data){
 (void)unused;
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->running || !s->folder_valid || !s->root)return;
 GtkWidget *parent=gtk_widget_get_toplevel(s->view);
 GtkWidget *dialog=gtk_dialog_new_with_buttons("CREATE DOWNLOAD FOLDER",
    GTK_IS_WINDOW(parent)?GTK_WINDOW(parent):NULL,
    GTK_DIALOG_MODAL|GTK_DIALOG_DESTROY_WITH_PARENT,
    "CANCEL",GTK_RESPONSE_CANCEL,"CREATE FOLDER",GTK_RESPONSE_ACCEPT,NULL);
 gtk_window_set_default_size(GTK_WINDOW(dialog),420,-1);
 GtkWidget *area=gtk_dialog_get_content_area(GTK_DIALOG(dialog));
 GtkWidget *explain=gtk_label_new(
   "Create a folder inside the selected approved download drive.");
 gtk_label_set_line_wrap(GTK_LABEL(explain),TRUE);
 gtk_label_set_xalign(GTK_LABEL(explain),0);
 gtk_box_pack_start(GTK_BOX(area),explain,FALSE,FALSE,7);
 GtkWidget *entry=gtk_entry_new();
 gtk_entry_set_max_length(GTK_ENTRY(entry),160);
 gtk_entry_set_placeholder_text(GTK_ENTRY(entry),"Games");
 gtk_box_pack_start(GTK_BOX(area),entry,FALSE,FALSE,6);
 gtk_widget_show_all(dialog);
 gint choice=gtk_dialog_run(GTK_DIALOG(dialog));
 gchar *name=choice==GTK_RESPONSE_ACCEPT ?
               g_strdup(gtk_entry_get_text(GTK_ENTRY(entry))):NULL;
 gtk_widget_destroy(dialog);
 if(!name)return;
 gchar *next=*s->relative ?
       g_strconcat(s->relative,"/",name,NULL):g_strdup(name);
 gboolean valid=safe_name(name) && !strchr(name,'\\') &&
                safe_relative(next);
 g_free(next);
 if(!valid){
   gtk_label_set_text(GTK_LABEL(s->status),
     "Use one folder name (such as Games), without /, \\, or ..");
   g_free(name);return;
 }
 g_free(s->pending_folder);s->pending_folder=name;
 start(s,'m');
}
static void on_folder_clicked(GtkButton *button,gpointer data){
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->running || !s->root)return;
 const char *folder=gtk_button_get_label(button);
 if(!safe_name(folder))return;
 gchar *next=(*s->relative) ? g_strconcat(s->relative,"/",folder,NULL) :
                             g_strdup(folder);
 g_free(s->relative);s->relative=next;
 start(s,'b');
}
static gboolean read_response(Picker *s,char action,char *wire){
 if(!wire || !*wire || strlen(wire)>32768 ||
    !g_utf8_validate(wire,-1,NULL))return FALSE;
 if(action=='m')return !strcmp(wire,"CREATED");
 if(action=='a'){
   if(strcmp(wire,"SUBMITTED"))return FALSE;
   record_recent_place(s);
   gtk_label_set_text(GTK_LABEL(s->status),"Torrent submitted to selected folder.");
   g_clear_pointer(&s->magnet,g_free);
   s->folder_valid=FALSE;
   gtk_widget_hide(s->view);
   if(s->on_added)s->on_added(s->added_data);
   return TRUE;
 }
 gchar **lines=g_strsplit(wire,"\n",-1);
 gboolean ok=TRUE;
 guint count=0;
 if(action=='r'){
   if(strcmp(lines[0],"ROOTS"))ok=FALSE;
   for(guint i=1;ok && lines[i];i++){
     gchar **fields=g_strsplit(lines[i],"\t",-1);
     if(++count>12 || g_strv_length(fields)!=3 ||
        strcmp(fields[0],"ROOT") || !safe_root(fields[1]) ||
        !safe_name(fields[2]))ok=FALSE;
     g_strfreev(fields);
   }
   if(ok && count==0)ok=FALSE;
   if(ok){
     s->loading_roots=TRUE;
     gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(s->roots));
     for(guint i=1;lines[i];i++){
       gchar **fields=g_strsplit(lines[i],"\t",-1);
       gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->roots),
                                 fields[1],fields[2]);
       g_strfreev(fields);
     }
     gtk_combo_box_set_active(GTK_COMBO_BOX(s->roots),0);
     s->loading_roots=FALSE;
   }
 }else if(action=='b'){
   gchar **fields=g_strsplit(lines[0],"\t",-1);
   if(g_strv_length(fields)!=3 || strcmp(fields[0],"FOLDERS") ||
      !safe_root(fields[1]) || !safe_relative(fields[2]) ||
      g_strcmp0(fields[1],s->root) ||
      g_strcmp0(fields[2],s->relative))ok=FALSE;
   g_strfreev(fields);
   for(guint i=1;ok && lines[i];i++){
     gchar **part=g_strsplit(lines[i],"\t",-1);
     if(++count>100 || g_strv_length(part)!=2 ||
        strcmp(part[0],"FOLDER") || !safe_name(part[1]))ok=FALSE;
     g_strfreev(part);
   }
   if(ok){
     clear_folder_buttons(s);
     for(guint i=1;lines[i];i++){
       gchar **part=g_strsplit(lines[i],"\t",-1);
       GtkWidget *button=gtk_button_new_with_label(part[1]);
       gtk_style_context_add_class(gtk_widget_get_style_context(button),"flat");
       gtk_widget_set_tooltip_text(button,part[1]);
       GtkWidget *folder_icon=gtk_image_new_from_icon_name("folder",
                                                          GTK_ICON_SIZE_MENU);
       gtk_button_set_image(GTK_BUTTON(button),folder_icon);
       gtk_button_set_always_show_image(GTK_BUTTON(button),TRUE);
       gtk_widget_set_halign(button,GTK_ALIGN_FILL);
       g_signal_connect(button,"clicked",G_CALLBACK(on_folder_clicked),s->view);
       gtk_box_pack_start(GTK_BOX(s->folders),button,FALSE,FALSE,1);
       g_strfreev(part);
     }
     /* Every folder change starts with the full directory. A search for
      * "Horror" in Movies must not silently hide folders inside Horror. */
     gtk_entry_set_text(GTK_ENTRY(s->filter),"");
     gtk_widget_show_all(s->folders);
     if(s->folder_scroll){
       GtkAdjustment *adj=gtk_scrolled_window_get_vadjustment(
                             GTK_SCROLLED_WINDOW(s->folder_scroll));
       if(adj)gtk_adjustment_set_value(adj,gtk_adjustment_get_lower(adj));
     }
     gchar *title=g_strdup_printf("%s / %s",s->root,s->relative && *s->relative ?
                                    s->relative : "(root)");
     gtk_label_set_text(GTK_LABEL(s->path),title);
     g_free(title);
     gtk_label_set_text(GTK_LABEL(s->status),
       "Open a folder or choose a Favorite / Recent location, then Add Torrent.");
     s->folder_valid=TRUE;
     if(s->auto_pin_created){
       s->auto_pin_created=FALSE;
       if(remember_current_place(s))
         gtk_label_set_text(GTK_LABEL(s->status),
           "New download folder created and saved as a location.");
     }
   }
 }else ok=FALSE;
 g_strfreev(lines);
 return ok;
}
static void finished(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 Job *job=data;
 Picker *s=state(job->view);
 gchar *out=NULL;
 GError *err=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(job->proc,res,&out,NULL,&err);
 if(s && !g_strcmp0(s->host,job->host) && !g_strcmp0(s->user,job->user)){
   if(!ok || !g_subprocess_get_successful(job->proc) || !out ||
      strlen(out)>32768){
     ok=FALSE;
   }else{
     /* Python print appends one newline. Remove that byte ONLY; spaces in
      * real genre names (e.g. 'Action ') are significant and must survive. */
     gsize n=strlen(out);
     if(n && out[n-1]=='\n')out[n-1]=0;
     ok=read_response(s,job->action,out);
   }
   if(!ok){
     s->folder_valid=FALSE;
     gtk_label_set_text(GTK_LABEL(s->status),
       "Folder operation failed. Check owner approval and library mounts.");
   }
   s->running=FALSE;
   if(ok && job->action=='m'){
     gchar *next=s->relative && *s->relative ?
         g_strconcat(s->relative,"/",s->pending_folder,NULL) :
         g_strdup(s->pending_folder);
     if(g_strcmp0(s->root,job->root) ||
        g_strcmp0(s->relative,job->relative) ||
        !safe_relative(next)){
       ok=FALSE;
     }else{
       g_free(s->relative);s->relative=next;next=NULL;
       s->auto_pin_created=TRUE;
       start(s,'b');
     }
     g_clear_pointer(&s->pending_folder,g_free);
     g_free(next);
   }
   if(ok && job->action=='r'){
     const gchar *id=gtk_combo_box_get_active_id(GTK_COMBO_BOX(s->roots));
     if(safe_root(id)){
       g_free(s->root);s->root=g_strdup(id);
       g_free(s->relative);s->relative=g_strdup("");
       start(s,'b');
     }else{ok=FALSE;}
   }
   if(!ok){
     if(job->action=='m')
       gtk_label_set_text(GTK_LABEL(s->status),
         "Cannot create folder. It may exist or the approved drive is not writable.");
     else
       gtk_label_set_text(GTK_LABEL(s->status),"No approved folders available.");
     g_clear_pointer(&s->pending_folder,g_free);
     s->auto_pin_created=FALSE;
   }
   button_states(s);
 }else if(s){s->running=FALSE;button_states(s);}
 g_clear_error(&err);g_free(out);
 g_object_unref(job->proc);g_object_unref(job->view);
 g_free(job->host);g_free(job->user);g_free(job->root);g_free(job->relative);
 g_free(job);
}
static void start(Picker *s,char action){
 if(s->running || !s->helper || !s->host || !s->user)return;
 const char *operation=action=='r'?"roots":action=='b'?"browse":
                       action=='m'?"mkdir":"add";
 const char *argv[]={"/usr/bin/python3",s->helper,s->host,s->user,operation,
                    action=='r'?NULL:s->root,
                    action=='r'?NULL:s->relative,
                    action=='a'?s->magnet:
                    action=='m'?s->pending_folder:NULL,NULL};
 GError *err=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,G_SUBPROCESS_FLAGS_STDOUT_PIPE|
                                     G_SUBPROCESS_FLAGS_STDERR_SILENCE,&err);
 if(!proc){
   gtk_label_set_text(GTK_LABEL(s->status),"Cannot start authorized folder request.");
   g_clear_error(&err);return;
 }
 Job *job=g_new0(Job,1);
 job->view=g_object_ref(s->view);
 job->proc=proc;
 job->host=g_strdup(s->host);job->user=g_strdup(s->user);
 job->root=g_strdup(s->root);job->relative=g_strdup(s->relative);
 job->action=action;
 s->running=TRUE;s->folder_valid=FALSE;
 button_states(s);
 gtk_label_set_text(GTK_LABEL(s->status),action=='a'?
    "Submitting to selected folder..." : action=='m'?
    "Creating approved download folder..." : "Reading approved folders...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,finished,job);
}
static void on_root(GtkComboBox *combo,gpointer data){
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->running || s->loading_roots)return;
 const gchar *id=gtk_combo_box_get_active_id(combo);
 if(!safe_root(id))return;
 g_free(s->root);s->root=g_strdup(id);
 g_free(s->relative);s->relative=g_strdup("");
 start(s,'b');
}
static void on_up(GtkButton *unused,gpointer data){
 (void)unused;
 Picker *s=state(GTK_WIDGET(data));
 if(!s || s->running || !s->relative || !*s->relative)return;
 gchar *slash=strrchr(s->relative,'/');
 if(slash)*slash=0;
 else *s->relative=0;
 start(s,'b');
}
static void on_add(GtkButton *unused,gpointer data){
 (void)unused;
 Picker *s=state(GTK_WIDGET(data));
 if(s && !s->running && s->folder_valid && s->magnet)start(s,'a');
}
GtkWidget *now_downloads_destination_view_new(void){
 GtkWidget *view=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
 gtk_widget_set_no_show_all(view,TRUE);
 Picker *s=g_new0(Picker,1);
 s->view=view;
  s->places=g_ptr_array_new_with_free_func(free_place);
 s->recents=g_ptr_array_new_with_free_func(free_place);
 g_object_set_data_full(G_OBJECT(view),"now-destination-state",s,free_state);
 GtkWidget *title=gtk_label_new("CHOOSE WHERE TO SAVE");
 gtk_label_set_xalign(GTK_LABEL(title),0);
 gtk_box_pack_start(GTK_BOX(view),title,FALSE,FALSE,0);
 GtkWidget *bar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 gtk_box_pack_start(GTK_BOX(view),bar,FALSE,FALSE,0);
 s->roots=gtk_combo_box_text_new();
 gtk_box_pack_start(GTK_BOX(bar),s->roots,TRUE,TRUE,0);
 g_signal_connect(s->roots,"changed",G_CALLBACK(on_root),view);
 s->up=gtk_button_new_with_label("← UP");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->up),"now-action");
 g_signal_connect(s->up,"clicked",G_CALLBACK(on_up),view);
 gtk_box_pack_start(GTK_BOX(bar),s->up,FALSE,FALSE,0);
 s->new_folder=gtk_button_new_with_label("+ NEW FOLDER");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->new_folder),"now-action");
 gtk_widget_set_tooltip_text(s->new_folder,
   "Create a Games, Books or other folder within the approved download drive");
 gtk_box_pack_start(GTK_BOX(bar),s->new_folder,FALSE,FALSE,0);
 g_signal_connect(s->new_folder,"clicked",G_CALLBACK(on_new_folder),view);

 s->path=gtk_label_new("Select an approved download drive.");
 gtk_label_set_xalign(GTK_LABEL(s->path),0);
 gtk_label_set_ellipsize(GTK_LABEL(s->path),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(view),s->path,FALSE,FALSE,0);
 GtkWidget *places_row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,5);
 gtk_box_pack_start(GTK_BOX(view),places_row,FALSE,FALSE,0);
 s->places_combo=gtk_combo_box_text_new();
 gtk_widget_set_tooltip_text(s->places_combo,
    "Jump to a Favorite or recently used folder; host authorization is checked each time");
 gtk_box_pack_start(GTK_BOX(places_row),s->places_combo,TRUE,TRUE,0);
 g_signal_connect(s->places_combo,"changed",G_CALLBACK(on_place_selected),view);
 s->pin_place=gtk_button_new_with_label("☆ Favorite");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->pin_place),"now-action");
 gtk_box_pack_start(GTK_BOX(places_row),s->pin_place,FALSE,FALSE,0);
 g_signal_connect(s->pin_place,"clicked",G_CALLBACK(on_save_place),view);
 s->status=gtk_label_new("Choose a folder before adding.");
 gtk_label_set_xalign(GTK_LABEL(s->status),0);
 gtk_label_set_line_wrap(GTK_LABEL(s->status),TRUE);
 gtk_box_pack_start(GTK_BOX(view),s->status,FALSE,FALSE,0);
 s->filter=gtk_search_entry_new();
 gtk_entry_set_placeholder_text(GTK_ENTRY(s->filter),
   "Find a folder in this location (e.g. Horror)");
 gtk_widget_set_tooltip_text(s->filter,
   "Filter the visible approved folders only; clear to show them all.");
 gtk_box_pack_start(GTK_BOX(view),s->filter,FALSE,FALSE,0);
 g_signal_connect(s->filter,"changed",G_CALLBACK(on_filter_changed),view);
 s->folder_scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(s->folder_scroll),
                                GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_scrolled_window_set_overlay_scrolling(
   GTK_SCROLLED_WINDOW(s->folder_scroll),FALSE);
 /* Focused destination step: the folder list no longer shares its viewport
  * with Search Results. Allow a generous visible section on short projectors;
  * the entire native Downloads page remains scrollable if needed. */
 gtk_widget_set_size_request(s->folder_scroll,-1,420);
 gtk_widget_set_vexpand(s->folder_scroll,TRUE);
 s->folders=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);
 gtk_container_add(GTK_CONTAINER(s->folder_scroll),s->folders);
 gtk_box_pack_start(GTK_BOX(view),s->folder_scroll,TRUE,TRUE,0);
 /* Confirmation stays under the scrollable directory browser. */
 GtkWidget *confirm_row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 s->add=gtk_button_new_with_label("ADD TORRENT");
 gtk_widget_set_name(s->add,"downloadconfirm");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->add),"now-action");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->add),"now-primary");
 g_signal_connect(s->add,"clicked",G_CALLBACK(on_add),view);
 gtk_box_pack_end(GTK_BOX(confirm_row),s->add,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(view),confirm_row,FALSE,FALSE,0);
 load_places(s);
 button_states(s);
 return view;
}
void now_downloads_destination_view_configure(GtkWidget *view,const char *host,
                                              const char *user,const char *helper){
 Picker *s=state(view);
 if(!s)return;
 if(g_strcmp0(s->host,host) || g_strcmp0(s->user,user)){
   g_clear_pointer(&s->magnet,g_free);
   g_clear_pointer(&s->root,g_free);
   g_clear_pointer(&s->relative,g_free);
   s->folder_valid=FALSE;
   gtk_widget_hide(view);
 }
 g_free(s->host);s->host=g_strdup(host);
 g_free(s->user);s->user=g_strdup(user);
 g_free(s->helper);s->helper=g_strdup(helper);
 refresh_place_choices(s);
 button_states(s);
}
gboolean now_downloads_destination_view_select(GtkWidget *view,const char *magnet){
 Picker *s=state(view);
 if(!s || !s->host || !s->helper || !magnet ||
    !g_str_has_prefix(magnet,"magnet:?xt=urn:bt") ||
    strlen(magnet)>1024 || s->running)return FALSE;
 g_free(s->magnet);s->magnet=g_strdup(magnet);
 s->folder_valid=FALSE;
 gtk_widget_set_no_show_all(view,FALSE);
 gtk_widget_show_all(view);
 gtk_widget_set_no_show_all(view,TRUE);
 start(s,'r');
 return TRUE;
}
void now_downloads_destination_view_on_added(GtkWidget *view,
                                             void (*callback)(gpointer),gpointer data){
 Picker *s=state(view);
 if(s){s->on_added=callback;s->added_data=data;}
}
