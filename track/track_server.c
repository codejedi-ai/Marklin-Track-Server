#include "track_server.h"
#include <string.h>

void init_track_server(track_server_t* server) {
    if (!server) return;
    for (int i = 0; i <= 256; i++) server->turnout_state[i] = 0;
}

void set_turnout_state(track_server_t* server, int address, int state) {
    if (!server) return;
    if (address == 0) address = 256;
    if (address < 1 || address > 256) return;
    server->turnout_state[address] = state ? 1 : 0;
}

int get_turnout_state(track_server_t* server, int address, int* out_state) {
    if (!server || !out_state) return 0;
    if (address == 0) address = 256;
    if (address < 1 || address > 256) return 0;
    *out_state = server->turnout_state[address];
    return 1;
}

void reset_turnouts(track_server_t* server) {
    if (!server) return;
    for (int i = 1; i <= 256; i++) server->turnout_state[i] = 0;
}
