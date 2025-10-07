#!/bin/bash

# Comprehensive test script for Märklin Track Server with Track Accessories

echo "=== Testing Märklin Track Server with Track Accessories ==="

# Create a test input file with proper binary commands
printf "add 5\n" > test_input.txt
printf "add 12\n" >> test_input.txt
printf "\0245" >> test_input.txt  # Speed 8 + F0 on for train 5
printf "\n" >> test_input.txt
printf "I12" >> test_input.txt    # Functions f1 and f4 on for train 12
printf "\n" >> test_input.txt
printf "!42" >> test_input.txt    # Set turnout 42 to STRAIGHT (ASCII 33)
printf "\n" >> test_input.txt
printf "\"42" >> test_input.txt   # Set turnout 42 to BRANCH (ASCII 34)
printf "\n" >> test_input.txt
printf " " >> test_input.txt      # End accessory switching (ASCII 32)
printf "\n" >> test_input.txt
printf "a" >> test_input.txt      # Emergency stop (ASCII 97)
printf "\n" >> test_input.txt
printf "\x60" >> test_input.txt   # Release (ASCII 96)
printf "\n" >> test_input.txt
printf "status\n" >> test_input.txt
printf "trains\n" >> test_input.txt
printf "quit\n" >> test_input.txt

echo "Running comprehensive test..."
./my_program < test_input.txt

echo "Cleaning up..."
rm test_input.txt
