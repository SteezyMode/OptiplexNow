#include "music_discover_model.h"
#include <glib.h>
#include <string.h>

static GPtrArray *entries_new(void)
{
    return g_ptr_array_new_with_free_func(now_music_discover_entry_free);
}

static GPtrArray *shelves_new(void)
{
    return g_ptr_array_new_with_free_func(now_music_discover_shelf_free);
}

static void append_row(GString *output, const char *kind, const char *id,
                       const char *title, const char *artist, const char *cover)
{
    const char *fields[] = {kind, id, title, artist, cover};
    for (guint i=0;i<G_N_ELEMENTS(fields);i++) {
        gchar *encoded=g_base64_encode((const guchar *)fields[i],strlen(fields[i]));
        if(i)g_string_append_c(output,'\t');
        g_string_append(output,encoded);
        g_free(encoded);
    }
    g_string_append_c(output,'\n');
}

static void test_discover_section_routing(void)
{
    const struct {const char *key;int category;} cases[]={
        {"top_picks",DISC_FOR_YOU},
        {"because_you_listen_artist",DISC_FOR_YOU},
        {"listeners_like_you",DISC_FOR_YOU},
        {"new_from_followed",DISC_FOR_YOU},
        {"rediscover",DISC_FOR_YOU},
        {"artists_you_might_like",DISC_NEW_ARTISTS},
        {"fresh_releases",DISC_FRESH},
        {"missing_essentials",DISC_FOR_YOU},
        {"anniversaries",DISC_EXPLORE},
        {"popular_in_your_genres",DISC_GENRES},
        {"unexplored_genres",DISC_GENRES},
        {"daily_mixes_hiphop",DISC_GENRES},
        {"radio_sections_ambient",DISC_GENRES},
        {"globally_trending",DISC_TRENDING},
        {"lastfm_weekly_artist_chart",DISC_TRENDING},
        {"lastfm_weekly_album_chart",DISC_TRENDING},
        {"unknown",DISC_EXPLORE},
    };
    for(guint i=0;i<G_N_ELEMENTS(cases);i++)
        g_assert_cmpint(now_music_discover_group_for(cases[i].key),
                        ==,cases[i].category);
    g_assert_cmpint(now_music_discover_group_for(NULL),==,DISC_EXPLORE);
}

static void test_bounded_decoded_rows_and_reset(void)
{
    const char *id="11111111-1111-4111-8111-111111111111";
    GString *wire=g_string_new("");
    GPtrArray *entries=entries_new(), *shelves=shelves_new();
    gboolean building=TRUE;
    append_row(wire,"section","fresh_releases","New releases","","");
    append_row(wire,"catalog_album",id,"日本語 — New","Artist","dn-album:123");
    append_row(wire,"catalog_artist","too-short","Ignored","Artist","");
    append_row(wire,"catalog_album",id,"","Artist","");
    int count=now_music_discover_parse(wire->str,entries,shelves,&building);
    g_assert_cmpint(count,==,1);
    g_assert_false(building);
    g_assert_cmpuint(entries->len,==,1);
    MusicDiscoverEntry *entry=g_ptr_array_index(entries,0);
    g_assert_cmpstr(entry->title,==,"日本語 — New");
    g_assert_cmpstr(entry->artist,==,"Artist");
    g_assert_cmpstr(entry->cover,==,"dn-album:123");
    g_assert_cmpint(entry->category,==,DISC_FRESH);
    g_assert_cmpuint(shelves->len,==,0);
    /* Existing cached model is replaced, not appended on navigation. */
    g_string_set_size(wire,0);
    append_row(wire,"section","__refreshing","Loading","","");
    append_row(wire,"catalog_album",id,"Must not leak in","Artist","");
    count=now_music_discover_parse(wire->str,entries,shelves,&building);
    g_assert_cmpint(count,==,0);
    g_assert_true(building);
    g_assert_cmpuint(entries->len,==,0);
    g_ptr_array_unref(entries);
    g_ptr_array_unref(shelves);
    g_string_free(wire,TRUE);
}

