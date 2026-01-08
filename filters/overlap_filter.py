"""
Overlap Filter (SAT Method)

Removes vehicle pairs that are physically overlapping.

Uses Separating Axis Theorem (SAT):
- Projects vehicles onto 4 axes (2 per vehicle: longitudinal + lateral)
- If separated on ANY axis → no overlap
- Accounts for vehicle orientation (yaw angles)

More accurate than circular approximation for oriented rectangles.
"""

import pandas as pd
import numpy as np
from tqdm import tqdm

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("Warning: Numba not available for overlap filter. Install with 'pip install numba' for 100x speedup.")


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Safety buffer for sensor noise tolerance (meters)
# Allows small overlaps due to measurement uncertainty
OVERLAP_BUFFER = 0.5

# Enable detailed statistics output
VERBOSE = True


# ============================================================================
# HELPER FUNCTIONS (Numba-accelerated SAT algorithm)
# ============================================================================

# Point-in-polygon algorithm with Numba acceleration
if NUMBA_AVAILABLE:
    @jit(nopython=True, parallel=True, cache=True)
    def check_overlap_sat(pos_x1, pos_y1, yaw1, size_x1, size_y1,
                          pos_x2, pos_y2, yaw2, size_x2, size_y2, 
                          buffer=0.1):
        """
        Check vehicle overlap using Separating Axis Theorem (SAT).
        
        Projects each vehicle onto both vehicles' local axes:
        - Vehicle 1: longitudinal (along yaw1), lateral (perpendicular)
        - Vehicle 2: longitudinal (along yaw2), lateral (perpendicular)
        
        If separated on ANY axis → no overlap.
        
        Args:
            pos_x1, pos_y1: Vehicle 1 positions
            yaw1: Vehicle 1 heading angles (radians)
            size_x1, size_y1: Vehicle 1 dimensions (length × width for cars/trucks)
            pos_x2, pos_y2: Vehicle 2 positions
            yaw2: Vehicle 2 heading angles
            size_x2, size_y2: Vehicle 2 dimensions
            buffer: Safety margin in meters (default 0.1m for sensor noise)
            
        Returns:
            Boolean array: True = overlap detected
        """
        n = len(pos_x1)
        result = np.empty(n, dtype=np.bool_)
        
        for i in prange(n):
            # Relative position vector
            dx = pos_x2[i] - pos_x1[i]
            dy = pos_y2[i] - pos_y1[i]
            
            # Project onto Vehicle 1's axes
            cos1 = np.cos(yaw1[i])
            sin1 = np.sin(yaw1[i])
            
            # Longitudinal: along heading direction
            proj_long1 = abs(dx * cos1 + dy * sin1)
            # Lateral: perpendicular to heading
            proj_lat1 = abs(-dx * sin1 + dy * cos1)
            
            # Project onto Vehicle 2's axes
            cos2 = np.cos(yaw2[i])
            sin2 = np.sin(yaw2[i])
            
            proj_long2 = abs(dx * cos2 + dy * sin2)
            proj_lat2 = abs(-dx * sin2 + dy * cos2)
            
            # Minimum separation required (half-extents with buffer)
            # For cars/trucks: size_x = length, size_y = width
            min_long = (size_x1[i] + size_x2[i]) / 2 - buffer
            min_lat = (size_y1[i] + size_y2[i]) / 2 - buffer
            
            # Check if separated on any axis
            separated = (proj_long1 > min_long) or (proj_lat1 > min_lat) or \
                       (proj_long2 > min_long) or (proj_lat2 > min_lat)
            
            # Overlap if NOT separated on all axes
            result[i] = not separated
        
        return result


# ============================================================================
# MAIN FILTER FUNCTION
# ============================================================================

def filter_overlapping_pairs(
    pairs: pd.DataFrame,
    buffer: float = OVERLAP_BUFFER,
    verbose: bool = VERBOSE
) -> pd.DataFrame:
    """
    Remove physically overlapping vehicle pairs.
    
    Uses SAT method for accurate orientation-aware overlap detection.
    
    Args:
        pairs: DataFrame with columns [pos_x1, pos_y1, yaw1, size_x1, size_y1,
                                        pos_x2, pos_y2, yaw2, size_x2, size_y2]
        buffer: Safety margin in meters (default 0.1m)
        verbose: Print filtering statistics
        
    Returns:
        Filtered pairs DataFrame with overlapping pairs removed
    """
    if verbose:
        print("\n" + "="*70)
        print("OVERLAP FILTER (SAT Method)")
        print("="*70)
        print(f"Input pairs: {len(pairs):,}")
        print(f"Safety buffer: {buffer:.2f}m")
    
    if len(pairs) == 0:
        if verbose:
            print("  No pairs to filter")
            print("="*70)
        return pairs
    
    # Check required columns
    required_cols = ['pos_x1', 'pos_y1', 'yaw1', 'size_x1', 'size_y1',
                     'pos_x2', 'pos_y2', 'yaw2', 'size_x2', 'size_y2']
    missing_cols = [col for col in required_cols if col not in pairs.columns]
    
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Convert to numpy arrays for Numba
    pos_x1 = pairs['pos_x1'].values
    pos_y1 = pairs['pos_y1'].values
    yaw1 = pairs['yaw1'].values
    size_x1 = pairs['size_x1'].values
    size_y1 = pairs['size_y1'].values
    
    pos_x2 = pairs['pos_x2'].values
    pos_y2 = pairs['pos_y2'].values
    yaw2 = pairs['yaw2'].values
    size_x2 = pairs['size_x2'].values
    size_y2 = pairs['size_y2'].values
    
    # Check for overlaps
    if verbose:
        print("  Checking for overlaps (SAT method)...")
    
    if NUMBA_AVAILABLE:
        overlap_mask = check_overlap_sat(
            pos_x1, pos_y1, yaw1, size_x1, size_y1,
            pos_x2, pos_y2, yaw2, size_x2, size_y2,
            buffer
        )
    else:
        # Fallback without Numba (slower)
        overlap_mask = np.zeros(len(pairs), dtype=bool)
        for i in tqdm(range(len(pairs)), desc="Checking overlaps", disable=not verbose):
            dx = pos_x2[i] - pos_x1[i]
            dy = pos_y2[i] - pos_y1[i]
            
            cos1, sin1 = np.cos(yaw1[i]), np.sin(yaw1[i])
            proj_long1 = abs(dx * cos1 + dy * sin1)
            proj_lat1 = abs(-dx * sin1 + dy * cos1)
            
            cos2, sin2 = np.cos(yaw2[i]), np.sin(yaw2[i])
            proj_long2 = abs(dx * cos2 + dy * sin2)
            proj_lat2 = abs(-dx * sin2 + dy * cos2)
            
            min_long = (size_y1[i] + size_y2[i]) / 2 - buffer
            min_lat = (size_x1[i] + size_x2[i]) / 2 - buffer
            
            separated = (proj_long1 > min_long) or (proj_lat1 > min_lat) or \
                       (proj_long2 > min_long) or (proj_lat2 > min_lat)
            
            overlap_mask[i] = not separated
    
    # Filter out overlapping pairs
    pairs_clean = pairs[~overlap_mask].copy()
    
    if verbose:
        overlap_count = overlap_mask.sum()
        print(f"\n  Overlapping pairs detected: {overlap_count:,}")
        print(f"  Pairs after filtering: {len(pairs_clean):,}")
        print(f"  Percentage removed: {100 * overlap_count / len(pairs):.2f}%")
        print("="*70)
    
    return pairs_clean