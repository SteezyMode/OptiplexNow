#include "music_discover_model.h"
#include <string.h>

/* The code below is lifted from the validated native Music Discover view.
 * Retain section precedence, row/UTF-8 limits, mixing and source-category
 * meanings. In particular, older back-catalog records are not "Fresh". */

void now_music_discover_entry_free(gpointer data){
 MusicDiscoverEntry *entry=data;
 if(!entry)return;
 g_free(entry->kind);g_free(entry->id);g_free(entry->title);
 g_free(entry->artist);g_free(entry->cover);g_free(entry);
}

void now_music_discover_shelf_free(gpointer data){
 MusicDiscoverShelf *shelf=data;
 if(!shelf)return;
 g_free(shelf->title);g_free(shelf->description);g_free(shelf);
}


char *now_music_discover_decode_field(const char *encoded){
 if(!encoded || strlen(encoded)>16384)return NULL;
 gsize len=0;
 guchar *decoded=g_base64_decode(encoded,&len);
 if(!decoded || len>4096 || memchr(decoded,0,len)){
  g_free(decoded);
  return NULL;
 }
 if(!g_utf8_validate((char*)decoded,(gssize)len,NULL)){
  g_free(decoded);
  return NULL;
 }
 char *answer=g_strndup((char*)decoded,len);
 g_free(decoded);
 return answer;
}


int now_music_discover_group_for(const char *key){
 if(!key)return DISC_EXPLORE;
 if(g_str_has_prefix(key,"because_you_listen_") ||
    !g_strcmp0(key,"top_picks") ||
    !g_strcmp0(key,"listeners_like_you") ||
    !g_strcmp0(key,"new_from_followed") ||
    !g_strcmp0(key,"rediscover"))return DISC_FOR_YOU;
 if(!g_strcmp0(key,"artists_you_might_like"))return DISC_NEW_ARTISTS;
 /* Only ListenBrainz's time-bounded fresh-releases feed is fresh.
  * Missing Essentials is a personalized back-catalog recommendation, and
  * anniversaries are older catalog history. They are never new releases. */
 if(!g_strcmp0(key,"fresh_releases"))return DISC_FRESH;
 if(!g_strcmp0(key,"missing_essentials"))return DISC_FOR_YOU;
 if(!g_strcmp0(key,"anniversaries"))return DISC_EXPLORE;
 if(!g_strcmp0(key,"popular_in_your_genres") ||
    !g_strcmp0(key,"unexplored_genres") ||
    g_str_has_prefix(key,"daily_mixes_") ||
    g_str_has_prefix(key,"radio_sections_"))return DISC_GENRES;
 if(!g_strcmp0(key,"globally_trending") ||
    !g_strcmp0(key,"lastfm_weekly_artist_chart") ||
    !g_strcmp0(key,"lastfm_weekly_album_chart"))return DISC_TRENDING;
 return DISC_EXPLORE;
}


int now_music_discover_parse(const char *output, GPtrArray *entries,
                             GPtrArray *shelves, gboolean *building){
 if(!entries || !shelves || !building)return 0;
 (*building)=FALSE;
 g_ptr_array_set_size(entries,0);
 g_ptr_array_set_size(shelves,0);
 char **lines=g_strsplit(output?output:"","\n",-1);
 int category=-1;
 int count=0;
 guint personal_shelves=0, mix_shelves=0;
 for(int i=0;lines[i] && i<300 && count<180;i++){
  char **parts=g_strsplit(lines[i],"\t",6);
  if(g_strv_length(parts)==5){
   char *kind=now_music_discover_decode_field(parts[0]);
   char *id=now_music_discover_decode_field(parts[1]);
   char *title=now_music_discover_decode_field(parts[2]);
   char *artist=now_music_discover_decode_field(parts[3]);
   char *cover=now_music_discover_decode_field(parts[4]);
   if(kind && id && title && artist && cover){
    if(!g_strcmp0(kind,"section")){
     if(!g_strcmp0(id,"__refreshing")){
      (*building)=TRUE;
      category=-1;
     }else category=now_music_discover_group_for(id);
     /* These tiles are generated from actual personalized recommendation
      * sections. A new artist or mix title can replace yesterday's; no
      * generic static 'Hip-Hop Mix' cards or empty placeholders. */
     gboolean personal=g_str_has_prefix(id,"because_you_listen_");
     gboolean mix=g_str_has_prefix(id,"daily_mixes_") ||
                  g_str_has_prefix(id,"radio_sections_");
     /* Reserve room for variety: a rich listening history should not
      * displace every genre/mixtape tile with four nearly identical artists. */
     gboolean dynamic=(personal && personal_shelves<2) ||
                      (mix && mix_shelves<2);
     if(dynamic && *title &&
        shelves->len<DISC_MAX_DYNAMIC){
      MusicDiscoverShelf *shelf=g_new0(MusicDiscoverShelf,1);
      shelf->title=g_strdup(title);
      shelf->description=g_strdup(personal?
             "Inspired by your listening":"A tailored selection");
      category=DISC_DYNAMIC_START+(int)shelves->len;
      g_ptr_array_add(shelves,shelf);
      if(personal)personal_shelves++;
      else mix_shelves++;
     }
    }else if(category>=0 &&
         (!g_strcmp0(kind,"catalog_album") ||
          !g_strcmp0(kind,"catalog_artist")) &&
         strlen(id)==36 && *title){
     MusicDiscoverEntry *entry=g_new0(MusicDiscoverEntry,1);
     entry->kind=g_strdup(kind);
     entry->id=g_strdup(id);
     entry->title=g_strdup(title);
     entry->artist=g_strdup(artist);
     entry->cover=g_strdup(cover);
     entry->category=category;
     g_ptr_array_add(entries,entry);
     count++;
    }
   }
   g_free(kind);g_free(id);g_free(title);g_free(artist);g_free(cover);
  }
  g_strfreev(parts);
 }
 g_strfreev(lines);
 return count;
}

