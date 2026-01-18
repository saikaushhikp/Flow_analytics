"""
Ghost Vehicle Filter

Removes vehicles that spawn or despawn inside the detection zone.

A vehicle is a "ghost" if:
- First position is inside zone (spawned ghost)
- Last position is inside zone (despawned ghost)

This filters out tracking errors, occlusions, and ID switches.
"""

import pandas as pd
import numpy as np
from shapely import wkt
from shapely.geometry import Point
from tqdm import tqdm

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("Warning: Numba not available for ghost filter. Install with 'pip install numba' for 10x speedup.")


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Ghost detection zone (inner area, excluding boundaries)
# Vehicles spawning/despawning inside this polygon are considered ghosts
# Updated 2026-01-07: Refined polygon to avoid catching legitimate edge entries
GHOST_ZONE_WKT = (
    "POLYGON ((-28.977 34.253, -12.788 47.989, 11.576 19.046, 19.752 15.448, "
    "39.702 53.876, 48.205 49.788, 42.809 39.649, 43.136 36.215, 55.073 21.826, "
    "71.915 27.549, 76.167 19.046, 36.104 3.675, 36.104 -2.376, 46.733 -13.168, "
    "52.457 -24.287, 58.097 -31.792, 48.598 -39.498, 31.753 -19.785, 25.122 -23.907, "
    "1.466 -11.721, -28.821 -22.652, -30.792 -17.276, 0.032 -5.986, -1.402 1.003, "
    "-28.977 34.253))"
)

# Enable detailed statistics output
VERBOSE = True


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Point-in-polygon algorithm with Numba acceleration
if NUMBA_AVAILABLE:
    @jit(nopython=True, cache=True)
    def point_in_polygon(x, y, poly_coords):
        """Fast point-in-polygon using ray casting algorithm."""
        n = len(poly_coords) - 1
        inside = False
        p1x, p1y = poly_coords[0]
        for i in range(1, n + 1):
            p2x, p2y = poly_coords[i]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    @jit(nopython=True, parallel=True, cache=True)
    def check_positions_parallel(first_x, first_y, last_x, last_y, poly_coords):
        """Parallel check if first or last position is inside polygon."""
        n = len(first_x)
        result = np.empty(n, dtype=np.bool_)
        
        # Parallel loop - each vehicle checked independently
        for i in prange(n):
            # Inline point-in-polygon for first position
            spawned = point_in_polygon(first_x[i], first_y[i], poly_coords)
            # Inline point-in-polygon for last position
            despawned = point_in_polygon(last_x[i], last_y[i], poly_coords)
            result[i] = spawned or despawned
        
        return result


def check_ghost_positions(first_x, first_y, last_x, last_y, poly_coords):
    """Check ghost positions - uses Numba parallel if available, else Shapely."""
    if NUMBA_AVAILABLE:
        return check_positions_parallel(first_x, first_y, last_x, last_y, poly_coords)
    else:
        # Fallback to Shapely
        from shapely.geometry import Polygon
        poly = Polygon(poly_coords)
        result = np.zeros(len(first_x), dtype=bool)
        for i in range(len(first_x)):
            spawned = poly.contains(Point(first_x[i], first_y[i]))
            despawned = poly.contains(Point(last_x[i], last_y[i]))
            result[i] = spawned or despawned
        return result


def filter_ghost_vehicles(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Remove ghost vehicles that spawn or despawn inside the detection zone. A vehicle is considered a ghost if:
    1. Its first position is inside the inner zone (spawned ghost)
    2. Its last position is inside the inner zone (despawned ghost)
    
    Args:
        df: DataFrame with columns [id, timestamp, pos_x, pos_y]
        verbose: Print filtering statistics
        
    Returns:
        DataFrame with ghost vehicles removed
    """
    if verbose:
        print("\n" + "="*70)
        print("GHOST VEHICLE FILTER")
        print("="*70)
        print(f"Input vehicles: {df['id'].nunique():,}")
    
    # Parse ghost detection zone
    ghost_zone = wkt.loads(GHOST_ZONE_WKT)
    
    # Get chronologically first and last positions WITHOUT full sort (efficient!)
    # Method: Find min/max timestamp indices per vehicle, then extract positions
    
    # Get indices of min and max timestamps per vehicle
    first_idx = df.groupby('id')['timestamp'].idxmin()
    last_idx = df.groupby('id')['timestamp'].idxmax()
    
    # Extract positions at those indices
    first_positions = df.loc[first_idx, ['id', 'pos_x', 'pos_y', 'timestamp']].reset_index(drop=True)
    first_positions.columns = ['id', 'first_x', 'first_y', 'first_timestamp']
    
    last_positions = df.loc[last_idx, ['id', 'pos_x', 'pos_y', 'timestamp']].reset_index(drop=True)
    last_positions.columns = ['id', 'last_x', 'last_y', 'last_timestamp']
    
    # Merge first and last positions
    positions = pd.merge(first_positions, last_positions, on='id')
    
    # Check if positions are inside ghost zone (vectorized with Numba if available)
    if verbose:
        print("Checking spawn/despawn locations...")
    
    # Extract polygon coordinates once
    ghost_coords = np.array(ghost_zone.exterior.coords)
    
    # Convert positions to numpy arrays for faster processing
    first_x = positions['first_x'].values
    first_y = positions['first_y'].values
    last_x = positions['last_x'].values
    last_y = positions['last_y'].values
    vehicle_ids = positions['id'].values
    
    # Check point-in-polygon for all positions (with progress bar)
    desc = f"Checking {len(vehicle_ids):,} vehicles" if verbose else None
    with tqdm(total=len(vehicle_ids), desc=desc, disable=not verbose, unit='vehicle') as pbar:
        ghost_flags = check_ghost_positions(first_x, first_y, last_x, last_y, ghost_coords)
        pbar.update(len(vehicle_ids))
    
    # Get IDs of ghost vehicles
    ghost_ids = set(vehicle_ids[ghost_flags])
    
    # Detailed statistics (if verbose)
    if verbose:
        print(f"\n  Ghost vehicles detected: {len(ghost_ids):,}")
        
        if len(ghost_ids) > 0:
            # Get breakdown using vectorized operations
            ghost_positions = positions[positions['id'].isin(ghost_ids)]
            
            spawned_flags = np.array([point_in_polygon(x, y, ghost_coords) if NUMBA_AVAILABLE 
                                     else ghost_zone.contains(Point(x, y))
                                     for x, y in zip(ghost_positions['first_x'], ghost_positions['first_y'])])
            despawned_flags = np.array([point_in_polygon(x, y, ghost_coords) if NUMBA_AVAILABLE 
                                       else ghost_zone.contains(Point(x, y))
                                       for x, y in zip(ghost_positions['last_x'], ghost_positions['last_y'])])
            
            both_count = (spawned_flags & despawned_flags).sum()
            spawned_only = (spawned_flags & ~despawned_flags).sum()
            despawned_only = (~spawned_flags & despawned_flags).sum()
            
            print(f"  - Breakdown:")
            print(f"    Spawned inside: {spawned_only:,}")
            print(f"    Despawned inside: {despawned_only:,}")
            print(f"    Both (full ghosts): {both_count:,}")
    
    # Filter out ghost vehicles
    df_clean = df[~df['id'].isin(ghost_ids)].copy()
    
    if verbose:
        print(f"\n  Vehicles after filtering: {df_clean['id'].nunique():,}")
        print(f"  Records removed: {len(df) - len(df_clean):,}")
        print(f"  Percentage removed: {100 * (1 - len(df_clean)/len(df)):.2f}%")
        print("="*70)
    
    return df_clean