#include "tray_actions.h"

#include <stdio.h>
#include <string.h>

#define EXPECT(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "Tray dispatch failed at line %d: %s\n", __LINE__, #condition); \
        return 1; \
    } \
} while (0)

typedef struct {
    char trace[64];
    int moonlight;
    int service;
} MockUI;

static void record(MockUI *ui, char event)
{
    size_t length = strlen(ui->trace);
    if (length + 1 < sizeof ui->trace) {
        ui->trace[length] = event;
        ui->trace[length + 1] = '\0';
    }
}

static void show(void *data) { record(data, 'W'); }
static void settings(void *data) { record(data, 'S'); }
static void info(void *data) { record(data, 'I'); }
static void quit(void *data) { record(data, 'Q'); }
static void restart(void *data) { record(data, 'R'); }
static int moonlight(void *data) { return ((MockUI *)data)->moonlight; }

static void service(void *data, int index)
{
    MockUI *ui = data;
    ui->service = index;
    record(ui, 'L');
}

int main(void)
{
    const NowTrayActions handlers = {
        .show_window = show,
        .open_settings = settings,
        .open_system_info = info,
        .quit = quit,
        .restart_streaming = restart,
        .launch_service = service,
        .moonlight_available = moonlight
    };
    MockUI ui = {.moonlight = 1, .service = -1};

    EXPECT(now_tray_dispatch_action(0, &handlers, &ui) == 1);
    EXPECT(strcmp(ui.trace, "L") == 0);
    EXPECT(ui.service == 0);

    memset(ui.trace, 0, sizeof ui.trace);
    ui.moonlight = 0;
    EXPECT(now_tray_dispatch_action(0, &handlers, &ui) == 1);
    EXPECT(strcmp(ui.trace, "WL") == 0);

    for (int index = 1; index < NOW_TRAY_ACTIONS; ++index) {
        memset(ui.trace, 0, sizeof ui.trace);
        ui.service = -1;
        EXPECT(now_tray_dispatch_action(index, &handlers, &ui) == 1);
        EXPECT(strcmp(ui.trace, index == 4 ? "WL" : "L") == 0);
        EXPECT(ui.service == index);
    }

    struct {
        int action;
        const char *trace;
    } cases[] = {
        {NOW_TRAY_OPEN_WINDOW, "W"},
        {NOW_TRAY_OPEN_SETTINGS, "WS"},
        {NOW_TRAY_OPEN_SYSTEM_INFO, "WI"},
        {NOW_TRAY_QUIT, "Q"},
        {NOW_TRAY_RESTART_STREAMING, "R"}
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        memset(ui.trace, 0, sizeof ui.trace);
        EXPECT(now_tray_dispatch_action(cases[i].action, &handlers, &ui) == 1);
        EXPECT(strcmp(ui.trace, cases[i].trace) == 0);
    }

    /* Unknown/stale menu IDs must not accidentally launch another action. */
    for (int index = -1; index <= 20; ++index) {
        if ((index >= 0 && index < NOW_TRAY_ACTIONS) ||
            (index >= NOW_TRAY_OPEN_WINDOW &&
             index <= NOW_TRAY_RESTART_STREAMING)) {
            continue;
        }
        memset(ui.trace, 0, sizeof ui.trace);
        EXPECT(now_tray_dispatch_action(index, &handlers, &ui) == 0);
        EXPECT(ui.trace[0] == '\0');
    }

    EXPECT(now_tray_dispatch_action(0, NULL, &ui) == 0);
    NowTrayActions missing = handlers;
    missing.launch_service = NULL;
    memset(ui.trace, 0, sizeof ui.trace);
    EXPECT(now_tray_dispatch_action(0, &missing, &ui) == 0);
    EXPECT(ui.trace[0] == '\0');

    missing = handlers;
    missing.show_window = NULL;
    memset(ui.trace, 0, sizeof ui.trace);
    EXPECT(now_tray_dispatch_action(4, &missing, &ui) == 0);
    EXPECT(ui.trace[0] == '\0');

    missing = handlers;
    missing.open_settings = NULL;
    memset(ui.trace, 0, sizeof ui.trace);
    EXPECT(now_tray_dispatch_action(NOW_TRAY_OPEN_SETTINGS, &missing, &ui) == 0);
    EXPECT(ui.trace[0] == '\0');

    puts("Tray dispatch: service selection, fallback, utility actions and invalid IDs passed.");
    return 0;
}
