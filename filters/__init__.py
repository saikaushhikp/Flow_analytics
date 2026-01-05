"""
Pre-processing filters for vehicle trajectory data quality.

Modules:
- ghost_filter: Remove vehicles that spawn/despawn inside detection zones
- teleportation_filter: Remove vehicles with unrealistic position jumps
- overlap_filter: Remove physically overlapping vehicle pairs (SAT method)
"""

from .ghost_filter import filter_ghost_vehicles
from .teleportation_filter import filter_teleportation_events, calibrate_threshold
from .overlap_filter import filter_overlapping_pairs

__all__ = [
    'filter_ghost_vehicles', 
    'filter_teleportation_events', 
    'calibrate_threshold',
    'filter_overlapping_pairs'
]
