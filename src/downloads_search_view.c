/* Native GTK search panel above the download queue. Result activation
 * passes only a validated magnet to the separate inline destination chooser.
 */
#include "downloads_search_view.h"
#include <gio/gio.h>
#include <string.h>

#define RESULT_LIMIT 100
#define PAGE_SIZE 20
#define MAX_WIRE 180000
typedef struct {
 GtkWidget *entry,*button,*more,*sort,*status,*list,*results,*pager,*previous,*next,*page_label;
 guint result_count,page;
 gchar *host,*user,*helper,*last_query;
 NowDownloadsMagnetSelected on_select;
 gpointer select_data;
 gboolean running,partial;
} SearchView;
typedef struct {
 GtkWidget *view;
 GSubprocess *proc;
 gchar *host,*user;
 gboolean full;
} SearchJob;

static SearchView *state(GtkWidget *view){
 return view ? g_object_get_data(G_OBJECT(view),"now-search-state") : NULL;
}
static void free_state(gpointer data){
 SearchView *s=data;
 g_free(s->host);g_free(s->user);g_free(s->helper);g_free(s->last_query);g_free(s);
}
/* GtkListBox owns the sorted order. Compare only bounded validated fields.
 * Unknown sizes/seeds sort last, not as fake tiny files or zero seeders. */
