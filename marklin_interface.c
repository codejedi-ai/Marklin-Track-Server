#include "marklin_interface.h"
#include <stdio.h>
#include <string.h>

// Parse Märklin 6051 Interface command from input string
int parse_marklin_command(const char* input, marklin_command_t* cmd) {
    if (!input || !cmd) return 0;
    
    // Skip whitespace
    while (*input == ' ' || *input == '\t') input++;
    
    // Handle single-byte commands (system and S88)
    if (strlen(input) == 1) {
        int info_char = (unsigned char)input[0]; // Use unsigned char to get correct ASCII value
        if (is_system_command(info_char)) {
            return parse_system_command(info_char, cmd);
        } else if (is_s88_command(info_char)) {
            return parse_s88_command(info_char, 0, cmd);
        }
        return 0;
    }
    
    // Handle two-byte commands
    if (strlen(input) < 2) return 0;
    
    int info_char = (unsigned char)input[0]; // Use unsigned char
    int address = (unsigned char)input[1];     // Use unsigned char
    
    // Determine command type based on info character
    if (is_special_functions_command(info_char)) {
        return parse_special_functions_command(info_char, address, cmd);
    } else if (is_accessory_command(info_char)) {
        return parse_accessory_command(info_char, address, cmd);
    } else if (is_s88_command(info_char)) {
        return parse_s88_command(info_char, address, cmd);
    } else {
        return parse_speed_direction_command(info_char, address, cmd);
    }
}

// Parse speed and direction command
int parse_speed_direction_command(int info_char, int address, marklin_command_t* cmd) {
    cmd->type = CMD_SPEED_DIRECTION;
    cmd->locomotive_address = address;
    cmd->accessory_address = 0; // Not used for locomotive commands
    
    // Extract F0 status (switching data)
    int f0_status = (info_char >= 16) ? 1 : 0;
    cmd->f0 = f0_status;
    
    // Extract speed/direction (operating data)
    int operating_data = info_char - (f0_status ? 16 : 0);
    
    if (operating_data == 15) {
        // Reverse command
        cmd->speed = 15;
        cmd->direction = 1; // Will be toggled in execution
    } else if (operating_data >= 0 && operating_data <= 14) {
        cmd->speed = operating_data;
        cmd->direction = 0; // Forward
    } else {
        return 0; // Invalid command
    }
    
    // Initialize special functions to 0 for speed commands
    cmd->f1 = cmd->f2 = cmd->f3 = cmd->f4 = 0;
    
    return 1;
}

// Parse special functions command
int parse_special_functions_command(int info_char, int address, marklin_command_t* cmd) {
    cmd->type = CMD_SPECIAL_FUNCTIONS;
    cmd->locomotive_address = address;
    cmd->accessory_address = 0; // Not used for locomotive commands
    
    // Extract function states using the formula:
    // Info Character = (1⋅f1) + (2⋅f2) + (4⋅f3) + (8⋅f4) + 64
    int function_data = info_char - 64;
    
    if (function_data < 0 || function_data > 15) return 0;
    
    cmd->f1 = (function_data & 1) ? 1 : 0;
    cmd->f2 = (function_data & 2) ? 1 : 0;
    cmd->f3 = (function_data & 4) ? 1 : 0;
    cmd->f4 = (function_data & 8) ? 1 : 0;
    
    // Special function commands don't change speed/direction/F0
    cmd->speed = -1; // Indicates no speed change
    cmd->direction = -1; // Indicates no direction change
    cmd->f0 = -1; // Indicates no F0 change
    
    return 1;
}

