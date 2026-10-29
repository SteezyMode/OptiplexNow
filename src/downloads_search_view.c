/* Native GTK search panel above the download queue. Result activation
 * passes only a validated magnet to the separate inline destination chooser.
 */
#include "downloads_search_view.h"
#include <gio/gio.h>
#include <string.h>

#define RESULT_LIMIT 100
#define MAX_WIRE 180000
typedef struct {
 GtkWidget *entry,*button,*headers[5],*status,*list,*results;
 guint result_count,sort_column;
 gboolean ascending;
 gchar *host,*user,*helper;
 NowDownloadsMagnetSelected on_select;
 gpointer select_data;
 gboolean running,partial,received_initial;
} SearchView;
typedef struct {
 GtkWidget *view;
 GSubprocess *proc;
 GDataInputStream *reader;
 gchar *host,*user;
 gboolean done,invalid,got_frame;
} SearchJob;

static SearchView *state(GtkWidget *view){
 return view ? g_object_get_data(G_OBJECT(view),"now-search-state") : NULL;
}
static void free_state(gpointer data){
 SearchView *s=data;
 g_free(s->host);g_free(s->user);g_free(s->helper);g_free(s);
}
/* Sort every accumulated result, including appended rows. Unknown
 * numeric values always go last in either direction. */
