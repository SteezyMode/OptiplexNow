#ifndef OPTIPLEX_NOW_CONFIG_H
#define OPTIPLEX_NOW_CONFIG_H

/* Retain on-disk field order. Other modules and older client presets use it. */
#define CONFIG_COUNT 17
#define CONFIG_VALUE_SIZE 512
#define FEATURED_MASK_SETTING 15
#define EXISTING_INSTALL_FEATURED_MASK 255u

extern char cfg[CONFIG_COUNT][CONFIG_VALUE_SIZE];
extern const char *const keys[CONFIG_COUNT];
extern int first_run;

/* Production operations use the existing XDG/legacy config directory. */
int now_config_load(void);
int now_config_save(void);

/* Explicit paths permit isolated tests without changing real client settings. */
int now_config_load_from(const char *path);
int now_config_save_to(const char *path);

#endif
