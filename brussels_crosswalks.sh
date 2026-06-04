#!/bin/bash
# Brussels Crosswalk Detection - Process all days (June 1 to Dec 31, 2025)
# Usage: ./brussels_crosswalks.sh

echo "=========================================="
echo "BRUSSELS CROSSWALK DETECTION - ALL DAYS"
echo "=========================================="
echo "Date Range: 2025-06-01 to 2025-06-14"
echo "Zone: Crosswalks (Pedestrian-Vehicle Conflicts)"
echo "=========================================="
echo ""

# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate flow_env

# Date range
START_DATE="2025-06-01"
END_DATE="2025-06-14"

# Convert to date objects
current_date="$START_DATE"

# Counter
count=0
total_days=$(( ( $(date -d "$END_DATE" +%s) - $(date -d "$START_DATE" +%s) ) / 86400 + 1 ))

echo "Processing $total_days days..."
echo ""

# Loop through each day
while [ "$current_date" != $(date -I -d "$END_DATE + 1 day") ]; do
    count=$((count + 1))
    echo "=========================================="
    echo "[$count/$total_days] Processing: $current_date"
    echo "=========================================="
    
    # Run detection for this day
    python regions/brussels/crosswalk_main.py \
        --start-date "$current_date" \
        --end-date "$current_date"
    
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: Failed on $current_date (exit code: $exit_code)"
        echo "Continue? (y/n)"
        read -r response
        if [ "$response" != "y" ]; then
            echo "Aborted by user."
            exit 1
        fi
    fi
    
    echo ""
    
    # Move to next day
    current_date=$(date -I -d "$current_date + 1 day")
done

echo "=========================================="
echo "BRUSSELS CROSSWALK DETECTION COMPLETE"
echo "=========================================="
echo "Processed: $count days"
echo "Results saved in: /home/ubuntu/results/prem/mdrac/brussels/crosswalks/"
echo "=========================================="
