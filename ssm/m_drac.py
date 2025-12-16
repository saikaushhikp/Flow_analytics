"""
Modified DRAC (M-DRAC) Near-Miss Detection Module

Based on: Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015)
"How Does the Driver's Perception Reaction Time Affect the Performances of Crash Surrogate Measures?"
PLOS ONE 10(9): e0138617
https://doi.org/10.1371/journal.pone.0138617

Formulas:
---------
TTC = D / (V_F - V_L)                           # Time to Collision
DRAC = (V_F - V_L)² / (2D)                      # Standard DRAC (distance-based)
MDRAC = (V_F - V_L) / [2 × (TTC - R)]           # Modified DRAC (time-based, with PRT)

Where:
- V_F = velocity of following vehicle (m/s)
- V_L = velocity of leading vehicle/pedestrian (m/s)
- D = distance gap between vehicles (meters)
- R = Perception-Reaction Time (PRT) of driver (seconds)
- TTC = Time to Collision (seconds)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import gc


# =============================================================================
# CONFIGURATION - Modify these values as needed
# =============================================================================

MDRAC_CONFIG = {
    # Perception-Reaction Time (PRT) by vehicle label (seconds)
    # Source: Triggs and Harris - 0.92s mean for rear-end situations
    'prt': {
        3: 0.92,    # motorcycle (same as car)
        4: 0.92,    # car - from paper (Triggs and Harris)
        6: 1.5,     # van - heavy vehicle adjustment
        7: 2.0,     # truck - heavy vehicle adjustment
        8: 2.0,     # bus - heavy vehicle adjustment
    },
    
    # DRAC thresholds by vehicle label (m/s²)
    # Source: AASHTO recommends 3.4 m/s² for comfortable braking
    'threshold': {
        3: 3.4,     # motorcycle - AASHTO standard
        4: 3.4,     # car - AASHTO standard
        6: 3.0,     # van - heavier, less maneuverable
        7: 2.0,     # truck - much heavier, longer braking
        8: 2.0,     # bus - much heavier, longer braking
    },
    
    # Detection parameters
    'max_distance': 15.0,           # meters - max distance to check for conflicts
    'min_speed_diff': 0.5,          # m/s - minimum (V_F - V_L) to consider
    'min_vehicle_speed': 1.0,       # m/s - minimum vehicle speed to consider
    
    # Object labels
    'pedestrian_label': 1,
    'vehicle_labels': [3, 4, 6, 7, 8],  # motorcycle, car, van, truck, bus
    
    # Processing
    'chunk_size': 50000,
}


# =============================================================================
# MDRAC DETECTOR CLASS
# =============================================================================

class ModifiedDRACDetector:
    """
    Modified DRAC (M-DRAC) Near-Miss Detection
    
    Based on Kuang et al. (2015) PLOS ONE paper.
    Accounts for driver's Perception-Reaction Time (PRT) in crash mechanism.
    
    Key formula:
        MDRAC = (V_F - V_L) / [2 × (TTC - R)]
        
    Critical condition:
        If TTC ≤ R: Collision unavoidable (driver has no reaction time)
    """
    
    # Label names for output
    LABEL_NAMES = {
        1: 'pedestrian',
        2: 'bicycle', 
        3: 'motorcycle',
        4: 'car',
        5: 'escooter',
        6: 'van',
        7: 'truck',
        8: 'bus'
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize MDRAC detector.
        
        Args:
            config: Optional custom configuration dict. 
                    Uses MDRAC_CONFIG defaults if not provided.
        """
        self.config = config if config is not None else MDRAC_CONFIG.copy()
        
        # Extract config values for quick access
        self.prt_map = self.config['prt']
        self.threshold_map = self.config['threshold']
        self.max_distance = self.config['max_distance']
        self.min_speed_diff = self.config['min_speed_diff']
        self.min_vehicle_speed = self.config['min_vehicle_speed']
        self.pedestrian_label = self.config['pedestrian_label']
        self.vehicle_labels = self.config['vehicle_labels']
        self.chunk_size = self.config['chunk_size']
    
    # -------------------------------------------------------------------------
    # Core Calculation Methods
    # -------------------------------------------------------------------------
    
    def calculate_ttc(self, v_following: np.ndarray, v_leading: np.ndarray, 
                      distance: np.ndarray) -> np.ndarray:
        """
        Calculate Time to Collision (TTC).
        
        Formula: TTC = D / (V_F - V_L)
        
        Args:
            v_following: Velocity of following vehicle (m/s)
            v_leading: Velocity of leading vehicle/pedestrian (m/s)
            distance: Distance between them (meters)
            
        Returns:
            TTC values (seconds). Returns inf where V_F <= V_L.
        """
        speed_diff = v_following - v_leading
        
        # Avoid division by zero - return inf where not closing in
        ttc = np.where(
            speed_diff > self.min_speed_diff,
            distance / speed_diff,
            np.inf
        )
        return ttc
    
    def calculate_drac(self, v_following: np.ndarray, v_leading: np.ndarray,
                       distance: np.ndarray) -> np.ndarray:
        """
        Calculate standard DRAC (distance-based).
        
        Formula: DRAC = (V_F - V_L)² / (2D)
        
        Args:
            v_following: Velocity of following vehicle (m/s)
            v_leading: Velocity of leading vehicle/pedestrian (m/s)
            distance: Distance between them (meters)
            
        Returns:
            DRAC values (m/s²). Returns 0 where not applicable.
        """
        speed_diff = v_following - v_leading
        
        # Avoid division by zero for very small distances
        drac = np.where(
            (speed_diff > self.min_speed_diff) & (distance > 0.5),
            (speed_diff ** 2) / (2 * distance),
            0.0
        )
        return drac
    
    def calculate_mdrac(self, v_following: np.ndarray, v_leading: np.ndarray,
                        ttc: np.ndarray, prt: np.ndarray) -> np.ndarray:
        """
        Calculate Modified DRAC (time-based, with PRT).
        
        Formula: MDRAC = (V_F - V_L) / [2 × (TTC - R)]
        
        Note: Uses LINEAR speed difference, not squared!
              This ensures result is in m/s² (deceleration), not m²/s³ (jerk).
        
        Args:
            v_following: Velocity of following vehicle (m/s)
            v_leading: Velocity of leading vehicle/pedestrian (m/s)
            ttc: Time to Collision (seconds)
            prt: Perception-Reaction Time (seconds)
            
        Returns:
            MDRAC values (m/s²). Returns inf where TTC <= PRT (critical).
        """
        speed_diff = v_following - v_leading
        time_available = ttc - prt
        
        # Where TTC <= PRT, driver has no time to react -> critical (return inf)
        # Otherwise, calculate MDRAC
        mdrac = np.where(
            time_available > 0,
            speed_diff / (2 * time_available),
            np.inf  # Critical: no reaction time available
        )
        return mdrac
    
    def classify_severity(self, ttc: np.ndarray, mdrac: np.ndarray,
                          prt: np.ndarray, threshold: np.ndarray) -> np.ndarray:
        """
        Classify conflict severity based on TTC, MDRAC, and thresholds.
        
        Severity Levels:
        - CRITICAL: TTC ≤ PRT (no reaction time, collision unavoidable)
        - SERIOUS: MDRAC ≥ 6.0 m/s² (emergency braking)
        - MODERATE: MDRAC ≥ threshold (hard braking needed)
        - LOW: 1.5 ≤ MDRAC < threshold (noticeable braking)
        - NONE: MDRAC < 1.5 m/s² (comfortable situation)
        
        Args:
            ttc: Time to Collision (seconds)
            mdrac: Modified DRAC value (m/s²)
            prt: Perception-Reaction Time (seconds)
            threshold: DRAC threshold for this vehicle type (m/s²)
            
        Returns:
            Array of severity labels
        """
        severity = np.full(len(ttc), 'none', dtype=object)
        
        # LOW: 1.5 ≤ MDRAC < threshold
        severity = np.where(
            (mdrac >= 1.5) & (mdrac < threshold),
            'low', severity
        )
        
        # MODERATE: MDRAC ≥ threshold and < 6.0
        severity = np.where(
            (mdrac >= threshold) & (mdrac < 6.0),
            'moderate', severity
        )
        
        # SERIOUS: MDRAC ≥ 6.0 m/s²
        severity = np.where(
            (mdrac >= 6.0) & (ttc > prt),
            'serious', severity
        )
        
        # CRITICAL: TTC ≤ PRT (no reaction time)
        severity = np.where(
            ttc <= prt,
            'critical', severity
        )
        
        return severity
    
    # -------------------------------------------------------------------------
    # Main Detection Methods
    # -------------------------------------------------------------------------
    
    def detect_conflicts(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect pedestrian-vehicle conflicts using MDRAC.
        
        Args:
            df: DataFrame with columns: timestamp, id, label, pos_x, pos_y, 
                vel, vel_x, vel_y, and optionally 'zone'
                
        Returns:
            DataFrame with detected conflicts and MDRAC metrics
        """
        # Separate pedestrians and vehicles
        pedestrians = df[df['label'] == self.pedestrian_label].copy()
        vehicles = df[df['label'].isin(self.vehicle_labels)].copy()
        
        if len(pedestrians) == 0 or len(vehicles) == 0:
            return self._empty_result_dataframe()
        
        # Filter vehicles by minimum speed
        vehicles = vehicles[vehicles['vel'] >= self.min_vehicle_speed]
        
        if len(vehicles) == 0:
            return self._empty_result_dataframe()
        
        # Create pairs by timestamp using merge
        pedestrians['_merge_key'] = 1
        vehicles['_merge_key'] = 1
        
        pairs = pd.merge(
            vehicles,
            pedestrians,
            on=['timestamp', '_merge_key'],
            suffixes=('_veh', '_ped')
        ).drop('_merge_key', axis=1)
        
        if len(pairs) == 0:
            return self._empty_result_dataframe()
        
        # Calculate distance between pairs
        pairs['distance'] = np.sqrt(
            (pairs['pos_x_veh'] - pairs['pos_x_ped'])**2 +
            (pairs['pos_y_veh'] - pairs['pos_y_ped'])**2
        )
        
        # Filter by distance
        pairs = pairs[
            (pairs['distance'] > 0.5) & 
            (pairs['distance'] <= self.max_distance)
        ]
        
        if len(pairs) == 0:
            return self._empty_result_dataframe()
        
        # Get PRT and threshold for each vehicle type
        pairs['prt'] = pairs['label_veh'].map(self.prt_map).fillna(0.92)
        pairs['threshold'] = pairs['label_veh'].map(self.threshold_map).fillna(3.4)
        
        # Calculate metrics
        v_following = pairs['vel_veh'].values
        v_leading = pairs['vel_ped'].values
        distance = pairs['distance'].values
        prt = pairs['prt'].values
        threshold = pairs['threshold'].values
        
        # TTC, DRAC, MDRAC
        ttc = self.calculate_ttc(v_following, v_leading, distance)
        drac = self.calculate_drac(v_following, v_leading, distance)
        mdrac = self.calculate_mdrac(v_following, v_leading, ttc, prt)
        
        # Severity classification
        severity = self.classify_severity(ttc, mdrac, prt, threshold)
        
        # Add results to pairs
        pairs['ttc'] = ttc
        pairs['drac'] = drac
        pairs['mdrac'] = mdrac
        pairs['severity'] = severity
        
        # Filter: Keep only conflicts (MDRAC >= 1.5 or TTC <= PRT)
        conflicts = pairs[
            (pairs['mdrac'] >= 1.5) | 
            (pairs['ttc'] <= pairs['prt'])
        ].copy()
        
        if len(conflicts) == 0:
            return self._empty_result_dataframe()
        
        # Create output dataframe
        result = self._format_output(conflicts)
        
        # Cleanup
        del pairs, conflicts
        gc.collect()
        
        return result
    
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process entire dataframe in chunks for memory efficiency.
        
        Args:
            df: Full dataset DataFrame
            
        Returns:
            DataFrame with all detected conflicts
        """
        print(f"Processing {len(df):,} records...")
        print(f"Unique timestamps: {df['timestamp'].nunique():,}")
        
        unique_timestamps = df['timestamp'].unique()
        total_timestamps = len(unique_timestamps)
        
        all_results = []
        
        for chunk_start in range(0, total_timestamps, self.chunk_size):
            chunk_end = min(chunk_start + self.chunk_size, total_timestamps)
            timestamp_chunk = unique_timestamps[chunk_start:chunk_end]
            
            print(f"  Processing timestamps {chunk_start+1}-{chunk_end} of {total_timestamps}...", end='\r')
            
            chunk_df = df[df['timestamp'].isin(timestamp_chunk)]
            chunk_results = self.detect_conflicts(chunk_df)
            
            if len(chunk_results) > 0:
                all_results.append(chunk_results)
            
            # Cleanup
            del chunk_df
            gc.collect()
        
        print()  # New line after progress
        
        if all_results:
            result_df = pd.concat(all_results, ignore_index=True)
            print(f"✓ Detected {len(result_df):,} conflict events")
            
            # Severity summary
            print(f"  Severity distribution: {result_df['severity'].value_counts().to_dict()}")
            
            return result_df
        else:
            print("✓ No conflicts detected")
            return self._empty_result_dataframe()
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _format_output(self, conflicts: pd.DataFrame) -> pd.DataFrame:
        """Format conflict data into standard output schema."""
        
        # Get zone if available
        if 'zone_veh' in conflicts.columns:
            zone = conflicts['zone_veh']
        elif 'zone_ped' in conflicts.columns:
            zone = conflicts['zone_ped']
        elif 'zone' in conflicts.columns:
            zone = conflicts['zone']
        else:
            zone = pd.Series(['unknown'] * len(conflicts))
        
        # Create object pair labels
        veh_names = conflicts['label_veh'].map(self.LABEL_NAMES)
        pair_labels = 'pedestrian-' + veh_names.astype(str)
        
        result = pd.DataFrame({
            'timestamp': conflicts['timestamp'],
            'zone': zone,
            'id_following': conflicts['id_veh'],
            'id_leading': conflicts['id_ped'],
            'label_following': conflicts['label_veh'],
            'label_leading': conflicts['label_ped'],
            'object_pair_labels': pair_labels,
            'pos_x_following': conflicts['pos_x_veh'],
            'pos_y_following': conflicts['pos_y_veh'],
            'pos_x_leading': conflicts['pos_x_ped'],
            'pos_y_leading': conflicts['pos_y_ped'],
            'vel_following': conflicts['vel_veh'],
            'vel_leading': conflicts['vel_ped'],
            'distance': conflicts['distance'],
            'ttc': conflicts['ttc'],
            'drac': conflicts['drac'],
            'mdrac': conflicts['mdrac'],
            'prt': conflicts['prt'],
            'threshold': conflicts['threshold'],
            'severity': conflicts['severity'],
        })
        
        return result
    
    def _empty_result_dataframe(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(columns=[
            'timestamp', 'zone', 'id_following', 'id_leading',
            'label_following', 'label_leading', 'object_pair_labels',
            'pos_x_following', 'pos_y_following', 
            'pos_x_leading', 'pos_y_leading',
            'vel_following', 'vel_leading', 'distance',
            'ttc', 'drac', 'mdrac', 'prt', 'threshold', 'severity'
        ])


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MDRAC Module - Formula Verification")
    print("=" * 60)
    
    # Test case: Vehicle at 10 m/s, pedestrian at 1 m/s, distance 15m
    v_f = 10.0  # m/s
    v_l = 1.0   # m/s
    d = 15.0    # m
    r = 0.92    # s (PRT for cars)
    
    detector = ModifiedDRACDetector()
    
    # Calculate TTC
    ttc = d / (v_f - v_l)
    print(f"\nTest Case:")
    print(f"  V_following = {v_f} m/s")
    print(f"  V_leading = {v_l} m/s") 
    print(f"  Distance = {d} m")
    print(f"  PRT = {r} s")
    
    print(f"\nResults:")
    print(f"  TTC = {ttc:.2f} s")
    
    # Standard DRAC
    drac = (v_f - v_l)**2 / (2 * d)
    print(f"  DRAC = {drac:.2f} m/s²")
    
    # MDRAC (corrected formula - no square on numerator!)
    mdrac = (v_f - v_l) / (2 * (ttc - r))
    print(f"  MDRAC = {mdrac:.2f} m/s²")
    
    print(f"\nDimensional Analysis:")
    print(f"  DRAC: (m/s)² / m = m/s² ✓")
    print(f"  MDRAC: (m/s) / s = m/s² ✓")
    
    print("\n" + "=" * 60)
