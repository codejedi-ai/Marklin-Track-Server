#include "s88_observer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

// Observer pattern implementation
subject_t* create_subject(int max_observers) {
    subject_t* subject = (subject_t*)malloc(sizeof(subject_t));
    if (!subject) return NULL;
    
    subject->observers = (observer_t**)malloc(max_observers * sizeof(observer_t*));
    if (!subject->observers) {
        free(subject);
        return NULL;
    }
    
    subject->observer_count = 0;
    subject->max_observers = max_observers;
    
    // Initialize function pointers
    subject->attach = subject_attach;
    subject->detach = subject_detach;
    subject->notify = subject_notify;
    
    return subject;
}

void destroy_subject(subject_t* subject) {
    if (!subject) return;
    
    // Detach all observers
    for (int i = 0; i < subject->observer_count; i++) {
        if (subject->observers[i]) {
            destroy_observer(subject->observers[i]);
        }
    }
    
    free(subject->observers);
    free(subject);
}

observer_t* create_observer(void (*update_func)(observer_t*, const char*, int), 
                           void (*destroy_func)(observer_t*), void* private_data) {
    observer_t* observer = (observer_t*)malloc(sizeof(observer_t));
    if (!observer) return NULL;
    
    observer->update = update_func;
    observer->destroy = destroy_func;
    observer->private_data = private_data;
    
    return observer;
}

void destroy_observer(observer_t* observer) {
    if (!observer) return;
    
    if (observer->destroy) {
        observer->destroy(observer);
    }
    
    free(observer);
}

// Subject methods
void subject_attach(subject_t* subject, observer_t* observer) {
    if (!subject || !observer) return;
    
    if (subject->observer_count < subject->max_observers) {
        subject->observers[subject->observer_count] = observer;
        subject->observer_count++;
    }
}

void subject_detach(subject_t* subject, observer_t* observer) {
    if (!subject || !observer) return;
    
    for (int i = 0; i < subject->observer_count; i++) {
        if (subject->observers[i] == observer) {
            // Shift remaining observers
            for (int j = i; j < subject->observer_count - 1; j++) {
                subject->observers[j] = subject->observers[j + 1];
            }
            subject->observer_count--;
            break;
        }
    }
}

void subject_notify(subject_t* subject, const char* data, int data_length) {
    if (!subject || !data) return;
    
    for (int i = 0; i < subject->observer_count; i++) {
        if (subject->observers[i] && subject->observers[i]->update) {
            subject->observers[i]->update(subject->observers[i], data, data_length);
        }
    }
}

// S88 Sensor Manager implementation
s88_sensor_manager_t* create_s88_manager() {
    s88_sensor_manager_t* manager = (s88_sensor_manager_t*)malloc(sizeof(s88_sensor_manager_t));
    if (!manager) return NULL;
    
    // Initialize base subject
    manager->base.observers = (observer_t**)malloc(10 * sizeof(observer_t*));
    manager->base.observer_count = 0;
    manager->base.max_observers = 10;
    manager->base.attach = subject_attach;
    manager->base.detach = subject_detach;
    manager->base.notify = subject_notify;
    
    // Initialize S88 modules
    for (int i = 0; i < S88_MAX_MODULES; i++) {
        manager->modules[i].module_number = i + 1;
        manager->modules[i].last_update_time = 0;
        manager->modules[i].is_active = 0;
        
        // Initialize all contacts to 0 (no occupancy)
        for (int j = 0; j < S88_CONTACTS_PER_MODULE; j++) {
            manager->modules[i].contact_states[j] = 0;
        }
    }
    
    manager->active_modules = 0;
    manager->last_poll_time = get_current_time_ms();
    
    return manager;
}

void destroy_s88_manager(s88_sensor_manager_t* manager) {
    if (!manager) return;
    
    destroy_subject((subject_t*)manager);
}

// S88 Command parsing (renamed to avoid conflict with marklin_interface)
int parse_s88_sensor_command(const char* input, s88_command_t* cmd) {
    if (!input || !cmd) return 0;
    
    // Skip whitespace
    while (*input == ' ' || *input == '\t') input++;
    
    if (strlen(input) < 1) return 0;
    
    int command_char = (int)input[0];
    
    // Determine command type based on ASCII value
    if (command_char >= S88_SINGLE_MODULE_BASE + 1 && command_char <= S88_SINGLE_MODULE_BASE + S88_MAX_MODULES) {
        // Single module read (192+x)
        cmd->type = S88_SINGLE_MODULE;
        cmd->target_module = command_char - S88_SINGLE_MODULE_BASE;
        cmd->module_count = 1;
        cmd->command_char = command_char;
        return 1;
    } else if (command_char >= S88_MULTIPLE_MODULE_BASE + 1 && command_char <= S88_MULTIPLE_MODULE_BASE + S88_MAX_MODULES) {
        // Multiple module read (128+x)
        cmd->type = S88_MULTIPLE_MODULE;
        cmd->module_count = command_char - S88_MULTIPLE_MODULE_BASE;
        cmd->target_module = 1; // Always starts from module 1
        cmd->command_char = command_char;
        return 1;
    }
    
    return 0; // Invalid command
}

