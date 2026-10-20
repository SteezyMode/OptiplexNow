#ifndef NOW_DISCOVERY_UI_H
#define NOW_DISCOVERY_UI_H

#include <gtk/gtk.h>

/* Nonblocking, read-only discovery of already-authorized NOW tailnet hosts.
 * No SSH authentication, pairing, privileged operations, or network sign-in. */
GtkWidget *now_discovery_open(GtkWindow *parent, GtkEntry *host_entry,
                             GtkLabel *notice);

#endif