static gint compare_rows(GtkListBoxRow *left,GtkListBoxRow *right,gpointer data){
 SearchView *s=data;
 GtkWidget *a=gtk_bin_get_child(GTK_BIN(left));
 GtkWidget *b=gtk_bin_get_child(GTK_BIN(right));
 const char *an=a?g_object_get_data(G_OBJECT(a),"now-search-title"):NULL;
 const char *bn=b?g_object_get_data(G_OBJECT(b),"now-search-title"):NULL;
 if(s->sort_column==0){
   gint cmp=g_ascii_strcasecmp(an?an:"",bn?bn:"");
   return s->ascending?cmp:-cmp;
 }
 const char *field=s->sort_column==1 ? "now-search-size" :
                   s->sort_column==2 ? "now-search-seeds" :
                   s->sort_column==3 ? "now-search-leechers" :
                                       "now-search-published";
 const gint64 *ap=a?g_object_get_data(G_OBJECT(a),field):NULL;
 const gint64 *bp=b?g_object_get_data(G_OBJECT(b),field):NULL;
 gint64 av=ap?*ap:-1,bv=bp?*bp:-1;
 if(av<0 || bv<0){
   if(av<0 && bv>=0)return 1;
   if(bv<0 && av>=0)return -1;
 }
 if(av!=bv)return (av<bv?-1:1)*(s->ascending?1:-1);
 return g_ascii_strcasecmp(an?an:"",bn?bn:"");
}
static void header_clicked(GtkButton *button,gpointer data){
 SearchView *s=state(GTK_WIDGET(data));
 if(!s || !s->list)return;
 guint column=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(button),"now-sort-column"));
 if(column<1 || column>5)return;
 column--;
 if(s->sort_column==column)s->ascending=!s->ascending;
 else{
   s->sort_column=column;
   s->ascending=(column==0 || column==1);
 }
 const char *labels[]={"NAME","SIZE","SEEDERS","LEECHERS","PUBLISHED"};
 for(guint i=0;i<5;i++){
   gchar *label=i==s->sort_column ?
       g_strdup_printf("%s %s",labels[i],s->ascending?"↑":"↓") :
       g_strdup(labels[i]);
   gtk_button_set_label(GTK_BUTTON(s->headers[i]),label);
   g_free(label);
 }
 gtk_list_box_invalidate_sort(GTK_LIST_BOX(s->list));
 /* An explicit sort starts at the top; incoming result frames do not scroll. */
 GtkAdjustment *position=gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(s->results));
 if(position)gtk_adjustment_set_value(position,gtk_adjustment_get_lower(position));
}
static void clear_results(SearchView *s){
 if(!s)return;
 s->result_count=0;s->partial=FALSE;s->received_initial=FALSE;
 GtkAdjustment *position=gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(s->results));
 if(position)gtk_adjustment_set_value(position,gtk_adjustment_get_lower(position));
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
 gboolean append=g_strv_length(header)==3 && !strcmp(header[0],"APPEND");
 gboolean ok=g_strv_length(header)==3 &&
   (!strcmp(header[0],"SEARCH") || append) &&
   integer(header[1],0,1,&partial) && integer(header[2],0,1000000,&total);
 if(append && !s->received_initial)ok=FALSE;
 g_strfreev(header);
 guint count=0;
 for(guint i=1;ok && lines[i];i++){
   gchar **parts=g_strsplit(lines[i],"\t",-1);
   gint64 size=0,seeds=0,can_add=0,published=-1,leechers=-1;
   guint fields=g_strv_length(parts);
   if(++count>RESULT_LIMIT || (fields!=6 && fields!=7 && fields!=8) ||
      strcmp(parts[0],"RESULT") ||
      !integer(parts[1],-1,G_MAXINT64,&size) ||
      !integer(parts[2],-1,G_MAXINT32,&seeds) ||
      !integer(parts[3],0,1,&can_add) || !*parts[4] ||
      g_utf8_strlen(parts[4],-1)>160 ||
      (can_add ? !magnet_field(parts[5]) : strcmp(parts[5],"-")) ||
      (fields>=7 && !integer(parts[6],-1,253402300799LL,&published)) ||
      (fields==8 && !integer(parts[7],-1,G_MAXINT32,&leechers)))
     ok=FALSE;
   g_strfreev(parts);
 }
 if(ok && count+(append?s->result_count:0)>1000)ok=FALSE;
 if(!ok){g_strfreev(lines);return FALSE;}
 if(!append){clear_results(s);s->received_initial=TRUE;}
 for(guint i=1;lines[i];i++){
   gchar **parts=g_strsplit(lines[i],"\t",-1);
   GtkWidget *row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
   gtk_widget_set_margin_start(row,6);
   gtk_widget_set_margin_end(row,6);
   gtk_widget_set_margin_top(row,5);
   gtk_widget_set_margin_bottom(row,5);
   gboolean usable=!strcmp(parts[3],"1");
   if(usable)
     g_object_set_data_full(G_OBJECT(row),"now-magnet",g_strdup(parts[5]),g_free);
   gtk_widget_set_tooltip_text(row,usable ?
     "Select to choose a download folder" :
     "Plugin returned a webpage rather than a usable magnet link");
   GtkWidget *name=text(parts[4]);
   gtk_widget_set_name(name,"nowsearchtitle");
   gtk_widget_set_hexpand(name,TRUE);
   gtk_widget_set_tooltip_text(name,parts[4]);
   gtk_box_pack_start(GTK_BOX(row),name,TRUE,TRUE,0);
   gint64 size=g_ascii_strtoll(parts[1],NULL,10);
   gint64 seeds=g_ascii_strtoll(parts[2],NULL,10);
   gint64 published=parts[6] ? g_ascii_strtoll(parts[6],NULL,10):-1;
   gint64 leechers=g_strv_length(parts)==8 ?
                   g_ascii_strtoll(parts[7],NULL,10):-1;
   gint64 *size_data=g_new(gint64,1),*seed_data=g_new(gint64,1);
   gint64 *published_data=g_new(gint64,1),*leecher_data=g_new(gint64,1);
   *size_data=size;*seed_data=seeds;*published_data=published;*leecher_data=leechers;
   g_object_set_data_full(G_OBJECT(row),"now-search-leechers",leecher_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-published",published_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-size",size_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-seeds",seed_data,g_free);
   g_object_set_data_full(G_OBJECT(row),"now-search-title",g_strdup(parts[4]),g_free);
   gchar *size_text=size>=0 ? g_format_size((guint64)size) : g_strdup("—");
   gchar *seed_text=seeds>=0 ? g_strdup_printf("%lld",(long long)seeds) :
                               g_strdup("—");
   gchar *leecher_text=leechers>=0 ? g_strdup_printf("%lld",(long long)leechers) :
                               g_strdup("—");
   GDateTime *published_date=published>0 ?
      g_date_time_new_from_unix_local(published):NULL;
   gchar *date_text=published_date ?
      g_date_time_format(published_date,"%Y-%m-%d") : g_strdup("—");
   if(published_date)g_date_time_unref(published_date);
   const char *fields[]={size_text,seed_text,leecher_text,date_text};
   const gint widths[]={108,84,84,122};
   for(guint col=0;col<4;col++){
     GtkWidget *cell=text(fields[col]);
     gtk_widget_set_name(cell,"nowsearchmeta");
     gtk_widget_set_size_request(cell,widths[col],-1);
     gtk_widget_set_halign(cell,GTK_ALIGN_START);
     gtk_box_pack_start(GTK_BOX(row),cell,FALSE,FALSE,0);
   }
   g_free(size_text);g_free(seed_text);g_free(leecher_text);g_free(date_text);
   gtk_container_add(GTK_CONTAINER(s->list),row);
   g_strfreev(parts);
 }
 s->result_count+=count;
 s->partial=partial!=0;
 gtk_list_box_invalidate_sort(GTK_LIST_BOX(s->list));
 if(s->result_count){
   gtk_widget_show_all(s->list);
   gtk_widget_show(s->results);
   gchar *message=NULL;
   if(total>s->result_count)
     message=g_strdup_printf("%u of %"G_GINT64_FORMAT" results%s — select a magnet to choose its folder",
       s->result_count,total,partial?" (searching...)":" (source count differs)");
   else
     message=g_strdup_printf("%u result%s%s — select a magnet to choose its folder",
       s->result_count,s->result_count==1?"":"s",partial ?
       (s->result_count>=1000?" (first 1000 shown)":" (searching...)") : "");
   gtk_label_set_text(GTK_LABEL(s->status),message);
   g_free(message);
 }else{
   gtk_label_set_text(GTK_LABEL(s->status),partial ?
      "Searching enabled plugins..." : "No results from enabled plugins.");
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
static void stream_finished(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 SearchJob *job=data;
 SearchView *s=state(job->view);
 GError *err=NULL;
 gboolean ok=g_subprocess_wait_finish(job->proc,res,&err) &&
             g_subprocess_get_successful(job->proc) &&
             job->done && job->got_frame && !job->invalid;
 if(s){
   if(!g_strcmp0(s->host,job->host) && !g_strcmp0(s->user,job->user)){
     if(!ok){
       if(!job->got_frame)clear_results(s);
       gtk_label_set_text(GTK_LABEL(s->status),
         "Search stopped or unavailable; previously received results retained.");
     }else if(s->partial){
       gchar *ended=g_strdup_printf(
         "%u result%s collected; search time limit reached. Some plugins may not have finished.",
         s->result_count,s->result_count==1?"":"s");
       gtk_label_set_text(GTK_LABEL(s->status),ended);
       g_free(ended);
     }
   }
   s->running=FALSE;
   gtk_widget_set_sensitive(s->entry,TRUE);
   gtk_widget_set_sensitive(s->button,s->host && s->user && s->helper);
 }
 g_clear_error(&err);
 g_object_unref(job->reader);
 g_object_unref(job->proc);
 g_object_unref(job->view);
 g_free(job->host);g_free(job->user);g_free(job);
}
static void stream_line(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 SearchJob *job=data;
 GError *err=NULL;
 gsize size=0;
 gchar *line=g_data_input_stream_read_line_finish(job->reader,res,&size,&err);
 if(!line || err){
   if(err)job->invalid=TRUE;
   g_clear_error(&err);g_free(line);
   g_subprocess_wait_async(job->proc,NULL,stream_finished,job);
   return;
 }
 if(size>0 && size<=245000 && g_str_has_prefix(line,"SNAPSHOT\t")){
   gsize bytes=0;
   guchar *raw=g_base64_decode(line+9,&bytes);
   if(bytes>0 && bytes<=MAX_WIRE && !memchr(raw,0,bytes)){
     gchar *wire=g_strndup((char *)raw,bytes);
     SearchView *s=state(job->view);
     if(s && !g_strcmp0(s->host,job->host) &&
        !g_strcmp0(s->user,job->user) &&
        now_downloads_search_view_update(job->view,wire))
       job->got_frame=TRUE;
     else job->invalid=TRUE;
     g_free(wire);
   }else job->invalid=TRUE;
   g_free(raw);
 }else if(!strcmp(line,"DONE")){
   job->done=TRUE;
 }else job->invalid=TRUE;
 g_free(line);
 if(job->invalid){
   g_subprocess_force_exit(job->proc);
   g_subprocess_wait_async(job->proc,NULL,stream_finished,job);
   return;
 }
 g_data_input_stream_read_line_async(job->reader,G_PRIORITY_DEFAULT,
                                     NULL,stream_line,job);
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
 const gchar *argv[]={"/usr/bin/python3",s->helper,s->host,s->user,query,
                      "--stream",NULL};
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
 job->reader=g_data_input_stream_new(g_subprocess_get_stdout_pipe(proc));
 s->running=TRUE;
 clear_results(s);
 gtk_widget_set_sensitive(s->entry,FALSE);
 gtk_widget_set_sensitive(s->button,FALSE);
 gtk_label_set_text(GTK_LABEL(s->status),
     "Searching enabled qBittorrent plugins; results update automatically...");
 g_data_input_stream_read_line_async(job->reader,G_PRIORITY_DEFAULT,
                                     NULL,stream_line,job);
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
 gtk_style_context_add_class(gtk_widget_get_style_context(s->button),"now-action");
 gtk_style_context_add_class(gtk_widget_get_style_context(s->button),"now-primary");
 gtk_widget_set_sensitive(s->button,FALSE);
 gtk_box_pack_start(GTK_BOX(bar),s->button,FALSE,FALSE,0);
 g_signal_connect(s->button,"clicked",G_CALLBACK(start_search),view);
 g_signal_connect(s->entry,"activate",G_CALLBACK(start_search),view);
 /* One continuously scrollable sortable table; all results remain visible. */
 GtkWidget *head=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6);
 gtk_widget_set_margin_start(head,6);
 gtk_widget_set_margin_end(head,6);
 const char *headers[]={"NAME","SIZE ↑","SEEDERS","LEECHERS","PUBLISHED"};
 const char *ids[]={"nowsearchheader_name","nowsearchheader_size",
                   "nowsearchheader_seeds","nowsearchheader_leechers",
                   "nowsearchheader_published"};
 const gint widths[]={-1,108,84,84,122};
 for(guint col=0;col<5;col++){
   GtkWidget *button=gtk_button_new_with_label(headers[col]);
   gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-action");
   gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-sort");
   gtk_widget_set_name(button,ids[col]);
   gtk_widget_set_tooltip_text(button,"Click to sort; click again to reverse");
   if(col==0)gtk_widget_set_hexpand(button,TRUE);
   else gtk_widget_set_size_request(button,widths[col],-1);
   gtk_box_pack_start(GTK_BOX(head),button,col==0,col==0,0);
   g_object_set_data(G_OBJECT(button),"now-sort-column",GUINT_TO_POINTER(col+1));
   g_signal_connect(button,"clicked",G_CALLBACK(header_clicked),view);
   s->headers[col]=button;
 }
 s->sort_column=1;s->ascending=TRUE;
 gtk_box_pack_start(GTK_BOX(view),head,FALSE,FALSE,0);
 s->status=text("Connect an approved owner device to search.");
 gtk_box_pack_start(GTK_BOX(view),s->status,FALSE,FALSE,0);
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
