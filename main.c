// Strict byte-by-byte Märklin input with TRIE recognition
#include <stdio.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include "trie.h"

#define MAX_COMMAND_LENGTH 4

static struct termios old_termios;
static int raw_mode = 0;
static char buffer[MAX_COMMAND_LENGTH];
static int buf_pos = 0;

static void enable_raw_mode() {
    if (raw_mode) return;
    tcgetattr(STDIN_FILENO, &old_termios);
    struct termios t = old_termios;
    t.c_lflag &= ~(ICANON | ECHO);
    t.c_cc[VMIN] = 1;
    t.c_cc[VTIME] = 0;
    tcsetattr(STDIN_FILENO, TCSANOW, &t);
    raw_mode = 1;
}

static void disable_raw_mode() {
    if (!raw_mode) return;
    tcsetattr(STDIN_FILENO, TCSANOW, &old_termios);
    raw_mode = 0;
}

int main() {
    trie_t* trie = create_trie();
    if (!trie) return 1;
    initialize_marklin_trie(trie);

    enable_raw_mode();
    printf("Byte-by-byte mode. Send Märklin bytes. Ctrl+C to exit.\n");

    while (1) {
        unsigned char ch;
        ssize_t n = read(STDIN_FILENO, &ch, 1);
        if (n != 1) break; // EOF or read error -> exit cleanly for non-interactive tests
        if (ch == 3) break; // Ctrl+C

        int result = parse_marklin_trie_command(trie, (char)ch, buffer, &buf_pos, MAX_COMMAND_LENGTH);

        if (result > 0) {
            int len = buf_pos;
            char tmp[MAX_COMMAND_LENGTH];
            memcpy(tmp, buffer, len);
            buf_pos = 0;
            buffer[0] = '\0';

            if (len == 2) {
                printf("Executing 2-byte command: [%u] [%u]\n", (unsigned char)tmp[0], (unsigned char)tmp[1]);
            } else {
                printf("Command detected (len=%d)\n", len);
            }
        }
    }

    disable_raw_mode();
    destroy_trie(trie);
	return 0;
}