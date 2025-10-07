#include "trie.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Create a new TRIE
trie_t* create_trie() {
    trie_t* trie = (trie_t*)malloc(sizeof(trie_t));
    if (!trie) return NULL;
    
    trie->root = create_trie_node();
    if (!trie->root) {
        free(trie);
        return NULL;
    }
    
    trie->total_commands = 0;
    return trie;
}

// Destroy TRIE and free all memory
void destroy_trie(trie_t* trie) {
    if (!trie) return;
    
    if (trie->root) {
        destroy_trie_node(trie->root);
    }
    
    free(trie);
}

// Create a new TRIE node
trie_node_t* create_trie_node() {
    trie_node_t* node = (trie_node_t*)malloc(sizeof(trie_node_t));
    if (!node) return NULL;
    
    // Initialize all children to NULL
    for (int i = 0; i < TRIE_ALPHABET_SIZE; i++) {
        node->children[i] = NULL;
    }
    
    node->command_type = TRIE_CMD_NONE;
    node->is_end_of_command = 0;
    node->command_length = 0;
    node->command_data = NULL;
    
    return node;
}

// Destroy TRIE node and all its children
void destroy_trie_node(trie_node_t* node) {
    if (!node) return;
    
    // Recursively destroy all children
    for (int i = 0; i < TRIE_ALPHABET_SIZE; i++) {
        if (node->children[i]) {
            destroy_trie_node(node->children[i]);
        }
    }
    
    // Free command data if it exists
    if (node->command_data) {
        free(node->command_data);
    }
    
    free(node);
}

// Insert a command into the TRIE
int insert_command(trie_t* trie, const char* command, trie_command_type type, void* data) {
    if (!trie || !trie->root || !command) return 0;
    
    trie_node_t* current = trie->root;
    int len = strlen(command);
    
    for (int i = 0; i < len; i++) {
        unsigned char c = (unsigned char)command[i];
        
        if (!current->children[c]) {
            current->children[c] = create_trie_node();
            if (!current->children[c]) return 0;
        }
        
        current = current->children[c];
    }
    
    // Mark end of command
    current->is_end_of_command = 1;
    current->command_type = type;
    current->command_length = len;
    
    // Store command data
    if (data) {
        current->command_data = malloc(sizeof(void*));
        if (current->command_data) {
            *(void**)current->command_data = data;
        }
    }
    
    trie->total_commands++;
    return 1;
}

// Search for a complete command in the TRIE
trie_node_t* search_command(trie_t* trie, const char* command) {
    if (!trie || !trie->root || !command) return NULL;
    
    trie_node_t* current = trie->root;
    int len = strlen(command);
    
    for (int i = 0; i < len; i++) {
        unsigned char c = (unsigned char)command[i];
        
        if (!current->children[c]) {
            return NULL; // Command not found
        }
        
        current = current->children[c];
    }
    
    return current->is_end_of_command ? current : NULL;
}

// Search for a prefix in the TRIE (for partial matches)
trie_node_t* search_prefix(trie_t* trie, const char* prefix) {
    if (!trie || !trie->root || !prefix) return NULL;
    
    trie_node_t* current = trie->root;
    int len = strlen(prefix);
    
    for (int i = 0; i < len; i++) {
        unsigned char c = (unsigned char)prefix[i];
        
        if (!current->children[c]) {
            return NULL; // Prefix not found
        }
        
        current = current->children[c];
    }
    
    return current;
}

