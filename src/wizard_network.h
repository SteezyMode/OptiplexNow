#ifndef OPTIPLEX_NOW_WIZARD_NETWORK_H
#define OPTIPLEX_NOW_WIZARD_NETWORK_H

#include <gio/gio.h>

typedef struct NowWizardNetwork NowWizardNetwork;

typedef enum {
    NOW_WIZARD_NET_STATUS = 0,
    NOW_WIZARD_NET_DISCOVERY = 1
} NowWizardNetworkKind;

/* Called on the initiating main context; reply and error are borrowed.
 * The owner must not retain them after the callback returns.
 */
typedef void (*NowWizardNetworkResult)(gpointer context, NowWizardNetworkKind kind,
                                      const char *reply, const GError *error);

/* Owns an initial reference. timeout_ms is per operation (normally 9000).
 * Has no GTK dependency and never manages Tailscale accounts or the host.
 */
NowWizardNetwork *now_wizard_network_new(NowWizardNetworkResult callback,
                                         gpointer context, guint timeout_ms);

/* Fixed, trusted absolute paths supplied by the application, not user input.
 * Each operation has one active job; attempts to double-submit return FALSE.
 */
gboolean now_wizard_network_start(NowWizardNetwork *network,
                                   NowWizardNetworkKind kind,
                                   const char *helper_path);
gboolean now_wizard_network_busy(const NowWizardNetwork *network,
                                  NowWizardNetworkKind kind);

/* Synchronously disconnects all result callbacks and cancels outstanding
 * jobs. Their worker references keep the controller alive until completion.
 * After this call the application must not access the network pointer.
 */
void now_wizard_network_close(NowWizardNetwork *network);

#endif
