/* Native Transfers. Receives bounded, owner-approved data; no privileged APIs here. */
#include "downloads_queue_view.h"
#include <math.h>
#include <string.h>

typedef struct {
 NowDownloadQueueAction callback;
 gpointer user_data;
} QueueContext;
typedef enum {
 NOW_FILTER_ACTIVE, NOW_FILTER_STALLED, NOW_FILTER_COMPLETED, NOW_FILTER_ALL
} NowQueueFilter;
static const char *const filter_names[]={"Active","Stalled","Completed","All"};
static void apply_queue_filter(GtkWidget *view);
static void on_filter_clicked(GtkToggleButton *button,gpointer data){
 if(!gtk_toggle_button_get_active(button))return;
 GtkWidget *view=GTK_WIDGET(data);
 g_object_set_data(G_OBJECT(view),"now-filter",
                   g_object_get_data(G_OBJECT(button),"now-filter-value"));
 apply_queue_filter(view);
}
static GtkWidget *list_for(GtkWidget *view){
 return view ? g_object_get_data(G_OBJECT(view),"now-download-list") : NULL;
}
static void clear_list(GtkWidget *list){
 if(!list)return;
 GList *children=gtk_container_get_children(GTK_CONTAINER(list));
 for(GList *at=children;at;at=at->next)
   gtk_widget_destroy(GTK_WIDGET(at->data));
 g_list_free(children);
}
static GtkWidget *text_label(const char *value){
 GtkWidget *label=gtk_label_new(value);
 gtk_label_set_xalign(GTK_LABEL(label),0);
 gtk_label_set_ellipsize(GTK_LABEL(label),PANGO_ELLIPSIZE_END);
 return label;
}
static void show_message(GtkWidget *list,const char *message){
 clear_list(list);
 GtkWidget *label=text_label(message);
 gtk_widget_set_margin_start(label,8);
 gtk_widget_set_margin_top(label,12);
 gtk_container_add(GTK_CONTAINER(list),label);
 gtk_widget_show_all(list);
}
static gboolean stalled_state(const gchar *state){
 return state && g_str_has_prefix(state,"stalled");
}
static gboolean matches_filter(NowQueueFilter filter,const gchar *state,
                               double progress){
 switch(filter){
  case NOW_FILTER_ACTIVE: return progress<100.0;
  case NOW_FILTER_STALLED: return stalled_state(state);
  case NOW_FILTER_COMPLETED: return progress>=100.0;
  default: return TRUE;
 }
}
static void apply_queue_filter(GtkWidget *view){
 GtkWidget *list=list_for(view);
 if(!list)return;
 NowQueueFilter selected=(NowQueueFilter)GPOINTER_TO_INT(
     g_object_get_data(G_OBJECT(view),"now-filter"));
 guint counts[4]={0,0,0,0},visible=0;
 GList *rows=gtk_container_get_children(GTK_CONTAINER(list));
 for(GList *it=rows;it;it=it->next){
   GtkWidget *row=GTK_WIDGET(it->data);
   GtkWidget *body=GTK_IS_BIN(row)?gtk_bin_get_child(GTK_BIN(row)):NULL;
   const gchar *state=body?
       g_object_get_data(G_OBJECT(body),"now-torrent-state"):NULL;
   const gchar *progress_text=body?
       g_object_get_data(G_OBJECT(body),"now-torrent-percent"):NULL;
   if(!state || !progress_text)continue;
   double percent=g_ascii_strtod(progress_text,NULL);
   for(guint i=0;i<4;i++)
     if(matches_filter((NowQueueFilter)i,state,percent))counts[i]++;
   gboolean match=matches_filter(selected,state,percent);
   gtk_widget_set_visible(row,match);
   if(match)visible++;
 }
 g_list_free(rows);
 GtkWidget *buttons[4];
 for(guint i=0;i<4;i++){
   gchar *key=g_strdup_printf("now-filter-button-%u",i);
   buttons[i]=g_object_get_data(G_OBJECT(view),key);
   g_free(key);
   if(buttons[i]){
     gchar *label=g_strdup_printf("%s (%u)",filter_names[i],counts[i]);
     gtk_button_set_label(GTK_BUTTON(buttons[i]),label);
     g_free(label);
   }
 }
 GtkWidget *empty=g_object_get_data(G_OBJECT(view),"now-queue-empty-filter");
 if(empty){
   gtk_label_set_text(GTK_LABEL(empty),counts[3]==0?
      "No torrents in the queue." :
      "No torrents in this category. Choose another tab to view them.");
   gtk_widget_set_visible(empty,visible==0);
 }
}
static gboolean valid_state(const char *value){
 if(!value || !*value || strlen(value)>48)return FALSE;
 for(const unsigned char *p=(const unsigned char*)value;*p;p++)
   if(!g_ascii_isalnum(*p) && *p!='_' && *p!='-')return FALSE;
 return TRUE;
}
static gboolean valid_hash(const char *value){
 if(!value || (strlen(value)!=40 && strlen(value)!=64))return FALSE;
 for(const unsigned char *p=(const unsigned char*)value;*p;p++)
   if(!g_ascii_isxdigit(*p))return FALSE;
 return TRUE;
}
static gboolean number(const char *value,gint64 min,gint64 max,gint64 *out){
 if(!value || !*value)return FALSE;
 gchar *end=NULL;
 gint64 n=g_ascii_strtoll(value,&end,10);
 if(!end || *end || n<min || n>max)return FALSE;
 if(out)*out=n;
 return TRUE;
}
static void perform_action(GtkWidget *button,gpointer data){
 GtkWidget *view=data;
 QueueContext *ctx=g_object_get_data(G_OBJECT(view),"now-queue-context");
 const char *action=g_object_get_data(G_OBJECT(button),"now-action");
 const char *hash=g_object_get_data(G_OBJECT(button),"now-hash");
 const char *name=g_object_get_data(G_OBJECT(button),"now-name");
 if(!ctx || !ctx->callback || !action || !valid_hash(hash) || !name)return;
 /* The queue refresh may rebuild rows while a modal confirmation runs. */
 gchar *operation_copy=g_strdup(action);
 gchar *hash_copy=g_strdup(hash);
 gchar *name_copy=g_strdup(name);
 if(!strcmp(operation_copy,"remove") || !strcmp(operation_copy,"remove_delete")){
   GtkWidget *parent=gtk_widget_get_toplevel(view);
   GtkWidget *dialog=gtk_message_dialog_new(
     GTK_IS_WINDOW(parent)?GTK_WINDOW(parent):NULL,GTK_DIALOG_MODAL,
     GTK_MESSAGE_WARNING,GTK_BUTTONS_NONE,
     !strcmp(operation_copy,"remove_delete") ?
       "Permanently delete the downloaded torrent files?" :
       "Remove torrent from Transfers?");
   gchar *warning=!strcmp(operation_copy,"remove_delete") ?
     g_strdup_printf("Torrent: %s\n\nDELETE DATA on the server for this torrent. "
                     "This cannot be undone. Only approved media subfolders "
                     "can be deleted through NOW.",name) :
     g_strdup("Downloaded files will be kept. Remove this torrent from qBittorrent's queue?");
   gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),"%s",warning);
   g_free(warning);
   gtk_dialog_add_buttons(GTK_DIALOG(dialog),"CANCEL",GTK_RESPONSE_CANCEL,
       !strcmp(operation_copy,"remove_delete") ?
         "DELETE TORRENT AND FILES" : "REMOVE TORRENT",GTK_RESPONSE_ACCEPT,NULL);
   gtk_dialog_set_default_response(GTK_DIALOG(dialog),GTK_RESPONSE_CANCEL);
   gint result=gtk_dialog_run(GTK_DIALOG(dialog));
   gtk_widget_destroy(dialog);
   if(result!=GTK_RESPONSE_ACCEPT)goto done;
 }
 ctx->callback(operation_copy,hash_copy,name_copy,ctx->user_data);
