#include "ui_games.h"

/* Projector-friendly compact view: no SSH, Wolf or Moonlight calls here. */
GtkWidget *now_games_page_new(GCallback on_play, GCallback on_settings,
                              GtkWidget **status_label)
{
    GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                   GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
    GtkWidget *content=gtk_box_new(GTK_ORIENTATION_VERTICAL,14);
    gtk_container_set_border_width(GTK_CONTAINER(content),14);
    gtk_container_add(GTK_CONTAINER(scroll),content);
    GtkWidget *title=gtk_label_new("GAMES");
    gtk_widget_set_name(title,"section");
    gtk_label_set_xalign(GTK_LABEL(title),0);
    gtk_box_pack_start(GTK_BOX(content),title,FALSE,FALSE,0);
    GtkWidget *heading=gtk_label_new("Steam Big Picture");
    gtk_widget_set_name(heading,"modalheading");
    gtk_label_set_xalign(GTK_LABEL(heading),0);
    gtk_box_pack_start(GTK_BOX(content),heading,FALSE,FALSE,0);
    GtkWidget *play=gtk_button_new_with_label("PLAY STEAM");
    gtk_widget_set_name(play,"tile");
    gtk_widget_set_size_request(play,-1,56);
    gtk_box_pack_start(GTK_BOX(content),play,FALSE,FALSE,0);
    g_signal_connect(play,"clicked",on_play,NULL);
    GtkWidget *status=gtk_label_new("READY TO PLAY");
    gtk_widget_set_name(status,"gameshint");
    gtk_label_set_line_wrap(GTK_LABEL(status),TRUE);
    gtk_label_set_xalign(GTK_LABEL(status),0);
    gtk_box_pack_start(GTK_BOX(content),status,FALSE,FALSE,0);
    if(status_label)*status_label=status;
    GtkWidget *settings=gtk_button_new_with_label("GAMES SETTINGS");
    gtk_widget_set_name(settings,"setupaction");
    gtk_box_pack_start(GTK_BOX(content),settings,FALSE,FALSE,0);
    g_signal_connect(settings,"clicked",on_settings,NULL);
    GtkWidget *help=gtk_label_new(
        "Approved owner devices launch Steam through Wolf and Moonlight. "
        "New devices require explicit owner enrollment in Games Settings.");
    gtk_widget_set_name(help,"helper");
    gtk_label_set_line_wrap(GTK_LABEL(help),TRUE);
    gtk_label_set_xalign(GTK_LABEL(help),0);
    gtk_box_pack_start(GTK_BOX(content),help,FALSE,FALSE,0);
    return scroll;
}
