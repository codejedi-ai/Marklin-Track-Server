# Märklin Track Server

A comprehensive track simulation server that simulates trains on a track using the Märklin 6051 Interface protocol.

## Features

- **Märklin 6051 Interface Support**: Full implementation of the Märklin 6051 Interface protocol for locomotive control
- **Train Simulation**: Realistic train movement with speed control, direction changes, and function control
- **Pathfinding**: Dijkstra's algorithm for optimal route calculation between track nodes
- **Collision Detection**: Basic collision prevention system
- **Track Management**: Support for complex track layouts with sensors, branches, merges, and switches
- **Interactive Command Interface**: Both Märklin protocol commands and extended server commands

## Märklin 6051 Interface Commands

The server implements the complete Märklin 6051 Interface specification:

### General Locomotive Control (Speed, Direction, and F0)
- **Format**: Two-byte ASCII sequence: `<info_char><address>`
- **Info Character**: Operating Data (0-14) + Switching Data (0 or 16)
- **Address**: Locomotive address (1-80)
- **Speed**: 0 (stop) to 14 (fastest), 15 (reverse)
- **F0**: Auxiliary function (lights) - 0 (off) or 1 (on)

**Example**: `\0245` sets locomotive 5 to speed 8 with F0 on
- Operating Data: 8
- Switching Data: 16 (F0 on)
- Info Character: 8 + 16 = 24
- Address: 5

### Special Function Control (f1-f4)
- **Format**: Two-byte ASCII sequence: `<info_char><address>`
- **Info Character**: (1⋅f1) + (2⋅f2) + (4⋅f3) + (8⋅f4) + 64
- **Address**: Locomotive address (1-80)

**Example**: `I12` sets locomotive 12 functions f1 and f4 on
- f1=1, f2=0, f3=0, f4=1
- Info Character: (1⋅1) + (2⋅0) + (4⋅0) + (8⋅1) + 64 = 73
- Address: 12

### Track Accessory Control (Turnouts/Signals)
- **Format**: Two-byte ASCII sequence: `<position><address>`
- **Position**: 33 (Straight/Green) or 34 (Branch/Red)
- **Address**: Accessory address (1-255, or 0 for address 256)
- **End Command**: Single byte 32 to end switching procedure

**Example**: `!42` sets turnout 42 to Straight position
- Position: 33 (Straight/Green)
- Address: 42

**Example**: `"42` sets turnout 42 to Branch position
- Position: 34 (Branch/Red)
- Address: 42

### System-Wide Commands
- **Emergency Stop**: Single byte 97 - Stops all trains immediately
- **Release**: Single byte 96 - Restores power to layout
- **End Accessory**: Single byte 32 - Ends accessory switching procedure

### S88 Feedback Module (Sensor) Commands
The S88 feedback modules are used to determine track occupancy and signal train locations to the computer.

#### Single Module Read
- **Format**: Single-byte ASCII command: `192 + module_number`
- **Module Range**: 1-31
- **Purpose**: Read the state of a specific S88 module

**Example**: `193` reads module 1 (192+1)

#### Multiple Module Read
- **Format**: Single-byte ASCII command: `128 + module_count`
- **Module Range**: 1-31
- **Purpose**: Read the state of modules 1 up to the specified module

**Example**: `132` reads modules 1-4 (128+4)

#### Sensor Data Structure
Each S88 module provides 16 contact states (0=no occupancy, 1=occupied) that can be used for:
- Track occupancy detection
- Train position tracking
- Collision avoidance
- Signal control

## Single-Character Input Mode

The server now operates in **single-character input mode**, making it behave more like the actual Märklin 6051 Interface. This provides:

- **Real-time command processing**: Commands are processed character by character as they arrive
- **Binary command detection**: Märklin binary commands are automatically detected and processed
- **Text command support**: Standard text commands (help, status, etc.) work normally
- **TRIE-based parsing**: Efficient command recognition using a TRIE data structure

### How It Works

1. **Character Classification**: 
   - Printable ASCII (32-126): Treated as text commands
   - Non-printable/binary: Processed as Märklin commands

2. **TRIE Command Recognition**: 
   - All Märklin commands are stored in a TRIE for fast lookup
   - Commands are recognized as soon as they're complete
   - Supports partial command building for multi-byte commands

3. **Track Table Integration**:
   - Real-time sensor state tracking
   - Automatic occupancy detection
   - S88 module state management

### TRIE Pattern
- **Purpose**: Efficient command parsing and recognition
- **Implementation**: `trie.h` and `trie.c` provide fast command lookup
- **Benefits**: O(k) lookup time where k is command length, supports partial matches
- **Files**: `trie.h`, `trie.c`

### Observer Pattern
- **Purpose**: Decouple command processing from output handling
- **Implementation**: S88 sensor commands use observer pattern for sensor data notifications
- **Benefits**: Flexible sensor data handling and easy extension for new sensor types
- **Files**: `s88_observer.h`, `s88_observer.c`

### Factory Pattern
- **Purpose**: Create different types of trains with specific characteristics
- **Implementation**: `train_factory.h` and `train_factory.c` provide train creation based on type
- **Train Types**: Standard, Freight, Passenger, High-Speed
- **Benefits**: Consistent train creation and easy addition of new train types
- **Files**: `train_factory.h`, `train_factory.c`

## Extended Commands

The server also supports extended commands for simulation management:

