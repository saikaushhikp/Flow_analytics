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
        self.prt = config['mdrac']['prt']  # Perception-Reaction Time by vehicle type
        self.min_mdrac = config['mdrac']['min_mdrac']  # Minimum threshold for detection
        self.severity_thresholds = config['mdrac']['severity']  # Severity classification
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main detection pipeline for MDRAC conflicts.
        
        Pipeline:
            1. Get filtered pairs (same-lane, car-following)
            2. Calculate MDRAC values
            3. Filter by minimum threshold
            4. Classify severity
            5. Format output
        
        Args:
            df: Vehicle data (id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel, yaw)
                
        Returns:
            DataFrame with columns: timestamp, pair_id, interaction, distance,
            ttc, closing_speed, speed_diff, mdrac, severity
        """
        # Step 1: Get MDRAC-specific pairs (same-lane car-following)
        pairs = get_mdrac_pairs(df, self.config)
        
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
        
        Creates:
            - pair_id: "leader_id_follower_id" (e.g., "10295_10287")
            - interaction: "leader_type_follower_type" (e.g., "car_truck")
        
        Args:
            pairs: DataFrame with all calculated values
            
        Returns:
            DataFrame with simplified schema for analysis
        """
        # Determine leader and follower IDs
        leader_id = np.where(
            pairs['is_veh1_follower'],
            pairs['id2'],  # veh2 is leader
            pairs['id1']   # veh1 is leader
        )
        follower_id = np.where(
            pairs['is_veh1_follower'],
            pairs['id1'],  # veh1 is follower
            pairs['id2']   # veh2 is follower
        )
        
        # Determine leader and follower vehicle types
        leader_label = np.where(
            pairs['is_veh1_follower'],
            pairs['label2'],
            pairs['label1']
        )
        follower_label = np.where(
            pairs['is_veh1_follower'],
            pairs['label1'],
            pairs['label2']
        )
        
        # Create human-readable interaction string
        interaction = [
            f"{self.LABEL_NAMES.get(int(lead), str(lead))}_"
            f"{self.LABEL_NAMES.get(int(foll), str(foll))}"
            for lead, foll in zip(leader_label, follower_label)
        ]
        
        # Create pair identifier
        pair_id = [f"{lead}_{foll}" for lead, foll in zip(leader_id, follower_id)]
        
        # Build output DataFrame
        output = pd.DataFrame({
            'timestamp': pairs['timestamp'].values,
            'pair_id': pair_id,
            'interaction': interaction,
            'distance': pairs['distance'].values,
            'ttc': pairs['ttc'].values,
            'closing_speed': pairs['closing_speed'].values,
            'speed_diff': pairs['speed_diff'].values,
            'mdrac': pairs['mdrac'].values,
            'severity': pairs['severity'].values
        })
        
        return output
    
    def _empty_output(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(columns=[
            'timestamp', 'pair_id', 'interaction', 'distance', 'ttc',
            'closing_speed', 'speed_diff', 'mdrac', 'severity'
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