// Parse Märklin command character by character using TRIE
int parse_marklin_trie_command(trie_t* trie, char character, char* buffer, int* buffer_pos, int buffer_size) {
    if (!trie || !buffer || !buffer_pos) return 0;
    
    // Add character to buffer
    if (*buffer_pos >= buffer_size - 1) {
        // Buffer overflow, reset
        *buffer_pos = 0;
        return 0;
    }
    
    buffer[*buffer_pos] = character;
    buffer[*buffer_pos + 1] = '\0';
    (*buffer_pos)++;
    
    // Search for current prefix in TRIE
    trie_node_t* node = search_prefix(trie, buffer);
    
    if (!node) {
        // No matching prefix found, reset buffer
        *buffer_pos = 0;
        buffer[0] = '\0';
        return 0;
    }
    
    // Check if this is a complete command
    if (node->is_end_of_command) {
        // Command complete, DON'T reset buffer - let caller handle it
        return node->command_type;
    }
    
    // Command still incomplete, continue parsing
    return -1; // Indicates command is still being built
}

// Initialize TRIE with all Märklin commands
void initialize_marklin_trie(trie_t* trie) {
    if (!trie) return;
    
    // System commands (single byte)
    insert_command(trie, "\x20", TRIE_CMD_ACCESSORY_END, NULL);      // ASCII 32
    insert_command(trie, "\x60", TRIE_CMD_RELEASE, NULL);           // ASCII 96
    insert_command(trie, "\x61", TRIE_CMD_EMERGENCY_STOP, NULL);   // ASCII 97
    
    // S88 commands (single byte)
    for (int i = 1; i <= 31; i++) {
        char single_cmd[2] = {128 + i, '\0'};  // 128+x for multiple modules
        char multi_cmd[2] = {192 + i, '\0'};   // 192+x for single module
        insert_command(trie, single_cmd, TRIE_CMD_S88_MULTIPLE, NULL);
        insert_command(trie, multi_cmd, TRIE_CMD_S88_SINGLE, NULL);
    }
    
    // Accessory commands (two bytes: position + address)
    // NOTE: Skip address 0 here to avoid embedding NUL in C-strings;
    // address 0 (meaning 256) can be handled separately if needed.
    for (int addr = 1; addr <= 255; addr++) {
        char straight_cmd[3] = {33, addr, '\0'};  // 33 + address for straight
        char branch_cmd[3] = {34, addr, '\0'};    // 34 + address for branch
        insert_command(trie, straight_cmd, TRIE_CMD_ACCESSORY_POSITION, NULL);
        insert_command(trie, branch_cmd, TRIE_CMD_ACCESSORY_POSITION, NULL);
    }
    
    // Locomotive commands (two bytes: info + address)
    for (int addr = 1; addr <= 80; addr++) {
        // Speed/direction commands (0-31)
        for (int info = 0; info <= 31; info++) {
            char speed_cmd[3] = {info, addr, '\0'};
            insert_command(trie, speed_cmd, TRIE_CMD_SPEED_DIRECTION, NULL);
        }
        
        // Special function commands (64+)
        for (int info = 64; info <= 127; info++) {
            char func_cmd[3] = {info, addr, '\0'};
            insert_command(trie, func_cmd, TRIE_CMD_SPECIAL_FUNCTIONS, NULL);
        }
    }
    
    // Extended commands (text-based)
    insert_command(trie, "help", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "status", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "trains", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "start", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "stop", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "quit", TRIE_CMD_EXTENDED, NULL);
    insert_command(trie, "exit", TRIE_CMD_EXTENDED, NULL);
}

// Print TRIE structure (for debugging)
void print_trie(trie_t* trie) {
    if (!trie || !trie->root) return;
    
    printf("TRIE with %d commands:\n", trie->total_commands);
    print_trie_node(trie->root, 0);
}

// Print TRIE node (recursive helper)
void print_trie_node(trie_node_t* node, int depth) {
    if (!node) return;
    
    for (int i = 0; i < TRIE_ALPHABET_SIZE; i++) {
        if (node->children[i]) {
            for (int j = 0; j < depth; j++) printf("  ");
            printf("'%c' (%d)", (char)i, i);
            
            if (node->children[i]->is_end_of_command) {
                printf(" -> CMD_TYPE_%d", node->children[i]->command_type);
            }
            printf("\n");
            
            print_trie_node(node->children[i], depth + 1);
        }
    }
}