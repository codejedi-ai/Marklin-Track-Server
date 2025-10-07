#include "train.h"
#include "track/track_data_new.h"
#include "heap.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Global variables for track occupancy
static track_occupancy_t track_occupancy[TRACK_MAX];
static int occupancy_initialized = 0;

// Initialize track occupancy tracking
void init_track_occupancy() {
    if (!occupancy_initialized) {
        for (int i = 0; i < TRACK_MAX; i++) {
            track_occupancy[i].node = NULL;
            track_occupancy[i].occupied_by = NULL;
            track_occupancy[i].position = 0;
        }
        occupancy_initialized = 1;
    }
}

// Initialize a train
void init_train(train_t* train, int id) {
    train->id = id;
    train->state = TRAIN_STOPPED;
    train->speed = 0;
    train->direction = 0;
    train->f0 = 0;
    train->f1 = train->f2 = train->f3 = train->f4 = 0;
    
    train->current_node = NULL;
    train->next_node = NULL;
    train->position_on_edge = 0;
    train->target_speed = 0;
    
    train->destination = NULL;
    train->path = NULL;
    train->path_length = 0;
    train->path_index = 0;
    
    train->last_update = 0;
    train->next_move_time = 0;
    
    // Initialize factory pattern fields with defaults
    train->max_speed = 14;
    train->acceleration_rate = 2;
    train->deceleration_rate = 3;
    train->length_mm = 2000;
}

// Set train speed and F0 function
void set_train_speed(train_t* train, int speed, int f0) {
    if (speed < 0 || speed > 15) return;
    if (f0 < 0 || f0 > 1) return;
    
    train->f0 = f0;
    
    if (speed == 15) {
        // Reverse command
        reverse_train(train);
    } else {
        train->speed = speed;
        train->target_speed = speed;
        
        if (speed == 0) {
            train->state = TRAIN_STOPPED;
        } else {
            train->state = train->direction ? TRAIN_MOVING_REVERSE : TRAIN_MOVING_FORWARD;
        }
    }
}

// Set special functions f1-f4
void set_train_functions(train_t* train, int f1, int f2, int f3, int f4) {
    train->f1 = f1 ? 1 : 0;
    train->f2 = f2 ? 1 : 0;
    train->f3 = f3 ? 1 : 0;
    train->f4 = f4 ? 1 : 0;
}

// Reverse train direction
void reverse_train(train_t* train) {
    train->direction = !train->direction;
    train->state = TRAIN_REVERSING;
    
    // Reverse the path if we have one
    if (train->path && train->path_length > 0) {
        // Simple path reversal - in a real system you'd recalculate
        for (int i = 0; i < train->path_length / 2; i++) {
            track_node* temp = train->path[i];
            train->path[i] = train->path[train->path_length - 1 - i];
            train->path[train->path_length - 1 - i] = temp;
        }
        train->path_index = train->path_length - 1 - train->path_index;
    }
}

// Priority queue element for Dijkstra's algorithm
struct path_element {
    int* distance;
    track_node* current_node;
};

int path_compare(void *a, void *b) {
    struct path_element *a1 = (struct path_element *)a;
    struct path_element *b1 = (struct path_element *)b;
    int distance_a = *(a1->distance);
    int distance_b = *(b1->distance);
    if (distance_a > distance_b) return -1;
    if (distance_a < distance_b) return 1;
    return 0;
}

