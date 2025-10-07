#!/bin/bash

# Test script for Märklin Track Server

echo "=== Testing Märklin Track Server ==="

# Create a test input file with proper binary commands
printf "add 5\nadd 12\n" > test_input.txt
printf "\0245" >> test_input.txt  # Speed 8 + F0 on for train 5
printf "\n" >> test_input.txt
printf "I12" >> test_input.txt    # Functions f1 and f4 on for train 12
printf "\n" >> test_input.txt
printf "status\n" >> test_input.txt
printf "trains\n" >> test_input.txt
printf "quit\n" >> test_input.txt

echo "Running test..."
./my_program < test_input.txt

echo "Cleaning up..."
rm test_input.txt