static void test_dynamic_shelf_variety_and_limit(void)
{
    GString *wire=g_string_new("");
    const char *id="22222222-2222-4222-8222-222222222222";
    GPtrArray *entries=entries_new(), *shelves=shelves_new();
    gboolean building=FALSE;
    for(int i=0;i<5;i++){
        gchar *key=g_strdup_printf("because_you_listen_%d",i);
        gchar *title=g_strdup_printf("Because %d",i);
        append_row(wire,"section",key,title,"","");
        append_row(wire,"catalog_artist",id,"Followed artist","Artist","");
        g_free(key);g_free(title);
    }
    for(int i=0;i<5;i++){
        gchar *key=g_strdup_printf("daily_mixes_%d",i);
        gchar *title=g_strdup_printf("Mix %d",i);
        append_row(wire,"section",key,title,"","");
        append_row(wire,"catalog_album",id,"Mix album","Artist","");
        g_free(key);g_free(title);
    }
    const int count=now_music_discover_parse(wire->str,entries,shelves,&building);
    g_assert_cmpint(count,==,10);
    g_assert_cmpuint(shelves->len,==,DISC_MAX_DYNAMIC);
    g_assert_cmpstr(((MusicDiscoverShelf *)g_ptr_array_index(shelves,0))->title,==,"Because 0");
    g_assert_cmpstr(((MusicDiscoverShelf *)g_ptr_array_index(shelves,1))->title,==,"Because 1");
    g_assert_cmpstr(((MusicDiscoverShelf *)g_ptr_array_index(shelves,2))->title,==,"Mix 0");
    g_assert_cmpstr(((MusicDiscoverShelf *)g_ptr_array_index(shelves,3))->title,==,"Mix 1");
    g_assert_cmpint(((MusicDiscoverEntry *)g_ptr_array_index(entries,0))->category,==,DISC_DYNAMIC_START);
    g_assert_cmpint(((MusicDiscoverEntry *)g_ptr_array_index(entries,2))->category,==,DISC_FOR_YOU);
    g_assert_cmpint(((MusicDiscoverEntry *)g_ptr_array_index(entries,5))->category,==,DISC_DYNAMIC_START+2);
    g_assert_cmpint(((MusicDiscoverEntry *)g_ptr_array_index(entries,7))->category,==,DISC_GENRES);
    g_ptr_array_unref(entries);
    g_ptr_array_unref(shelves);
    g_string_free(wire,TRUE);
}

static void test_parser_limits_and_decode_guards(void)
{
    GPtrArray *entries=entries_new(), *shelves=shelves_new();
    GString *wire=g_string_new("");
    const char *id="33333333-3333-4333-8333-333333333333";
    append_row(wire,"section","top_picks","For You","","");
    for(int i=0;i<320;i++)
        append_row(wire,"catalog_album",id,"Bounded item","Artist","");
    gboolean building=FALSE;
    int count=now_music_discover_parse(wire->str,entries,shelves,&building);
    g_assert_cmpint(count,==,180);
    g_assert_cmpuint(entries->len,==,180);
    g_assert_cmpuint(shelves->len,==,0);
    g_string_free(wire,TRUE);
    char *valid=now_music_discover_decode_field("5pel5pys6Kqe");
    g_assert_cmpstr(valid,==,"日本語");
    g_free(valid);
    g_assert_null(now_music_discover_decode_field(NULL));
    char *long_string=g_strnfill(4097,'X');
    char *too_long=g_base64_encode((const guchar *)long_string,strlen(long_string));
    g_assert_null(now_music_discover_decode_field(too_long));
    g_free(too_long);g_free(long_string);
    const guchar nul[]={'o','k',0,'x'};
    char *embedded_nul=g_base64_encode(nul,sizeof nul);
    g_assert_null(now_music_discover_decode_field(embedded_nul));
    g_free(embedded_nul);
    const guchar non_utf8[]={0xC3,0x28};
    char *bad_utf8=g_base64_encode(non_utf8,sizeof non_utf8);
    g_assert_null(now_music_discover_decode_field(bad_utf8));
    g_free(bad_utf8);
    char *oversized=g_strnfill(16385,'A');
    g_assert_null(now_music_discover_decode_field(oversized));
    g_free(oversized);
    g_ptr_array_unref(entries);
    g_ptr_array_unref(shelves);
}

int main(int argc,char **argv)
{
    g_test_init(&argc,&argv,NULL);
    g_test_add_func("/music/discover/routing",test_discover_section_routing);
    g_test_add_func("/music/discover/decoded-rows",test_bounded_decoded_rows_and_reset);
    g_test_add_func("/music/discover/dynamic-shelves",test_dynamic_shelf_variety_and_limit);
    g_test_add_func("/music/discover/limits",test_parser_limits_and_decode_guards);
    return g_test_run();
}
