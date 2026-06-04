#!/bin/bash
# Oulu Lane Detection - Process all available days
# Handles gaps in data automatically
# Usage: ./oulu_lanes.sh

echo "=========================================="
echo "OULU LANE DETECTION - ALL AVAILABLE DAYS"
echo "=========================================="
echo "Zone: Lanes (Vehicle-Vehicle Conflicts)"
echo "Data: /home/ubuntu/data/uploads/oulu_data/objects/clean/objects/clean"
echo "=========================================="
echo ""

# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate flow_env

# Data directory
DATA_DIR="/home/ubuntu/data/uploads/oulu_data/objects/clean/objects/clean"

# Get all unique dates from the data directory
echo "Scanning available dates..."
available_dates=$(ls "$DATA_DIR" | grep -E '^2025-[0-9]{2}-[0-9]{2}-' | cut -d'-' -f1-3 | sort -u)
total_days=$(echo "$available_dates" | wc -l)

echo "Found $total_days days of data"
echo ""

# Date range info
first_date=$(echo "$available_dates" | head -1)
last_date=$(echo "$available_dates" | tail -1)
echo "Date range: $first_date to $last_date"
echo ""

# Confirmation
echo "This will process all $total_days days of Oulu lane detection."
echo "Press Enter to continue or Ctrl+C to cancel..."
read

echo ""
echo "Starting batch processing..."
echo ""

# Counter
count=0

# Loop through each available date
while IFS= read -r current_date; do
    count=$((count + 1))
    echo "=========================================="
    echo "[$count/$total_days] Processing: $current_date"
    echo "=========================================="
    
    # Run detection for this day
    python regions/oulu/lane_main.py \
        --start-date "$current_date" \
        --end-date "$current_date"
    
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: Failed on $current_date (exit code: $exit_code)"
        echo "Continue with next day? (y/n)"
        read -r response
        if [ "$response" != "y" ]; then
            echo "Aborted by user."
            exit 1
        fi
    fi
    
    echo ""
done <<< "$available_dates"

echo "=========================================="
echo "OULU LANE DETECTION COMPLETE"
echo "=========================================="
echo "Processed: $count days"
echo "Results saved in: /home/ubuntu/results/prem/mdrac/oulu/lanes/"
echo "=========================================="
