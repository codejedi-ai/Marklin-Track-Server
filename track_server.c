#include "track_server.h"
#include "track_data_new.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

// Initialize track server
void init_track_server(track_server_t* server) {
    if (!server) return;
    
    // Initialize track
    init_tracka(server->track);
    
    // Initialize trains
    for (int i = 0; i < MAX_TRAINS; i++) {
        init_train(&server->trains[i], 0); // 0 means inactive
    }
    
    server->active_trains = 0;
    server->simulation_running = 0;
    server->last_update_time = get_current_time_ms();
    memset(server->command_buffer, 0, MAX_COMMAND_LENGTH);
    
    // Initialize track table
    server->track_table = create_track_table();
    if (server->track_table) {
        initialize_default_track_table(server->track_table, server->track);
    }
}

// Start simulation
void start_simulation(track_server_t* server) {
    if (!server) return;
    
    server->simulation_running = 1;
    server->last_update_time = get_current_time_ms();
    printf("Track simulation started\n");
}

// Stop simulation
void stop_simulation(track_server_t* server) {
    if (!server) return;
    
    server->simulation_running = 0;
    
    // Stop all trains
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (server->trains[i].id > 0) {
            set_train_speed(&server->trains[i], 0, 0);
        }
    }
    
    // Clean up track table
    if (server->track_table) {
        destroy_track_table(server->track_table);
        server->track_table = NULL;
    }
    
    printf("Track simulation stopped\n");
}

// Update simulation
void update_simulation(track_server_t* server) {
    if (!server || !server->simulation_running) return;
    
    unsigned long current_time = get_current_time_ms();
    
    // Update all active trains
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (server->trains[i].id > 0) {
            update_train(&server->trains[i], current_time);
            
            // Check for collisions
            if (check_collision(&server->trains[i], server->track)) {
                printf("COLLISION DETECTED: Train %d\n", server->trains[i].id);
                set_train_speed(&server->trains[i], 0, 0);
                server->trains[i].state = TRAIN_COLLISION;
            }
        }
    }
    
    server->last_update_time = current_time;
}

// Process command string
int process_command(track_server_t* server, const char* command) {
    if (!server || !command) return 0;
    
    // Skip whitespace
    while (*command == ' ' || *command == '\t') command++;
    
    if (strlen(command) == 0) return 1;
    
    // Handle special commands
    if (strcmp(command, "help") == 0) {
        print_help();
        return 1;
    }
    
    if (strcmp(command, "status") == 0) {
        print_server_status(server);
        return 1;
    }
    
    if (strcmp(command, "trains") == 0) {
        print_all_trains(server);
        return 1;
    }
    
    if (strcmp(command, "start") == 0) {
        start_simulation(server);
        return 1;
    }
    
    if (strcmp(command, "stop") == 0) {
        stop_simulation(server);
        return 1;
    }
    
    // Try to parse as Märklin command
    marklin_command_t cmd;
    if (parse_marklin_command(command, &cmd)) {
        if (validate_command(&cmd)) {
            return execute_command(&cmd, server->trains, server->track_table);
        }
    }
    
    // Try to parse as extended command
    char cmd_copy[MAX_COMMAND_LENGTH];
    strncpy(cmd_copy, command, MAX_COMMAND_LENGTH - 1);
    cmd_copy[MAX_COMMAND_LENGTH - 1] = '\0';
    
    char* token = strtok(cmd_copy, " ");
    if (!token) return 0;
    
    if (strcmp(token, "add") == 0) {
        token = strtok(NULL, " ");
        if (token) {
            int train_id = atoi(token);
            if (train_id > 0 && train_id <= 80) {
                add_train(server, train_id);
                return 1;
            }
        }
    }
    
    if (strcmp(token, "remove") == 0) {
        token = strtok(NULL, " ");
        if (token) {
            int train_id = atoi(token);
            if (train_id > 0 && train_id <= 80) {
                remove_train(server, train_id);
                return 1;
            }
        }
    }
    
    if (strcmp(token, "path") == 0) {
        token = strtok(NULL, " ");
        if (token) {
            int train_id = atoi(token);
            token = strtok(NULL, " ");
            if (token) {
                handle_path_command(server, train_id, token);
                return 1;
            }
        }
    }
    
    printf("Unknown command: %s\n", command);
    return 0;
}

// Print server status
void print_server_status(track_server_t* server) {
    if (!server) return;
    
    printf("=== Track Server Status ===\n");
    printf("Simulation: %s\n", server->simulation_running ? "RUNNING" : "STOPPED");
    printf("Active trains: %d\n", server->active_trains);
    printf("Track: Initialized (%d nodes)\n", TRACK_MAX);
    printf("Last update: %lu ms\n", server->last_update_time);
    printf("===========================\n");
}

// Print all trains
void print_all_trains(track_server_t* server) {
    if (!server) return;
    
    printf("=== Active Trains ===\n");
    int count = 0;
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (server->trains[i].id > 0) {
            print_train_status(&server->trains[i]);
            count++;
        }
    }
    if (count == 0) {
        printf("No active trains\n");
    }
    printf("====================\n");
}

