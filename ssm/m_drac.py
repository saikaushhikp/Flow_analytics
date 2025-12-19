"""
Modified DRAC (M-DRAC) Near-Miss Detection Module

Generalized implementation for any object-object interaction (vehicle-vehicle,
pedestrian-vehicle, etc.) based on configuration.

Based on: Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015)
"How Does the Driver's Perception Reaction Time Affect the Performances of 
Crash Surrogate Measures?" PLOS ONE 10(9): e0138617

Formula:
    MDRAC = (V_F - V_L) / [2 × (TTC - PRT)]

Where:
    V_F = velocity of following object (m/s)
    V_L = velocity of leading object (m/s)
    TTC = Time to Collision (seconds)
    PRT = Perception-Reaction Time (seconds)

Critical Condition:
    If TTC ≤ PRT: MDRAC = ∞ (no time to react, collision unavoidable)
"""

import pandas as pd
import numpy as np
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ssm.utils import find_vehicle_vehicle_pairs, load_config


class ModifiedDRAC:
    """
    Generalized M-DRAC detector for object-object near-miss conflicts.
    
    Works with any object types (vehicles, pedestrians, etc.) based on
    config.yaml settings. Uses pre-filtered pairs from utils with
    leader/follower already identified.
    """
    
    # Label name mappings for output formatting
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
    
    def __init__(self, config: Optional[dict] = None, config_path: str = 'config.yaml'):
        """
        Initialize M-DRAC detector.
        
        Args:
            config: Configuration dictionary (optional)
            config_path: Path to config.yaml if config not provided
        """
        if config is None:
            config = load_config(config_path)
        
        self.config = config
        self.prt = config['mdrac']['prt']
        self.min_mdrac = config['mdrac']['min_mdrac']
        self.severity_thresholds = config['mdrac']['severity']
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main detection pipeline for near-miss conflicts.
        
        Args:
            df: Raw data from preprocessing with columns:
                id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel
                
        Returns:
            DataFrame with detected conflicts:
                timestamp, pair_id, interaction, distance, ttc, closing_speed,
                speed_diff, mdrac, severity
        """
        # Step 1: Get filtered pairs with leader/follower identified
        pairs = find_vehicle_vehicle_pairs(df, self.config)
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 2: Calculate M-DRAC
        pairs = self.calculate_mdrac(pairs)
        
        # Step 3: Filter by minimum M-DRAC threshold
        pairs = pairs[pairs['mdrac'] >= self.min_mdrac]
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 4: Classify severity
        pairs = self.classify_severity(pairs)
        
        # Step 5: Temporal deduplication
        conflicts = self.deduplicate_temporal(pairs)
        
        # Step 6: Format output
        return self.format_output(conflicts)
    
    def calculate_mdrac(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate M-DRAC for pairs with identified leader/follower.
        
        Uses follower's PRT for calculation.
        
        Formula (corrected for 2D):
            MDRAC = closing_speed / [2 × (TTC - PRT)]
        
        Note: We use closing_speed (projected approach velocity) instead of
        simple speed difference because it accounts for 2D motion.
        
        If TTC <= PRT: MDRAC = inf (critical)
        
        Args:
            pairs: DataFrame from find_vehicle_vehicle_pairs()
            
        Returns:
            DataFrame with mdrac and prt_used columns added
        """
        # Determine follower label for each pair
        follower_label = np.where(
            pairs['is_veh1_follower'],
            pairs['label1'],
            pairs['label2']
        )
        
        # Get PRT values for followers
        prt_values = np.array([self.prt.get(label, 1.0) for label in follower_label])
        
        # Calculate time available for reaction
        time_available = pairs['ttc'].values - prt_values
        
        # M-DRAC formula using closing_speed (correct for 2D)
        # MDRAC = closing_speed / [2 × (TTC - PRT)]
        mdrac = np.where(
            time_available > 0,
            pairs['closing_speed'].values / (2 * time_available),
            np.inf  # Critical: TTC <= PRT, no reaction time
        )
        
        pairs = pairs.copy()
        pairs['mdrac'] = mdrac
        pairs['prt_used'] = prt_values
        
        return pairs
    
    def classify_severity(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Classify conflict severity based on M-DRAC value.
        
        Severity levels:
            - CRITICAL: TTC <= PRT (mdrac = inf)
            - SEVERE: mdrac >= 7.0 m/s²
            - MODERATE: mdrac >= 5.0 m/s²
            - NORMAL: mdrac >= 3.4 m/s²
        
        Args:
            pairs: DataFrame with mdrac column
            
        Returns:
            DataFrame with severity column added
        """
        severity = np.full(len(pairs), 'normal', dtype=object)
        
        # MODERATE: mdrac >= 5.0
        severity = np.where(
            pairs['mdrac'] >= self.severity_thresholds['moderate'],
            'moderate',
            severity
        )
        
        # SEVERE: mdrac >= 7.0
        severity = np.where(
            pairs['mdrac'] >= self.severity_thresholds['severe'],
            'severe',
            severity
        )
        
        # CRITICAL: mdrac = inf (TTC <= PRT)
        severity = np.where(
            np.isinf(pairs['mdrac']),
            'critical',
            severity
        )
        
        pairs = pairs.copy()
        pairs['severity'] = severity
        
        return pairs
    
    def deduplicate_temporal(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Remove temporal duplicates - keep only first detection of each pair.
        
        Same pair may be detected across multiple timestamps. We keep only
        the first timestamp when the pair is classified as a near-miss.
        
        Args:
            pairs: DataFrame with conflicts
            
        Returns:
            DataFrame with duplicates removed
        """
        pairs = pairs.sort_values('timestamp')
        
        # Create canonical pair key (order-independent)
        pairs = pairs.copy()
        pairs['pair_key'] = pairs.apply(
            lambda row: f"{min(row['id1'], row['id2'])}-{max(row['id1'], row['id2'])}",
            axis=1
        )
        
        # Keep first occurrence of each pair
        return pairs.drop_duplicates(subset='pair_key', keep='first')
    
    def format_output(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Format final output with clean schema.
        
        Creates pair_id as "leader_id_follower_id" and interaction as
        "leader_type_follower_type" (e.g., "car_truck").
        
        Args:
            pairs: DataFrame with all calculated values
            
        Returns:
            DataFrame with simplified schema
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
        
        # Determine leader and follower labels
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
        
        # Create interaction string
        interaction = [
            f"{self.LABEL_NAMES.get(int(lead), str(lead))}_"
            f"{self.LABEL_NAMES.get(int(foll), str(foll))}"
            for lead, foll in zip(leader_label, follower_label)
        ]
        
        # Create pair_id string
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
    """
    Example usage of ModifiedDRAC detector.
    
    Usage:
        python ssm/m_drac.py
    """
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
