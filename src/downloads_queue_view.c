/* Native Transfers. Receives bounded, owner-approved data; no privileged APIs here. */
#include "downloads_queue_view.h"
#include <math.h>
#include <string.h>

typedef struct {
 NowDownloadQueueAction callback;
 gpointer user_data;
} QueueContext;
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
static void perform_action(GtkButton *button,gpointer data){
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
 if(!strcmp(operation_copy,"remove")){
   GtkWidget *parent=gtk_widget_get_toplevel(view);
   GtkWidget *dialog=gtk_message_dialog_new(
     GTK_IS_WINDOW(parent)?GTK_WINDOW(parent):NULL,GTK_DIALOG_MODAL,
     GTK_MESSAGE_WARNING,GTK_BUTTONS_NONE,
     "Remove torrent from Transfers?");
   gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
     "Downloaded files will be kept. Remove this torrent from qBittorrent's queue?");
   gtk_dialog_add_buttons(GTK_DIALOG(dialog),"CANCEL",GTK_RESPONSE_CANCEL,
                          "REMOVE TORRENT",GTK_RESPONSE_ACCEPT,NULL);
   gint result=gtk_dialog_run(GTK_DIALOG(dialog));
   gtk_widget_destroy(dialog);
   if(result!=GTK_RESPONSE_ACCEPT)goto done;
 }
 ctx->callback(operation_copy,hash_copy,name_copy,ctx->user_data);
done:
 g_free(operation_copy);g_free(hash_copy);g_free(name_copy);
}
static GtkWidget *action_button(GtkWidget *view,const char *label,
                                const char *action,const char *hash,
                                const char *name){
 GtkWidget *button=gtk_button_new_with_label(label);
 gtk_widget_set_name(button,"downloadoperation");
 gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-action");
 g_object_set_data_full(G_OBJECT(button),"now-action",g_strdup(action),g_free);
 g_object_set_data_full(G_OBJECT(button),"now-hash",g_strdup(hash),g_free);
 g_object_set_data_full(G_OBJECT(button),"now-name",g_strdup(name),g_free);
 g_signal_connect(button,"clicked",G_CALLBACK(perform_action),view);
 return button;
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
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 GtkWidget *list=gtk_list_box_new();
 gtk_widget_set_name(list,"nowqueuelist");
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(list),GTK_SELECTION_NONE);
 gtk_container_add(GTK_CONTAINER(scroll),list);
 g_object_set_data(G_OBJECT(scroll),"now-download-list",list);
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
   show_message(list,"No downloads in queue.");
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
     GtkWidget *buttons=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,5);
     const char *toggle=(!strcmp(parts[2],"pausedDL") ||
                          !strcmp(parts[2],"pausedUP") ||
                          !strcmp(parts[2],"stoppedDL") ||
                          !strcmp(parts[2],"stoppedUP")) ? "resume" : "pause";
     const char *actions[]={toggle,"reannounce","recheck","remove"};
     const char *labels[]={!strcmp(toggle,"pause")?"PAUSE":"RESUME",
                           "REANNOUNCE","RECHECK","REMOVE"};
     for(guint j=0;j<4;j++)
       gtk_box_pack_start(GTK_BOX(buttons),
          action_button(view,labels[j],actions[j],parts[4],parts[3]),FALSE,FALSE,0);
     gtk_box_pack_start(GTK_BOX(row),buttons,FALSE,FALSE,0);
     gtk_container_add(GTK_CONTAINER(list),row);
     g_strfreev(parts);
   }
   gtk_widget_show_all(list);
 }
 g_strfreev(lines);
 return TRUE;
}
