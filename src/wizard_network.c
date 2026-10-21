#include "wizard_network.h"

#include "tailscale_async.h"

typedef struct WizardJob WizardJob;

struct NowWizardNetwork {
    NowWizardNetworkResult callback;
    gpointer context;
    WizardJob *active[2];
    guint timeout_ms;
    guint references;
    gboolean closed;
};

struct WizardJob {
    NowWizardNetwork *network;
    NowWizardNetworkKind kind;
    GCancellable *cancel;
    guint timer_id;
    gboolean timed_out;
};

static void network_unref(NowWizardNetwork *network)
{
    g_assert(network->references > 0);
    if (--network->references == 0) {
        g_free(network);
    }
}

static gboolean job_timed_out(gpointer data)
{
    WizardJob *job = data;
    job->timer_id = 0;
    job->timed_out = TRUE;
    g_cancellable_cancel(job->cancel);
    return G_SOURCE_REMOVE;
}

static void job_completed(GObject *source, GAsyncResult *result, gpointer data)
{
    (void)source;
    WizardJob *job = data;
    NowWizardNetwork *network = job->network;
    GError *error = NULL;
    char *reply = now_tailscale_run_finish(result, &error);

    if (job->timer_id) {
        g_source_remove(job->timer_id);
        job->timer_id = 0;
    }
    if (network->active[job->kind] == job) {
        network->active[job->kind] = NULL;
    }
    if (job->timed_out) {
        g_clear_error(&error);
        error = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_TIMED_OUT,
                                    "Connection check timed out");
        g_clear_pointer(&reply, g_free);
    }

    /* No callback is permitted after close, including for a cancelled job.
     * The callback is allowed to close the network during a nested GTK loop.
     */
    if (!network->closed && network->callback) {
        network->callback(network->context, job->kind, reply, error);
    }

    g_free(reply);
    g_clear_error(&error);
    g_object_unref(job->cancel);
    g_free(job);
    network_unref(network);
}

NowWizardNetwork *now_wizard_network_new(NowWizardNetworkResult callback,
                                         gpointer context, guint timeout_ms)
{
    g_return_val_if_fail(callback != NULL, NULL);
    NowWizardNetwork *network = g_new0(NowWizardNetwork, 1);
    network->references = 1;
    network->callback = callback;
    network->context = context;
    network->timeout_ms = timeout_ms ? timeout_ms : 9000;
    return network;
}

gboolean now_wizard_network_start(NowWizardNetwork *network,
                                   NowWizardNetworkKind kind,
                                   const char *helper_path)
{
    g_return_val_if_fail(network != NULL, FALSE);
    if (network->closed || kind < NOW_WIZARD_NET_STATUS ||
        kind > NOW_WIZARD_NET_DISCOVERY || network->active[kind] ||
        !helper_path || !g_path_is_absolute(helper_path)) {
        return FALSE;
    }

    WizardJob *job = g_new0(WizardJob, 1);
    job->network = network;
    job->kind = kind;
    job->cancel = g_cancellable_new();
    network->active[kind] = job;
    network->references++;
    job->timer_id = g_timeout_add(network->timeout_ms, job_timed_out, job);
    now_tailscale_run_async(helper_path, job->cancel, job_completed, job);
    return TRUE;
}

gboolean now_wizard_network_busy(const NowWizardNetwork *network,
                                  NowWizardNetworkKind kind)
{
    return network && !network->closed &&
           kind >= NOW_WIZARD_NET_STATUS && kind <= NOW_WIZARD_NET_DISCOVERY &&
           network->active[kind] != NULL;
}

void now_wizard_network_close(NowWizardNetwork *network)
{
    if (!network || network->closed) {
        return;
    }
    network->closed = TRUE;
    network->callback = NULL;
    network->context = NULL;
    for (guint index = 0; index < G_N_ELEMENTS(network->active); index++) {
        if (network->active[index]) {
            g_cancellable_cancel(network->active[index]->cancel);
        }
    }
    network_unref(network);
}
