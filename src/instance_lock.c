#define _GNU_SOURCE
#include "instance_lock.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static volatile sig_atomic_t reopen_requested = 0;
static int instance_fd = -1;

static void request_reopen(int signo){ (void)signo; reopen_requested=1; }
int now_instance_claim(void){
 char path[PATH_MAX];
 const char *runtime=getenv("XDG_RUNTIME_DIR");
 int n;
 if(runtime && *runtime){
   n=snprintf(path,sizeof path,"%s/optiplex-now.lock",runtime);
 }else{
   const char *home=getenv("HOME");
   char cache[PATH_MAX];
   n=snprintf(cache,sizeof cache,"%s/.cache",home?home:"/tmp");
   if(n<0 || (size_t)n>=sizeof cache){
     fprintf(stderr,"Instance cache path is too long\n");
     return -1;
   }
   if(mkdir(cache,0700)!=0 && errno!=EEXIST){
     fprintf(stderr,"Could not create instance cache: %s\n",strerror(errno));
     return -1;
   }
   n=snprintf(path,sizeof path,"%s/optiplex-now.lock",cache);
 }
 if(n<0 || (size_t)n>=sizeof path){
   fprintf(stderr,"Instance lock path is too long\n");
   return -1;
 }
 instance_fd=open(path,O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
 if(instance_fd<0){
   fprintf(stderr,"Could not open instance lock: %s\n",strerror(errno));
   return -1;
 }
 struct stat st;
 if(fstat(instance_fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_uid!=geteuid()){
   fprintf(stderr,"Instance lock must be a regular file owned by this user\n");
   goto lock_error;
 }
 if(flock(instance_fd,LOCK_EX|LOCK_NB)!=0){
   if(errno!=EWOULDBLOCK && errno!=EAGAIN){
     fprintf(stderr,"Could not acquire instance lock: %s\n",strerror(errno));
     goto lock_error;
   }
   char buf[64]={0};
   if(lseek(instance_fd,0,SEEK_SET)>=0){
     ssize_t got=read(instance_fd,buf,sizeof(buf)-1);
     if(got>0){
       char *end=NULL;
       errno=0;
       long pid=strtol(buf,&end,10);
       if(errno==0 && end!=buf && (*end=='\n' || *end=='\0') && pid>1 && pid<=INT_MAX)
         kill((pid_t)pid,SIGUSR1);
     }
   }
   close(instance_fd);
   instance_fd=-1;
   return 0;
 }
 struct sigaction sa={0};
 sa.sa_handler=request_reopen;
 sigemptyset(&sa.sa_mask);
 if(sigaction(SIGUSR1,&sa,NULL)!=0){
   fprintf(stderr,"Could not install reopen signal handler: %s\n",strerror(errno));
   goto lock_error;
 }
 char buf[64];
 n=snprintf(buf,sizeof buf,"%ld\n",(long)getpid());
 if(n<0 || (size_t)n>=sizeof buf || ftruncate(instance_fd,0)!=0 ||
    lseek(instance_fd,0,SEEK_SET)<0){
   fprintf(stderr,"Could not prepare instance PID file: %s\n",strerror(errno));
   goto lock_error;
 }
 size_t written=0;
 while(written<(size_t)n){
   ssize_t k=write(instance_fd,buf+written,(size_t)n-written);
   if(k<0 && errno==EINTR)continue;
   if(k<=0){
     fprintf(stderr,"Could not write instance PID: %s\n",strerror(errno));
     goto lock_error;
   }
   written+=(size_t)k;
 }
 return 1;
lock_error:
 close(instance_fd);
 instance_fd=-1;
 return -1;
}

int now_instance_reopen_pending(void)
{
    if (!reopen_requested) return 0;
    reopen_requested = 0;
    return 1;
}
