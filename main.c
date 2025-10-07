#include <stdio.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include "track_server.h"
#include "trie.h"
#include "track_table.h"

#define MAX_COMMAND_LENGTH 256

// Global variables for single-character input
static struct termios old_termios;
static int raw_mode = 0;
static char command_buffer[MAX_COMMAND_LENGTH];
static int buffer_pos = 0;
static trie_t* command_trie = NULL;
static track_table_t* track_table = NULL;

// Function to enable raw mode for single character input
void enable_raw_mode() {
    if (raw_mode) return;
    
    tcgetattr(STDIN_FILENO, &old_termios);
    struct termios new_termios = old_termios;
    
    // Disable canonical mode and echo
    new_termios.c_lflag &= ~(ICANON | ECHO);
    new_termios.c_cc[VMIN] = 1;  // Read one character at a time
    new_termios.c_cc[VTIME] = 0; // No timeout
    
    tcsetattr(STDIN_FILENO, TCSANOW, &new_termios);
    raw_mode = 1;
}

// Function to disable raw mode
void disable_raw_mode() {
    if (!raw_mode) return;
    
    tcsetattr(STDIN_FILENO, TCSANOW, &old_termios);
    raw_mode = 0;
}

// Process single character input using TRIE
int process_single_character(track_server_t* server, char character) {
    if (!server || !command_trie) return 0;
    
    // Handle special characters
    if (character == '\n' || character == '\r') {
        // End of line - process any remaining text command
        if (buffer_pos > 0) {
            command_buffer[buffer_pos] = '\0';
            if (strcmp(command_buffer, "quit") == 0 || strcmp(command_buffer, "exit") == 0) {
                return -1; // Signal to quit
            }
            process_command(server, command_buffer);
            buffer_pos = 0;
            command_buffer[0] = '\0';
        }
        printf("\n> ");
        fflush(stdout);
		return 1;
	}
    
    if (character == 127 || character == '\b') {
        // Backspace
        if (buffer_pos > 0) {
            buffer_pos--;
            printf("\b \b");
            fflush(stdout);
        }
        return 1;
    }
    
    if (character == 3) { // Ctrl+C
        printf("\nExiting...\n");
        return -1;
    }
    
    // Check if this is a printable ASCII character (text command) or binary (Märklin command)
    if (character >= 32 && character <= 126) {
        // Printable ASCII - treat as text command
        if (buffer_pos < MAX_COMMAND_LENGTH - 1) {
            command_buffer[buffer_pos] = character;
            buffer_pos++;
            printf("%c", character);
            fflush(stdout);
        }
        return 1;
    } else {
        // Binary character - try to parse as Märklin command using TRIE
        int result = parse_marklin_trie_command(command_trie, character, command_buffer, &buffer_pos, MAX_COMMAND_LENGTH);
        
        if (result > 0) {
            // Complete Märklin command found
            printf("\nMärklin command detected: ");
            switch (result) {
                case TRIE_CMD_SPEED_DIRECTION:
                    printf("Speed/Direction command\n");
                    break;
                case TRIE_CMD_SPECIAL_FUNCTIONS:
                    printf("Special Functions command\n");
                    break;
                case TRIE_CMD_ACCESSORY_POSITION:
                    printf("Accessory Position command\n");
                    break;
                case TRIE_CMD_ACCESSORY_END:
                    printf("Accessory End command\n");
                    break;
                case TRIE_CMD_EMERGENCY_STOP:
                    printf("Emergency Stop command\n");
                    break;
                case TRIE_CMD_RELEASE:
                    printf("Release command\n");
                    break;
                case TRIE_CMD_S88_SINGLE:
                    printf("S88 Single Module command\n");
                    break;
                case TRIE_CMD_S88_MULTIPLE:
                    printf("S88 Multiple Module command\n");
                    break;
                default:
                    printf("Unknown command\n");
                    break;
            }
            
            // Process the command (preserve buffer until after processing)
            char temp_buffer[MAX_COMMAND_LENGTH];
            strncpy(temp_buffer, command_buffer, MAX_COMMAND_LENGTH - 1);
            temp_buffer[MAX_COMMAND_LENGTH - 1] = '\0';
            
            
            // Reset buffer first
            buffer_pos = 0;
            command_buffer[0] = '\0';
            
            // Process the preserved command
            process_command(server, temp_buffer);
            
            printf("> ");
            fflush(stdout);
            return 1;
        } else if (result == -1) {
            // Command still being built, continue
            printf("[%d]", (unsigned char)character);
            fflush(stdout);
            return 1;
        } else {
            // No valid command found
            printf("\nUnknown binary command: [%d]\n", (unsigned char)character);
            buffer_pos = 0;
            command_buffer[0] = '\0';
            printf("> ");
            fflush(stdout);
            return 1;
        }
    }
}

int main()
{
    track_server_t server;
    
    // Initialize the track server
    init_track_server(&server);
    
    // Initialize TRIE for command parsing
    command_trie = create_trie();
    if (!command_trie) {
        printf("Error: Failed to create command TRIE\n");
        return 1;
    }
    initialize_marklin_trie(command_trie);
    
    // Initialize track table
    track_table = server.track_table;  // Use the track table from server
    
    printf("=== Märklin Track Server ===\n");
    printf("Track simulation server with Märklin 6051 Interface support\n");
    printf("Single-character input mode enabled (like real Märklin interface)\n");
    printf("Type 'help' for available commands\n");
    printf("Type 'quit' to exit\n");
    printf("Press Ctrl+C to force exit\n\n");
    
    // Start simulation
    start_simulation(&server);
    
    // Enable raw mode for single character input
    enable_raw_mode();
    
    printf("> ");
    fflush(stdout);
    
    // Main command loop - single character input
    char character;
    while (1) {
        if (read(STDIN_FILENO, &character, 1) == 1) {
            int result = process_single_character(&server, character);
            if (result == -1) {
                break; // Quit signal
            }
            
            // Update simulation
            update_simulation(&server);
            
            // Update track table
            if (track_table) {
                update_track_table_sensors(track_table, server.trains);
            }
        }
    }
    
    // Cleanup
    disable_raw_mode();
    stop_simulation(&server);
    
    if (command_trie) {
        destroy_trie(command_trie);
    }
    
    // Track table is managed by the server, no need to destroy it here
    
    printf("\nTrack server shutdown complete\n");
    
	return 0;
}