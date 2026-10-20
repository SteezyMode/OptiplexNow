#ifndef NOW_SERVER_PREFLIGHT_UI_H
#define NOW_SERVER_PREFLIGHT_UI_H

#include <gtk/gtk.h>

/* Opens a read-only compatibility report for THIS computer.
 * Does not change the machine, contact remote servers, or start an installer.
 * Returns an owned-by-GTK widget pointer for transient callers/tests. */
GtkWidget *now_preflight_open(GtkWindow *parent);

#endif
