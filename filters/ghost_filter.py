"""
Ghost Vehicle Filter

Removes vehicles that spawn/despawn inside the detection zone rather than 
entering/exiting through boundaries (tracking errors, occlusions, ID switches).
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
    print("Warning: Numba not available. Install with 'pip install numba' for 10x speedup.")


# Ghost detection zone (inner area, excluding boundaries)
GHOST_ZONE_WKT = (
    "POLYGON ((-32.631 37.697, -18.294 50.062, 11.992 17.804, 20.595 15.833, "
    "40.129 54.363, 48.552 49.883, 42.817 39.13, 43.354 35.905, 55.182 21.747, "
    "74.179 28.378, 78.659 20.492, 36.186 3.288, 36.186 -1.909, 46.58 -12.841, "
    "52.136 -23.594, 74 -49.4, 64.86 -55.493, 31.706 -19.472, 0.881 -11.586, "
    "-34.065 -24.848, -36.215 -19.83, -0.552 -6.568, 3.032 -5.852, 0.881 0.242, "
    "-32.631 37.697))"
)


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


def visualize_ghost_zone(save_path=None):
    """
    Visualize the ghost detection zone.
    
    Args:
        save_path: If provided, saves figure to this path instead of displaying
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MPLPolygon
        
        ghost_zone = wkt.loads(GHOST_ZONE_WKT)
        coords = list(ghost_zone.exterior.coords)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        polygon = MPLPolygon(coords, fill=True, alpha=0.3, color='red',
                            edgecolor='darkred', linewidth=2)
        ax.add_patch(polygon)
        
        # Plot zone boundary
        x_coords, y_coords = zip(*coords)
        ax.plot(x_coords, y_coords, 'r-', linewidth=2, label='Ghost Detection Zone')
        
        ax.set_xlabel('X Position (m)', fontsize=12)
        ax.set_ylabel('Y Position (m)', fontsize=12)
        ax.set_title('Ghost Vehicle Detection Zone (Inner Area)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.axis('equal')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Figure saved to: {save_path}")
        else:
            plt.show(block=True)  # block=True ensures plot stays open
        
        return fig
        
    except ImportError:
        print("Matplotlib not available. Install with: pip install matplotlib")
        return None


# Testing
if __name__ == "__main__":
    # Test with dummy data
    print("Testing Ghost Filter...")
    
    # Create test data with ghost vehicles
    test_data = {
        'id': [1, 1, 1, 2, 2, 2, 3, 3, 3],
        'timestamp': [0, 1, 2, 0, 1, 2, 0, 1, 2],
        'pos_x': [
            -40, -35, -30,  # Vehicle 1: enters from outside (OK)
            10, 15, 80,     # Vehicle 2: spawns inside, exits outside (GHOST)
            20, 25, 30      # Vehicle 3: enters and exits inside (FULL GHOST)
        ],
        'pos_y': [
            40, 35, 30,
            20, 18, 25,
            20, 18, 16
        ]
    }
    
    df_test = pd.DataFrame(test_data)
    print(f"\nTest data: {len(df_test)} records, {df_test['id'].nunique()} vehicles")
    
    # Apply filter
    df_filtered = filter_ghost_vehicles(df_test, verbose=True)
    visualize_ghost_zone('ghost_zone')
    print(f"\nExpected: Vehicle 1 kept, Vehicles 2 & 3 removed")
    print(f"Actual: {df_filtered['id'].nunique()} vehicle(s) remaining")
    print(f"Vehicle IDs kept: {sorted(df_filtered['id'].unique())}")
