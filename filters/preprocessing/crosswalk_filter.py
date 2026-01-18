"""
Crosswalk zone filtering - removes vehicles moving parallel to crosswalks.

Vehicles traveling along the crosswalk (not crossing it) are removed.
"""

import pandas as pd
import numpy as np


def compute_polygon_orientation(poly):
    """
    Calculate the orientation of a polygon based on its longest edge.
    Returns angle in degrees.
    """
    coords = list(poly.exterior.coords)
    edges = []

    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        dx, dy = x2 - x1, y2 - y1
        length = (dx**2 + dy**2) ** 0.5
        edges.append((length, dx, dy))

    # Get longest edge
    _, dx, dy = max(edges, key=lambda e: e[0])
    return np.degrees(np.arctan2(dy, dx))


def filter_parallel_vehicles(df_zone, orientation_deg, threshold=4.0):
    """
    Filter vehicles moving parallel to crosswalk axis.
    Vehicles traveling along the crosswalk (not crossing) are removed.
    
    Args:
        df_zone: DataFrame with objects in a single zone
        orientation_deg: Crosswalk orientation in degrees
        threshold: Maximum angle difference (degrees) to consider parallel
    
    Returns:
        parallel_ids: List of IDs to remove
        df_zone_filtered: Filtered DataFrame
    """
    # Filter all vehicle types (exclude pedestrians)
    vehicle_labels = [3, 4, 6, 7, 8]  # from motorcycle through bus except for the escooter
    vehicles = df_zone[df_zone["label"].isin(vehicle_labels)].copy()

    if vehicles.empty:
        return [], df_zone

    # Compute vehicle heading from yaw
    vehicles["heading_deg"] = np.degrees(vehicles["yaw"])

    # Fallback: use velocity direction if yaw is missing
    missing = vehicles["heading_deg"].isna()
    vehicles.loc[missing, "heading_deg"] = np.degrees(
        np.arctan2(vehicles.loc[missing, "vel_y"], vehicles.loc[missing, "vel_x"])
    )

    # Calculate angular difference
    def angle_diff(a, b):
        d = (a - b + 180) % 360 - 180
        return abs(d)

    vehicles["angle_diff"] = vehicles.apply(
        lambda r: angle_diff(r["heading_deg"], orientation_deg),
        axis=1
    )

    # Find vehicles moving parallel to crosswalk
    parallel = vehicles[vehicles["angle_diff"] < threshold]["id"].unique().tolist()

    # Remove parallel vehicles
    df_zone_filtered = df_zone[~df_zone["id"].isin(parallel)]

    return parallel, df_zone_filtered
