#include "presets.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *const fields[NOW_PRESET_CONFIG_COUNT] = {
    "host","user","relay","relay_user","wake_command","videos","music",
    "downloads","browser","moonlight_appimage","storage_path","model_host",
    "model_name","tray_buttons","ai_url","featured_actions","web_gaming_url"
};

static int fail(const char *why) {
    fprintf(stderr,"Preset test failed: %s\n",why);
    return 1;
}

static int write_text(const char *path,const char *text) {
    FILE *fp=fopen(path,"w");
    if(!fp)return 0;
    int ok=fputs(text,fp)!=EOF;
    return fclose(fp)==0 && ok;
}

int main(void) {
    char path[]="/tmp/now-preset-test-XXXXXX";
    int fd=mkstemp(path);
    if(fd<0)return fail("mkstemp");
    close(fd);
    int result=1;
    char values[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE]={{0}};
    char imported[NOW_PRESET_CONFIG_COUNT][NOW_PRESET_VALUE_SIZE]={{0}};
    strcpy(values[0],"example.local");
    strcpy(values[1],"alice");
    strcpy(values[5],"https://media.example.local");
    strcpy(values[14],"https://ai.example.local");
    strcpy(values[16],"https://games.example.local/");
    strcpy(values[9],"/private/device-specific/moonlight.AppImage");

    if(!now_preset_write(path,values,fields))goto end;
    struct stat st;
    if(stat(path,&st)!=0 || (st.st_mode & 077)!=0)goto end;
    FILE *fp=fopen(path,"r");
    if(!fp)goto end;
    char header[160]={0};
    int v2=fgets(header,sizeof header,fp)!=NULL && strcmp(header,"# OptiPlex Now server preset v3\n")==0;
    fclose(fp);
    if(!v2)goto end;
    if(!now_preset_read(path,imported,fields))goto end;
    if(strcmp(imported[0],"example.local")||strcmp(imported[14],"https://ai.example.local")||strcmp(imported[16],"https://games.example.local/"))goto end;
    if(imported[9][0])goto end; /* Device-specific path must never be in a portable preset. */

    memset(imported,0,sizeof imported);
    if(!write_text(path,"# OptiPlex Now server preset v1\nhost=legacy.local\nuser=bob\n"))goto end;
    if(!now_preset_read(path,imported,fields)||strcmp(imported[0],"legacy.local"))goto end;

    memset(imported,0,sizeof imported);
    if(!write_text(path,"# OptiPlex Now server preset v2 (v1 imports supported)\nhost=legacy2.local\nuser=bob\n"))goto end;
    if(!now_preset_read(path,imported,fields)||strcmp(imported[0],"legacy2.local"))goto end;

    memset(imported,0,sizeof imported);
    if(!write_text(path,"# OptiPlex Now server preset v2\nhost=ok.local\nuser=bob\nssh_key=/private/id_ed25519\n"))goto end;
    if(now_preset_read(path,imported,fields))goto end; /* No unknown/secret keys. */
    /* Failed parse must not partially overwrite caller settings. */
    memset(imported,0,sizeof imported);
    strcpy(imported[0],"original.local");
    strcpy(imported[1],"existing");
    if(!write_text(path,"# OptiPlex Now server preset v2\nhost=new.local\nuser=alice\nssh_key=/private/id_ed25519\n"))goto end;
    if(now_preset_read(path,imported,fields))goto end;
    if(strcmp(imported[0],"original.local")||strcmp(imported[1],"existing"))goto end;

    /* Oversized or broken records must leave the settings untouched. */
    if(!write_text(path,"# OptiPlex Now server preset v2\nhost=new.local\nuser=an invalid user\n"))goto end;
    if(now_preset_read(path,imported,fields))goto end;
    if(strcmp(imported[0],"original.local"))goto end;


    memset(imported,0,sizeof imported);
    if(!write_text(path,"# OptiPlex Now server preset v2\nhost=bad host\nuser=bob\n"))goto end;
    if(now_preset_read(path,imported,fields))goto end;

    char web[768];
    if(!now_web_gaming_url("https://games.example.local/",0,web,sizeof web)
         || strcmp(web,"https://games.example.local?launch=steam"))goto end;
    if(!now_web_gaming_url("http://100.82.11.5:8080/app/",1,web,sizeof web)
         || strcmp(web,"http://100.82.11.5:8080/app/settings"))goto end;
    if(now_web_gaming_url("",0,web,sizeof web)||web[0])goto end;
    if(now_web_gaming_url("https://bob:password@example.com",0,web,sizeof web)||web[0])goto end;
    if(now_web_gaming_url("https://games.example.com?token=secret",0,web,sizeof web)||web[0])goto end;
    if(now_web_gaming_url("https://games.example.local",0,web,8)||web[0])goto end;
    if(now_safe_preset_url("https://bob:password@example.com"))goto end;
    if(now_safe_wake_path("/tmp/a;rm -rf /"))goto end;
    if(!now_valid_host("server.local")||!now_valid_user("alice"))goto end;
    result=0;
end:
    unlink(path);
    if(result)return fail("round-trip, legacy import, privacy or validation");
    puts("Preset tests: v2 round-trip, v1/legacy-v2 import, permissions and bad input passed.");
    return 0;
}
