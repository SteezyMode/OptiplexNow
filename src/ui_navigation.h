#ifndef NOW_UI_NAVIGATION_H
#define NOW_UI_NAVIGATION_H
#include <gtk/gtk.h>
/* Page switching belongs to the application shell, not service controllers. */
void now_nav_bind_link(GtkWidget *button, GtkWidget *stack, const char *page);
void now_nav_update_back(GObject *stack, GParamSpec *param, gpointer back_button);
void now_nav_show_page(GtkWidget *stack, const char *page);
#endif
