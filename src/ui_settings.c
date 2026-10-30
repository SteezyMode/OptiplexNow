#include "ui_settings.h"
#include "ui_navigation.h"
#include "config.h"
#include "tray_prefs.h"
#include "desktop_autostart.h"
#include "ui_state.h"
#include <string.h>

/* Presentation mirrors the previous main.c GTK markup; all actions
 * remain application-owned callback hooks. */
static GtkWidget *label(const char *text,const char *id){
 GtkWidget *l=gtk_label_new(text);
 gtk_label_set_xalign(GTK_LABEL(l),0);
 if(id)gtk_widget_set_name(l,id);
 return l;
}
static GtkWidget *button(const char *text,const char *id){
 GtkWidget *b=gtk_button_new_with_label(text);
 if(id)gtk_widget_set_name(b,id);
 return b;
}
static void add(GtkWidget *box,GtkWidget *child,int expand){
 gtk_box_pack_start(GTK_BOX(box),child,expand,expand,0);
}
static GtkWidget *settings_page(GtkWidget *stack,const char *name){
 GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 GtkWidget *content=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);
 gtk_container_set_border_width(GTK_CONTAINER(content),14);
 gtk_container_add(GTK_CONTAINER(scroll),content);
 gtk_stack_add_named(GTK_STACK(stack),scroll,name);
 return content;
}
static void settings_link(GtkWidget *container,GtkWidget *stack,const char *caption,const char *page){
 gboolean back=g_str_has_prefix(caption,"‹");
 GtkWidget *b=button(caption,back?"navback":"setupaction");
 if(back)gtk_widget_set_halign(b,GTK_ALIGN_START);
 now_nav_bind_link(b,stack,page);
 add(container,b,0);
}
/* XFCE-style list ordering: move the existing row, preserving its checkboxes. */
static void tray_order_move(GtkWidget *button,gpointer direction_ptr){
 GtkWidget *row=gtk_widget_get_ancestor(button,GTK_TYPE_LIST_BOX_ROW);
 if(!row)return;
 GtkListBox *list=GTK_LIST_BOX(gtk_widget_get_parent(row));
 int from=gtk_list_box_row_get_index(GTK_LIST_BOX_ROW(row));
 int delta=GPOINTER_TO_INT(direction_ptr);
 int to=from+delta;
 if(to<0 || to>=8)return;
 g_object_ref(row);
 gtk_container_remove(GTK_CONTAINER(list),row);
 gtk_list_box_insert(list,row,to);
 g_object_unref(row);
 gtk_widget_show_all(GTK_WIDGET(list));
}
void now_settings_collect(const NowSettingsForm *form, NowSettingsDraft *draft)
{
    if (!form || !draft) return;
    memset(draft, 0, sizeof *draft);
    for (int i = 0; i < 8; ++i) {
        draft->fields[i] = gtk_entry_get_text(GTK_ENTRY(form->fields[i]));
        draft->tray_selected[i] = gtk_toggle_button_get_active(
            GTK_TOGGLE_BUTTON(form->tray_checks[i]));
        draft->featured_selected[i] = gtk_toggle_button_get_active(
            GTK_TOGGLE_BUTTON(form->featured_checks[i]));
        GtkListBoxRow *row = gtk_list_box_get_row_at_index(
            GTK_LIST_BOX(form->order_list), i);
        draft->order[i] = row ?
            GPOINTER_TO_INT(g_object_get_data(G_OBJECT(row), "service-id")) - 1 : i;
    }
    draft->disk_path = gtk_entry_get_text(GTK_ENTRY(form->diskentry));
    draft->browser_choice = gtk_combo_box_get_active(GTK_COMBO_BOX(form->combo));
    draft->desktop_caption = gtk_entry_get_text(
        GTK_ENTRY(form->desktop_caption_entry));
    draft->web_gaming_url = gtk_entry_get_text(
        GTK_ENTRY(form->web_url_entry));
    draft->startup_page = gtk_combo_box_get_active_id(
        GTK_COMBO_BOX(form->startup_choice));
    draft->login_tray_enabled = gtk_toggle_button_get_active(
        GTK_TOGGLE_BUTTON(form->login_tray_toggle));
}

