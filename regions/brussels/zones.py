"""
Zone definitions for Brussels intersection.

Contains lane zones, footpath zones, and crosswalk zones.
"""

def get_lane_zones():
    """
    Detection zones (lanes) for Brussels intersection.
    
    Returns:
        List of zone dicts with 'id', 'name', 'vertices' (WKT POLYGON), 'min_z', 'max_z'
    """
    return [
        {"id": "1087", "name": "A-L1", "type": "detection", 
         "vertices": "POLYGON ((-11.9 -7.698, -14.4 -9.994, -24.5 2.256, -23.2 3.466, -11.9 -7.698))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1088", "name": "A-L2", "type": "detection", 
         "vertices": "POLYGON ((-23.2 3.466, -24.48 2.232, -26.82 4.704, -28.054 6.038, -25.643 8.292, -24.386 7.024, -23.2 3.466))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1089", "name": "B-L1", "type": "detection", 
         "vertices": "POLYGON ((48.1 1.134, 33.928 13.936, 27.856 8.414, 43.002 -5.062, 48.1 1.134))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1090", "name": "B-L2", "type": "detection", 
         "vertices": "POLYGON ((18.7 -12.838, 27.856 8.414, 33.928 13.936, 45.2 6.512, 53.45 11.776, 44.55  -17.19, 18.7 -12.838))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1091", "name": "C-L1", "type": "detection", 
         "vertices": "POLYGON ((46.968 9.966, 46.292 23.066, 26.68 24.72, 27.356 21.114, 46.968 9.966))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1092", "name": "C-L2", "type": "detection", 
         "vertices": "POLYGON ((27.356 21.114, 26.68 24.72, 18.16 25.44, 11.18 25.12, 18.48 20.646, 27.356 21.114))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1095", "name": "D-L1", "type": "detection", 
         "vertices": "POLYGON ((-42.5 -22.95, -29.58 -10.37, -19.61 -19.79, -32.53 -32.37, -42.5 -22.95))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1096", "name": "D-L2", "type": "detection", 
         "vertices": "POLYGON ((-32.53 -32.37, -19.61 -19.79, -16.14 -23.09, -10.64 -28.37, -19.11 -36.45, -8.26 -47.47, -22.6 -60.91, -32.53 -32.37))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1093", "name": "E-L2", "type": "detection", 
         "vertices": "POLYGON ((7.97 14.272, 11.903 17.612, -24.514 57.166, -27.924 54.162, 7.97 14.272))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1094", "name": "E-L1", "type": "detection", 
         "vertices": "POLYGON ((-39.209 44.825, -2.024 4.96, 5.445 11.618, -9.819 28.018, -19.074 31.104, -20.536 31.997, -35.881 47.829, -39.209 44.825))", 
         "min_z": -1.5, "max_z": 3.5},
    ]


def get_footpath_zones():
    """
    Footpath/pedestrian-only zones for Brussels.
    
    Returns:
        List of footpath zone dicts
    """
    return [
        {"id":"1081","name":"FalseDetection (Vehicles as Pedestrians)","type":"analytics",
         "vertices":"POLYGON ((-8.6426068 4.1825497, -5.2591289 6.6106291, 2.4873278 -1.8810115, 3.0701297 -4.1885040, -4.8739637 -7.3121410, -5.9190415 -5.1056689, -14.9469623 -8.3614314, -15.4947729 -6.7531838, -6.4707399 -3.4197283, -5.5463181 -0.1021501, -8.6426068 4.1825497))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1082","name":"FalseDetection (Vehicle as Pedestrian)","type":"analytics",
         "vertices":"POLYGON ((-3.3894790 -13.3168241, 11.5404031 -7.8269771, 18.9154074 -17.2223685, 14.9261910 -19.9865761, 21.4404136 -27.6760383, 20.0765345 -28.6872835, 7.1069287 -14.4841637, -11.9112838 -20.7401988, -12.4875105 -18.6473010, -2.5169133 -15.3193791, -3.3894790 -13.3168241))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1083","name":"FalseDetection (Vehicles as Pedestrians)","type":"analytics",
         "vertices":"POLYGON ((65.0702212 14.5604360, 36.5624449 3.1898636, 35.8594607 -0.3697733, 48.5353798 -17.2319024, 52.8105665 -14.6263596, 49.1754262 -9.8991876, 52.2197357 2.2111523, 68.4919414 9.0673664, 65.0702212 14.5604360))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1084","name":"FalseDetection (Vehicles as Pedestrians)","type":"analytics",
         "vertices":"POLYGON ((5.9894856 29.2443364, 7.5000886 30.3643575, 15.4508444 22.7984588, 22.8276900 37.1368332, 27.9001775 34.9101554, 20.8424398 19.4127592, 17.0919999 16.0917894, 5.9894856 29.2443364))","min_z":-1.5,"max_z":3.5}
    ]


def get_crosswalk_zones():
    """
    Crosswalk/zebra crossing zones for Brussels.
    
    Returns:
        List of crosswalk zone dicts
    """
    return [
        {"id":"1015","name":"Crosswalk Houba - South","type":"analytics",
         "vertices":"POLYGON ((25.0 -23.6, 42.8 -8.5, 40.3 -5.5, 22.6 -21.0, 25.0 -23.6))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1016","name":"Crosswalk Amandiers","type":"analytics",
         "vertices":"POLYGON ((-2.7 -13.4, -4.8 -7.4, -1.4 -6.0, 0.7 -12.2, -2.7 -13.4))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1017","name":"Crosswalk Houba - North","type":"analytics",
         "vertices":"POLYGON ((-3.1 4.7, 13.8 19.3, 16.9 16.1, 0.0 1.4, -3.1 4.7))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1018","name":"Crosswalk Magnolias","type":"analytics",
         "vertices":"POLYGON ((30.5 15.5, 32.2 18.9, 23.4 23.5, 21.6 20.2, 30.5 15.5))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1019","name":"Crosswalk Charlotte [1]","type":"analytics",
         "vertices":"POLYGON ((36.4 15.3, 40.4 5.2, 37.1 3.8, 33.1 14.0, 36.4 15.3))","min_z":-1.5,"max_z":3.5}
    ]
