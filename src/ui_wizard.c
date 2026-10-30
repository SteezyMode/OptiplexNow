#include "ui_wizard.h"

/* Only page layout and callback wiring. No credentials, daemon operations,
 * subprocesses or disk writes are handled from this translation unit. */

static GtkWidget *label(const char *text,const char *id)
{
 GtkWidget *widget=gtk_label_new(text);
 gtk_label_set_xalign(GTK_LABEL(widget),0);
 if(id)gtk_widget_set_name(widget,id);
 return widget;
}
static GtkWidget *button(const char *text,const char *id)
{
 GtkWidget *widget=gtk_button_new_with_label(text);
 if(id)gtk_widget_set_name(widget,id);
 return widget;
}
static void add(GtkWidget *box,GtkWidget *widget,int expand)
{
 gtk_box_pack_start(GTK_BOX(box),widget,expand,expand,0);
}
static GtkWidget *wizard_button(NowWizardView *view,GtkWidget *page,
                                 const char *title,const char *id,
                                 GCallback on_action,gpointer context)
{
 (void)view;
 GtkWidget *widget=button(title,"setupaction");
 gtk_widget_set_name(widget,id);
 gtk_style_context_add_class(
    gtk_widget_get_style_context(widget),"setupaction");
 g_signal_connect_data(widget,"clicked",on_action,context,NULL,0);
 add(page,widget,0);
 return widget;
}