done:
 g_free(operation_copy);g_free(hash_copy);g_free(name_copy);
}
/* Standard native right-click menu. No persistent action rows. */
static void show_transfer_menu(GtkWidget *view,const char *hash,
                               const char *name,const char *state,
                               GdkEvent *event){
 GtkWidget *menu=gtk_menu_new();
 const char *toggle=(!strcmp(state,"pausedDL") || !strcmp(state,"pausedUP") ||
                     !strcmp(state,"stoppedDL") || !strcmp(state,"stoppedUP"))
                     ? "resume" : "pause";
 const char *actions[]={toggle,"reannounce","recheck","files",
                        "remove","remove_delete"};
 const char *labels[]={!strcmp(toggle,"pause")?"Pause":"Resume",
                       "Reannounce","Force recheck","View files",
                       "Remove torrent (keep files)","Delete torrent and files"};
 for(guint j=0;j<G_N_ELEMENTS(actions);j++){
   if(j==4)gtk_menu_shell_append(GTK_MENU_SHELL(menu),
                                 gtk_separator_menu_item_new());
   GtkWidget *item=gtk_menu_item_new_with_label(labels[j]);
   g_object_set_data_full(G_OBJECT(item),"now-action",g_strdup(actions[j]),g_free);
   g_object_set_data_full(G_OBJECT(item),"now-hash",g_strdup(hash),g_free);
   g_object_set_data_full(G_OBJECT(item),"now-name",g_strdup(name),g_free);
   g_signal_connect(item,"activate",G_CALLBACK(perform_action),view);
   gtk_menu_shell_append(GTK_MENU_SHELL(menu),item);
 }
 g_signal_connect_swapped(menu,"selection-done",G_CALLBACK(gtk_widget_destroy),menu);
 gtk_widget_show_all(menu);
 gtk_menu_popup_at_pointer(GTK_MENU(menu),event);
}
static gboolean transfer_button_press(GtkWidget *widget,GdkEventButton *event,
                                      gpointer data){
 if(event->type!=GDK_BUTTON_PRESS || event->button!=3)return FALSE;
 const char *hash=g_object_get_data(G_OBJECT(widget),"now-torrent-hash");
 const char *name=g_object_get_data(G_OBJECT(widget),"now-torrent-name");
 const char *state=g_object_get_data(G_OBJECT(widget),"now-torrent-state");
 if(hash && name && state)
   show_transfer_menu(GTK_WIDGET(data),hash,name,state,(GdkEvent *)event);
 return TRUE;
}
static gboolean transfer_key_press(GtkWidget *widget,GdkEventKey *event,
                                   gpointer data){
 if(event->keyval!=GDK_KEY_Menu &&
    !(event->keyval==GDK_KEY_F10 && (event->state&GDK_SHIFT_MASK)))
   return FALSE;
 const char *hash=g_object_get_data(G_OBJECT(widget),"now-torrent-hash");
 const char *name=g_object_get_data(G_OBJECT(widget),"now-torrent-name");
 const char *state=g_object_get_data(G_OBJECT(widget),"now-torrent-state");
 if(hash && name && state)
   show_transfer_menu(GTK_WIDGET(data),hash,name,state,NULL);
 return TRUE;
}
void now_downloads_queue_view_on_action(GtkWidget *view,
                                       NowDownloadQueueAction callback,
                                       gpointer user_data){
 if(!view)return;
 QueueContext *ctx=g_new0(QueueContext,1);
 ctx->callback=callback;ctx->user_data=user_data;
 g_object_set_data_full(G_OBJECT(view),"now-queue-context",ctx,g_free);
}
GtkWidget *now_downloads_queue_view_new(void){
 /* The parent Downloads page owns vertical scrolling. A nested Transfers
  * scroller trapped the wheel and stranded toolbar/picker controls. */
 GtkWidget *scroll=gtk_box_new(GTK_ORIENTATION_VERTICAL,7);
 GtkWidget *filters=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,5);
 GtkWidget *previous=NULL;
 for(guint i=0;i<4;i++){
   GtkWidget *button=gtk_radio_button_new_with_label_from_widget(
       previous?GTK_RADIO_BUTTON(previous):NULL,filter_names[i]);
   if(!previous)previous=button;
   g_object_set_data(G_OBJECT(button),"now-filter-value",
                     GINT_TO_POINTER((gint)i));
   gchar *key=g_strdup_printf("now-filter-button-%u",i);
   g_object_set_data(G_OBJECT(scroll),key,button);
   g_free(key);
   g_signal_connect(button,"toggled",G_CALLBACK(on_filter_clicked),scroll);
   gtk_box_pack_start(GTK_BOX(filters),button,FALSE,FALSE,0);
   if(i==0)gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(button),TRUE);
 }
 gtk_box_pack_start(GTK_BOX(scroll),filters,FALSE,FALSE,0);
 GtkWidget *list=gtk_list_box_new();
 gtk_widget_set_name(list,"nowqueuelist");
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(list),GTK_SELECTION_NONE);
 gtk_box_pack_start(GTK_BOX(scroll),list,FALSE,FALSE,0);
 g_object_set_data(G_OBJECT(scroll),"now-download-list",list);
 GtkWidget *empty=gtk_label_new("");
 gtk_label_set_xalign(GTK_LABEL(empty),0);
 gtk_widget_set_margin_start(empty,8);
 g_object_set_data(G_OBJECT(scroll),"now-queue-empty-filter",empty);
 gtk_box_pack_start(GTK_BOX(scroll),empty,FALSE,FALSE,0);
 /* Show only after the first queue response. The early placeholder is useful. */
 show_message(list,"Open Downloads to view the approved host queue.");
 return scroll;
}
void now_downloads_queue_view_message(GtkWidget *view,const char *message){
 GtkWidget *list=list_for(view);
 if(list)show_message(list,message ? message : "Queue unavailable.");
}
gboolean now_downloads_queue_view_update(GtkWidget *view,const char *wire){
 GtkWidget *list=list_for(view);
 if(!list || !wire || !*wire || strlen(wire)>32768 ||
    wire[strlen(wire)-1]=='\n' || !g_utf8_validate(wire,-1,NULL))return FALSE;
 gchar **lines=g_strsplit(wire,"\n",-1);
 gboolean empty=!strcmp(wire,"EMPTY"), valid=TRUE;
 guint count=0;
 if(!empty){
   for(guint i=0;lines[i];i++){
     if(++count>100 || !*lines[i]){valid=FALSE;break;}
     gchar **parts=g_strsplit(lines[i],"\t",-1);
     gint64 speed=0,eta=0,seeds=0;
     if(g_strv_length(parts)!=8 || strcmp(parts[0],"ITEM") ||
        !valid_state(parts[2]) || !*parts[3] ||
        g_utf8_strlen(parts[3],-1)>160 || !valid_hash(parts[4]) ||
        !number(parts[5],-1,G_MAXINT32,&speed) ||
        !number(parts[6],-1,G_MAXINT32,&eta) ||
        !number(parts[7],-1,G_MAXINT32,&seeds)){
       valid=FALSE;
     }else{
       gchar *end=NULL;
       double progress=g_ascii_strtod(parts[1],&end);
       if(!*parts[1] || !end || *end || !isfinite(progress) ||
          progress<0 || progress>100)valid=FALSE;
     }
     g_strfreev(parts);
     if(!valid)break;
   }
 }
 if(!valid){g_strfreev(lines);return FALSE;}
 clear_list(list);
 if(empty){
   /* The filter-specific empty hint handles this state. */
   gtk_widget_show(list);
 }else{
   for(guint i=0;lines[i];i++){
     gchar **parts=g_strsplit(lines[i],"\t",-1);
     double percent=g_ascii_strtod(parts[1],NULL);
     gint64 speed=g_ascii_strtoll(parts[5],NULL,10);
     gint64 eta=g_ascii_strtoll(parts[6],NULL,10);
     gint64 seeds=g_ascii_strtoll(parts[7],NULL,10);
     GtkWidget *row=gtk_box_new(GTK_ORIENTATION_VERTICAL,5);
     gtk_widget_set_margin_start(row,8);
     gtk_widget_set_margin_end(row,8);
     gtk_widget_set_margin_top(row,7);
     gtk_widget_set_margin_bottom(row,7);
     GtkWidget *title=text_label(parts[3]);
     GtkWidget *bar=gtk_progress_bar_new();
     gtk_progress_bar_set_fraction(GTK_PROGRESS_BAR(bar),percent/100.0);
     gchar *speed_text=speed>=0 ? g_format_size((guint64)speed) :
                                  g_strdup("Unknown");
     gchar *detail=g_strdup_printf(
        "%.1f%% · %s · %s/s · ETA %s · %lld seeds",
        percent,parts[2],speed_text,eta>=0 && eta<86400 ?
             "see below" : "unknown",(long long)seeds);
     if(eta>=0 && eta<86400){
       g_free(detail);
       detail=g_strdup_printf("%.1f%% · %s · %s/s · ETA %lldm %llds · %lld seeds",
          percent,parts[2],speed_text,(long long)(eta/60),
          (long long)(eta%60),(long long)seeds);
     }
     g_free(speed_text);
     GtkWidget *meta=text_label(detail);g_free(detail);
     gtk_widget_set_name(title,"downloadtitle");
     gtk_widget_set_name(meta,"downloadmeta");
     gtk_box_pack_start(GTK_BOX(row),title,FALSE,FALSE,0);
     gtk_box_pack_start(GTK_BOX(row),bar,FALSE,FALSE,0);
     gtk_box_pack_start(GTK_BOX(row),meta,FALSE,FALSE,0);
     GtkWidget *event_box=gtk_event_box_new();
     gtk_widget_set_can_focus(event_box,TRUE);
     gtk_widget_set_tooltip_text(event_box,
          "Right-click for torrent actions; Shift+F10 for keyboard.");
     g_object_set_data_full(G_OBJECT(event_box),"now-torrent-hash",
                            g_strdup(parts[4]),g_free);
     g_object_set_data_full(G_OBJECT(event_box),"now-torrent-name",
                            g_strdup(parts[3]),g_free);
     g_object_set_data_full(G_OBJECT(event_box),"now-torrent-state",
                            g_strdup(parts[2]),g_free);
     g_object_set_data_full(G_OBJECT(event_box),"now-torrent-percent",
                            g_strdup(parts[1]),g_free);
     gtk_container_add(GTK_CONTAINER(event_box),row);
     g_signal_connect(event_box,"button-press-event",
                      G_CALLBACK(transfer_button_press),view);
     g_signal_connect(event_box,"key-press-event",
                      G_CALLBACK(transfer_key_press),view);
     gtk_container_add(GTK_CONTAINER(list),event_box);
     g_strfreev(parts);
   }
   gtk_widget_show_all(list);
 }
 apply_queue_filter(view);
 g_strfreev(lines);
 return TRUE;
}

