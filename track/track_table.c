#include "track_table.h"
#include "track_data_new.h"
#include "../s88_observer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

// Create a new track table
track_table_t* create_track_table() {
    track_table_t* table = (track_table_t*)malloc(sizeof(track_table_t));
    if (!table) return NULL;
    
    table->entry_count = 0;
    table->next_id = 1;
    
    // Initialize all entries
    for (int i = 0; i < MAX_TRACK_TABLE_SIZE; i++) {
        table->entries[i].id = 0;
        table->entries[i].type = TRACK_ELEMENT_SENSOR;
        table->entries[i].name[0] = '\0';
        table->entries[i].node = NULL;
        table->entries[i].address = 0;
        table->entries[i].state = 0;
        table->entries[i].s88_module = 0;
        table->entries[i].s88_contact = 0;
        table->entries[i].occupied_by = NULL;
        table->entries[i].last_update = 0;
    }
    
    return table;
}

// Destroy track table
void destroy_track_table(track_table_t* table) {
    if (table) {
        free(table);
    }
}

// Add a track element to the table
int add_track_element(track_table_t* table, track_element_type type, const char* name, 
                     track_node* node, int address, int s88_module, int s88_contact) {
    if (!table || table->entry_count >= MAX_TRACK_TABLE_SIZE) return 0;
    
    int id = table->next_id++;
    track_table_entry_t* entry = &table->entries[table->entry_count];
    
    entry->id = id;
    entry->type = type;
    strncpy(entry->name, name, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';
    entry->node = node;
    entry->address = address;
    entry->state = 0;
    entry->s88_module = s88_module;
    entry->s88_contact = s88_contact;
    entry->occupied_by = NULL;
    entry->last_update = get_current_time_ms();
    
    table->entry_count++;
    return id;
}

// Remove a track element from the table
int remove_track_element(track_table_t* table, int id) {
    if (!table) return 0;
    
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].id == id) {
            // Shift remaining entries
            for (int j = i; j < table->entry_count - 1; j++) {
                table->entries[j] = table->entries[j + 1];
            }
            table->entry_count--;
            return 1;
        }
    }
    
    return 0;
}

// Find track element by ID
track_table_entry_t* find_track_element(track_table_t* table, int id) {
    if (!table) return NULL;
    
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].id == id) {
            return &table->entries[i];
        }
    }
    
    return NULL;
}

// Find track element by address
track_table_entry_t* find_track_element_by_address(track_table_t* table, int address) {
    if (!table) return NULL;
    
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].address == address) {
            return &table->entries[i];
        }
    }
    
    return NULL;
}

// Find track element by name
track_table_entry_t* find_track_element_by_name(track_table_t* table, const char* name) {
    if (!table || !name) return NULL;
    
    for (int i = 0; i < table->entry_count; i++) {
        if (strcmp(table->entries[i].name, name) == 0) {
            return &table->entries[i];
        }
    }
    
    return NULL;
}

// Set track element state
int set_track_element_state(track_table_t* table, int id, int state) {
    track_table_entry_t* entry = find_track_element(table, id);
    if (!entry) return 0;
    
    entry->state = state;
    entry->last_update = get_current_time_ms();
    return 1;
}

// Get track element state
int get_track_element_state(track_table_t* table, int id) {
    track_table_entry_t* entry = find_track_element(table, id);
    return entry ? entry->state : -1;
}

// Set track element occupancy
int set_track_element_occupancy(track_table_t* table, int id, train_t* train) {
    track_table_entry_t* entry = find_track_element(table, id);
    if (!entry) return 0;
    
    entry->occupied_by = train;
    entry->last_update = get_current_time_ms();
    return 1;
}

// Get track element occupancy
train_t* get_track_element_occupancy(track_table_t* table, int id) {
    track_table_entry_t* entry = find_track_element(table, id);
    return entry ? entry->occupied_by : NULL;
}

// Update S88 sensors based on train positions
int update_track_table_sensors(track_table_t* table, train_t* trains) {
    if (!table || !trains) return 0;
    
    // Clear all sensor states first
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].type == TRACK_ELEMENT_SENSOR) {
            table->entries[i].state = 0;
            table->entries[i].occupied_by = NULL;
        }
    }
    
    // Update sensor states based on train positions
    for (int t = 0; t < MAX_TRAINS; t++) {
        if (trains[t].id > 0 && trains[t].current_node) {
            // Find sensor elements at this node
            for (int i = 0; i < table->entry_count; i++) {
                if (table->entries[i].type == TRACK_ELEMENT_SENSOR &&
                    table->entries[i].node == trains[t].current_node) {
                    table->entries[i].state = 1;
                    table->entries[i].occupied_by = &trains[t];
                    table->entries[i].last_update = get_current_time_ms();
                }
            }
        }
    }
    
    return 1;
}

// Get S88 module state
int get_s88_module_state(track_table_t* table, int module_number, int* contact_states) {
    if (!table || !contact_states) return 0;
    
    // Initialize all contacts to 0
    for (int i = 0; i < 16; i++) {
        contact_states[i] = 0;
    }
    
    // Find all sensors in this module
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].type == TRACK_ELEMENT_SENSOR &&
            table->entries[i].s88_module == module_number &&
            table->entries[i].s88_contact >= 1 && table->entries[i].s88_contact <= 16) {
            contact_states[table->entries[i].s88_contact - 1] = table->entries[i].state;
        }
    }
    
    return 1;
}