// Add train to simulation
int add_train(track_server_t* server, int train_id) {
    if (!server || train_id < 1 || train_id > 80) return 0;
    
    // Check if train already exists
    if (find_train(server, train_id)) {
        printf("Train %d already exists\n", train_id);
        return 0;
    }
    
    // Find empty slot
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (server->trains[i].id == 0) {
            init_train(&server->trains[i], train_id);
            move_train(&server->trains[i], server->track);
            server->active_trains++;
            printf("Train %d added to simulation\n", train_id);
            return 1;
        }
    }
    
    printf("Cannot add train %d: maximum trains reached\n", train_id);
    return 0;
}

// Remove train from simulation
int remove_train(track_server_t* server, int train_id) {
    if (!server || train_id < 1 || train_id > 80) return 0;
    
    train_t* train = find_train(server, train_id);
    if (!train) {
        printf("Train %d not found\n", train_id);
        return 0;
    }
    
    // Stop train
    set_train_speed(train, 0, 0);
    train->id = 0; // Mark as inactive
    server->active_trains--;
    printf("Train %d removed from simulation\n", train_id);
    return 1;
}

// Find train by ID
train_t* find_train(track_server_t* server, int train_id) {
    if (!server || train_id < 1 || train_id > 80) return NULL;
    
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (server->trains[i].id == train_id) {
            return &server->trains[i];
        }
    }
    return NULL;
}

// Handle speed command
int handle_speed_command(track_server_t* server, int train_id, int speed, int f0) {
    train_t* train = find_train(server, train_id);
    if (!train) {
        printf("Train %d not found\n", train_id);
        return 0;
    }
    
    set_train_speed(train, speed, f0);
    return 1;
}

// Handle function command
int handle_function_command(track_server_t* server, int train_id, int f1, int f2, int f3, int f4) {
    train_t* train = find_train(server, train_id);
    if (!train) {
        printf("Train %d not found\n", train_id);
        return 0;
    }
    
    set_train_functions(train, f1, f2, f3, f4);
    return 1;
}

// Handle reverse command
int handle_reverse_command(track_server_t* server, int train_id) {
    train_t* train = find_train(server, train_id);
    if (!train) {
        printf("Train %d not found\n", train_id);
        return 0;
    }
    
    reverse_train(train);
    return 1;
}

// Handle path command
int handle_path_command(track_server_t* server, int train_id, const char* destination) {
    train_t* train = find_train(server, train_id);
    if (!train) {
        printf("Train %d not found\n", train_id);
        return 0;
    }
    
    // Find destination node by name
    track_node* dest_node = NULL;
    for (int i = 0; i < TRACK_MAX; i++) {
        if (strcmp(server->track[i].name, destination) == 0) {
            dest_node = &server->track[i];
            break;
        }
    }
    
    if (!dest_node) {
        printf("Destination node '%s' not found\n", destination);
        return 0;
    }
    
    if (calculate_path(train, dest_node, server->track)) {
        printf("Path calculated for train %d to %s\n", train_id, destination);
        return 1;
    } else {
        printf("No path found for train %d to %s\n", train_id, destination);
        return 0;
    }
}

// get_current_time_ms is defined in s88_observer.c

// Print help information
void print_help() {
    printf("=== Track Server Commands ===\n");
    printf("Märklin 6051 Interface Commands:\n");
    printf("  Locomotive Control:\n");
    printf("    <info_char><address> - Send command to locomotive\n");
    printf("      Info char 0-31: Speed/Direction + F0\n");
    printf("      Info char 64+: Special Functions f1-f4\n");
    printf("\n");
    printf("  Track Accessory Control:\n");
    printf("    <33><address> - Set turnout/signal to STRAIGHT/GREEN\n");
    printf("    <34><address> - Set turnout/signal to BRANCH/RED\n");
    printf("    <32>          - End accessory switching procedure\n");
    printf("    Address range: 1-255 (or 0 for address 256)\n");
    printf("\n");
    printf("  System Commands:\n");
    printf("    <97> - Emergency Stop (Nothalt)\n");
    printf("    <96> - Release (Freigabe)\n");
    printf("\n");
    printf("  S88 Sensor Commands:\n");
    printf("    <192+x> - Read single S88 module x (1-31)\n");
    printf("    <128+x> - Read S88 modules 1 to x (1-31)\n");
    printf("\n");
    printf("Extended Commands:\n");
    printf("  help              - Show this help\n");
    printf("  status            - Show server status\n");
    printf("  trains            - Show all active trains\n");
    printf("  start             - Start simulation\n");
    printf("  stop              - Stop simulation\n");
    printf("  add <id>          - Add train to simulation\n");
    printf("  remove <id>       - Remove train from simulation\n");
    printf("  path <id> <node>  - Set path for train to destination\n");
    printf("\n");
    printf("Examples:\n");
    printf("  add 5             - Add train 5\n");
    printf("  %c5               - Set train 5 to speed 8 with F0 on\n", 24);
    printf("  %c12              - Set train 12 functions f1 and f4 on\n", 73);
    printf("  %c42              - Set turnout 42 to STRAIGHT position\n", 33);
    printf("  %c42              - Set turnout 42 to BRANCH position\n", 34);
    printf("  %c                - End accessory switching\n", 32);
    printf("  %c                - Emergency stop all trains\n", 97);
    printf("  %c                - Release power to layout\n", 96);
    printf("  %c                - Read S88 module 1\n", 193);
    printf("  %c                - Read S88 modules 1-4\n", 132);
    printf("  path 5 A1         - Set path for train 5 to node A1\n");
    printf("=============================\n");
}