// Calculate path using Dijkstra's algorithm
int calculate_path(train_t* train, track_node* destination, track_node* track) {
    (void)track; // Suppress unused parameter warning
    if (!train->current_node || !destination) return 0;
    
    // Initialize Dijkstra's algorithm
    struct heap* h = (struct heap*)malloc(sizeof(struct heap));
    initHeap(h, path_compare);
    
    // Visited array
    int visited[NODE_EXIT + 1][TRACK_MAX];
    memset(visited, 0, sizeof(visited));
    visited[train->current_node->type][train->current_node->num] = 1;
    
    // Distance array
    int distance[NODE_EXIT + 1][TRACK_MAX];
    for (int i = 0; i < NODE_EXIT; i++) {
        for (int j = 0; j < TRACK_MAX; j++) {
            distance[i][j] = 1000000;
        }
    }
    distance[train->current_node->type][train->current_node->num] = 0;
    
    // Previous array for path reconstruction
    track_node* previous[NODE_EXIT + 1][TRACK_MAX];
    
    // Start with current node
    struct path_element* p = (struct path_element*)malloc(sizeof(struct path_element));
    p->distance = &distance[train->current_node->type][train->current_node->num];
    p->current_node = train->current_node;
    insert(h, p);
    
    // Dijkstra's algorithm
    while (!isEmpty(h)) {
        struct path_element* current = (struct path_element*)removeMax(h);
        track_node* current_node = current->current_node;
        int current_distance = *(current->distance);
        free(current);
        
        visited[current_node->type][current_node->num] = 1;
        
        // Check reverse direction
        track_node* rev_node = current_node->reverse;
        if (!visited[rev_node->type][rev_node->num] && 
            current_distance <= distance[rev_node->type][rev_node->num]) {
            distance[rev_node->type][rev_node->num] = current_distance;
            previous[rev_node->type][rev_node->num] = current_node;
            
            struct path_element* p1 = (struct path_element*)malloc(sizeof(struct path_element));
            p1->distance = &distance[rev_node->type][rev_node->num];
            p1->current_node = rev_node;
            insert(h, p1);
        }
        
        // Check ahead direction
        if (current_node->type != NODE_EXIT) {
            track_edge* edge1 = &current_node->edge[DIR_AHEAD];
            track_node* next_node = edge1->dest;
            if (!visited[next_node->type][next_node->num] && 
                current_distance + edge1->dist <= distance[next_node->type][next_node->num]) {
                distance[next_node->type][next_node->num] = current_distance + edge1->dist;
                previous[next_node->type][next_node->num] = current_node;
                
                struct path_element* p2 = (struct path_element*)malloc(sizeof(struct path_element));
                p2->distance = &distance[next_node->type][next_node->num];
                p2->current_node = next_node;
                insert(h, p2);
            }
        }
        
        // Check curved direction for branches
        if (current_node->type == NODE_BRANCH) {
            track_edge* edge2 = &current_node->edge[DIR_CURVED];
            track_node* curved_node = edge2->dest;
            if (!visited[curved_node->type][curved_node->num] && 
                current_distance + edge2->dist <= distance[curved_node->type][curved_node->num]) {
                distance[curved_node->type][curved_node->num] = current_distance + edge2->dist;
                previous[curved_node->type][curved_node->num] = current_node;
                
                struct path_element* p3 = (struct path_element*)malloc(sizeof(struct path_element));
                p3->distance = &distance[curved_node->type][curved_node->num];
                p3->current_node = curved_node;
                insert(h, p3);
            }
        }
    }
    
    free(h);
    
    // Reconstruct path
    if (distance[destination->type][destination->num] >= 1000000) {
        return 0; // No path found
    }
    
    // Count path length
    int path_length = 0;
    track_node* current = destination;
    while (current != train->current_node) {
        path_length++;
        current = previous[current->type][current->num];
    }
    
    // Allocate and build path
    if (train->path) free(train->path);
    train->path = (track_node**)malloc(path_length * sizeof(track_node*));
    train->path_length = path_length;
    
    current = destination;
    for (int i = path_length - 1; i >= 0; i--) {
        train->path[i] = current;
        current = previous[current->type][current->num];
    }
    
    train->path_index = 0;
    train->destination = destination;
    
    return 1;
}

// Update train position and state
void update_train(train_t* train, unsigned long current_time) {
    if (!train->current_node || train->state == TRAIN_STOPPED) return;
    
    // Calculate movement based on speed
    int speed_mm_per_ms = train->speed * 2; // Rough approximation
    if (speed_mm_per_ms == 0) return;
    
    unsigned long time_diff = current_time - train->last_update;
    if (time_diff < 100) return; // Update every 100ms minimum
    
    int distance_to_move = (time_diff * speed_mm_per_ms) / 1000;
    
    if (train->next_node) {
        track_edge* current_edge = NULL;
        
        // Find the edge we're moving along
        for (int i = 0; i < 2; i++) {
            if (train->current_node->edge[i].dest == train->next_node) {
                current_edge = &train->current_node->edge[i];
                break;
            }
        }
        
        if (current_edge) {
            train->position_on_edge += distance_to_move;
            
            // Check if we've reached the next node
            if (train->position_on_edge >= current_edge->dist) {
                train->position_on_edge = 0;
                train->current_node = train->next_node;
                
                // Get next node in path
                if (train->path && train->path_index < train->path_length - 1) {
                    train->path_index++;
                    train->next_node = train->path[train->path_index];
                } else {
                    train->next_node = NULL;
                    if (train->current_node == train->destination) {
                        train->state = TRAIN_STOPPED;
                        train->speed = 0;
                    }
                }
            }
        }
    }
    
    train->last_update = current_time;
}

// Check for collisions
int check_collision(train_t* train, track_node* track) {
    (void)track; // Suppress unused parameter warning
    init_track_occupancy();
    
    // Check if current position is occupied
    for (int i = 0; i < TRACK_MAX; i++) {
        if (track_occupancy[i].node == train->current_node && 
            track_occupancy[i].occupied_by != train) {
            return 1; // Collision detected
        }
    }
    
    return 0;
}

// Move train to a specific node
void move_train(train_t* train, track_node* track) {
    if (!train->current_node) {
        // Find a suitable starting position
        for (int i = 0; i < TRACK_MAX; i++) {
            if (track[i].type == NODE_ENTER) {
                train->current_node = &track[i];
                break;
            }
        }
    }
}

// Print train status
void print_train_status(train_t* train) {
    printf("Train %d: ", train->id);
    printf("State=%d, Speed=%d, Dir=%d, ", train->state, train->speed, train->direction);
    printf("F0=%d, F1=%d, F2=%d, F3=%d, F4=%d, ", train->f0, train->f1, train->f2, train->f3, train->f4);
    if (train->current_node) {
        printf("At=%s", train->current_node->name);
    }
    if (train->next_node) {
        printf("->%s", train->next_node->name);
    }
    printf("\n");
}