/* The view never saves preferences or performs owner/host actions. */
GtkWidget *now_settings_build(GtkWidget *main_pages, GtkWidget *parent,
                              const NowSettingsCallbacks *callbacks,
                              const char values[CONFIG_COUNT][CONFIG_VALUE_SIZE],
                              unsigned featured_mask, unsigned tray_mask,
                              GtkWidget **tailscale_label_out){
 if(!main_pages || !parent || !callbacks || !values)return NULL;
 GtkWidget *win=parent;
 GtkWidget *settings_view=NULL;
 NowSettingsForm *form=g_new0(NowSettingsForm,1);
 GtkWidget*d=win;
 settings_view=gtk_scrolled_window_new(NULL,NULL);
 gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(settings_view),
  GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
 form->root=settings_view;
 g_object_set_data_full(G_OBJECT(settings_view),"now-settings-form",form,g_free);
 GtkWidget*area=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
 gtk_container_add(GTK_CONTAINER(settings_view),area);
 gtk_stack_add_named(GTK_STACK(main_pages),settings_view,"settings");
 GtkWidget*stack=gtk_stack_new();
 g_object_set_data(G_OBJECT(settings_view),"now-settings-stack",stack);
 gtk_stack_set_transition_type(GTK_STACK(stack),GTK_STACK_TRANSITION_TYPE_SLIDE_LEFT_RIGHT);
 gtk_widget_set_vexpand(stack,TRUE);
 add(area,stack,1);
 GtkWidget*home=settings_page(stack,"home");
 settings_link(home,stack,"GAMING & STREAMING  ›","gaming");
 settings_link(home,stack,"APPEARANCE & TRAY  ›","preferences");
 GtkWidget*other_apps=button("OTHER APPS  ›","setupaction");
 now_nav_bind_link(other_apps,main_pages,"software");
 add(home,other_apps,0);
 GtkWidget*system_info=button("SYSTEM INFO  ›","setupaction");
 g_signal_connect(system_info,"clicked",callbacks->on_system_info,NULL);
 add(home,system_info,0);
 
 add(home,label("SETUP & MAINTENANCE","modalheading"),0);
 settings_link(home,stack,"CONNECTIONS & SERVER  ›","connection");
 GtkWidget*connection=settings_page(stack,"connection");
 GtkWidget*gaming=settings_page(stack,"gaming");
 GtkWidget*preferences=settings_page(stack,"preferences");
 GtkWidget*pages[]={connection,gaming,preferences};
 for(int k=0;k<3;k++)settings_link(pages[k],stack,"‹ BACK TO SETTINGS","home");
 GtkWidget*col=connection;
 add(col,label("CONNECTION","modalheading"),0);
 add(col,label("Videos and Downloads use approved host discovery when available. Manual service URLs are optional in Advanced Settings.","helper"),0);
 GtkWidget*guided=button("SETUP WIZARD","setupaction");g_signal_connect_data(guided,"clicked",callbacks->on_wizard,NULL,NULL,0);add(col,guided,0);
 add(col,label("HOST SETUP (READ-ONLY)","modalheading"),0);
 GtkWidget*host_review=button("CHECK THIS PC FOR SERVER SETUP","setupaction");
 g_signal_connect(host_review,"clicked",callbacks->on_server_readiness,NULL);
 add(col,host_review,0);
 add(col,label("Checks hardware and installation blockers. Does not install or restart services.","helper"),0);
 GtkWidget *tailscale_label=label("CHECKING TAILSCALE","helper");add(col,tailscale_label,0);
 if(tailscale_label_out)*tailscale_label_out=tailscale_label;
 GtkWidget*gt=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(gt),10);gtk_grid_set_row_spacing(GTK_GRID(gt),7);add(col,gt,0);
 GtkWidget*advanced_grid=gtk_grid_new();gtk_grid_set_column_spacing(GTK_GRID(advanced_grid),10);gtk_grid_set_row_spacing(GTK_GRID(advanced_grid),7);
 GtkWidget*advanced=gtk_expander_new("ADVANCED SETTINGS");gtk_container_add(GTK_CONTAINER(advanced),advanced_grid);
 const char*names[]={"Server IP","SSH user","Wake relay IP","Relay SSH user","Wake command","Videos URL (override)","Music URL (optional)","Downloads URL (override)"};
 GtkWidget **fields=form->fields;
 for(int i=0;i<8;i++){
  GtkWidget*l=label(names[i],NULL);gtk_widget_set_size_request(l,110,-1);
  GtkWidget*dest=i<2?gt:advanced_grid;int row=i<2?i:i-2;
  gtk_grid_attach(GTK_GRID(dest),l,0,row,1,1);
  fields[i]=gtk_entry_new();gtk_entry_set_text(GTK_ENTRY(fields[i]),values[i]);gtk_widget_set_hexpand(fields[i],1);gtk_grid_attach(GTK_GRID(dest),fields[i],1,row,1,1);
 }
 GtkWidget*disklabel=label("Downloads disk",NULL);
 GtkWidget*diskentry=gtk_entry_new();gtk_entry_set_text(GTK_ENTRY(diskentry),values[10]);gtk_widget_set_hexpand(diskentry,1);
 gtk_grid_attach(GTK_GRID(advanced_grid),disklabel,0,7,1,1);gtk_grid_attach(GTK_GRID(advanced_grid),diskentry,1,7,1,1);
 GtkWidget*combo=gtk_combo_box_text_new();const char*opts[]={"Default browser (automatic)","System default","Chrome Flatpak","Chrome native"};
 for(int i=0;i<4;i++)gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo),opts[i]);
 int which=!strcmp(values[8],"system")?1:!strcmp(values[8],"chrome-flatpak")?2:!strcmp(values[8],"chrome")?3:0;
 gtk_combo_box_set_active(GTK_COMBO_BOX(combo),which);
 gtk_grid_attach(GTK_GRID(advanced_grid),label("Browser",NULL),0,6,1,1);
 gtk_grid_attach(GTK_GRID(advanced_grid),combo,1,6,1,1);
 GtkWidget*actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,7);
 GtkWidget*t=button("TAILSCALE","setupaction");g_signal_connect_data(t,"clicked",callbacks->on_tail,NULL,NULL,0);add(actions,t,1);
 add(col,actions,0);
 /* Ordinary SSH access stays available to owners under Advanced Settings,
  * never in the normal client enrollment wizard. */
 PairContext *server_context=&form->server_context,*relay_context=&form->relay_context;
 server_context->relay=0;relay_context->relay=1;
 for(int i=0;i<8;i++){server_context->inputs[i]=fields[i];relay_context->inputs[i]=fields[i];}
 server_context->parent=d;relay_context->parent=d;
 GtkWidget*admin_ssh=button("AUTHORIZE OWNER ADMIN SSH KEY","setupaction");
 g_signal_connect_data(admin_ssh,"clicked",callbacks->on_pair_click,server_context,NULL,0);
 gtk_grid_attach(GTK_GRID(advanced_grid),admin_ssh,0,8,2,1);
 GtkWidget*relay_ssh=button("AUTHORIZE WAKE RELAY SSH KEY","setupaction");
 g_signal_connect_data(relay_ssh,"clicked",callbacks->on_pair_click,relay_context,NULL,0);
 gtk_grid_attach(GTK_GRID(advanced_grid),relay_ssh,0,9,2,1);
 GtkWidget*ssh_warning=label(
   "OWNER ADMIN ONLY. These keys grant ordinary server-account shell access, "
   "not restricted Games/Downloads authorization. Do not use for client onboarding.",
   "helper");
 gtk_label_set_line_wrap(GTK_LABEL(ssh_warning),TRUE);
 gtk_grid_attach(GTK_GRID(advanced_grid),ssh_warning,0,10,2,1);
 col=gaming;
 add(col,label("STREAMING","modalheading"),0);
 GtkWidget*games=button("STREAMING SETUP (MOONLIGHT + WOLF)","setupaction");
 g_signal_connect_data(games,"clicked",callbacks->on_games_setup_from_settings,server_context,NULL,0);add(col,games,0);
 add(col,label("WEB GAMING URL (OPTIONAL)","helper"),0);
 GtkWidget*web_url_entry=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(web_url_entry),"https://your-streaming-host.example");
 gtk_entry_set_text(GTK_ENTRY(web_url_entry),values[16]);add(col,web_url_entry,0);
 GtkWidget*websettings=button("WEB GAMING SETTINGS","setupaction");
 g_signal_connect_data(websettings,"clicked",callbacks->on_web_gaming_settings,NULL,NULL,0);add(col,websettings,0);
 GtkWidget*webadmin=button("WEB GAMING ADMIN","setupaction");
 g_signal_connect_data(webadmin,"clicked",callbacks->on_web_gaming_admin,NULL,NULL,0);add(col,webadmin,0);
 col=preferences;
 add(col,label("OPEN ON STARTUP","modalheading"),0);
 add(col,label("Open on Dashboard or Games. Downloads remains a normal tab; tray shortcuts are independent. Window size is remembered.","helper"),0);
 GtkWidget*startup_choice=gtk_combo_box_text_new();
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(startup_choice),"dashboard","Dashboard");
 gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(startup_choice),"games","Games");
 gtk_combo_box_set_active_id(GTK_COMBO_BOX(startup_choice),now_ui_state_start_page());
 form->startup_choice=startup_choice;
 add(col,startup_choice,0);
 gboolean login_enabled=FALSE;
 gboolean login_supported=now_desktop_autostart_get(&login_enabled);
 GtkWidget*login_tray_toggle=gtk_check_button_new_with_label(
   "START MINIMIZED IN SYSTEM TRAY AT LOGIN");
 gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(login_tray_toggle),login_enabled);
 gtk_widget_set_sensitive(login_tray_toggle,login_supported);
 form->login_tray_toggle=login_tray_toggle;
 add(col,login_tray_toggle,0);
 add(col,label(login_supported?
   "Runs once at desktop login. First-time setup or a missing system tray opens the window instead.":
   "An existing autostart entry is not recognized. Preserve or review it manually.",
   "helper"),0);
 add(col,label("DESKTOP SHORTCUT NAME","modalheading"),0);
 add(col,label("Caption after Desktop | in tray. Does not rename Wolf itself.","helper"),0);
 char desktop_label[128];now_tray_desktop_caption(desktop_label,sizeof desktop_label);
 GtkWidget*desktop_caption_entry=gtk_entry_new();
 gtk_entry_set_max_length(GTK_ENTRY(desktop_caption_entry),48);
 gtk_entry_set_text(GTK_ENTRY(desktop_caption_entry),desktop_label);
 add(col,desktop_caption_entry,0);
 add(col,label("SHORTCUTS","modalheading"),0);
 add(col,label("Featured services appear above; the rest stay in Additional Services. Tray is independent.","helper"),0);
 GtkWidget **featured_checks=form->featured_checks,**tray_checks=form->tray_checks;
 GtkWidget*order_list=gtk_list_box_new();
 gtk_list_box_set_selection_mode(GTK_LIST_BOX(order_list),GTK_SELECTION_NONE);
 gtk_widget_set_name(order_list,"trayorder");
 int current_order[8];now_tray_order_load(current_order);
 GtkWidget*headers=gtk_grid_new();
 gtk_grid_set_column_spacing(GTK_GRID(headers),12);
 const char*head_names[]={"SERVICE","PRIMARY","TRAY","MOVE"};
 int widths[]={128,72,52,84};
 for(int h=0;h<4;h++){
  GtkWidget*heading=label(head_names[h],"storagehead");
  gtk_widget_set_size_request(heading,widths[h],-1);
  gtk_label_set_xalign(GTK_LABEL(heading),h==0?0.0f:0.5f);
  gtk_grid_attach(GTK_GRID(headers),heading,h,0,1,1);
 }
 add(col,headers,0);

 unsigned fm=featured_mask,tm=tray_mask;
 for(int n=0;n<8;n++){
   int i=current_order[n];
   GtkWidget*row=gtk_list_box_row_new();
   g_object_set_data(G_OBJECT(row),"service-id",GINT_TO_POINTER(i+1));
   GtkWidget*line=gtk_grid_new();
   gtk_grid_set_column_spacing(GTK_GRID(line),12);
   gtk_container_add(GTK_CONTAINER(row),line);
   GtkWidget*name=label(now_tray_service_name(i),NULL);
   gtk_widget_set_size_request(name,128,-1);
   gtk_label_set_xalign(GTK_LABEL(name),0);
   gtk_grid_attach(GTK_GRID(line),name,0,0,1,1);
   featured_checks[i]=gtk_check_button_new();
   tray_checks[i]=gtk_check_button_new();
   gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(featured_checks[i]),(fm&(1u<<i))!=0);
   gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(tray_checks[i]),(tm&(1u<<i))!=0);
   GtkWidget*primary_box=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,0);
   GtkWidget*tray_box=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,0);
   gtk_widget_set_size_request(primary_box,72,-1);
   gtk_widget_set_size_request(tray_box,52,-1);
   gtk_box_pack_start(GTK_BOX(primary_box),featured_checks[i],TRUE,FALSE,0);
   gtk_box_pack_start(GTK_BOX(tray_box),tray_checks[i],TRUE,FALSE,0);
   gtk_grid_attach(GTK_GRID(line),primary_box,1,0,1,1);
   gtk_grid_attach(GTK_GRID(line),tray_box,2,0,1,1);
   GtkWidget*arrows=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,3);
   gtk_widget_set_size_request(arrows,84,-1);
   gtk_box_set_homogeneous(GTK_BOX(arrows),TRUE);
   GtkWidget*up=button("↑","setting"),*down=button("↓","setting");
   g_signal_connect(up,"clicked",G_CALLBACK(tray_order_move),GINT_TO_POINTER(-1));
   g_signal_connect(down,"clicked",G_CALLBACK(tray_order_move),GINT_TO_POINTER(1));
   add(arrows,up,0);add(arrows,down,0);
   gtk_grid_attach(GTK_GRID(line),arrows,3,0,1,1);
   gtk_list_box_insert(GTK_LIST_BOX(order_list),row,-1);
 }
 add(col,order_list,0);
 col=connection;
 add(col,label("UPDATES & MAINTENANCE","modalheading"),0);
 GtkWidget*webmaint=button("WEB GAMING MAINTENANCE","setupaction");
 g_signal_connect_data(webmaint,"clicked",callbacks->on_web_gaming_maintenance,NULL,NULL,0);add(col,webmaint,0);
 add(col,advanced,0);
 PresetExportContext *export_context=&form->export_context;
 export_context->parent=d;export_context->disk=diskentry;
 for(int i=0;i<8;i++)export_context->fields[i]=fields[i];
 GtkWidget*export_btn=button("EXPORT MY OPTIPLEX","setupaction");
 g_signal_connect_data(export_btn,"clicked",callbacks->on_export_preset,export_context,NULL,0);add(col,export_btn,0);
  GtkWidget*full_export=button("EXPORT FULL BACKUP","setupaction");
 g_signal_connect_data(full_export,"clicked",callbacks->on_export_full_backup,d,NULL,0);add(col,full_export,0);
 GtkWidget*full_import=button("RESTORE FULL BACKUP","setupaction");
 g_signal_connect_data(full_import,"clicked",callbacks->on_restore_full_backup,NULL,NULL,0);add(col,full_import,0);

 GtkWidget*hint=label("Preset has addresses, never passwords or SSH keys.","helper");add(col,hint,0);
 form->diskentry=diskentry;form->combo=combo;
 form->order_list=order_list;form->web_url_entry=web_url_entry;
 form->desktop_caption_entry=desktop_caption_entry;
 GtkWidget*actions_footer=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
 gtk_container_set_border_width(GTK_CONTAINER(actions_footer),10);
 GtkWidget*cancel=button("CANCEL","navtab"),*save=button("SAVE SETTINGS","setupaction");
 gtk_box_pack_end(GTK_BOX(actions_footer),save,FALSE,FALSE,0);
 gtk_box_pack_end(GTK_BOX(actions_footer),cancel,FALSE,FALSE,0);
 g_signal_connect(cancel,"clicked",callbacks->on_discard,NULL);
 g_signal_connect(save,"clicked",callbacks->on_save,form);
 add(area,actions_footer,0);
 gtk_widget_show_all(settings_view);
 gtk_stack_set_visible_child_name(GTK_STACK(stack),"home");
 gtk_stack_set_visible_child_name(GTK_STACK(main_pages),"settings");
 return settings_view;
}

