#ifndef NOW_INSTANCE_LOCK_H
#define NOW_INSTANCE_LOCK_H

/* Linux desktop singleton: 1 = primary instance, 0 = existing instance
 * signaled to reopen, -1 = local lock/IO error. No GTK or host dependency.
 * On success the lock remains held until process exit. */
int now_instance_claim(void);

/* Signal-safe SIGUSR1 notification, consumed by the GTK main loop.
 * Returns one once after an existing process requests a reopen. */
int now_instance_reopen_pending(void);

#endif
