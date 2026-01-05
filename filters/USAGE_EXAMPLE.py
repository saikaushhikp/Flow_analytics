"""
Usage Example: Pre-processing Filters for base_v2.ipynb

Add this cell after zone assignment and before pair generation in base_v2.ipynb
"""

# =============================================================================
# PRE-PROCESSING FILTERS
# =============================================================================

# Import filters
import sys
sys.path.append('/home/ubuntu/prem')
from filters import filter_ghost_vehicles, filter_teleportation_events, calibrate_threshold

print("\n" + "="*70)
print("PRE-PROCESSING: DATA QUALITY FILTERS")
print("="*70)

log_memory("Before filters")

# Optional: Calibrate teleportation threshold from your data
# This analyzes the jump distance distribution and recommends optimal threshold
# Run this ONCE to find the best threshold, then use that value
# recommended_threshold = calibrate_threshold(df, sampling_rate=10.0, verbose=True)

# Step 1: Ghost Vehicle Filter
# Remove vehicles that spawn/despawn inside detection zone
df = filter_ghost_vehicles(df, verbose=True)

# Step 2: Teleportation Filter  
# Remove vehicles with unrealistic position jumps
# Use recommended_threshold from calibration, or default 3.5m (126 km/h at 10Hz)
df = filter_teleportation_events(df, max_jump=3.5, sampling_rate=10.0, verbose=True)

log_memory("After filters")

print("\n" + "="*70)
print(f"Final dataset: {len(df):,} records, {df['id'].nunique():,} vehicles")
print("="*70)

# =============================================================================
# CALIBRATION WORKFLOW (Optional - Run Once)
# =============================================================================
# 
# Step 1: Run calibration to find optimal threshold
#   recommended = calibrate_threshold(df, sampling_rate=10.0, verbose=True)
#   # Output: 99.5th percentile threshold
# 
# Step 2: Apply filter with calibrated threshold
#   df = filter_teleportation_events(df, max_jump=recommended, verbose=True)
# 
# Expected calibration output:
# - Mean jump: ~0.5-1.0 m (normal vehicle movement)
# - 99.5%: ~2.5-3.5 m (recommended threshold)
# - 99.9%: ~5-10 m (extreme cases, likely errors)
#