// Parse accessory command (turnouts/signals)
int parse_accessory_command(int info_char, int address, marklin_command_t* cmd) {
    cmd->type = CMD_ACCESSORY_POSITION;
    cmd->locomotive_address = 0; // Not used for accessory commands
    
    // Validate accessory address (1-256, where 256 is represented as 0)
    if (address == 0) {
        cmd->accessory_address = 256;
    } else if (address >= 1 && address <= 255) {
        cmd->accessory_address = address;
    } else {
        return 0; // Invalid address
    }
    
    // Set position based on info character
    if (info_char == 33) {
        cmd->position = ACCESSORY_STRAIGHT;
    } else if (info_char == 34) {
        cmd->position = ACCESSORY_BRANCH;
    } else {
        return 0; // Invalid position command
    }
    
    // Accessory commands don't affect locomotive parameters
    cmd->speed = -1;
    cmd->direction = -1;
    cmd->f0 = -1;
    cmd->f1 = cmd->f2 = cmd->f3 = cmd->f4 = -1;
    
    return 1;
}

// Parse system command (emergency stop, release)
int parse_system_command(int info_char, marklin_command_t* cmd) {
    cmd->locomotive_address = 0;
    cmd->accessory_address = 0;
    
    if (info_char == 97) {
        cmd->type = CMD_EMERGENCY_STOP;
    } else if (info_char == 96) {
        cmd->type = CMD_RELEASE;
    } else if (info_char == 32) {
        cmd->type = CMD_ACCESSORY_END;
    } else {
        return 0; // Invalid system command
    }
    
    // System commands don't affect locomotive parameters
    cmd->speed = -1;
    cmd->direction = -1;
    cmd->f0 = -1;
    cmd->f1 = cmd->f2 = cmd->f3 = cmd->f4 = -1;
    
    return 1;
}

// Check if info character indicates special functions command
int is_special_functions_command(int info_char) {
    // Special functions commands have info character >= 64
    return info_char >= 64;
}

// Check if info character indicates accessory command
int is_accessory_command(int info_char) {
    // Accessory commands are 33 (straight) or 34 (branch)
    return info_char == 33 || info_char == 34;
}

// Parse S88 command
int parse_s88_command(int info_char, int address, marklin_command_t* cmd) {
    (void)address; // Suppress unused parameter warning
    cmd->locomotive_address = 0; // Not used for S88 commands
    cmd->accessory_address = 0;  // Not used for S88 commands
    
    // Determine S88 command type and extract module number
    if (info_char >= 192 && info_char <= 192 + 31) {
        // Single module read (192+x)
        cmd->type = CMD_S88_SINGLE;
        cmd->s88_module_number = info_char - 192;
    } else if (info_char >= 128 && info_char <= 128 + 31) {
        // Multiple module read (128+x)
        cmd->type = CMD_S88_MULTIPLE;
        cmd->s88_module_number = info_char - 128;
    } else {
        return 0; // Invalid S88 command
    }
    
    // Validate S88 module number (1-31)
    if (cmd->s88_module_number < 1 || cmd->s88_module_number > 31) {
        return 0; // Invalid module number
    }
    
    // S88 commands don't affect locomotive parameters
    cmd->speed = -1;
    cmd->direction = -1;
    cmd->f0 = -1;
    cmd->f1 = cmd->f2 = cmd->f3 = cmd->f4 = -1;
    
    return 1;
}

// Check if info character indicates S88 command
int is_s88_command(int info_char) {
    // S88 commands are 128+x (multiple) or 192+x (single)
    return (info_char >= 128 && info_char <= 128 + 31) ||
           (info_char >= 192 && info_char <= 192 + 31);
}

// Check if info character indicates system command
int is_system_command(int info_char) {
    // System commands are 32 (end), 96 (release), or 97 (emergency stop)
    return info_char == 32 || info_char == 96 || info_char == 97;
}

