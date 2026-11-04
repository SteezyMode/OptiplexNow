#ifndef NOW_TRAY_MENU_LIFETIME_H
#define NOW_TRAY_MENU_LIFETIME_H

#include <gtk/gtk.h>

/*
 * The application's root GtkMenu needs its own strong reference. An SNI
 * AppIndicator also refs the active menu, then drops its ref synchronously
 * when the next menu is installed. A borrowed old-menu pointer can otherwise
 * be freed before GTK destroys it. The classic GtkStatusIcon uses no SNI ref.
 *
 * Take one app-owned reference at creation and release it only after
 * replacing the AppIndicator menu, independently of either tray backend.
 */
static inline GtkWidget *now_tray_menu_owned_new(void){
 GtkWidget *menu=gtk_menu_new();
 g_object_ref_sink(menu);
 return menu;
}

static inline void now_tray_menu_owned_destroy(GtkWidget *menu){
 if(!menu)return;
 gtk_widget_destroy(menu);
 g_object_unref(menu);
}

#endif
