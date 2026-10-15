/* OptiPlex Now encrypted backup helper. v1 format, fixed allowed paths only.
 * Build: gcc -O2 -Wall backup_v18.c -lcrypto -o optiplex-now-backup
 * Invocation: optiplex-now-backup export|restore backup.onb
 * The passphrase is passed on stdin, never command-line or env.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <openssl/rand.h>
#include <openssl/evp.h>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <errno.h>
#define MAX_RECORD 262144
#define MAX_PLAIN (5*MAX_RECORD + 1024)
#define RECORDS 5
#define KDF_ITER 600000
/* 0 client prefs, 1 SSH private, 2 SSH public, 3 Moonlight Qt AppImage/native, 4 Moonlight Flatpak */
static const char *paths[RECORDS]={".config/optiplex-desk/config.ini",".ssh/id_ed25519",".ssh/id_ed25519.pub",".config/Moonlight Game Streaming Project/Moonlight.conf",".var/app/com.moonlight_stream.Moonlight/config/Moonlight Game Streaming Project/Moonlight.conf"};
static const unsigned char magic[8]={'O','P','N','B','A','K','1','\n'};
static unsigned char *getbuf(size_t sz){return calloc(sz?sz:1,1);}
static void put32(unsigned char *p,uint32_t n){p[0]=n>>24;p[1]=n>>16;p[2]=n>>8;p[3]=n;}
static uint32_t get32(const unsigned char *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static int writeall(int fd,const void *ptr,size_t n){const unsigned char*p=ptr;while(n){ssize_t k=write(fd,p,n);if(k<0&&errno==EINTR)continue;if(k<=0)return 0;p+=k;n-=(size_t)k;}return 1;}
static int readall(int fd,void *ptr,size_t n){unsigned char*p=ptr;while(n){ssize_t k=read(fd,p,n);if(k<0&&errno==EINTR)continue;if(k<=0)return 0;p+=k;n-=(size_t)k;}return 1;}
static int record_path(char *dest,size_t n,int idx){const char*home=getenv("HOME");if(!home||*home!='/')return 0;return snprintf(dest,n,"%s/%s",home,paths[idx])<(int)n;}
static int mkdir_parents(char *name){char t[PATH_MAX];size_t len=strlen(name);if(len>=sizeof t)return 0;memcpy(t,name,len+1);
 for(char *p=t+1;*p;p++)if(*p=='/'){*p=0;if(mkdir(t,0700)<0&&errno!=EEXIST)return 0;struct stat st;if(lstat(t,&st)!=0||!S_ISDIR(st.st_mode))return 0;*p='/';}return 1;}
/* Atomic writes for restored entries. Refuse symlinks at the destination. */
static int restore_file(int idx,const unsigned char *data,size_t len){
 char path[PATH_MAX],temp[PATH_MAX];if(!record_path(path,sizeof path,idx)||!mkdir_parents(path))return 0;
 struct stat st;if(lstat(path,&st)==0&&!S_ISREG(st.st_mode))return 0;
 if(snprintf(temp,sizeof temp,"%s.XXXXXX",path)>=(int)sizeof temp)return 0;
 int fd=mkstemp(temp);if(fd<0)return 0;
 int ok=fchmod(fd,idx==2?0644:0600)==0&&writeall(fd,data,len)&&fsync(fd)==0;
 if(close(fd)<0)ok=0;
 if(ok){if(rename(temp,path)!=0)ok=0;}
 if(!ok)unlink(temp);return ok;
}
static int capture(unsigned char *plain,size_t *pos){
 memcpy(plain,magic,8);*pos=8;
 for(int i=0;i<RECORDS;i++){
  char path[PATH_MAX];if(!record_path(path,sizeof path,i))return 0;
  struct stat st;uint32_t length=0;
  if(lstat(path,&st)==0){if(!S_ISREG(st.st_mode)||st.st_size<0||st.st_size>MAX_RECORD)return 0;length=(uint32_t)st.st_size;}
  if(*pos+5+length>MAX_PLAIN)return 0;
  plain[(*pos)++]=(unsigned char)i;put32(plain+*pos,length);*pos+=4;
  if(length){int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0)return 0;int ok=readall(fd,plain+*pos,length);close(fd);if(!ok)return 0;*pos+=length;}
 }
 return 1;
}
static int validate_records(const unsigned char *plain,size_t n,const unsigned char **ptrs,uint32_t *lengths){
 if(n<8||memcmp(plain,magic,8)!=0)return 0;size_t p=8;
 for(int i=0;i<RECORDS;i++){
  if(p+5>n||plain[p++]!=i)return 0;
  lengths[i]=get32(plain+p);p+=4;
  if(lengths[i]>MAX_RECORD||p+lengths[i]>n)return 0;
  ptrs[i]=plain+p;p+=lengths[i];
 }
 return p==n;
}
static int load_password(char *s,size_t n){if(!fgets(s,n,stdin))return 0;size_t i=strcspn(s,"\r\n");if(i<12||i>1024)return 0;s[i]=0;return 1;}
int main(int argc,char**argv){
 umask(077);
 if(argc!=3||strcmp(argv[1],"export")&&strcmp(argv[1],"restore")){fprintf(stderr,"Usage: optiplex-now-backup export|restore FILE\n");return 2;}
 char password[2048]={0};if(!load_password(password,sizeof password)){fprintf(stderr,"Passphrase must have at least 12 characters.\n");return 3;}
 const int is_export=!strcmp(argv[1],"export");int ok=0;
 unsigned char salt[16],iv[12],key[32],tag[16];unsigned char *plain=getbuf(MAX_PLAIN),*cipher=getbuf(MAX_PLAIN);
 size_t plain_len=0,cipher_len=0;EVP_CIPHER_CTX *ctx=EVP_CIPHER_CTX_new();
 if(!plain||!cipher||!ctx)goto done;
 if(is_export){
  if(!capture(plain,&plain_len)||RAND_bytes(salt,16)!=1||RAND_bytes(iv,12)!=1)goto done;
 }else{
  int fd=open(argv[2],O_RDONLY|O_NOFOLLOW);if(fd<0)goto done;
  struct stat st;if(fstat(fd,&st)!=0||!S_ISREG(st.st_mode)||st.st_size<56||st.st_size>(off_t)(MAX_PLAIN+56)){close(fd);goto done;}
  unsigned char hdr[40];if(!readall(fd,hdr,40)||memcmp(hdr,"OPNENC1\n",8)!=0){close(fd);goto done;}
  memcpy(salt,hdr+8,16);memcpy(iv,hdr+24,12);uint32_t sz=get32(hdr+36);if(sz>MAX_PLAIN||st.st_size!=(off_t)(40+sz+16)){close(fd);goto done;}
  cipher_len=sz;if(!readall(fd,cipher,cipher_len)||!readall(fd,tag,16)){close(fd);goto done;}close(fd);
 }
 if(PKCS5_PBKDF2_HMAC(password,strlen(password),salt,16,KDF_ITER,EVP_sha256(),32,key)!=1)goto done;
 if(is_export){
  int k=0,z=0;
  if(EVP_EncryptInit_ex(ctx,EVP_aes_256_gcm(),NULL,key,iv)!=1 ||
     EVP_EncryptUpdate(ctx,cipher,&k,plain,(int)plain_len)!=1 ||
     EVP_EncryptFinal_ex(ctx,cipher+k,&z)!=1 ||
     EVP_CIPHER_CTX_ctrl(ctx,EVP_CTRL_GCM_GET_TAG,16,tag)!=1)goto done;
  cipher_len=(size_t)(k+z);
  if(cipher_len>MAX_PLAIN)goto done;
  unsigned char hdr[40];memcpy(hdr,"OPNENC1\n",8);memcpy(hdr+8,salt,16);memcpy(hdr+24,iv,12);put32(hdr+36,(uint32_t)cipher_len);
  char tmp[PATH_MAX];if(snprintf(tmp,sizeof tmp,"%s.tmp.XXXXXX",argv[2])>=(int)sizeof tmp)goto done;
  int fd=mkstemp(tmp);if(fd<0)goto done;
  int good=writeall(fd,hdr,40)&&writeall(fd,cipher,cipher_len)&&writeall(fd,tag,16)&&fsync(fd)==0;
  if(close(fd)!=0)good=0;
  if(good&&rename(tmp,argv[2])!=0)good=0;
  if(!good)unlink(tmp);ok=good;
 }else{
  int k=0,z=0;
  if(EVP_DecryptInit_ex(ctx,EVP_aes_256_gcm(),NULL,key,iv)!=1||
     EVP_DecryptUpdate(ctx,plain,&k,cipher,(int)cipher_len)!=1||
     EVP_CIPHER_CTX_ctrl(ctx,EVP_CTRL_GCM_SET_TAG,16,tag)!=1||
     EVP_DecryptFinal_ex(ctx,plain+k,&z)!=1)goto done;
  plain_len=(size_t)(k+z);
  const unsigned char *p[RECORDS];uint32_t lengths[RECORDS];
  if(!validate_records(plain,plain_len,p,lengths))goto done;
  /* Validate all output targets before any file is written. */
  for(int i=0;i<RECORDS;i++)if(lengths[i]){char path[PATH_MAX];struct stat st;if(!record_path(path,sizeof path,i))goto done;if(lstat(path,&st)==0&&!S_ISREG(st.st_mode))goto done;}
  ok=1;for(int i=0;i<RECORDS;i++)if(lengths[i]&&!restore_file(i,p[i],lengths[i])){ok=0;break;}
 }
done:
 OPENSSL_cleanse(password,sizeof password);OPENSSL_cleanse(key,sizeof key);
 if(plain){OPENSSL_cleanse(plain,MAX_PLAIN);free(plain);}if(cipher){OPENSSL_cleanse(cipher,MAX_PLAIN);free(cipher);}if(ctx)EVP_CIPHER_CTX_free(ctx);
 if(!ok)fprintf(stderr,"Backup operation failed. Verify the password and file.\n");
 return ok?0:1;
}
