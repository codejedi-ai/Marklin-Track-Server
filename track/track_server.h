#ifndef _TRACK_SERVER_H_
#define _TRACK_SERVER_H_

// Minimal track server: only switch (turnout) state management

typedef struct {
    int turnout_state[257]; // 1..256 (0 represents 256)
} track_server_t;

void init_track_server(track_server_t* server);
void set_turnout_state(track_server_t* server, int address, int state); // state: 0=straight,1=branch
int get_turnout_state(track_server_t* server, int address, int* out_state);
void reset_turnouts(track_server_t* server);

#endif
