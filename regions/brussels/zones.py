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
        
        {"id": "1078", "name": "Road Amandiers", "type": "detection", 
         "vertices": "POLYGON ((-3.647 -6.919, -1.396 -12.809, -38.802 -19.516, -40.405 -14.457, -3.647 -6.919))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1026", "name": "Road Magnolias Ext-Int", "type": "detection", 
         "vertices": "POLYGON ((25.972 23.141, 30.457 20.900, 57.356 69.179, 51.165 71.153, 25.972 23.141))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1028", "name": "Road Magnolias Int-Ext", "type": "detection", 
         "vertices": "POLYGON ((30.784 20.389, 35.741 18.109, 63.984 67.427, 57.415 69.162, 30.784 20.389))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1029", "name": "Road Charlotte Ext-Int", "type": "detection", 
         "vertices": "POLYGON ((42.237 12.467, 45.928 5.568, 91.796 15.434, 87.991 23.286, 42.237 12.467))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1030", "name": "Road Charlotte Int-Ext", "type": "detection", 
         "vertices": "POLYGON ((46.346 5.375, 48.068 0.934, 91.109 8.481, 88.941 14.666, 46.346 5.375))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1020", "name": "Road Houba South Ext-Int", "type": "detection", 
         "vertices": "POLYGON ((40.518 -24.133, 51.798 -17.563, 58.960 -25.899, 67.106 -39.482, 76.605 -50.162, 67.012 -54.701, 40.518 -24.133))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1021", "name": "Road Houba South Int-Ext [1]", "type": "detection", 
         "vertices": "POLYGON ((40.620 -24.138, 36.046 -27.110, 62.600 -58.019, 67.407 -54.967, 40.620 -24.138))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1022", "name": "Road Houba South Int-Ext [2]", "type": "detection", 
         "vertices": "POLYGON ((29.548 -30.272, 33.015 -28.519, 57.912 -59.340, 53.424 -60.689, 29.548 -30.272))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1025", "name": "Road Houba North Ext-Int", "type": "detection", 
         "vertices": "POLYGON ((7.97 14.272, 11.903 17.612, -24.514 57.166, -27.924 54.162, 7.97 14.272))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1024", "name": "Road Houba North Ext-Int", "type": "detection", 
         "vertices": "POLYGON ((-39.209 44.825, -2.024 4.96, 5.445 11.618, -9.819 28.018, -19.074 31.104, -20.536 31.997, -35.881 47.829, -39.209 44.825))", 
         "min_z": -1.5, "max_z": 3.5},
        
        {"id": "1032", "name": "Intersection", "type": "detection", 
         "vertices": "POLYGON ((0.036 1.192, 17.081 15.742, 23.737 18.842, 37.316 11.617, 43.361 -0.003, 42.225 -6.232, 46.996 -12.432, 25.739 -26.225, 11.971 -10.105, 5.848 -11.207, 1.819 -1.565, 0.036 1.192))", 
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
         "vertices":"POLYGON ((-3.727 -6.982, -5.076 -4.433, -13.627 -6.223, -14.256 -4.466, -5.848 -2.150, -5.258 0.866, -8.535 5.558, -5.705 7.394, 2.650 -2.008, 2.777 -4.907, -3.727 -6.982))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1082","name":"FalseDetection (Vehicle as Pedestrian)","type":"analytics",
         "vertices":"POLYGON ((-1.556 -12.598, -0.982 -14.856, -9.957 -16.444, -9.330 -19.119, 8.392 -16.487, 22.851 -33.628, 24.564 -32.509, 17.241 -22.672, 20.614 -20.002, 13.021 -9.722, -1.556 -12.598))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1083","name":"FalseDetection (Vehicles as Pedestrians)","type":"analytics",
         "vertices":"POLYGON ((61.859 -29.950, 69.282 -28.308, 62.568 -20.418, 65.661 -8.128, 88.467 -3.029, 81.293 6.758, 42.634 -1.345, 42.223 -6.147, 61.859 -29.950))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1084","name":"FalseDetection (Vehicles as Pedestrians)","type":"analytics",
         "vertices":"POLYGON ((5.422 32.496, 3.075 30.791, 18.284 15.316, 22.774 16.955, 32.753 35.740, 23.572 38.798, 15.635 24.862, 5.422 32.496))","min_z":-1.5,"max_z":3.5}
    ]


def get_crosswalk_zones():
    """
    Crosswalk/zebra crossing zones for Brussels.
    
    Returns:
        List of crosswalk zone dicts
    """
    return [
        {"id":"1015","name":"Crosswalk Houba - South","type":"analytics",
         "vertices":"POLYGON ((29.286 -30.339, 52.373 -17.041, 48.219 -12.569, 25.213 -25.578, 29.286 -30.339))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1016","name":"Crosswalk Amandiers","type":"analytics",
         "vertices":"POLYGON ((-1.468 -12.894, -3.672 -7.122, -0.258 -6.063, 2.236 -11.939, -1.468 -12.894))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1017","name":"Crosswalk Houba - North","type":"analytics",
         "vertices":"POLYGON ((-3.075 4.867, 14.007 19.339, 17.412 15.910, 0.338 0.920, -3.075 4.867))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1018","name":"Crosswalk Magnolias","type":"analytics",
         "vertices":"POLYGON ((34.657 13.889, 36.411 17.791, 25.996 23.306, 23.710 19.387, 34.657 13.889))","min_z":-1.5,"max_z":3.5},
        
        {"id":"1019","name":"Crosswalk Charlotte [1]","type":"analytics",
         "vertices":"POLYGON ((42.941 13.222, 49.066 0.762, 43.928 -0.541, 37.081 11.468, 42.941 13.222))","min_z":-1.5,"max_z":3.5}, 
        
        {"id":"1052","name":"Crosswalk Charlotte [2]","type":"analytics",
         "vertices":"POLYGON ((58.124 21.753, 64.969 26.481, 68.939 23.293, 62.197 18.243, 58.124 21.753))","min_z":-1.5,"max_z":3.5}
    ]