// Set S88 contact state
int set_s88_contact_state(track_table_t* table, int module_number, int contact_number, int state) {
    if (!table) return 0;
    
    for (int i = 0; i < table->entry_count; i++) {
        if (table->entries[i].type == TRACK_ELEMENT_SENSOR &&
            table->entries[i].s88_module == module_number &&
            table->entries[i].s88_contact == contact_number) {
            table->entries[i].state = state;
            table->entries[i].last_update = get_current_time_ms();
            return 1;
        }
    }
    
    return 0;
}

// Print track table
void print_track_table(track_table_t* table) {
    if (!table) return;
    
    printf("=== Track Table ===\n");
    printf("Total elements: %d\n", table->entry_count);
    printf("ID | Type      | Name        | Address | S88 Mod | S88 Con | State | Occupied\n");
    printf("---|-----------|-------------|---------|---------|---------|-------|---------\n");
    
    for (int i = 0; i < table->entry_count; i++) {
        track_table_entry_t* entry = &table->entries[i];
        const char* type_str = "Unknown";
        switch (entry->type) {
            case TRACK_ELEMENT_SENSOR: type_str = "Sensor"; break;
            case TRACK_ELEMENT_TURNOUT: type_str = "Turnout"; break;
            case TRACK_ELEMENT_SIGNAL: type_str = "Signal"; break;
            case TRACK_ELEMENT_BLOCK: type_str = "Block"; break;
            case TRACK_ELEMENT_LOCOMOTIVE: type_str = "Locomotive"; break;
        }
        
        printf("%2d | %-9s | %-11s | %7d | %7d | %7d | %5d | %s\n",
               entry->id, type_str, entry->name, entry->address,
               entry->s88_module, entry->s88_contact, entry->state,
               entry->occupied_by ? "Yes" : "No");
    }
    printf("==================\n");
}

// Print single track element
void print_track_element(track_table_entry_t* entry) {
    if (!entry) return;
    
    const char* type_str = "Unknown";
    switch (entry->type) {
        case TRACK_ELEMENT_SENSOR: type_str = "Sensor"; break;
        case TRACK_ELEMENT_TURNOUT: type_str = "Turnout"; break;
        case TRACK_ELEMENT_SIGNAL: type_str = "Signal"; break;
        case TRACK_ELEMENT_BLOCK: type_str = "Block"; break;
        case TRACK_ELEMENT_LOCOMOTIVE: type_str = "Locomotive"; break;
    }
    
    printf("Track Element: ID=%d, Type=%s, Name=%s, Address=%d, State=%d\n",
           entry->id, type_str, entry->name, entry->address, entry->state);
    if (entry->s88_module > 0) {
        printf("  S88: Module=%d, Contact=%d\n", entry->s88_module, entry->s88_contact);
    }
    if (entry->occupied_by) {
        printf("  Occupied by: Train %d\n", entry->occupied_by->id);
    }
}

// Get track elements by type
int get_track_elements_by_type(track_table_t* table, track_element_type type, 
                              track_table_entry_t** results, int max_results) {
    if (!table || !results) return 0;
    
    int count = 0;
    for (int i = 0; i < table->entry_count && count < max_results; i++) {
        if (table->entries[i].type == type) {
            results[count] = &table->entries[i];
            count++;
        }
    }
    
    return count;
}

// Get occupied elements
int get_occupied_elements(track_table_t* table, track_table_entry_t** results, int max_results) {
    if (!table || !results) return 0;
    
    int count = 0;
    for (int i = 0; i < table->entry_count && count < max_results; i++) {
        if (table->entries[i].occupied_by != NULL) {
            results[count] = &table->entries[i];
            count++;
        }
    }
    
    return count;
}

// Initialize default track table with track nodes
void initialize_default_track_table(track_table_t* table, track_node* track_nodes) {
    if (!table || !track_nodes) return;
    
    // Add sensors for each track node
    for (int i = 0; i < TRACK_MAX; i++) {
        if (track_nodes[i].num > 0) {
            char name[32];
            snprintf(name, sizeof(name), "SENSOR_%s", track_nodes[i].name);
            
            // Map node to S88 module and contact
            int s88_module = (i % 31) + 1;  // Distribute across modules 1-31
            int s88_contact = (i % 16) + 1; // Distribute across contacts 1-16
            
            add_track_element(table, TRACK_ELEMENT_SENSOR, name, &track_nodes[i], 
                             i + 1, s88_module, s88_contact);
        }
    }
    
    // Add real turnouts from track data
    int turnout_address = 1;
    for (int i = 0; i < TRACK_MAX; i++) {
        if (track_nodes[i].num > 0 && track_nodes[i].type == NODE_BRANCH) {
            char name[32];
            snprintf(name, sizeof(name), "TURNOUT_%s", track_nodes[i].name);
            
            add_track_element(table, TRACK_ELEMENT_TURNOUT, name, &track_nodes[i], 
                             turnout_address, 0, 0);
            turnout_address++;
        }
    }

    // Add some example signals (these would need to be defined in track data)
    add_track_element(table, TRACK_ELEMENT_SIGNAL, "SIGNAL_A1", NULL, 10, 0, 0);
    add_track_element(table, TRACK_ELEMENT_SIGNAL, "SIGNAL_A2", NULL, 11, 0, 0);
}

// get_current_time_ms is defined in s88_observer.c
