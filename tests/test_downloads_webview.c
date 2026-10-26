/* Unit checks for the embedded WebUI origin policy. No actual network. */
#include "downloads_webview.h"
#include <glib.h>

static void test_private_tailnet(void){
 g_assert_true(now_downloads_webview_url_allowed(
    "http://100.121.156.34:8085/","100.121.156.34"));
 g_assert_true(now_downloads_webview_url_allowed(
    "http://192.168.40.212:8085/#/","192.168.40.212"));
 g_assert_true(now_downloads_webview_url_allowed(
    "https://plex.example.test:443/","plex.example.test"));
}
static void test_other_hosts_rejected(void){
 g_assert_false(now_downloads_webview_url_allowed(
    "http://100.121.156.33:8085/","100.121.156.34"));
 g_assert_false(now_downloads_webview_url_allowed(
    "http://evil.example.test:8085/","evil.example.test"));
 g_assert_false(now_downloads_webview_url_allowed(
    "https://bob:password@home.example.test/","home.example.test"));
 g_assert_false(now_downloads_webview_url_allowed(
    "file:///etc/passwd","100.121.156.34"));
 g_assert_false(now_downloads_webview_url_allowed(
    "javascript:alert(1)","100.121.156.34"));
 g_assert_false(now_downloads_webview_url_allowed(
    "http://100.121.156.34:8085/?redirect=bad","100.121.156.34"));
}
static void test_bounded_validation(void){
 g_assert_false(now_downloads_webview_url_allowed(NULL,"100.121.156.34"));
 g_assert_false(now_downloads_webview_url_allowed("http://100.121.156.34:8085/",NULL));
 g_assert_false(now_downloads_webview_url_allowed(
    "http://100.121.156.34:8085/",""));
 g_assert_false(now_downloads_webview_url_allowed(
    "http://100.121.156.34:0/","100.121.156.34"));
}
int main(int argc,char **argv){
 g_test_init(&argc,&argv,NULL);
 g_test_add_func("/webui/private-host",test_private_tailnet);
 g_test_add_func("/webui/deny-external",test_other_hosts_rejected);
 g_test_add_func("/webui/invalid",test_bounded_validation);
 return g_test_run();
}
