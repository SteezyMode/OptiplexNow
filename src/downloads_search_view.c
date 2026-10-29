/* Native GTK search panel above the download queue. Result activation
 * passes only a validated magnet to the separate inline destination chooser.
 */
#include "downloads_search_view.h"
#include <gio/gio.h>
#include <string.h>

#define RESULT_LIMIT 20
typedef struct {
 GtkWidget *entry,*button,*status,*list,*results;
 gchar *host,*user,*helper;
 NowDownloadsMagnetSelected on_select;
 gpointer select_data;
 gboolean running;
} SearchView;
typedef struct {
 GtkWidget *view;
 GSubprocess *proc;
 gchar *host,*user;
} SearchJob;

static SearchView *state(GtkWidget *view){
 return view ? g_object_get_data(G_OBJECT(view),"now-search-state") : NULL;
}
static void free_state(gpointer data){
 SearchView *s=data;
 g_free(s->host);g_free(s->user);g_free(s->helper);g_free(s);
}
static void clear_results(SearchView *s){
 if(!s)return;
 GList *items=gtk_container_get_children(GTK_CONTAINER(s->list));
 for(GList *item=items;item;item=item->next)
   gtk_widget_destroy(GTK_WIDGET(item->data));
 g_list_free(items);
 gtk_widget_hide(s->results);
}
static GtkWidget *text(const char *value){
 GtkWidget *label=gtk_label_new(value);
 gtk_label_set_xalign(GTK_LABEL(label),0);
 gtk_label_set_ellipsize(GTK_LABEL(label),PANGO_ELLIPSIZE_END);
 return label;
}
static gboolean magnet_field(const char *value){
 if(!value || strlen(value)>1024 || strlen(value)<24 ||
    !g_str_has_prefix(value,"magnet:?xt=urn:bt"))return FALSE;
 for(const unsigned char *p=(const unsigned char *)value;*p;p++)
   if(*p<33 || *p>126)return FALSE;
 return TRUE;
}
static gboolean integer(const char *value,gint64 min,gint64 max,gint64 *out){
 if(!value || !*value)return FALSE;
 gchar *end=NULL;
 gint64 v=g_ascii_strtoll(value,&end,10);
 if(!end || *end || v<min || v>max)return FALSE;
 if(out)*out=v;
 return TRUE;
}
gboolean now_downloads_search_view_update(GtkWidget *view,const char *wire){
 SearchView *s=state(view);
 if(!s || !wire || !*wire || strlen(wire)>32768 ||
    wire[strlen(wire)-1]=='\n' || !g_utf8_validate(wire,-1,NULL))
   return FALSE;
 gchar **lines=g_strsplit(wire,"\n",-1);
 gchar **header=g_strsplit(lines[0],"\t",-1);
 gint64 partial=0,total=0;
 gboolean ok=g_strv_length(header)==3 && !strcmp(header[0],"SEARCH") &&
   integer(header[1],0,1,&partial) && integer(header[2],0,1000000,&total);
 g_strfreev(header);
 guint count=0;
 for(guint i=1;ok && lines[i];i++){
   gchar **parts=g_strsplit(lines[i],"\t",-1);
   gint64 size=0,seeds=0,can_add=0;
   if(++count>RESULT_LIMIT || g_strv_length(parts)!=6 ||
      strcmp(parts[0],"RESULT") ||
      !integer(parts[1],-1,G_MAXINT64,&size) ||
      !integer(parts[2],-1,G_MAXINT32,&seeds) ||
      !integer(parts[3],0,1,&can_add) || !*parts[4] ||
      g_utf8_strlen(parts[4],-1)>160 ||
      (can_add ? !magnet_field(parts[5]) : strcmp(parts[5],"-")))
     ok=FALSE;
   g_strfreev(parts);
 }
 if(!ok){g_strfreev(lines);return FALSE;}
 clear_results(s);
 for(guint i=1;lines[i];i++){
   gchar **parts=g_strsplit(lines[i],"\t",-1);
   GtkWidget *row=gtk_box_new(GTK_ORIENTATION_VERTICAL,3);
   gtk_widget_set_margin_start(row,6);
   gtk_widget_set_margin_end(row,6);
   gtk_widget_set_margin_top(row,5);
   gtk_widget_set_margin_bottom(row,5);
   if(!strcmp(parts[3],"1"))
     g_object_set_data_full(G_OBJECT(row),"now-magnet",g_strdup(parts[5]),g_free);
   GtkWidget *name=text(parts[4]);
   gtk_box_pack_start(GTK_BOX(row),name,FALSE,FALSE,0);
   gint64 size=g_ascii_strtoll(parts[1],NULL,10);
   gint64 seeds=g_ascii_strtoll(parts[2],NULL,10);
   gchar *size_text=size>=0 ? g_format_size((guint64)size) : g_strdup("Size unknown");
   gchar *seed_text=seeds>=0 ? g_strdup_printf("%lld seeds",(long long)seeds) :
                               g_strdup("Seeds unknown");
   gchar *detail=g_strdup_printf("%s  ·  %s  ·  %s",
       size_text,seed_text,
       !strcmp(parts[3],"1") ? "Magnet link ready" :
                                "Plugin link unsupported");
   g_free(size_text);g_free(seed_text);
   GtkWidget *meta=text(detail);
   g_free(detail);
   /* Avoid rendering filesystem paths, HTML result links or private hashes. */
   gtk_box_pack_start(GTK_BOX(row),meta,FALSE,FALSE,0);
   gtk_container_add(GTK_CONTAINER(s->list),row);
   g_strfreev(parts);
 }
 if(count){
   gtk_widget_show_all(s->list);
   gtk_widget_show(s->results);
   gchar *message=g_strdup_printf("%u result%s%s — select a magnet to choose its folder",
       count,count==1?"":"s",partial?" (partial)":"");
   gtk_label_set_text(GTK_LABEL(s->status),message);
   g_free(message);
 }else{
   gtk_label_set_text(GTK_LABEL(s->status),partial ?
      "Still searching; retry for more results." : "No results from enabled plugins.");
 }
 g_strfreev(lines);
 return TRUE;
}
static void on_result_activated(GtkListBox *list,GtkListBoxRow *row,
                                gpointer data){
 (void)list;
 SearchView *s=state(GTK_WIDGET(data));
 if(!s)return;
 GtkWidget *child=gtk_bin_get_child(GTK_BIN(row));
 const char *magnet=child?g_object_get_data(G_OBJECT(child),"now-magnet"):NULL;
 if(!magnet){
   gtk_label_set_text(GTK_LABEL(s->status),
     "This plugin result is a webpage, not a direct magnet. Try another result.");
   return;
 }
 if(s->on_select)s->on_select(magnet,s->select_data);
}
void now_downloads_search_view_on_select(GtkWidget *view,
                                         NowDownloadsMagnetSelected callback,
                                         gpointer user_data){
 SearchView *s=state(view);
 if(s){s->on_select=callback;s->select_data=user_data;}
}
static void search_complete(GObject *unused,GAsyncResult *res,gpointer data){
 (void)unused;
 SearchJob *job=data;
 SearchView *s=state(job->view);
 gchar *stdout_text=NULL;
 GError *err=NULL;
 gboolean completed=g_subprocess_communicate_utf8_finish(
   job->proc,res,&stdout_text,NULL,&err);
 if(s && !g_strcmp0(s->host,job->host) && !g_strcmp0(s->user,job->user)){
   gboolean ok=completed && g_subprocess_get_successful(job->proc) &&
      stdout_text && strlen(stdout_text)<=32768 &&
      now_downloads_search_view_update(job->view,g_strchomp(stdout_text));
   if(!ok){
     clear_results(s);
     gtk_label_set_text(GTK_LABEL(s->status),
       "Search unavailable. Check authorized host, VPN and installed plugins.");
   }
   s->running=FALSE;
   gtk_widget_set_sensitive(s->button,s->host && s->user && s->helper);
 }else if(s){
   s->running=FALSE;
   gtk_widget_set_sensitive(s->button,s->host && s->user && s->helper);
 }
 g_clear_error(&err);g_free(stdout_text);
 g_object_unref(job->proc);g_object_unref(job->view);
 g_free(job->host);g_free(job->user);g_free(job);
}
static void start_search(GtkWidget *unused,gpointer data){
 (void)unused;
 GtkWidget *view=data;
 SearchView *s=state(view);
 if(!s || s->running || !s->host || !s->user || !s->helper)return;
 const char *query=gtk_entry_get_text(GTK_ENTRY(s->entry));
 if(!query || g_utf8_strlen(query,-1)<2 || strlen(query)>384){
   gtk_label_set_text(GTK_LABEL(s->status),"Enter a search of 2–96 characters.");
   return;
 }
 const gchar *argv[]={"/usr/bin/python3",s->helper,s->host,s->user,query,NULL};
 GError *err=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,G_SUBPROCESS_FLAGS_STDOUT_PIPE|
                                     G_SUBPROCESS_FLAGS_STDERR_SILENCE,&err);
 if(!proc){
   gtk_label_set_text(GTK_LABEL(s->status),"Unable to start approved search.");
   g_clear_error(&err);return;
 }
 SearchJob *job=g_new0(SearchJob,1);
 job->view=g_object_ref(view);job->proc=proc;
 job->host=g_strdup(s->host);job->user=g_strdup(s->user);
 s->running=TRUE;
 clear_results(s);
 gtk_widget_set_sensitive(s->button,FALSE);
 gtk_label_set_text(GTK_LABEL(s->status),"Searching approved qBittorrent plugins...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,search_complete,job);
}
GtkWidget *now_downloads_search_view_new(void){
 GtkWidget *view=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
 SearchView *s=g_new0(SearchView,1);
 g_object_set_data_full(G_OBJECT(view),"now-search-state",s,free_state);
 GtkWidget *bar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 gtk_box_pack_start(GTK_BOX(view),bar,FALSE,FALSE,0);
 s->entry=gtk_entry_new();
 gtk_entry_set_placeholder_text(GTK_ENTRY(s->entry),"Search downloads");
 gtk_entry_set_max_length(GTK_ENTRY(s->entry),96);
 gtk_box_pack_start(GTK_BOX(bar),s->entry,TRUE,TRUE,0);
 s->button=gtk_button_new_with_label("SEARCH");
 gtk_widget_set_sensitive(s->button,FALSE);
 gtk_box_pack_start(GTK_BOX(bar),s->button,FALSE,FALSE,0);
 g_signal_connect(s->button,"clicked",G_CALLBACK(start_search),view);
 g_signal_connect(s->entry,"activate",G_CALLBACK(start_search),view);
 s->status=text("Connect an approved owner device to search.");
 gtk_box_pack_start(GTK_BOX(view),s->status,FALSE,FALSE,0);
 s->results=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(s->results),
                               GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_size_request(s->results,-1,150);
 gtk_widget_set_no_show_all(s->results,TRUE);
 s->list=gtk_list_box_new();
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(s->list),GTK_SELECTION_SINGLE);
 g_signal_connect(s->list,"row-activated",G_CALLBACK(on_result_activated),view);
 gtk_container_add(GTK_CONTAINER(s->results),s->list);
 gtk_box_pack_start(GTK_BOX(view),s->results,FALSE,FALSE,0);
 gtk_widget_hide(s->results);
 return view;
}
void now_downloads_search_view_configure(GtkWidget *view,const char *host,
                                          const char *user,const char *helper){
 SearchView *s=state(view);
 if(!s)return;
 if(g_strcmp0(s->host,host) || g_strcmp0(s->user,user)){
   clear_results(s);
   gtk_label_set_text(GTK_LABEL(s->status),
     host && user ? "Search enabled qBittorrent plugins." :
                    "Owner device approval required to search.");
 }
 g_free(s->host);s->host=g_strdup(host);
 g_free(s->user);s->user=g_strdup(user);
 g_free(s->helper);s->helper=g_strdup(helper);
 gtk_widget_set_sensitive(s->button,!s->running && s->host && s->user && s->helper);
}
