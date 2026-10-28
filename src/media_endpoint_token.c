#include "media_endpoint_token.h"
#include <string.h>

static gboolean valid_path(const gchar *path)
{
    if (!path || path[0] != '/')
        return FALSE;
    if (path[1] == '\0')
        return TRUE;
    if (strlen(path) > 49)
        return FALSE;
    for (const unsigned char *p = (const unsigned char *)path + 1; *p; ++p)
        if (!(g_ascii_isalnum(*p) || *p == '_' || *p == '-'))
            return FALSE;
    return TRUE;
}

gchar *now_media_url_from_token(const char *host, const char *result)
{
    if (!host || !*host || strlen(host) > 253 || !result)
        return NULL;
    size_t len = strlen(result);
    if (len < 1 || len > 100 || result[len - 1] != '\n')
        return NULL;
    if (!strcmp(result, "available\n")) {
        return strchr(host, ':') ?
            g_strdup_printf("http://[%s]:8096/", host) :
            g_strdup_printf("http://%s:8096/", host);
    }
    gchar **fields = g_strsplit(result, "|", -1);
    gchar *url = NULL;
    if (g_strv_length(fields) == 4 &&
        !strcmp(fields[0], "available") &&
        (!strcmp(fields[1], "http") || !strcmp(fields[1], "https")) &&
        fields[2] && fields[2][0] && strlen(fields[2]) <= 5 &&
        fields[3] && g_str_has_suffix(fields[3], "\n")) {
        gchar *path = g_strndup(fields[3], strlen(fields[3]) - 1);
        gboolean digits = TRUE;
        for (const char *p = fields[2]; *p; ++p)
            if (!g_ascii_isdigit(*p)) digits = FALSE;
        guint64 port = digits ? g_ascii_strtoull(fields[2], NULL, 10) : 0;
        if (port > 0 && port <= 65535 && valid_path(path)) {
            url = strchr(host, ':') ?
                g_strdup_printf("%s://[%s]:%u%s", fields[1], host,
                                (unsigned int)port, path) :
                g_strdup_printf("%s://%s:%u%s", fields[1], host,
                                (unsigned int)port, path);
            if (path[1]) {
                gchar *with_slash = g_strconcat(url, "/", NULL);
                g_free(url);
                url = with_slash;
            }
        }
        g_free(path);
    }
    g_strfreev(fields);
    return url;
}