// Execute command on train and track elements
int execute_command(marklin_command_t* cmd, train_t* trains, track_table_t* track_table) {
    if (!cmd || !trains) return 0;
    
    switch (cmd->type) {
        case CMD_SPEED_DIRECTION:
            {
                // Find the train with matching address
                train_t* train = NULL;
                for (int i = 0; i < MAX_TRAINS; i++) {
                    if (trains[i].id == cmd->locomotive_address) {
                        train = &trains[i];
                        break;
                    }
                }
                
                if (!train) {
                    printf("Error: Train %d not found\n", cmd->locomotive_address);
                    return 0;
                }
                
                if (cmd->speed == 15) {
                    // Reverse command
                    reverse_train(train);
                    printf("Train %d: Reverse direction\n", train->id);
                } else {
                    // Speed and F0 command
                    set_train_speed(train, cmd->speed, cmd->f0);
                    printf("Train %d: Speed=%d, F0=%d\n", train->id, cmd->speed, cmd->f0);
                }
            }
            break;
            
        case CMD_SPECIAL_FUNCTIONS:
            {
                // Find the train with matching address
                train_t* train = NULL;
                for (int i = 0; i < MAX_TRAINS; i++) {
                    if (trains[i].id == cmd->locomotive_address) {
                        train = &trains[i];
                        break;
                    }
                }
                
                if (!train) {
                    printf("Error: Train %d not found\n", cmd->locomotive_address);
                    return 0;
                }
                
                set_train_functions(train, cmd->f1, cmd->f2, cmd->f3, cmd->f4);
                printf("Train %d: F1=%d, F2=%d, F3=%d, F4=%d\n", 
                       train->id, cmd->f1, cmd->f2, cmd->f3, cmd->f4);
            }
            break;
            
        case CMD_ACCESSORY_POSITION:
            {
                if (!track_table) {
                    printf("Error: Track table not available\n");
                    break;
                }
                
                // Find the track element by address
                track_table_entry_t* element = find_track_element_by_address(track_table, cmd->accessory_address);
                
                if (!element) {
                    printf("Error: Accessory %d not found in track table\n", cmd->accessory_address);
                    break;
                }
                
                // Set the accessory state based on position
                int new_state = (cmd->position == ACCESSORY_STRAIGHT) ? 0 : 1; // 0=straight, 1=branch
                set_track_element_state(track_table, element->id, new_state);
                
                printf("Accessory %d (%s): Set to %s position\n",
                       cmd->accessory_address, element->name,
                       cmd->position == ACCESSORY_STRAIGHT ? "STRAIGHT/GREEN" : "BRANCH/RED");
            }
            break;
            
        case CMD_ACCESSORY_END:
            printf("Accessory switching procedure ended\n");
            break;
            
        case CMD_EMERGENCY_STOP:
            printf("EMERGENCY STOP: All trains stopped\n");
            // Stop all trains
            for (int i = 0; i < MAX_TRAINS; i++) {
                if (trains[i].id > 0) {
                    set_train_speed(&trains[i], 0, 0);
                }
            }
            break;
            
        case CMD_RELEASE:
            printf("RELEASE: Power restored to layout\n");
            break;
            
        case CMD_S88_SINGLE:
            {
                if (!track_table) {
                    printf("Error: Track table not available\n");
                    break;
                }
                
                int contact_states[16];
                if (get_s88_module_state(track_table, cmd->s88_module_number, contact_states)) {
                    printf("S88 Module %d sensor states: ", cmd->s88_module_number);
                    for (int i = 0; i < 16; i++) {
                        printf("%d", contact_states[i]);
                        if (i < 15) printf(" ");
                    }
                    printf("\n");
                } else {
                    printf("Error: Could not read S88 module %d\n", cmd->s88_module_number);
                }
            }
            break;
            
        case CMD_S88_MULTIPLE:
            {
                if (!track_table) {
                    printf("Error: Track table not available\n");
                    break;
                }
                
                printf("S88 Modules 1 to %d sensor states:\n", cmd->s88_module_number);
                for (int module = 1; module <= cmd->s88_module_number; module++) {
                    int contact_states[16];
                    if (get_s88_module_state(track_table, module, contact_states)) {
                        printf("  Module %d: ", module);
                        for (int i = 0; i < 16; i++) {
                            printf("%d", contact_states[i]);
                            if (i < 15) printf(" ");
                        }
                        printf("\n");
                    }
                }
            }
            break;
            
        default:
            printf("Error: Unknown command type\n");
            return 0;
    }
    
    return 1;
}

