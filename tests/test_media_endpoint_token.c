#include "media_endpoint_token.h"
#include <glib.h>

int main(void)
{
    const char *host = "100.121.156.34";
    gchar *url = now_media_url_from_token(host, "available\n");
    g_assert_cmpstr(url, ==, "http://100.121.156.34:8096/");
    g_free(url);

    url = now_media_url_from_token(host, "available|https|443|/jellyfin\n");
    g_assert_cmpstr(url, ==, "https://100.121.156.34:443/jellyfin/");
    g_free(url);

    url = now_media_url_from_token("fe80::1", "available|http|8097|/\n");
    g_assert_cmpstr(url, ==, "http://[fe80::1]:8097/");
    g_free(url);

    const char *invalid[] = {
        "available|http|8096|/other", "available|http|8096|/other\nextra",
        "available|http|0|/\n", "available|http|65536|/\n",
        "available|http|-1|/\n", "available|ftp|443|/\n",
        "available|https|443|//host\n", "available|http|443|/%2e\n",
        "available|http|443|/foo/bar\n",
        "available|http|443|/foo?x=1\n",
        "available|http|443|/foo#fragment\n",
        "available|http|443|/foo@example\n",
        "available|http|443|/foo|x\n",
        "unavailable\n", "available\nextra", "available|http|80|/\r\n",
        NULL
    };
    for (int i = 0; invalid[i]; ++i)
        g_assert_null(now_media_url_from_token(host, invalid[i]));
    return 0;
}
