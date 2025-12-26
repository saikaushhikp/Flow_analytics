"""
Modified DRAC (M-DRAC) Near-Miss Detection Module

Implements MDRAC for longitudinal car-following conflicts.

Reference:
    Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015)
    "How Does the Driver's Perception Reaction Time Affect the Performances of 
    Crash Surrogate Measures?" PLOS ONE 10(9): e0138617

Formula:
    MDRAC = closing_speed / [2 × (TTC - PRT)]

Where:
    closing_speed = rate of gap closure (m/s)
    TTC = Time to Collision (seconds)
    PRT = Perception-Reaction Time (seconds)

Critical Condition:
    If TTC ≤ PRT: MDRAC = ∞ (no time to react)
"""

import pandas as pd
import numpy as np
from typing import Optional
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ssm.utils import get_mdrac_pairs, load_config


class ModifiedDRAC:
    """
    M-DRAC detector for longitudinal car-following conflicts.
    
    Uses pairs pre-filtered by utils.get_mdrac_pairs() with leader/follower
    already identified. This class focuses only on MDRAC calculation and
    severity classification.
    """
    
    # Label mappings for human-readable output
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
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize M-DRAC detector with configuration.
        
        Args:
            config: Configuration dictionary (loads from CONFIG_PATH if None)
        """
        if config is None:
            config = load_config()
        
        self.config = config
        self.prt = config['mdrac']['prt']                       # Perception-Reaction Time by vehicle type
        self.min_mdrac = config['mdrac']['min_mdrac']           # Minimum threshold for detection
        self.severity_thresholds = config['mdrac']['severity']  # Severity classification
    
    def detect(self, data: pd.DataFrame, is_pairs_data: bool = False) -> pd.DataFrame:
        """
        Main detection pipeline for MDRAC conflicts.
        
        Pipeline:
            1. Get filtered pairs (same-lane, car-following) - SKIPPED if is_pairs_data=True
            2. Calculate MDRAC values
            3. Filter by minimum threshold
            4. Classify severity
            5. Format output
        
        Args:
            data: Vehicle data (id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel, yaw)
                  OR pre-filtered pairs DataFrame (timestamp, id1, id2, pos_x1, vel_x1, ...)
            is_pairs_data: If True, data is already pairs (skip pair generation).
                          If False, data is vehicle data (default - backward compatible).
                
        Returns:
            DataFrame with columns: timestamp, pair_id, zone, conflict_type, interaction,
            distance, ttc, closing_speed, speed_diff, mdrac, severity
            
        Usage:
            # Traditional (generates pairs internally):
            conflicts = detector.detect(vehicle_df)
            
            # Optimized (reuse base pairs):
            pairs = get_mdrac_pairs(vehicle_df, config)
            conflicts = detector.detect(pairs, is_pairs_data=True)
        """
        # Step 1: Get MDRAC-specific pairs (with skip flag)
        pairs = get_mdrac_pairs(data, self.config, skip_pair_generation=is_pairs_data)
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 2: Calculate MDRAC
        pairs = self.calculate_mdrac(pairs)
        
        # Step 3: Filter by minimum threshold
        pairs = pairs[pairs['mdrac'] >= self.min_mdrac]
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 4: Classify severity
        pairs = self.classify_severity(pairs)
        
        # Step 5: Format output
        return self.format_output(pairs)
    
    def calculate_mdrac(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate MDRAC for each pair.
        
        Uses follower's Perception-Reaction Time for calculation.
        
        Formula:
            MDRAC = closing_speed / [2 × (TTC - PRT)]
        
        Special cases:
            - TTC ≤ PRT: MDRAC = ∞ (critical, no reaction time)
            - TTC > PRT: Normal calculation
                
        Args:
            pairs: DataFrame with leader/follower identified
            
        Returns:
            DataFrame with mdrac and prt_used columns
        """
        # Get follower's label for each pair
        follower_label = np.where(
            pairs['is_veh1_follower'],
            pairs['label1'],
            pairs['label2']
        )
        
        # Lookup PRT for follower's vehicle type
        prt_values = np.array([self.prt.get(label, 1.0) for label in follower_label])
        
        # Time available for reaction
        time_available = pairs['ttc'].values - prt_values
        
        # MDRAC formula
        mdrac = np.where(
            time_available > 0,
            pairs['closing_speed'].values / (2 * time_available),
            np.inf  # Critical: no time to react
        )
        
        pairs = pairs.copy()
        pairs['mdrac'] = mdrac
        pairs['prt_used'] = prt_values
        
        return pairs
    
    def classify_severity(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Classify severity based on MDRAC value.
        
        Thresholds (from config):
            - normal: min_mdrac ≤ mdrac < moderate (typically ≥ 3.4 m/s²)
            - moderate: moderate ≤ mdrac < severe (typically ≥ 5.0 m/s²)
            - severe: severe ≤ mdrac < ∞ (typically ≥ 7.0 m/s²)
            - critical: mdrac = ∞ (TTC ≤ PRT, unavoidable)
        
        Args:
            pairs: DataFrame with mdrac column
            
        Returns:
            DataFrame with severity column
        """
        severity = np.full(len(pairs), 'normal', dtype=object)
        
        # Apply thresholds in ascending order
        severity = np.where(
            pairs['mdrac'] >= self.severity_thresholds['moderate'],
            'moderate',
            severity
        )
        
        severity = np.where(
            pairs['mdrac'] >= self.severity_thresholds['severe'],
            'severe',
            severity
        )
        
        severity = np.where(
            np.isinf(pairs['mdrac']),
            'critical',
            severity
        )
        
        pairs = pairs.copy()
        pairs['severity'] = severity
        
        return pairs
    
    def format_output(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Format final output with clean schema.
        
        Schema: timestamp, id1, id2, [label1]_v_[label2], leader, dist, TTC, MDRAC, 
                closing_speed, speed_diff, yaw_diff, link
        
        Args:
            pairs: DataFrame with all calculated values
            
        Returns:
            DataFrame with simplified schema for analysis
        """
        # Determine leader ID
        leader_id = np.where(
            pairs['is_veh1_follower'],
            pairs['id2'],  # veh2 is leader
            pairs['id1']   # veh1 is leader
        )
        
        # Get label names
        label1_names = pd.Series(pairs['label1'].values).map(self.LABEL_NAMES).fillna(pairs['label1'].astype(str))
        label2_names = pd.Series(pairs['label2'].values).map(self.LABEL_NAMES).fillna(pairs['label2'].astype(str))
        interaction = label1_names + '_v_' + label2_names
        
        # Calculate yaw difference (absolute)
        yaw_diff = np.abs(pairs['yaw1'].values - pairs['yaw2'].values)
        # Normalize to [0, pi]
        yaw_diff = np.where(yaw_diff > np.pi, 2*np.pi - yaw_diff, yaw_diff)
        yaw_diff = np.degrees(yaw_diff)  # Convert to degrees
        
        # Generate replay links
        # Format: https://di-india-collab.flow-analytics.io/tools/replay/{date}T{time-10s}Z
        timestamps = pd.to_datetime(pairs['timestamp'])
        replay_times = timestamps - pd.Timedelta(seconds=10)
        links = replay_times.apply(lambda t: f"https://di-india-collab.flow-analytics.io/tools/replay/{t.strftime('%Y-%m-%d')}T{t.strftime('%H:%M:%S')}Z")
        
        # Build output DataFrame
        output = pd.DataFrame({
            'timestamp': pairs['timestamp'].values,
            'id1': pairs['id1'].values,
            'id2': pairs['id2'].values,
            'interaction': interaction.values,
            'leader': leader_id,
            'dist': pairs['distance'].values,
            'TTC': pairs['ttc'].values,
            'MDRAC': pairs['mdrac'].values,
            'closing_speed': pairs['closing_speed'].values,
            'speed_diff': pairs['speed_diff'].values,
            'yaw_diff': yaw_diff,
            'link': links.values
        })
        
        return output
    
    def _empty_output(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(columns=[
            'timestamp', 'id1', 'id2', 'interaction', 'leader', 'dist', 'TTC', 
            'MDRAC', 'closing_speed', 'speed_diff', 'yaw_diff', 'link'
        ])


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Load configuration
    config = load_config('config.yaml')
    
    # Initialize detector
    detector = ModifiedDRAC(config)
    
    # Load preprocessed data (from base_v2.ipynb)
    # df = pd.read_parquet('path/to/preprocessed_data.parquet')
    
    # Detect conflicts
    # conflicts = detector.detect(df)
    
    # Save results
    # conflicts.to_csv('conflicts_mdrac.csv', index=False)
    
    print("ModifiedDRAC detector initialized successfully!")
    print(f"Configuration loaded: {len(config)} sections")
    print(f"Vehicle labels: {config['filters']['vehicle_labels']}")
    print(f"M-DRAC thresholds: {config['mdrac']['severity']}")
