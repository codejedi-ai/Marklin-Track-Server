#ifndef _TRACK_SERVER_H_
#define _TRACK_SERVER_H_

#include "../train.h"
#include "../marklin_interface.h"
#include "track_node.h"
#include "track_data_new.h"
#include "track_table.h"

#define MAX_COMMAND_LENGTH 256
#define SIMULATION_UPDATE_INTERVAL 100 // milliseconds

// Track server state
typedef struct {
    train_t trains[MAX_TRAINS];
    track_node track[TRACK_MAX];
    track_table_t* track_table;  // Track table for Märklin interface
    int active_trains;
    int simulation_running;
    unsigned long last_update_time;
    char command_buffer[MAX_COMMAND_LENGTH];
} track_server_t;

// Function declarations
void init_track_server(track_server_t* server);
void start_simulation(track_server_t* server);
void stop_simulation(track_server_t* server);
void update_simulation(track_server_t* server);
int process_command(track_server_t* server, const char* command);
void print_server_status(track_server_t* server);
void print_all_trains(track_server_t* server);
int add_train(track_server_t* server, int train_id);
int remove_train(track_server_t* server, int train_id);
train_t* find_train(track_server_t* server, int train_id);

// Command processing functions
int handle_speed_command(track_server_t* server, int train_id, int speed, int f0);
int handle_function_command(track_server_t* server, int train_id, int f1, int f2, int f3, int f4);
int handle_reverse_command(track_server_t* server, int train_id);
int handle_path_command(track_server_t* server, int train_id, const char* destination);

// Utility functions
unsigned long get_current_time_ms();
void print_help();

#endif