int calculate_s88_command_char(s88_command_type type, int module_number) {
    if (module_number < 1 || module_number > S88_MAX_MODULES) return -1;
    
    switch (type) {
        case S88_SINGLE_MODULE:
            return S88_SINGLE_MODULE_BASE + module_number;
        case S88_MULTIPLE_MODULE:
            return S88_MULTIPLE_MODULE_BASE + module_number;
        default:
            return -1;
    }
}

int validate_s88_command(s88_command_t* cmd) {
    if (!cmd) return 0;
    
    switch (cmd->type) {
        case S88_SINGLE_MODULE:
            if (cmd->target_module < 1 || cmd->target_module > S88_MAX_MODULES) {
                printf("Error: Invalid module number %d (must be 1-31)\n", cmd->target_module);
                return 0;
            }
            break;
        case S88_MULTIPLE_MODULE:
            if (cmd->module_count < 1 || cmd->module_count > S88_MAX_MODULES) {
                printf("Error: Invalid module count %d (must be 1-31)\n", cmd->module_count);
                return 0;
            }
            break;
        default:
            printf("Error: Unknown S88 command type\n");
            return 0;
    }
    
    return 1;
}

void print_s88_command(s88_command_t* cmd) {
    if (!cmd) return;
    
    printf("S88 Command: ");
    switch (cmd->type) {
        case S88_SINGLE_MODULE:
            printf("Type=Single Module, Module=%d, Char=%d", 
                   cmd->target_module, cmd->command_char);
            break;
        case S88_MULTIPLE_MODULE:
            printf("Type=Multiple Modules, Count=%d, Char=%d", 
                   cmd->module_count, cmd->command_char);
            break;
    }
    printf("\n");
}

// Execute S88 command
int execute_s88_command(s88_command_t* cmd, s88_sensor_manager_t* manager) {
    if (!cmd || !manager) return 0;
    
    if (!validate_s88_command(cmd)) return 0;
    
    printf("S88 Command executed: ");
    switch (cmd->type) {
        case S88_SINGLE_MODULE:
            printf("Reading module %d\n", cmd->target_module);
            // Simulate sensor data for single module
            simulate_s88_data(manager, cmd->target_module, cmd->target_module);
            break;
            
        case S88_MULTIPLE_MODULE:
            printf("Reading modules 1 to %d\n", cmd->module_count);
            // Simulate sensor data for multiple modules
            for (int i = 1; i <= cmd->module_count; i++) {
                simulate_s88_data(manager, i, i);
            }
            break;
    }
    
    return 1;
}

// Simulate S88 sensor data based on train positions
void simulate_s88_data(s88_sensor_manager_t* manager, int module_num, int train_id) {
    if (module_num < 1 || module_num > S88_MAX_MODULES) return;
    
    s88_module_t* module = &manager->modules[module_num - 1];
    module->is_active = 1;
    module->last_update_time = get_current_time_ms();
    
    // Simulate occupancy based on train presence
    // In a real system, this would be based on actual sensor readings
    for (int i = 0; i < S88_CONTACTS_PER_MODULE; i++) {
        // Simulate some contacts as occupied (for demonstration)
        module->contact_states[i] = (train_id % 3 == 0 && i < 4) ? 1 : 0;
    }
    
    // Notify observers with sensor data
    char sensor_data[64];
    snprintf(sensor_data, sizeof(sensor_data), "S88_MODULE_%d_DATA", module_num);
    manager->base.notify((subject_t*)manager, sensor_data, strlen(sensor_data));
}

// Update S88 sensors based on train positions
void update_s88_sensors(s88_sensor_manager_t* manager, train_t* trains) {
    if (!manager || !trains) return;
    
    unsigned long current_time = get_current_time_ms();
    
    // Update sensor states based on train positions
    for (int i = 0; i < MAX_TRAINS; i++) {
        if (trains[i].id > 0 && trains[i].current_node) {
            // Map train position to sensor module
            int module_num = map_train_to_sensor_module(&trains[i]);
            if (module_num > 0 && module_num <= S88_MAX_MODULES) {
                simulate_s88_data(manager, module_num, trains[i].id);
            }
        }
    }
    
    manager->last_poll_time = current_time;
}

// Map train position to sensor module (simplified mapping)
int map_train_to_sensor_module(train_t* train) {
    if (!train || !train->current_node) return 0;
    
    // Simple mapping: use node number modulo 31 + 1
    return (train->current_node->num % S88_MAX_MODULES) + 1;
}

// Print S88 sensor status
void print_s88_status(s88_sensor_manager_t* manager) {
    if (!manager) return;
    
    printf("=== S88 Sensor Status ===\n");
    printf("Active modules: %d\n", manager->active_modules);
    printf("Last poll time: %lu ms\n", manager->last_poll_time);
    
    for (int i = 0; i < S88_MAX_MODULES; i++) {
        if (manager->modules[i].is_active) {
            printf("Module %d: ", manager->modules[i].module_number);
            for (int j = 0; j < S88_CONTACTS_PER_MODULE; j++) {
                printf("%d", manager->modules[i].contact_states[j]);
                if (j < S88_CONTACTS_PER_MODULE - 1) printf(" ");
            }
            printf(" (last update: %lu ms)\n", manager->modules[i].last_update_time);
        }
    }
    printf("========================\n");
}

// Get current time in milliseconds
unsigned long get_current_time_ms() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000 + tv.tv_usec / 1000;
}
