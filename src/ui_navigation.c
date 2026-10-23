#include "ui_navigation.h"
#include <string.h>

static void open_page(GtkWidget *button, gpointer unused){
 (void)unused;
 GtkWidget *stack=g_object_get_data(G_OBJECT(button),"now-nav-stack");
 const char *page=g_object_get_data(G_OBJECT(button),"now-nav-page");
 if(stack && GTK_IS_STACK(stack) && page)
   gtk_stack_set_visible_child_name(GTK_STACK(stack),page);
}
void now_nav_bind_link(GtkWidget *button,GtkWidget *stack,const char *page){
 g_return_if_fail(GTK_IS_BUTTON(button) && GTK_IS_STACK(stack) && page);
 g_object_set_data(G_OBJECT(button),"now-nav-stack",stack);
 g_object_set_data_full(G_OBJECT(button),"now-nav-page",g_strdup(page),g_free);
 g_signal_connect(button,"clicked",G_CALLBACK(open_page),NULL);
}
void now_nav_update_back(GObject *stack,GParamSpec *param,gpointer back_button){
 (void)param;
 GtkWidget *back=GTK_WIDGET(back_button);
 const char *page=gtk_stack_get_visible_child_name(GTK_STACK(stack));
 if(page && strcmp(page,"dashboard")==0)gtk_widget_hide(back);
 else gtk_widget_show(back);
}
void now_nav_show_page(GtkWidget *stack,const char *page){
 if(!stack || !GTK_IS_STACK(stack) || !page)return;
 if(gtk_stack_get_child_by_name(GTK_STACK(stack),page))
   gtk_stack_set_visible_child_name(GTK_STACK(stack),page);
}
