# Specify the compiler
CC = gcc

# Specify compiler flags
CFLAGS = -Wall -Wextra

# Specify the target executable
TARGET = my_program

# Specify the source files
SRCS := $(wildcard *.c) $(wildcard *.S) $(wildcard C-heap/*.c) $(wildcard C-heap/*.S) $(wildcard track/*.c) $(wildcard dsa/*.c)

# Specify the object files
OBJS = $(SRCS:.c=.o)

# Default target
all: $(TARGET)

# Compile each source file into an object file
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Link the object files to create the executable
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

# Clean up the object files and the executable
clean:
	rm -f $(OBJS) $(TARGET)