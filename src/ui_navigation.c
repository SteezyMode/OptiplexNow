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
void now_nav_mark_tab(GtkWidget *button,const char *page){
 g_return_if_fail(GTK_IS_BUTTON(button) && page);
 g_object_set_data_full(G_OBJECT(button),"now-nav-tab-page",g_strdup(page),g_free);
}
void now_nav_update_tabs(GObject *stack,GParamSpec *param,gpointer navigation_bar){
 (void)param;
 g_return_if_fail(GTK_IS_STACK(stack) && GTK_IS_CONTAINER(navigation_bar));
 const char *page=gtk_stack_get_visible_child_name(GTK_STACK(stack));
 /* Auxiliary Settings pages should keep the top-level Settings tab active. */
 if(page && (!strcmp(page,"info") || !strcmp(page,"software")))page="settings";
 GList *children=gtk_container_get_children(GTK_CONTAINER(navigation_bar));
 for(GList *item=children;item;item=item->next){
   GtkWidget *tab=GTK_WIDGET(item->data);
   const char *tab_page=g_object_get_data(G_OBJECT(tab),"now-nav-tab-page");
   if(!tab_page)continue;
   GtkStyleContext *style=gtk_widget_get_style_context(tab);
   if(page && strcmp(page,tab_page)==0)
     gtk_style_context_add_class(style,"active");
   else
     gtk_style_context_remove_class(style,"active");
 }
 g_list_free(children);
}
void now_nav_show_page(GtkWidget *stack,const char *page){
 if(!stack || !GTK_IS_STACK(stack) || !page)return;
 if(gtk_stack_get_child_by_name(GTK_STACK(stack),page))
   gtk_stack_set_visible_child_name(GTK_STACK(stack),page);
}
