"""
Preprocessing filters package for PREM.

Contains filters that clean and prepare raw trajectory data:
- lifetime_filter: Removes short-lived detections
- zone_assignment: Spatial zone assignment
- footpath_filter: Removes vehicles in pedestrian zones
- crosswalk_filter: Removes vehicles parallel to crosswalks
- static_filter: Removes stationary vehicles
- ghost_filter: Removes spawn/despawn artifacts (in this package now)
- overlap_filter: Removes overlapping pairs (in this package now)
"""

from .lifetime_filter import filter_by_lifetime
from .zone_assignment import attach_zones_to_objects
from .footpath_filter import apply_footpath_zone_filter
from .crosswalk_filter import compute_polygon_orientation, filter_parallel_vehicles
from .static_filter import filter_static_objects

__all__ = [
    'filter_by_lifetime',
    'attach_zones_to_objects',
    'apply_footpath_zone_filter',
    'compute_polygon_orientation',
    'filter_parallel_vehicles',
    'filter_static_objects',
]
