#ifndef _S88_OBSERVER_H_
#define _S88_OBSERVER_H_

#include "train/train.h"

// S88 Sensor Module Configuration
#define S88_MAX_MODULES 31
#define S88_CONTACTS_PER_MODULE 16
#define S88_SINGLE_MODULE_BASE 192
#define S88_MULTIPLE_MODULE_BASE 128

// S88 Sensor data structure
typedef struct {
    int module_number;                    // Module number (1-31)
    int contact_states[S88_CONTACTS_PER_MODULE]; // 16 contact states per module
    unsigned long last_update_time;      // Last update timestamp
    int is_active;                       // Module is active/responding
} s88_module_t;

// Observer pattern interfaces
typedef struct observer observer_t;
typedef struct subject subject_t;

// Observer interface
struct observer {
    void (*update)(observer_t* self, const char* data, int data_length);
    void (*destroy)(observer_t* self);
    void* private_data; // For storing observer-specific data
};

// Subject interface (for S88 command handling)
struct subject {
    void (*attach)(subject_t* self, observer_t* observer);
    void (*detach)(subject_t* self, observer_t* observer);
    void (*notify)(subject_t* self, const char* data, int data_length);
    observer_t** observers;
    int observer_count;
    int max_observers;
};

// S88 Command types
typedef enum {
    S88_SINGLE_MODULE,    // Read single module (192+x)
    S88_MULTIPLE_MODULE   // Read multiple modules (128+x)
} s88_command_type;

// S88 Command structure
typedef struct {
    s88_command_type type;
    int module_count;     // Number of modules to read (1-31)
    int target_module;    // For single module reads
    int command_char;     // Calculated ASCII character
} s88_command_t;

// S88 Sensor Manager (Subject)
typedef struct {
    subject_t base;
    s88_module_t modules[S88_MAX_MODULES];
    int active_modules;
    unsigned long last_poll_time;
} s88_sensor_manager_t;

// Function declarations
// Observer pattern
subject_t* create_subject(int max_observers);
void destroy_subject(subject_t* subject);
observer_t* create_observer(void (*update_func)(observer_t*, const char*, int), 
                           void (*destroy_func)(observer_t*), void* private_data);
void destroy_observer(observer_t* observer);
void subject_attach(subject_t* subject, observer_t* observer);
void subject_detach(subject_t* subject, observer_t* observer);
void subject_notify(subject_t* subject, const char* data, int data_length);

// S88 Sensor Manager
s88_sensor_manager_t* create_s88_manager();
void destroy_s88_manager(s88_sensor_manager_t* manager);
int parse_s88_sensor_command(const char* input, s88_command_t* cmd);
int execute_s88_command(s88_command_t* cmd, s88_sensor_manager_t* manager);
void update_s88_sensors(s88_sensor_manager_t* manager, train_t* trains);
void print_s88_status(s88_sensor_manager_t* manager);

// S88 Command parsing
int calculate_s88_command_char(s88_command_type type, int module_number);
int validate_s88_command(s88_command_t* cmd);
void print_s88_command(s88_command_t* cmd);

// Helper functions
unsigned long get_current_time_ms();
void simulate_s88_data(s88_sensor_manager_t* manager, int module_num, int train_id);
int map_train_to_sensor_module(train_t* train);

#endif
