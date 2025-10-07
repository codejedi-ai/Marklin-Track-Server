#ifndef _TRAIN_H_
#define _TRAIN_H_

#include "track_node.h"

#define MAX_TRAINS 10
#define MAX_SPEED_STEPS 14
#define MAX_FUNCTIONS 4

// Train states
typedef enum {
    TRAIN_STOPPED,
    TRAIN_MOVING_FORWARD,
    TRAIN_MOVING_REVERSE,
    TRAIN_REVERSING,
    TRAIN_COLLISION,
    TRAIN_OFFLINE
} train_state;

// Train data structure
typedef struct {
    int id;                    // Train ID (1-80)
    train_state state;        // Current state
    int speed;                // Speed step (0-14, 0=stop, 15=reverse)
    int direction;            // 0=forward, 1=reverse
    int f0;                   // Auxiliary function F0 (lights) 0=off, 1=on
    int f1, f2, f3, f4;      // Special functions f1-f4 (0=off, 1=on)
    
    // Position and movement
    track_node* current_node; // Current track node
    track_node* next_node;    // Next track node in path
    int position_on_edge;     // Position along current edge (0 to edge->dist)
    int target_speed;         // Target speed for gradual acceleration
    
    // Pathfinding
    track_node* destination;  // Final destination
    track_node** path;        // Calculated path to destination
    int path_length;          // Length of current path
    int path_index;           // Current position in path
    
    // Timing
    unsigned long last_update; // Last update timestamp
    unsigned long next_move_time; // When to move to next position
    
    // Factory pattern fields
    int max_speed;            // Maximum speed steps for this train type
    int acceleration_rate;    // Acceleration rate (steps per second)
    int deceleration_rate;   // Deceleration rate (steps per second)
    int length_mm;           // Train length in millimeters
    
} train_t;

// Track occupancy tracking
typedef struct {
    track_node* node;
    train_t* occupied_by;
    int position; // Position along edge if occupied
} track_occupancy_t;

// Function declarations
void init_train(train_t* train, int id);
void update_train(train_t* train, unsigned long current_time);
void set_train_speed(train_t* train, int speed, int f0);
void set_train_functions(train_t* train, int f1, int f2, int f3, int f4);
void reverse_train(train_t* train);
int calculate_path(train_t* train, track_node* destination, track_node* track);
void move_train(train_t* train, track_node* track);
int check_collision(train_t* train, track_node* track);
void print_train_status(train_t* train);

#endif
