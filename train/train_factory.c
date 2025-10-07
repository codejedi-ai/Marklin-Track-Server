#include "train_factory.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Train Factory implementation
train_factory_t* create_train_factory() {
    train_factory_t* factory = (train_factory_t*)malloc(sizeof(train_factory_t));
    if (!factory) return NULL;
    
    // Initialize function pointers
    factory->create_train = factory_create_train;
    factory->destroy_train = factory_destroy_train;
    factory->destroy_factory = factory_destroy_factory;
    factory->validate_config = factory_validate_config;
    
    return factory;
}

train_t* factory_create_train(train_factory_t* factory, train_config_t* config) {
    if (!factory || !config) return NULL;
    
    if (!factory->validate_config(factory, config)) {
        printf("Error: Invalid train configuration\n");
        return NULL;
    }
    
    train_t* train = NULL;
    
    switch (config->type) {
        case TRAIN_TYPE_STANDARD:
            train = create_standard_train(config->id);
            break;
        case TRAIN_TYPE_FREIGHT:
            train = create_freight_train(config->id);
            break;
        case TRAIN_TYPE_PASSENGER:
            train = create_passenger_train(config->id);
            break;
        case TRAIN_TYPE_HIGH_SPEED:
            train = create_high_speed_train(config->id);
            break;
        default:
            printf("Error: Unknown train type\n");
            return NULL;
    }
    
    if (train) {
        // Apply configuration settings
        train->max_speed = config->max_speed;
        train->acceleration_rate = config->acceleration_rate;
        train->deceleration_rate = config->deceleration_rate;
        train->length_mm = config->length_mm;
        
        printf("Created %s train (ID: %d)\n", config->name, config->id);
    }
    
    return train;
}

void factory_destroy_train(train_factory_t* factory, train_t* train) {
    (void)factory; // Suppress unused parameter warning
    
    if (train) {
        // Free any allocated resources
        if (train->path) {
            free(train->path);
            train->path = NULL;
        }
        
        // Reset train to inactive state
        train->id = 0;
        printf("Train destroyed\n");
    }
}

void factory_destroy_factory(train_factory_t* factory) {
    if (factory) {
        free(factory);
    }
}

int factory_validate_config(train_factory_t* factory, train_config_t* config) {
    (void)factory; // Suppress unused parameter warning
    
    return validate_train_config(config);
}

// Train configuration creation
train_config_t* create_train_config(train_type_t type, int id) {
    train_config_t* config = (train_config_t*)malloc(sizeof(train_config_t));
    if (!config) return NULL;
    
    config->type = type;
    config->id = id;
    
    // Set default values based on train type
    switch (type) {
        case TRAIN_TYPE_STANDARD:
            config->max_speed = 14;
            config->acceleration_rate = 2;
            config->deceleration_rate = 3;
            config->length_mm = 2000;
            config->name = "Standard Locomotive";
            break;
            
        case TRAIN_TYPE_FREIGHT:
            config->max_speed = 10;
            config->acceleration_rate = 1;
            config->deceleration_rate = 2;
            config->length_mm = 5000;
            config->name = "Freight Train";
            break;
            
        case TRAIN_TYPE_PASSENGER:
            config->max_speed = 12;
            config->acceleration_rate = 2;
            config->deceleration_rate = 2;
            config->length_mm = 3000;
            config->name = "Passenger Train";
            break;
            
        case TRAIN_TYPE_HIGH_SPEED:
            config->max_speed = 14;
            config->acceleration_rate = 3;
            config->deceleration_rate = 4;
            config->length_mm = 2500;
            config->name = "High-Speed Train";
            break;
            
        default:
            free(config);
            return NULL;
    }
    
    return config;
}

void destroy_train_config(train_config_t* config) {
    if (config) {
        free(config);
    }
}

// Train type specific creation functions
train_t* create_standard_train(int id) {
    train_t* train = (train_t*)malloc(sizeof(train_t));
    if (!train) return NULL;
    
    init_train(train, id);
    train->max_speed = 14;
    train->acceleration_rate = 2;
    train->deceleration_rate = 3;
    train->length_mm = 2000;
    
    return train;
}

train_t* create_freight_train(int id) {
    train_t* train = (train_t*)malloc(sizeof(train_t));
    if (!train) return NULL;
    
    init_train(train, id);
    train->max_speed = 10;
    train->acceleration_rate = 1;
    train->deceleration_rate = 2;
    train->length_mm = 5000;
    
    return train;
}

train_t* create_passenger_train(int id) {
    train_t* train = (train_t*)malloc(sizeof(train_t));
    if (!train) return NULL;
    
    init_train(train, id);
    train->max_speed = 12;
    train->acceleration_rate = 2;
    train->deceleration_rate = 2;
    train->length_mm = 3000;
    
    return train;
}

train_t* create_high_speed_train(int id) {
    train_t* train = (train_t*)malloc(sizeof(train_t));
    if (!train) return NULL;
    
    init_train(train, id);
    train->max_speed = 14;
    train->acceleration_rate = 3;
    train->deceleration_rate = 4;
    train->length_mm = 2500;
    
    return train;
}

// Configuration validation
int validate_train_config(train_config_t* config) {
    if (!config) return 0;
    
    if (config->id < 1 || config->id > 80) {
        printf("Error: Invalid train ID %d (must be 1-80)\n", config->id);
        return 0;
    }
    
    if (config->max_speed < 1 || config->max_speed > 14) {
        printf("Error: Invalid max speed %d (must be 1-14)\n", config->max_speed);
        return 0;
    }
    
    if (config->acceleration_rate < 1 || config->acceleration_rate > 10) {
        printf("Error: Invalid acceleration rate %d (must be 1-10)\n", config->acceleration_rate);
        return 0;
    }
    
    if (config->deceleration_rate < 1 || config->deceleration_rate > 10) {
        printf("Error: Invalid deceleration rate %d (must be 1-10)\n", config->deceleration_rate);
        return 0;
    }
    
    if (config->length_mm < 100 || config->length_mm > 10000) {
        printf("Error: Invalid train length %d mm (must be 100-10000)\n", config->length_mm);
        return 0;
    }
    
    return 1;
}

void print_train_config(train_config_t* config) {
    if (!config) return;
    
    printf("Train Configuration:\n");
    printf("  Type: %s\n", config->name);
    printf("  ID: %d\n", config->id);
    printf("  Max Speed: %d\n", config->max_speed);
    printf("  Acceleration Rate: %d\n", config->acceleration_rate);
    printf("  Deceleration Rate: %d\n", config->deceleration_rate);
    printf("  Length: %d mm\n", config->length_mm);
}

// Convenience function to create train by type
train_t* create_train_by_type(train_type_t type, int id) {
    train_factory_t* factory = create_train_factory();
    if (!factory) return NULL;
    
    train_config_t* config = create_train_config(type, id);
    if (!config) {
        factory->destroy_factory(factory);
        return NULL;
    }
    
    train_t* train = factory->create_train(factory, config);
    
    destroy_train_config(config);
    factory->destroy_factory(factory);
    
    return train;
}
