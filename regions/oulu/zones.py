"""
Zone definitions for Oulu pedestrian crossing.

Contains crosswalk zone (1095) and supporting zones for filtering.
"""

def get_crosswalk_zone():
    """
    Pedestrian crossing zone (zone 1095) for Oulu.
    
    Returns:
        Zone dict with 'id', 'name', 'type', 'vertices' (WKT POLYGON), 'min_z', 'max_z'
    """
    return {
        "id": "1095",
        "name": "crosswalk",
        "type": "analytics",
        "vertices": "POLYGON ((0.495 -8.313, -3.587 -8.395, -3.958 7.769, 0.082 8.016, 0.495 -8.477, 0.495 -8.313))",
        "min_z": -1.5,
        "max_z": 3.5
    }


def get_footpath_zones():
    """
    Footpath zones for filtering unwanted traffic in Oulu.
    
    Returns:
        List of footpath zone dicts
    """
    return [
        {"id": "1096", "name": "footpath", "type": "analytics",
         "vertices": "POLYGON ((6.678 -14.456, 6.501 -8.014, -9.102 -8.25, -8.806 -14.515, 6.501 -14.515, 6.678 -14.456))",
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1097", "name": "footpath2", "type": "analytics",
         "vertices": "POLYGON ((-9.938 7.329, -2.253 7.81, -0.054 8.815, 2.401 10.918, 3.509 14.038, 4.03 18.173, 3.62 21.805, -2.036 21.909, -1.972 16.083, -1.724 14.309, -10.084 14.084, -9.938 7.245, -9.938 7.329))",
         "min_z": -1.5, "max_z": 3.5}
    ]


def get_near_miss_zones():
    """
    Near-miss analysis zones (sub-zones within crossing area) for Oulu.
    
    Returns:
        List of near-miss zone dicts
    """
    return [
        {"id": "1001", "name": "crossing_1", "type": "analytics",
         "vertices": "POLYGON ((6.556 -7.752, 6.479 -1.295, -8.924 -1.684, -9.002 -8.141, 6.712 -7.83, 6.556 -7.752))",
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1002", "name": "crossing_2", "type": "analytics",
         "vertices": "POLYGON ((6.274 0.645, -9.332 0.825, -9.513 7.41, 6.093 8.222, 6.454 0.464, 6.454 0.464, 6.274 0.645))",
         "min_z": -1.5, "max_z": 3.5}
    ]


def get_exclusion_zone():
    """
    Exclusion zone for removing false detections in Oulu.
    
    Returns:
        Exclusion zone dict
    """
    return {
        "id": "1094",
        "name": "zone_094",
        "type": "exclusion",
        "vertices": "POLYGON ((-8.4336882 2.1768715, -5.2991780 2.1445578, -5.2925792 0.5711740, -8.4323510 0.6434359, -8.4336882 2.1768715))",
        "min_z": -1.5,
        "max_z": 3.5
    }