/* A per-torrent file inspection dialog, not a filesystem browser.
 * The owner broker returns bounded relative names, sizes and progress only.
 * No arbitrary path or delete capability is exposed here. */
gboolean now_downloads_queue_view_files_dialog(GtkWidget *view,
       const char *wire,const char *expected_hash,const char *torrent_name){
 if(!view || !GTK_IS_WIDGET(view) || !valid_hash(expected_hash) ||
    !wire || !g_utf8_validate(wire,-1,NULL) ||
    !*wire || strlen(wire)>32768 || wire[strlen(wire)-1]=='\n')
   return FALSE;
 gchar **lines=g_strsplit(wire,"\n",-1);
 gchar **header=g_strsplit(lines[0],"\t",-1);
 gint64 truncated=0,total=0;
 gboolean valid=g_strv_length(header)==4 && !strcmp(header[0],"FILES") &&
       !g_ascii_strcasecmp(header[1],expected_hash) &&
       number(header[2],0,1,&truncated) &&
       number(header[3],0,120,&total) &&
       g_strv_length(lines)==(guint)total+1;
 g_strfreev(header);
 for(guint i=1;valid && lines[i];i++){
   gchar **fields=g_strsplit(lines[i],"\t",-1);
   gint64 bytes=0,priority=0;
   gchar *end=NULL;
   double progress=0;
   if(g_strv_length(fields)!=5 ||
      strcmp(fields[0],"FILE") ||
      !number(fields[1],0,G_MAXINT64,&bytes) ||
      !number(fields[3],0,7,&priority) ||
      !*fields[2]){
     valid=FALSE;
   }else{
     progress=g_ascii_strtod(fields[2],&end);
     const char *name=fields[4];
     valid=end && !*end && isfinite(progress) && progress>=0 &&
           progress<=100 && name && *name &&
           g_utf8_strlen(name,-1)<=220 && name[0]!='/' &&
           !strchr(name,'\\');
     if(valid){
       gchar **pieces=g_strsplit(name,"/",-1);
       for(guint j=0;pieces[j];j++)
         if(!*pieces[j] || !strcmp(pieces[j],".") ||
            !strcmp(pieces[j],".."))valid=FALSE;
       g_strfreev(pieces);
     }
   }
   g_strfreev(fields);
 }
 if(!valid){g_strfreev(lines);return FALSE;}
 GtkWidget *toplevel=gtk_widget_get_toplevel(view);
 GtkWidget *dialog=gtk_dialog_new_with_buttons("TORRENT FILES",
     GTK_IS_WINDOW(toplevel)?GTK_WINDOW(toplevel):NULL,
     GTK_DIALOG_MODAL|GTK_DIALOG_DESTROY_WITH_PARENT,
     "CLOSE",GTK_RESPONSE_CLOSE,NULL);
 gtk_window_set_default_size(GTK_WINDOW(dialog),650,430);
 GtkWidget *area=gtk_dialog_get_content_area(GTK_DIALOG(dialog));
 gtk_container_set_border_width(GTK_CONTAINER(area),12);
 GtkWidget *heading=gtk_label_new(torrent_name?torrent_name:"Torrent files");
 gtk_label_set_xalign(GTK_LABEL(heading),0);
 gtk_label_set_ellipsize(GTK_LABEL(heading),PANGO_ELLIPSIZE_END);
 gtk_widget_set_tooltip_text(heading,torrent_name?torrent_name:"Torrent files");
 gtk_box_pack_start(GTK_BOX(area),heading,FALSE,FALSE,4);
 GtkWidget *summary=gtk_label_new(truncated ?
      "First 120 files shown; open Advanced VueTorrent for the complete list." :
      "Read-only torrent contents. No downloaded files are opened or modified.");
 gtk_label_set_xalign(GTK_LABEL(summary),0);
 gtk_label_set_line_wrap(GTK_LABEL(summary),TRUE);
 gtk_box_pack_start(GTK_BOX(area),summary,FALSE,FALSE,4);
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 gtk_widget_set_vexpand(scroll,TRUE);
 GtkWidget *list=gtk_list_box_new();
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(list),GTK_SELECTION_NONE);
 gtk_container_add(GTK_CONTAINER(scroll),list);
 gtk_box_pack_start(GTK_BOX(area),scroll,TRUE,TRUE,4);
 for(guint i=1;lines[i];i++){
   gchar **fields=g_strsplit(lines[i],"\t",-1);
   gint64 bytes=g_ascii_strtoll(fields[1],NULL,10);
   const gchar *progress=fields[2];
   gint priority=(gint)g_ascii_strtoll(fields[3],NULL,10);
   GtkWidget *row=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);
   gtk_widget_set_margin_start(row,8);
   gtk_widget_set_margin_end(row,8);
   gtk_widget_set_margin_top(row,6);
   gtk_widget_set_margin_bottom(row,6);
   GtkWidget *name=gtk_label_new(fields[4]);
   gtk_label_set_xalign(GTK_LABEL(name),0);
   gtk_label_set_ellipsize(GTK_LABEL(name),PANGO_ELLIPSIZE_MIDDLE);
   gtk_widget_set_tooltip_text(name,fields[4]);
   gchar *size=g_format_size((guint64)bytes);
   gchar *meta=g_strdup_printf("%s · %s%% downloaded · %s",size,progress,
                                priority==0?"Skipped":"Included");
   GtkWidget *detail=gtk_label_new(meta);
   gtk_label_set_xalign(GTK_LABEL(detail),0);
   gtk_box_pack_start(GTK_BOX(row),name,FALSE,FALSE,0);
   gtk_box_pack_start(GTK_BOX(row),detail,FALSE,FALSE,0);
   gtk_container_add(GTK_CONTAINER(list),row);
   g_free(meta);g_free(size);g_strfreev(fields);
 }
 if(total==0){
   GtkWidget *empty=gtk_label_new("No file metadata available yet.");
   gtk_container_add(GTK_CONTAINER(list),empty);
 }
 gtk_widget_show_all(dialog);
 gtk_dialog_run(GTK_DIALOG(dialog));
 gtk_widget_destroy(dialog);
 g_strfreev(lines);
 return TRUE;
}
