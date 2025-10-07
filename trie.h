#ifndef _TRIE_H_
#define _TRIE_H_

#include <stdint.h>

// TRIE for Märklin command parsing
// Supports ASCII characters 0-255 for binary command handling
#define TRIE_ALPHABET_SIZE 256

// Command types that can be stored in TRIE
typedef enum {
    TRIE_CMD_NONE = 0,
    TRIE_CMD_SPEED_DIRECTION,
    TRIE_CMD_SPECIAL_FUNCTIONS,
    TRIE_CMD_ACCESSORY_POSITION,
    TRIE_CMD_ACCESSORY_END,
    TRIE_CMD_EMERGENCY_STOP,
    TRIE_CMD_RELEASE,
    TRIE_CMD_S88_SINGLE,
    TRIE_CMD_S88_MULTIPLE,
    TRIE_CMD_EXTENDED  // For extended commands like "add", "help", etc.
} trie_command_type;

// TRIE node structure
typedef struct trie_node {
    struct trie_node* children[TRIE_ALPHABET_SIZE];
    trie_command_type command_type;
    int is_end_of_command;
    int command_length;  // Length of command when complete
    void* command_data; // Additional data for the command
} trie_node_t;

// TRIE structure
typedef struct {
    trie_node_t* root;
    int total_commands;
} trie_t;

// Function declarations
trie_t* create_trie();
void destroy_trie(trie_t* trie);
trie_node_t* create_trie_node();
void destroy_trie_node(trie_node_t* node);

// TRIE operations
int insert_command(trie_t* trie, const char* command, trie_command_type type, void* data);
trie_node_t* search_command(trie_t* trie, const char* command);
trie_node_t* search_prefix(trie_t* trie, const char* prefix);

// Märklin command parsing with TRIE
int parse_marklin_trie_command(trie_t* trie, char character, char* buffer, int* buffer_pos, int buffer_size);
void initialize_marklin_trie(trie_t* trie);

// Helper functions
void print_trie(trie_t* trie);
void print_trie_node(trie_node_t* node, int depth);

#endif