static gint compare_rows(GtkListBoxRow *left,GtkListBoxRow *right,gpointer data){
 SearchView *s=data;
 GtkWidget *a=gtk_bin_get_child(GTK_BIN(left));
 GtkWidget *b=gtk_bin_get_child(GTK_BIN(right));
 const gint64 *asz=a?g_object_get_data(G_OBJECT(a),"now-search-size"):NULL;
 const gint64 *bsz=b?g_object_get_data(G_OBJECT(b),"now-search-size"):NULL;
 const gint64 *asd=a?g_object_get_data(G_OBJECT(a),"now-search-seeds"):NULL;
 const gint64 *bsd=b?g_object_get_data(G_OBJECT(b),"now-search-seeds"):NULL;
 const char *an=a?g_object_get_data(G_OBJECT(a),"now-search-title"):NULL;
 const char *bn=b?g_object_get_data(G_OBJECT(b),"now-search-title"):NULL;
 const char *mode=gtk_combo_box_get_active_id(GTK_COMBO_BOX(s->sort));
 gint64 av=0,bv=0;
 if(g_strcmp0(mode,"seeds")==0){
   av=asd?*asd:-1;bv=bsd?*bsd:-1;
   if(av<0 || bv<0){if(av<0 && bv>=0)return 1;if(bv<0 && av>=0)return -1;}
   if(av!=bv)return av>bv?-1:1;
 }else if(g_strcmp0(mode,"small")==0 || g_strcmp0(mode,"large")==0){
   av=asz?*asz:-1;bv=bsz?*bsz:-1;
   if(av<0 || bv<0){if(av<0 && bv>=0)return 1;if(bv<0 && av>=0)return -1;}
   if(av!=bv)return (av<bv ? -1 : 1)*(g_strcmp0(mode,"large")==0?-1:1);
 }
 return g_ascii_strcasecmp(an?an:"",bn?bn:"");
}
static void show_page(SearchView *s){
 if(!s || !s->pager || !s->list)return;
 guint pages=(s->result_count+PAGE_SIZE-1)/PAGE_SIZE;
 if(!pages){gtk_widget_hide(s->pager);return;}
 if(s->page>=pages)s->page=pages-1;
 GList *rows=gtk_container_get_children(GTK_CONTAINER(s->list));
 guint index=0;
 for(GList *at=rows;at;at=at->next,index++){
   GtkWidget *row=GTK_WIDGET(at->data);
   gboolean visible=index>=s->page*PAGE_SIZE &&
                    index<(s->page+1)*PAGE_SIZE;
   gtk_widget_set_no_show_all(row,!visible);
   if(visible)gtk_widget_show(row);
   else gtk_widget_hide(row);
 }
 g_list_free(rows);
 gchar *caption=g_strdup_printf("Page %u of %u  ·  %u results",
                                  s->page+1,pages,s->result_count);
 gtk_label_set_text(GTK_LABEL(s->page_label),caption);
 g_free(caption);
 gtk_widget_set_sensitive(s->previous,s->page>0);
 gtk_widget_set_sensitive(s->next,s->page+1<pages);
 gtk_widget_show_all(s->pager);
}
static void previous_page(GtkButton *unused,gpointer data){
 (void)unused;
 SearchView *s=state(GTK_WIDGET(data));
 if(s && s->page){s->page--;show_page(s);}
}
static void next_page(GtkButton *unused,gpointer data){
 (void)unused;
 SearchView *s=state(GTK_WIDGET(data));
 if(s && (s->page+1)*PAGE_SIZE<s->result_count){s->page++;show_page(s);}
}
static void clear_results(SearchView *s){
 if(!s)return;
 s->result_count=0;s->page=0;s->partial=FALSE;
 if(s->more)gtk_widget_hide(s->more);
 if(s->pager)gtk_widget_hide(s->pager);
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
 if(!s || !wire || !*wire || strlen(wire)>MAX_WIRE ||
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
   gtk_widget_set_name(name,"nowsearchtitle");
   gtk_box_pack_start(GTK_BOX(row),name,FALSE,FALSE,0);
   gint64 size=g_ascii_strtoll(parts[1],NULL,10);
   gint64 seeds=g_ascii_strtoll(parts[2],NULL,10);
   gint64 *size_data=g_new(gint64,1),*seed_data=g_new(gint64,1);
   *size_data=size;*seed_data=seeds;
   g_object_set_data_full(G_OBJECT(row),"now-search-size",size_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-seeds",seed_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-title",g_strdup(parts[4]),g_free);
   gchar *size_text=size>=0 ? g_format_size((guint64)size) : g_strdup("Size unknown");
   gchar *seed_text=seeds>=0 ? g_strdup_printf("%lld seeds",(long long)seeds) :
                               g_strdup("Seeds unknown");
   gchar *detail=g_strdup_printf("%s  ·  %s  ·  %s",
       size_text,seed_text,
       !strcmp(parts[3],"1") ? "Magnet link ready" :
                                "Plugin link unsupported");
   g_free(size_text);g_free(seed_text);
   GtkWidget *meta=text(detail);
   gtk_widget_set_name(meta,"nowsearchmeta");
   g_free(detail);
   /* Avoid rendering filesystem paths, HTML result links or private hashes. */
   gtk_box_pack_start(GTK_BOX(row),meta,FALSE,FALSE,0);
   gtk_container_add(GTK_CONTAINER(s->list),row);
   g_strfreev(parts);
 }
 s->result_count=count;
 s->page=0;s->partial=partial!=0;
 gtk_list_box_invalidate_sort(GTK_LIST_BOX(s->list));
 if(s->more){
   if(s->partial && count && count<RESULT_LIMIT)gtk_widget_show(s->more);
   else gtk_widget_hide(s->more);
 }
 if(count){
   gtk_widget_show_all(s->list);
   gtk_widget_show(s->results);
   show_page(s);
   gchar *message=g_strdup_printf("%u result%s%s — select a magnet to choose its folder",
       count,count==1?"":"s",partial?" (partial — More Results available)":"");
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
static void sort_changed(GtkComboBox *unused,gpointer data){
 (void)unused;
 SearchView *s=state(GTK_WIDGET(data));
 if(s && s->list){s->page=0;gtk_list_box_invalidate_sort(GTK_LIST_BOX(s->list));show_page(s);}
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
      stdout_text && strlen(stdout_text)<=MAX_WIRE &&
      now_downloads_search_view_update(job->view,g_strchomp(stdout_text));
   if(!ok){
     if(!job->full)clear_results(s);
     gtk_label_set_text(GTK_LABEL(s->status),job->full ?
       "More results unavailable. Previous results retained." :
       "Search unavailable. Check authorized host, VPN and installed plugins.");
   }
   s->running=FALSE;
   gtk_widget_set_sensitive(s->entry,TRUE);
   gtk_widget_set_sensitive(s->button,s->host && s->user && s->helper);
   if(s->more)gtk_widget_set_sensitive(s->more,TRUE);
 }else if(s){
   s->running=FALSE;
   gtk_widget_set_sensitive(s->entry,TRUE);
   gtk_widget_set_sensitive(s->button,s->host && s->user && s->helper);
   if(s->more)gtk_widget_set_sensitive(s->more,TRUE);
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
 gboolean full=unused==s->more;
 if(full && (!s->partial || !s->result_count || !s->last_query ||
             g_strcmp0(query,s->last_query)))return;
 const gchar *argv[]={"/usr/bin/python3",s->helper,s->host,s->user,query,
                      full?"--full":NULL,NULL};
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
 job->full=full;
 s->running=TRUE;
 if(!full){
   g_free(s->last_query);s->last_query=g_strdup(query);
   clear_results(s);
 }
 gtk_widget_set_sensitive(s->entry,FALSE);
 gtk_widget_set_sensitive(s->button,FALSE);
 if(s->more)gtk_widget_set_sensitive(s->more,FALSE);
 gtk_label_set_text(GTK_LABEL(s->status),full?
     "Searching enabled plugins for more results (up to 12 seconds)..." :
     "Searching approved qBittorrent plugins...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,search_complete,job);
}
GtkWidget *now_downloads_search_view_new(void){
 GtkWidget *view=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
 gtk_widget_set_vexpand(view,TRUE);
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
 s->sort=gtk_combo_box_text_new();
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->sort),"small","SMALLER FILES FIRST");
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->sort),"seeds","MOST SEEDERS");
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->sort),"large","LARGER FILES FIRST");
 gtk_combo_box_set_active_id(GTK_COMBO_BOX(s->sort),"small");
 gtk_box_pack_start(GTK_BOX(bar),s->sort,FALSE,FALSE,0);
 g_signal_connect(s->sort,"changed",G_CALLBACK(sort_changed),view);
 s->status=text("Connect an approved owner device to search.");
 gtk_box_pack_start(GTK_BOX(view),s->status,FALSE,FALSE,0);
 s->more=gtk_button_new_with_label("MORE RESULTS");
 gtk_widget_set_no_show_all(s->more,TRUE);
 gtk_box_pack_start(GTK_BOX(view),s->more,FALSE,FALSE,0);
 gtk_widget_hide(s->more);
 g_signal_connect(s->more,"clicked",G_CALLBACK(start_search),view);
 s->results=gtk_scrolled_window_new(NULL,NULL);
 gtk_widget_set_name(s->results,"nowsearchresults");
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(s->results),
                               GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_size_request(s->results,-1,150);
 gtk_widget_set_vexpand(s->results,TRUE);
 gtk_widget_set_no_show_all(s->results,TRUE);
 s->list=gtk_list_box_new();
 gtk_widget_set_name(s->list,"nowsearchlist");
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(s->list),GTK_SELECTION_SINGLE);
 gtk_list_box_set_sort_func(GTK_LIST_BOX(s->list),compare_rows,s,NULL);
 g_signal_connect(s->list,"row-activated",G_CALLBACK(on_result_activated),view);
 gtk_container_add(GTK_CONTAINER(s->results),s->list);
 gtk_box_pack_start(GTK_BOX(view),s->results,TRUE,TRUE,0);
 gtk_widget_hide(s->results);
 s->pager=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 gtk_widget_set_no_show_all(s->pager,TRUE);
 s->previous=gtk_button_new_with_label("PREVIOUS");
 s->next=gtk_button_new_with_label("NEXT");
 s->page_label=gtk_label_new("Page 1");
 gtk_box_pack_start(GTK_BOX(s->pager),s->previous,FALSE,FALSE,0);
 gtk_box_pack_start(GTK_BOX(s->pager),s->page_label,TRUE,TRUE,0);
 gtk_box_pack_end(GTK_BOX(s->pager),s->next,FALSE,FALSE,0);
 g_signal_connect(s->previous,"clicked",G_CALLBACK(previous_page),view);
 g_signal_connect(s->next,"clicked",G_CALLBACK(next_page),view);
 gtk_box_pack_start(GTK_BOX(view),s->pager,FALSE,FALSE,0);
 gtk_widget_hide(s->pager);
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
