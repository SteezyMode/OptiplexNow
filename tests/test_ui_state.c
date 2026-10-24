#include "ui_state.h"
#include <glib.h>
#include <glib/gstdio.h>
#include <string.h>

int main(void){
 GError *error=NULL;
 char *tmp=g_dir_make_tmp("now-ui-state-XXXXXX",&error);
 g_assert_no_error(error);
 g_assert_nonnull(tmp);
 g_assert_true(g_setenv("XDG_CONFIG_HOME",tmp,TRUE));

 now_ui_state_load();
 int w=0,h=0;
 now_ui_state_window_size(&w,&h);
 g_assert_cmpint(w,==,640);
 g_assert_cmpint(h,==,500);
 g_assert_cmpstr(now_ui_state_start_page(),==,"dashboard");

 now_ui_state_remember_size(880,540);
 now_ui_state_set_start_page("software");
 g_assert_true(now_ui_state_save());
 now_ui_state_set_start_page("dashboard");
 now_ui_state_remember_size(640,500);
 now_ui_state_load();
 now_ui_state_window_size(&w,&h);
 g_assert_cmpint(w,==,880);
 g_assert_cmpint(h,==,540);
 g_assert_cmpstr(now_ui_state_start_page(),==,"software");

 now_ui_state_set_start_page("arbitrary-ssh-page");
 g_assert_cmpstr(now_ui_state_start_page(),==,"software");
 now_ui_state_remember_size(9999,100);
 now_ui_state_window_size(&w,&h);
 g_assert_cmpint(w,==,880);
 g_assert_cmpint(h,==,540);

 char *path=g_build_filename(tmp,"optiplex-now","ui-state.ini",NULL);
 g_assert_true(g_file_set_contents(path,
   "[window]\nwidth=999999\nheight=-5\nstart_page=unknown\n",-1,&error));
 g_assert_no_error(error);
 now_ui_state_load();
 now_ui_state_window_size(&w,&h);
 g_assert_cmpint(w,==,640);
 g_assert_cmpint(h,==,500);
 g_assert_cmpstr(now_ui_state_start_page(),==,"dashboard");

 /* An earlier beta could save Downloads as the startup page. Defer it
  * rather than leave the first view uninitialized; keep saved geometry. */
 g_assert_true(g_file_set_contents(path,
   "[window]\nwidth=880\nheight=540\nstart_page=downloads\n",-1,&error));
 g_assert_no_error(error);
 now_ui_state_load();
 now_ui_state_window_size(&w,&h);
 g_assert_cmpint(w,==,880);
 g_assert_cmpint(h,==,540);
 g_assert_cmpstr(now_ui_state_start_page(),==,"dashboard");
 now_ui_state_set_start_page("downloads");
 g_assert_cmpstr(now_ui_state_start_page(),==,"dashboard");

 g_assert_cmpint(g_remove(path),==,0);
 char *dir=g_path_get_dirname(path);
 g_assert_cmpint(g_rmdir(dir),==,0);
 g_assert_cmpint(g_rmdir(tmp),==,0);
 g_free(dir);g_free(path);g_free(tmp);
 return 0;
}
