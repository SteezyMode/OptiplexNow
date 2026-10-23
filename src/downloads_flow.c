#include "downloads_flow.h"
#include "presets.h"
#include <gio/gio.h>
#include <string.h>

static GtkWidget *queue_label;
static gboolean running;

typedef struct {
 GSubprocess *proc;
 char *host;
} QueueJob;

static char *helper_path(void){
 char *exe=g_file_read_link("/proc/self/exe",NULL);
 if(!exe)return g_strdup("/usr/lib/optiplex-now/download-queue-client.py");
 char *bin=g_path_get_dirname(exe);
 char *usr=g_path_get_dirname(bin);
 char *name=g_path_get_basename(usr);
 char *path;
 if(!strcmp(name,"usr") && strcmp(usr,"/usr")){
   char *root=g_path_get_dirname(usr);
   path=g_build_filename(root,"usr","lib","optiplex-now","download-queue-client.py",NULL);
   g_free(root);
 }else path=g_strdup("/usr/lib/optiplex-now/download-queue-client.py");
 g_free(exe);g_free(bin);g_free(usr);g_free(name);
 return path;
}
static void complete(GObject *source,GAsyncResult *res,gpointer data){
 (void)source;
 QueueJob *job=data;
 char *out=NULL;
 GError *err=NULL;
 gboolean ok=g_subprocess_communicate_utf8_finish(job->proc,res,&out,NULL,&err);
 if(queue_label){
   if(ok && g_subprocess_get_successful(job->proc) && out && strlen(out)<32768)
     gtk_label_set_text(GTK_LABEL(queue_label),out);
   else gtk_label_set_text(GTK_LABEL(queue_label),"Queue unavailable. Check server connection.");
 }
 running=FALSE;
 g_clear_error(&err);g_free(out);
 g_object_unref(job->proc);g_free(job->host);g_free(job);
}
void now_downloads_refresh(const char *host,const char *user){
 if(!queue_label || running)return;
 if(!now_valid_host(host) || !now_valid_user(user)){
   gtk_label_set_text(GTK_LABEL(queue_label),"Connect an approved NOW host in Settings.");
   return;
 }
 char *helper=helper_path();
 if(!g_file_test(helper,G_FILE_TEST_IS_REGULAR)){
   gtk_label_set_text(GTK_LABEL(queue_label),"Downloads helper missing.");
   g_free(helper);return;
 }
 const char *argv[]={"/usr/bin/python3",helper,host,user,NULL};
 GError *error=NULL;
 GSubprocess *proc=g_subprocess_newv(argv,
   G_SUBPROCESS_FLAGS_STDOUT_PIPE|G_SUBPROCESS_FLAGS_STDERR_SILENCE,&error);
 g_free(helper);
 if(!proc){
   gtk_label_set_text(GTK_LABEL(queue_label),"Unable to start queue request.");
   g_clear_error(&error);return;
 }
 QueueJob *job=g_new0(QueueJob,1);
 job->proc=proc;job->host=g_strdup(host);
 running=TRUE;
 gtk_label_set_text(GTK_LABEL(queue_label),"Reading authorized download queue...");
 g_subprocess_communicate_utf8_async(proc,NULL,NULL,complete,job);
}
GtkWidget *now_downloads_page(void){
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);
 GtkWidget *body=gtk_box_new(GTK_ORIENTATION_VERTICAL,14);
 gtk_container_set_border_width(GTK_CONTAINER(body),20);
 gtk_container_add(GTK_CONTAINER(scroll),body);
 GtkWidget *head=gtk_label_new("DOWNLOAD QUEUE  •  READ ONLY");
 gtk_label_set_xalign(GTK_LABEL(head),0);
 gtk_box_pack_start(GTK_BOX(body),head,FALSE,FALSE,0);
 queue_label=gtk_label_new("Select Downloads to inspect the approved server.");
 gtk_label_set_selectable(GTK_LABEL(queue_label),TRUE);
 gtk_label_set_xalign(GTK_LABEL(queue_label),0);
 gtk_label_set_yalign(GTK_LABEL(queue_label),0);
 gtk_label_set_line_wrap(GTK_LABEL(queue_label),TRUE);
 gtk_box_pack_start(GTK_BOX(body),queue_label,FALSE,FALSE,0);
 return scroll;
}
