#include "ui_state.h"
#include <glib/gstdio.h>
#include <string.h>

#define MIN_WIDTH 480
#define MIN_HEIGHT 360
#define MAX_WIDTH 3840
#define MAX_HEIGHT 2160

static int window_width = 640;
static int window_height = 500;
static const char *start_page = "dashboard";

static gboolean allowed_page(const char *page) {
 return page && (!strcmp(page,"dashboard") || !strcmp(page,"software") ||
                 !strcmp(page,"downloads"));
}

static char *state_path(void) {
 return g_build_filename(g_get_user_config_dir(),"optiplex-now","ui-state.ini",NULL);
}

void now_ui_state_load(void) {
 window_width=640;window_height=500;start_page="dashboard";
 char *path=state_path();
 GKeyFile *key=g_key_file_new();
 if(g_key_file_load_from_file(key,path,G_KEY_FILE_NONE,NULL)) {
  GError *err=NULL;
  int w=g_key_file_get_integer(key,"window","width",&err);
  if(!err && w>=MIN_WIDTH && w<=MAX_WIDTH)window_width=w;
  g_clear_error(&err);
  int h=g_key_file_get_integer(key,"window","height",&err);
  if(!err && h>=MIN_HEIGHT && h<=MAX_HEIGHT)window_height=h;
  g_clear_error(&err);
  char *page=g_key_file_get_string(key,"window","start_page",NULL);
  if(allowed_page(page)) {
   if(!strcmp(page,"software"))start_page="software";
   else if(!strcmp(page,"downloads"))start_page="downloads";
  }
  g_free(page);
 }
 g_key_file_unref(key);
 g_free(path);
}

void now_ui_state_window_size(int *width,int *height) {
 if(width)*width=window_width;
 if(height)*height=window_height;
}
void now_ui_state_remember_size(int width,int height) {
 if(width>=MIN_WIDTH && width<=MAX_WIDTH && height>=MIN_HEIGHT && height<=MAX_HEIGHT) {
  window_width=width;
  window_height=height;
 }
}
const char *now_ui_state_start_page(void) {return start_page;}
void now_ui_state_set_start_page(const char *page) {
 if(!allowed_page(page))return;
 if(!strcmp(page,"downloads"))start_page="downloads";
 else if(!strcmp(page,"software"))start_page="software";
 else start_page="dashboard";
}
gboolean now_ui_state_save(void) {
 char *path=state_path();
 char *dir=g_path_get_dirname(path);
 if(g_mkdir_with_parents(dir,0700)!=0) {
  g_free(dir);g_free(path);return FALSE;
 }
 GKeyFile *key=g_key_file_new();
 g_key_file_set_integer(key,"window","width",window_width);
 g_key_file_set_integer(key,"window","height",window_height);
 g_key_file_set_string(key,"window","start_page",start_page);
 gsize length=0;
 char *data=g_key_file_to_data(key,&length,NULL);
 GError *err=NULL;
 gboolean ok=g_file_set_contents(path,data,(gssize)length,&err);
 g_clear_error(&err);
 g_free(data);g_key_file_unref(key);g_free(dir);g_free(path);
 return ok;
}