- `help` - Show available commands
- `status` - Show server status
- `trains` - Show all active trains
- `start` - Start simulation
- `stop` - Stop simulation
- `add <id>` - Add train to simulation (1-80)
- `remove <id>` - Remove train from simulation
- `path <id> <node>` - Set path for train to destination node
- `quit` - Exit the server

## Building and Running

### Prerequisites
- GCC compiler
- Make

### Build
```bash
make clean
make
```

### Run
```bash
./my_program
```

### Test Märklin Commands
```bash
# Using Python to send proper binary commands
python3 -c "
import subprocess
commands = [
    b'add 5',
    b'add 12',
    bytes([24]) + bytes([5]),   # Speed 8 + F0 on for train 5
    bytes([73]) + bytes([12]), # Functions f1 and f4 on for train 12
    bytes([33]) + bytes([42]), # Set turnout 42 to STRAIGHT
    bytes([34]) + bytes([42]), # Set turnout 42 to BRANCH
    bytes([32]),               # End accessory switching
    bytes([193]),              # Read S88 module 1 (192+1)
    bytes([132]),              # Read S88 modules 1-4 (128+4)
    bytes([97]),               # Emergency stop
    bytes([96]),               # Release
    b'status',
    b'trains',
    b'quit'
]
input_str = b'\n'.join(commands) + b'\n'
result = subprocess.run(['./my_program'], input=input_str, capture_output=True)
print(result.stdout.decode('utf-8', errors='replace'))
"
```

## Architecture

### Core Components

1. **train.h/train.c**: Train data structures and movement logic
2. **marklin_interface.h/marklin_interface.c**: Märklin 6051 protocol implementation
3. **track_server.h/track_server.c**: Main server logic and command processing
4. **track_data_new.h/track_data_new.c**: Track layout and node definitions
5. **track_node.h**: Track node data structures
6. **heap.h/heap.c**: Priority queue implementation for pathfinding
7. **s88_observer.h/s88_observer.c**: S88 sensor feedback module with Observer pattern
8. **train_factory.h/train_factory.c**: Factory pattern for creating different train types
9. **trie.h/trie.c**: TRIE data structure for efficient command parsing
10. **track_table.h/track_table.c**: Track table for Märklin interface interaction

### Key Data Structures

- `train_t`: Complete train state including speed, direction, functions, position, and path
- `marklin_command_t`: Parsed Märklin command structure
- `track_server_t`: Server state including active trains and track data
- `track_node`: Track layout nodes (sensors, branches, merges, etc.)
- `s88_module_t`: S88 sensor module data with 16 contact states
- `s88_command_t`: S88 sensor command structure
- `train_config_t`: Train configuration for factory pattern
- `trie_t`: TRIE data structure for command parsing
- `track_table_t`: Track table for managing track elements and sensors
- `track_table_entry_t`: Individual track element entry

## Track Layout

The server uses a complex track layout with:
- **144 track nodes** including sensors, branches, merges, and entry/exit points
- **Multiple track sections** (A, B, C, D, E) with interconnected paths
- **Branch and merge points** for complex routing
- **Sensor nodes** for position tracking
- **Entry/exit points** for train management

## Simulation Features

- **Real-time Updates**: Continuous simulation with configurable update intervals
- **Speed Control**: 14-speed-step control with gradual acceleration
- **Direction Control**: Forward/reverse with automatic path reversal
- **Function Control**: F0 (lights) and f1-f4 (special functions)
- **Pathfinding**: Automatic route calculation using Dijkstra's algorithm
- **Collision Detection**: Basic collision prevention (can be enhanced)

## Example Usage

```
=== Märklin Track Server ===
Track simulation server with Märklin 6051 Interface support
Type 'help' for available commands
Type 'quit' to exit

Track simulation started
> add 5
Train 5 added to simulation
> add 12
Train 12 added to simulation
> [Märklin command: Speed 8 + F0 on for train 5]
Train 5: Speed=8, F0=1
> [Märklin command: Functions f1 and f4 on for train 12]
Train 12: F1=1, F2=0, F3=0, F4=1
> [Märklin command: Set turnout 42 to STRAIGHT]
Accessory 42: Set to STRAIGHT/GREEN position
> [Märklin command: Set turnout 42 to BRANCH]
Accessory 42: Set to BRANCH/RED position
> [Märklin command: End accessory switching]
Accessory switching procedure ended
> [Märklin command: Emergency stop]
EMERGENCY STOP: All trains stopped
> [Märklin command: Release]
RELEASE: Power restored to layout
> status
=== Track Server Status ===
Simulation: RUNNING
Active trains: 2
Track: Initialized (144 nodes)
Last update: 1759815741654 ms
===========================
> trains
=== Active Trains ===
Train 5: State=0, Speed=0, Dir=0, F0=0, F1=0, F2=0, F3=0, F4=0, At=EN1
Train 12: State=0, Speed=0, Dir=0, F0=0, F1=1, F2=0, F3=0, F4=1, At=EN1
====================
> quit
Track simulation stopped
Track server shutdown complete
```

## Technical Details

- **Protocol Compliance**: Full Märklin 6051 Interface specification implementation
- **Pathfinding Algorithm**: Dijkstra's algorithm with priority queue
- **Memory Management**: Dynamic allocation with proper cleanup
- **Thread Safety**: Single-threaded design for simplicity
- **Extensibility**: Modular design allows easy addition of new features

## Future Enhancements

- Multi-threading support for concurrent train operations
- Enhanced collision detection with predictive algorithms
- Sensor simulation with automatic train detection
- Switch control for branch/merge points
- Web interface for remote control
- Logging and replay functionality
- Performance optimization for large track layouts