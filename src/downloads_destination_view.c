/* Inline, owner-only folder browser and explicit Add. No shell, passwords,
 * direct WebUI endpoint, extra window, host absolute path or media organizer.
 * Each browse/add is revalidated by the restricted host-side owner broker.
 */
#include "downloads_destination_view.h"
#include <gio/gio.h>
#include <string.h>

typedef struct {
 GtkWidget *view,*roots,*folders,*path,*status,*up,*add;
 gchar *host,*user,*helper,*root,*relative,*magnet;
 gboolean running,loading_roots,folder_valid;
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
static void free_state(gpointer data){
 Picker *s=data;
 g_free(s->host);g_free(s->user);g_free(s->helper);
 g_free(s->root);g_free(s->relative);g_free(s->magnet);g_free(s);
}
static void clear_folder_buttons(Picker *s){
 GList *children=gtk_container_get_children(GTK_CONTAINER(s->folders));
 for(GList *at=children;at;at=at->next)
   gtk_widget_destroy(GTK_WIDGET(at->data));
 g_list_free(children);
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
static void button_states(Picker *s){
 gtk_widget_set_sensitive(s->add,!s->running && s->folder_valid &&
                          s->magnet && s->root);
 gtk_widget_set_sensitive(s->up,!s->running && s->relative && *s->relative);
 gtk_widget_set_sensitive(s->roots,!s->running);
}
static void start(Picker *s,char action);
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
 if(action=='a'){
   if(strcmp(wire,"SUBMITTED"))return FALSE;
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
       gtk_widget_set_halign(button,GTK_ALIGN_FILL);
       g_signal_connect(button,"clicked",G_CALLBACK(on_folder_clicked),s->view);
       gtk_box_pack_start(GTK_BOX(s->folders),button,FALSE,FALSE,1);
       g_strfreev(part);
     }
     gtk_widget_show_all(s->folders);
     gchar *title=g_strdup_printf("%s / %s",s->root,s->relative && *s->relative ?
                                    s->relative : "(root)");
     gtk_label_set_text(GTK_LABEL(s->path),title);
     g_free(title);
     gtk_label_set_text(GTK_LABEL(s->status),
       "Choose a subfolder, or Add to the folder shown.");
     s->folder_valid=TRUE;
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
   if(ok && job->action=='r'){
     const gchar *id=gtk_combo_box_get_active_id(GTK_COMBO_BOX(s->roots));
     if(safe_root(id)){
       g_free(s->root);s->root=g_strdup(id);
       g_free(s->relative);s->relative=g_strdup("");
       start(s,'b');
     }else{ok=FALSE;}
   }
   if(!ok)gtk_label_set_text(GTK_LABEL(s->status),
                           "No approved folders available.");
   button_states(s);
 }else if(s){s->running=FALSE;button_states(s);}
 g_clear_error(&err);g_free(out);
 g_object_unref(job->proc);g_object_unref(job->view);
 g_free(job->host);g_free(job->user);g_free(job->root);g_free(job->relative);
 g_free(job);
}
static void start(Picker *s,char action){
 if(s->running || !s->helper || !s->host || !s->user)return;
 const char *operation=action=='r'?"roots":action=='b'?"browse":"add";
 const char *argv[]={"/usr/bin/python3",s->helper,s->host,s->user,operation,
                    action=='r'?NULL:s->root,
                    action=='r'?NULL:s->relative,
                    action=='a'?s->magnet:NULL,NULL};
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
    "Submitting to selected folder..." : "Reading approved media folders...");
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
 g_object_set_data_full(G_OBJECT(view),"now-destination-state",s,free_state);
 GtkWidget *title=gtk_label_new("SAVE SELECTED TORRENT TO");
 gtk_label_set_xalign(GTK_LABEL(title),0);
 gtk_box_pack_start(GTK_BOX(view),title,FALSE,FALSE,0);
 GtkWidget *bar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 gtk_box_pack_start(GTK_BOX(view),bar,FALSE,FALSE,0);
 s->roots=gtk_combo_box_text_new();
 gtk_box_pack_start(GTK_BOX(bar),s->roots,TRUE,TRUE,0);
 g_signal_connect(s->roots,"changed",G_CALLBACK(on_root),view);
 s->up=gtk_button_new_with_label("UP");
 g_signal_connect(s->up,"clicked",G_CALLBACK(on_up),view);
 gtk_box_pack_start(GTK_BOX(bar),s->up,FALSE,FALSE,0);
 s->add=gtk_button_new_with_label("ADD TO DOWNLOADS");
 g_signal_connect(s->add,"clicked",G_CALLBACK(on_add),view);
 gtk_box_pack_start(GTK_BOX(bar),s->add,FALSE,FALSE,0);
 s->path=gtk_label_new("Select a media drive.");
 gtk_label_set_xalign(GTK_LABEL(s->path),0);
 gtk_label_set_ellipsize(GTK_LABEL(s->path),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(view),s->path,FALSE,FALSE,0);
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_size_request(scroll,-1,110);
 s->folders=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);
 gtk_container_add(GTK_CONTAINER(scroll),s->folders);
 gtk_box_pack_start(GTK_BOX(view),scroll,FALSE,FALSE,0);
 s->status=gtk_label_new("Choose a folder before adding.");
 gtk_label_set_xalign(GTK_LABEL(s->status),0);
 gtk_label_set_ellipsize(GTK_LABEL(s->status),PANGO_ELLIPSIZE_END);
 gtk_box_pack_start(GTK_BOX(view),s->status,FALSE,FALSE,0);
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
 button_states(s);
}
void now_downloads_destination_view_select(GtkWidget *view,const char *magnet){
 Picker *s=state(view);
 if(!s || !s->host || !s->helper || !magnet ||
    !g_str_has_prefix(magnet,"magnet:?xt=urn:bt") ||
    strlen(magnet)>1024 || s->running)return;
 g_free(s->magnet);s->magnet=g_strdup(magnet);
 s->folder_valid=FALSE;
 gtk_widget_set_no_show_all(view,FALSE);
 gtk_widget_show_all(view);
 gtk_widget_set_no_show_all(view,TRUE);
 start(s,'r');
}
void now_downloads_destination_view_on_added(GtkWidget *view,
                                             void (*callback)(gpointer),gpointer data){
 Picker *s=state(view);
 if(s){s->on_added=callback;s->added_data=data;}
}