GtkWidget *now_wizard_view_build(
    NowWizardView *view, GtkWindow *parent,
    const char values[CONFIG_COUNT][CONFIG_VALUE_SIZE],
    gboolean has_existing_setup, const char *moonlight_status,
    GCallback on_action, GCallback on_validate, gpointer context)
{
 if(!view || !parent || !values || !moonlight_status || !on_action || !on_validate)
    return NULL;
 GtkWidget *a=gtk_assistant_new();
 view->assistant=a;
 gtk_window_set_title(GTK_WINDOW(a),"OptiPlex Now | Setup");
 gtk_window_set_default_size(GTK_WINDOW(a),710,480);
 gtk_window_set_transient_for(GTK_WINDOW(a),parent);
 gtk_window_set_modal(GTK_WINDOW(a),TRUE);
 /* Page 1: keep existing device setup. No credentials or pairings are reset. */
 GtkWidget*one=gtk_box_new(GTK_ORIENTATION_VERTICAL,14);gtk_container_set_border_width(GTK_CONTAINER(one),24);
 add(one,label("CONNECT THIS DEVICE","modalheading"),0);
 view->ts_state=label("CHECKING TAILSCALE","gameshint");add(one,view->ts_state,0);
 view->tailscale_button=wizard_button(view,one,"CONNECT TAILSCALE","w_ts",on_action,context);
 wizard_button(view,one,"NEW TO TAILSCALE? CREATE ACCOUNT ↗","w_ts_signup",on_action,context);
 add(one,label("Connection status updates automatically after sign-in.","helper"),0);
 wizard_button(view,one,"IMPORT MY OPTIPLEX","w_import",on_action,context);
 wizard_button(view,one,"RESTORE FULL BACKUP (TRUSTED PC)","w_restore",on_action,context);
 view->preset_notice=label("","helper");add(one,view->preset_notice,0);
 if(has_existing_setup){
    add(one,label("EXISTING CONNECTION FOUND","helper"),0);
    wizard_button(view,one,"KEEP EXISTING SETUP","w_keep",on_action,context);
 }
 gtk_assistant_append_page(GTK_ASSISTANT(a),one);gtk_assistant_set_page_title(GTK_ASSISTANT(a),one,"NOW Setup: Tailscale");gtk_assistant_set_page_type(GTK_ASSISTANT(a),one,1);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),one,1);
 /* Page 2: choose your server. All values are prefilled from saved configuration. */
 GtkWidget*two=gtk_box_new(GTK_ORIENTATION_VERTICAL,13);view->server_page=two;gtk_container_set_border_width(GTK_CONTAINER(two),24);
 add(two,label("FIND YOUR SERVER","modalheading"),0);
 view->find_button=wizard_button(view,two,"FIND SERVER ON TAILSCALE","w_find",on_action,context);
 add(two,label("SERVER ADDRESS — CHOOSE ABOVE OR ENTER MANUALLY","helper"),0);
 view->host=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(view->host),"Tailscale IP or hostname");gtk_entry_set_text(GTK_ENTRY(view->host),values[0]);add(two,view->host,0);
 add(two,label("SERVER LINUX ACCOUNT (OWNER ALPHA)","helper"),0);
 view->user=gtk_entry_new();gtk_entry_set_placeholder_text(GTK_ENTRY(view->user),"Server Linux username");gtk_entry_set_text(GTK_ENTRY(view->user),values[1]);add(two,view->user,0);
 GtkWidget*owner_account_hint=label(
   "The owner-only alpha currently needs the host's configured Linux "
   "account to address the restricted service broker. This does not grant "
   "ordinary SSH or server permissions. Do not share an administrator password.", "helper");
 gtk_label_set_line_wrap(GTK_LABEL(owner_account_hint),TRUE);
 add(two,owner_account_hint,0);
 g_signal_connect_data(view->host,"changed",on_validate,context,NULL,0);
 g_signal_connect_data(view->user,"changed",on_validate,context,NULL,0);
 view->notice=label("","helper");add(two,view->notice,0);
 wizard_button(view,two,"NEW SERVER SETUP (PLANNED)","w_future",on_action,context);
 gtk_assistant_append_page(GTK_ASSISTANT(a),two);gtk_assistant_set_page_title(GTK_ASSISTANT(a),two,"NOW Setup: Server");gtk_assistant_set_page_type(GTK_ASSISTANT(a),two,0);
 /* Page 3: independent Moonlight identity for this Linux profile. */
 GtkWidget*four=gtk_box_new(GTK_ORIENTATION_VERTICAL,12);gtk_container_set_border_width(GTK_CONTAINER(four),24);
 add(four,label("CONNECT TO GAME HOST","modalheading"),0);
 add(four,label("Connect once during setup, then play from Games.","helper"),0);
 view->game_state=label(moonlight_status,"gameshint");add(four,view->game_state,0);
 view->wolf_state=label("CHECKING WOLF...","gameshint");add(four,view->wolf_state,0);
 view->games_page=four;
 wizard_button(view,four,"OPEN / INSTALL MOONLIGHT","w_moonlight",on_action,context);
 wizard_button(view,four,"SELECT APPIMAGE","w_appimage",on_action,context);
 wizard_button(view,four,"CONNECT TO GAME HOST","w_wolf",on_action,context);
 wizard_button(view,four,"REQUEST OWNER APPROVAL (PHONE QR)","w_owner_approve",on_action,context);
 GtkWidget*owner_access_note=label(
   "Two separate approvals: first pair Moonlight with Wolf, then request "
   "NOW owner access for managed Games and Downloads. A configured private "
   "Tailscale host listener can offer owner-phone QR approval without "
   "preapproved SSH; otherwise the host owner must enable or review "
   "enrollment. Requests never authorize themselves.", "helper");
 gtk_label_set_line_wrap(GTK_LABEL(owner_access_note),TRUE);
 add(four,owner_access_note,0);
 
 gtk_assistant_append_page(GTK_ASSISTANT(a),four);gtk_assistant_set_page_title(GTK_ASSISTANT(a),four,"NOW Setup: Games");gtk_assistant_set_page_type(GTK_ASSISTANT(a),four,0);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),four,1);
 /* Page 4: finish without manual URLs. */
 GtkWidget*six=gtk_box_new(GTK_ORIENTATION_VERTICAL,15);view->finish_page=six;gtk_container_set_border_width(GTK_CONTAINER(six),24);
 add(six,label("NEXT: VERIFY DEVICE ACCESS","modalheading"),0);
 GtkWidget*owner_ready_note=label(
   "Saving a server address does not prove device authorization. First confirm "
   "Moonlight/Wolf pairing, then use REQUEST OWNER APPROVAL on the Games setup "
   "page and VERIFY ACCESS in the approval window. Your owner must independently "
   "approve this device. The wizard may finish with access still pending; "
   "do not assume Games or Downloads works until the host verifies it. "
   "Videos opens Jellyfin in your browser and may require its own login.",
   "helper");
 gtk_label_set_line_wrap(GTK_LABEL(owner_ready_note),TRUE);
 add(six,owner_ready_note,0);
 add(six,label("Saved settings carry over between updates.","helper"),0);
 add(six,label("Open System Info from the dashboard for live hardware details.","helper"),0);
 gtk_assistant_append_page(GTK_ASSISTANT(a),six);gtk_assistant_set_page_title(GTK_ASSISTANT(a),six,"NOW Setup: Finish");gtk_assistant_set_page_type(GTK_ASSISTANT(a),six,2);gtk_assistant_set_page_complete(GTK_ASSISTANT(a),six,1);
 return a;
}
