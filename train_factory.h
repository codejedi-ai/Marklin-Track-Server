#ifndef _TRAIN_FACTORY_H_
#define _TRAIN_FACTORY_H_

#include "train.h"

// Train types for factory pattern
typedef enum {
    TRAIN_TYPE_STANDARD,    // Standard locomotive
    TRAIN_TYPE_FREIGHT,     // Freight train
    TRAIN_TYPE_PASSENGER,   // Passenger train
    TRAIN_TYPE_HIGH_SPEED   // High-speed train
} train_type_t;

// Train configuration structure
typedef struct {
    train_type_t type;
    int id;
    int max_speed;          // Maximum speed steps
    int acceleration_rate;  // Acceleration rate (steps per second)
    int deceleration_rate; // Deceleration rate (steps per second)
    int length_mm;         // Train length in millimeters
    char* name;            // Train name/description
} train_config_t;

// Train Factory interface
typedef struct train_factory train_factory_t;

struct train_factory {
    train_t* (*create_train)(train_factory_t* factory, train_config_t* config);
    void (*destroy_train)(train_factory_t* factory, train_t* train);
    void (*destroy_factory)(train_factory_t* factory);
    int (*validate_config)(train_factory_t* factory, train_config_t* config);
};

// Function declarations
train_factory_t* create_train_factory();
train_t* create_train_by_type(train_type_t type, int id);
train_config_t* create_train_config(train_type_t type, int id);
void destroy_train_config(train_config_t* config);

// Train type specific creation functions
train_t* create_standard_train(int id);
train_t* create_freight_train(int id);
train_t* create_passenger_train(int id);
train_t* create_high_speed_train(int id);

// Configuration validation
int validate_train_config(train_config_t* config);
void print_train_config(train_config_t* config);

// Factory pattern implementation
train_t* factory_create_train(train_factory_t* factory, train_config_t* config);
void factory_destroy_train(train_factory_t* factory, train_t* train);
void factory_destroy_factory(train_factory_t* factory);
int factory_validate_config(train_factory_t* factory, train_config_t* config);

#endif
