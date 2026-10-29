/* Native download progress list. Input is the sanitized bounded line protocol
 * from download-queue-client.py --native, not raw qBittorrent JSON.
 * This module holds NO credentials, WebUI cookies or Docker paths.
 */
#include "downloads_queue_view.h"
#include <math.h>
#include <string.h>

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
GtkWidget *now_downloads_queue_view_new(void){
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 GtkWidget *list=gtk_list_box_new();
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
static gboolean valid_state(const char *state){
 if(!state || !*state || strlen(state)>48)return FALSE;
 for(const unsigned char *p=(const unsigned char *)state;*p;p++)
   if(!g_ascii_isalnum(*p) && *p!='_' && *p!='-')return FALSE;
 return TRUE;
}
gboolean now_downloads_queue_view_update(GtkWidget *view,const char *wire){
 GtkWidget *list=list_for(view);
 if(!list || !wire || !*wire || strlen(wire)>32768 ||
    !g_utf8_validate(wire,-1,NULL))return FALSE;
 gchar **lines=g_strsplit(wire,"\n",-1);
 guint count=0;
 gboolean empty=!strcmp(wire,"EMPTY");
 gboolean valid=TRUE;
 if(!empty){
   for(guint i=0;lines[i];i++){
     if(++count>100 || !*lines[i]){valid=FALSE;break;}
     gchar **parts=g_strsplit(lines[i],"\t",-1);
     if(g_strv_length(parts)!=4 || strcmp(parts[0],"ITEM") ||
        !valid_state(parts[2]) || !*parts[3] ||
        g_utf8_strlen(parts[3],-1)>160){
       valid=FALSE;
     }else{
       gchar *end=NULL;
       double p=g_ascii_strtod(parts[1],&end);
       if(!*parts[1] || !end || *end || !isfinite(p) || p<0 || p>100)
         valid=FALSE;
     }
     g_strfreev(parts);
     if(!valid)break;
   }
 }
 if(!valid){
   g_strfreev(lines);
   return FALSE;
 }
 clear_list(list);
 if(empty){
   show_message(list,"No downloads in queue.");
 }else{
   for(guint i=0;lines[i];i++){
     gchar **parts=g_strsplit(lines[i],"\t",4);
     const double percent=g_ascii_strtod(parts[1],NULL);
     GtkWidget *row=gtk_box_new(GTK_ORIENTATION_VERTICAL,3);
     gtk_widget_set_margin_start(row,8);
     gtk_widget_set_margin_end(row,8);
     gtk_widget_set_margin_top(row,6);
     gtk_widget_set_margin_bottom(row,6);
     GtkWidget *name=text_label(parts[3]);
     GtkWidget *state=text_label(parts[2]);
     GtkWidget *bar=gtk_progress_bar_new();
     gtk_progress_bar_set_fraction(GTK_PROGRESS_BAR(bar),percent/100.0);
     gchar *detail=g_strdup_printf("%.1f%%  %s",percent,parts[2]);
     gtk_label_set_text(GTK_LABEL(state),detail);
     g_free(detail);
     gtk_box_pack_start(GTK_BOX(row),name,FALSE,FALSE,0);
     gtk_box_pack_start(GTK_BOX(row),bar,FALSE,FALSE,0);
     gtk_box_pack_start(GTK_BOX(row),state,FALSE,FALSE,0);
     gtk_container_add(GTK_CONTAINER(list),row);
     g_strfreev(parts);
   }
   gtk_widget_show_all(list);
 }
 g_strfreev(lines);
 return TRUE;
}
