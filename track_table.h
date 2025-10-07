#ifndef _TRACK_TABLE_H_
#define _TRACK_TABLE_H_

#include "track_node.h"
#include "train.h"

// Track table for Märklin interface interaction
#define MAX_TRACK_TABLE_SIZE 1000

// Track element types for Märklin interface
typedef enum {
    TRACK_ELEMENT_SENSOR,      // Track sensor (S88 feedback)
    TRACK_ELEMENT_TURNOUT,     // Turnout/switch
    TRACK_ELEMENT_SIGNAL,      // Signal
    TRACK_ELEMENT_BLOCK,       // Track block
    TRACK_ELEMENT_LOCOMOTIVE   // Locomotive position
} track_element_type;

// Track table entry
typedef struct {
    int id;                     // Unique identifier
    track_element_type type;     // Type of track element
    char name[32];              // Human-readable name
    track_node* node;           // Associated track node
    int address;                // Märklin address (1-256 for accessories, 1-80 for locomotives)
    int state;                  // Current state (0/1 for binary, position for turnouts)
    int s88_module;             // S88 module number (1-31) if applicable
    int s88_contact;            // S88 contact number (1-16) if applicable
    train_t* occupied_by;       // Train occupying this element (if applicable)
    unsigned long last_update;  // Last update timestamp
} track_table_entry_t;

// Track table structure
typedef struct {
    track_table_entry_t entries[MAX_TRACK_TABLE_SIZE];
    int entry_count;
    int next_id;
} track_table_t;

// Function declarations
track_table_t* create_track_table();
void destroy_track_table(track_table_t* table);
int add_track_element(track_table_t* table, track_element_type type, const char* name, 
                     track_node* node, int address, int s88_module, int s88_contact);
int remove_track_element(track_table_t* table, int id);
track_table_entry_t* find_track_element(track_table_t* table, int id);
track_table_entry_t* find_track_element_by_address(track_table_t* table, int address);
track_table_entry_t* find_track_element_by_name(track_table_t* table, const char* name);

// Track element operations
int set_track_element_state(track_table_t* table, int id, int state);
int get_track_element_state(track_table_t* table, int id);
int set_track_element_occupancy(track_table_t* table, int id, train_t* train);
train_t* get_track_element_occupancy(track_table_t* table, int id);

// S88 sensor operations
int update_track_table_sensors(track_table_t* table, train_t* trains);
int get_s88_module_state(track_table_t* table, int module_number, int* contact_states);
int set_s88_contact_state(track_table_t* table, int module_number, int contact_number, int state);

// Track table queries
void print_track_table(track_table_t* table);
void print_track_element(track_table_entry_t* entry);
int get_track_elements_by_type(track_table_t* table, track_element_type type, 
                              track_table_entry_t** results, int max_results);
int get_occupied_elements(track_table_t* table, track_table_entry_t** results, int max_results);

// Initialization
void initialize_default_track_table(track_table_t* table, track_node* track_nodes);

#endif