// Print command details
void print_command(marklin_command_t* cmd) {
    if (!cmd) return;
    
    printf("Command: ");
    
    switch (cmd->type) {
        case CMD_SPEED_DIRECTION:
            printf("Type=Speed/Direction, Address=%d, Speed=%d, F0=%d", 
                   cmd->locomotive_address, cmd->speed, cmd->f0);
            if (cmd->speed == 15) {
                printf(" (REVERSE)");
            }
            break;
            
        case CMD_SPECIAL_FUNCTIONS:
            printf("Type=Special Functions, Address=%d, F1=%d, F2=%d, F3=%d, F4=%d", 
                   cmd->locomotive_address, cmd->f1, cmd->f2, cmd->f3, cmd->f4);
            break;
            
        case CMD_ACCESSORY_POSITION:
            printf("Type=Accessory Position, Address=%d, Position=%s", 
                   cmd->accessory_address,
                   cmd->position == ACCESSORY_STRAIGHT ? "STRAIGHT/GREEN" : "BRANCH/RED");
            break;
            
        case CMD_ACCESSORY_END:
            printf("Type=Accessory End");
            break;
            
        case CMD_EMERGENCY_STOP:
            printf("Type=Emergency Stop");
            break;
            
        case CMD_RELEASE:
            printf("Type=Release");
            break;
            
        case CMD_S88_SINGLE:
            printf("Type=S88 Single Module, Module=%d", cmd->s88_module_number);
            break;
            
        case CMD_S88_MULTIPLE:
            printf("Type=S88 Multiple Modules, Count=%d", cmd->s88_module_number);
            break;
            
        default:
            printf("Type=Unknown");
            break;
    }
    printf("\n");
}

// Validate command
int validate_command(marklin_command_t* cmd) {
    if (!cmd) return 0;
    
    switch (cmd->type) {
        case CMD_SPEED_DIRECTION:
            // Validate locomotive address
            if (cmd->locomotive_address < 1 || cmd->locomotive_address > 80) {
                printf("Error: Invalid locomotive address %d (must be 1-80)\n", cmd->locomotive_address);
                return 0;
            }
            if (cmd->speed < 0 || cmd->speed > 15) {
                printf("Error: Invalid speed %d (must be 0-15)\n", cmd->speed);
                return 0;
            }
            if (cmd->f0 < 0 || cmd->f0 > 1) {
                printf("Error: Invalid F0 value %d (must be 0 or 1)\n", cmd->f0);
                return 0;
            }
            break;
            
        case CMD_SPECIAL_FUNCTIONS:
            // Validate locomotive address
            if (cmd->locomotive_address < 1 || cmd->locomotive_address > 80) {
                printf("Error: Invalid locomotive address %d (must be 1-80)\n", cmd->locomotive_address);
                return 0;
            }
            if (cmd->f1 < 0 || cmd->f1 > 1 || cmd->f2 < 0 || cmd->f2 > 1 ||
                cmd->f3 < 0 || cmd->f3 > 1 || cmd->f4 < 0 || cmd->f4 > 1) {
                printf("Error: Invalid function values (must be 0 or 1)\n");
                return 0;
            }
            break;
            
        case CMD_ACCESSORY_POSITION:
            // Validate accessory address
            if (cmd->accessory_address < 1 || cmd->accessory_address > 256) {
                printf("Error: Invalid accessory address %d (must be 1-256)\n", cmd->accessory_address);
                return 0;
            }
            if (cmd->position != ACCESSORY_STRAIGHT && cmd->position != ACCESSORY_BRANCH) {
                printf("Error: Invalid accessory position %d\n", cmd->position);
                return 0;
            }
            break;
            
        case CMD_ACCESSORY_END:
        case CMD_EMERGENCY_STOP:
        case CMD_RELEASE:
            // System commands don't need additional validation
            break;
            
        case CMD_S88_SINGLE:
        case CMD_S88_MULTIPLE:
            // Validate S88 module number
            if (cmd->s88_module_number < 1 || cmd->s88_module_number > 31) {
                printf("Error: Invalid S88 module number %d (must be 1-31)\n", cmd->s88_module_number);
                return 0;
            }
            break;
            
        default:
            printf("Error: Unknown command type\n");
            return 0;
    }
    
    return 1;
}
