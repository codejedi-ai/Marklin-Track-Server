#ifndef _MARKLIN_INTERFACE_H_
#define _MARKLIN_INTERFACE_H_

#include "train/train.h"
#include "track/track_table.h"

// Märklin 6051 Interface command types
typedef enum {
    CMD_SPEED_DIRECTION,    // General locomotive control (speed, direction, F0)
    CMD_SPECIAL_FUNCTIONS,  // Special function control (f1-f4)
    CMD_ACCESSORY_POSITION, // Track accessory position (turnouts/signals)
    CMD_ACCESSORY_END,      // End accessory switching procedure
    CMD_EMERGENCY_STOP,     // System-wide emergency stop
    CMD_RELEASE,            // System-wide power release (GO)
    CMD_S88_SINGLE,         // S88 single module read (192+x)
    CMD_S88_MULTIPLE        // S88 multiple module read (128+x)
} command_type;

// Accessory position types
typedef enum {
    ACCESSORY_STRAIGHT = 33,  // Straight/Green position
    ACCESSORY_BRANCH = 34     // Branch/Red position
} accessory_position;

// Command structure
typedef struct {
    command_type type;
    int locomotive_address;  // 1-80 for locomotives
    int accessory_address;    // 1-256 for accessories
    int s88_module_number;   // 1-31 for S88 modules
    int speed;              // 0-14 (0=stop, 15=reverse)
    int direction;          // 0=forward, 1=reverse
    int f0;                 // Auxiliary function F0 (0=off, 1=on)
    int f1, f2, f3, f4;    // Special functions (0=off, 1=on)
    accessory_position position; // For accessory commands
} marklin_command_t;

// Function declarations
int parse_marklin_command(const char* input, marklin_command_t* cmd);
int execute_command(marklin_command_t* cmd, train_t* trains, track_table_t* track_table);
void print_command(marklin_command_t* cmd);
int validate_command(marklin_command_t* cmd);

// Helper functions for command parsing
int parse_speed_direction_command(int info_char, int address, marklin_command_t* cmd);
int parse_special_functions_command(int info_char, int address, marklin_command_t* cmd);
int parse_accessory_command(int info_char, int address, marklin_command_t* cmd);
int parse_system_command(int info_char, marklin_command_t* cmd);
int parse_s88_command(int info_char, int address, marklin_command_t* cmd);
int is_special_functions_command(int info_char);
int is_accessory_command(int info_char);
int is_system_command(int info_char);
int is_s88_command(int info_char);

#endif
