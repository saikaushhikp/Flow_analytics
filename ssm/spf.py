"""
Safety Potential Field (SPF) Near-Miss Detection Module

Implements Composite Safety Potential Field (C-SPF) for general traffic conflicts.

Reference:
    Zuo et al. (2025) "Composite Safety Potential Field for Highway Driving 
    Risk Assessment"

Risk Components:
    O-field: Physical collision probability (trajectory intersection)
    S-field: Driver discomfort (proximity to safety bubble)
    C-SPF: Composite risk = max(O-field, S-field)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ssm.utils import get_spf_pairs, load_config, CONFIG_PATH


# Numerical stability constant
EPSILON = 1e-2


# =============================================================================
# OBJECTIVE FIELD (O-FIELD) - Physical Collision Probability
# =============================================================================

def calculate_o_field(
    pos_i: np.ndarray,
    vel_i: np.ndarray,
    width_i: float,
    pos_j: np.ndarray,
    vel_j: np.ndarray,
    width_j: float,
    beta_p: float,
    beta_t: float,
    t_star: float
) -> float:
    """
    Calculate O-field: physical collision probability from trajectory analysis.
    
    Combines spatial risk (will paths intersect?) with temporal risk (is collision
    imminent?). Uses miss distance and time-to-closest-point calculations.
    
    Formula: r_o = exp(-((d_min/d_star)^β_p)) × exp(-((t_min/t_star)^β_t))
    
    Args:
        pos_i, vel_i: Ego vehicle position [x,y] and velocity [vx,vy] (m, m/s)
        width_i: Ego vehicle width (m)
        pos_j, vel_j: Target vehicle position and velocity
        width_j: Target vehicle width (m)
        beta_p: Spatial shape factor
        beta_t: Temporal shape factor
        t_star: Time horizon (s)
        
    Returns:
        Risk value [0.0, 1.0] where ≥0.37 indicates high collision risk
    """
    # Relative kinematics
    D_ij = pos_j - pos_i
    V_ij = vel_j - vel_i
    
    # Edge cases
    D_mag = np.linalg.norm(D_ij)
    if D_mag < EPSILON:
        return 1.0  # Already colliding
    
    V_mag_sq = np.dot(V_ij, V_ij)
    if V_mag_sq < EPSILON:
        return 0.0  # No relative motion
    
    # Check if approaching (Δv · Δr < 0)
    D_dot_V = np.dot(D_ij, V_ij)
    if D_dot_V >= 0:
        return 0.0  # Diverging
    
    # Calculate miss distance (perpendicular distance between trajectories)
    cross_product = D_ij[0] * V_ij[1] - D_ij[1] * V_ij[0]
    d_min = abs(cross_product) / np.sqrt(V_mag_sq)
    
    # Time to closest point
    t_min = -D_dot_V / V_mag_sq
    
    # Spatial and temporal risk components
    d_star = 0.5 * (width_i + width_j)
    P_ij = np.exp(-((d_min / d_star) ** beta_p))
    T_ij = np.exp(-((t_min / t_star) ** beta_t))
    
    return P_ij * T_ij


# =============================================================================
# SUBJECTIVE FIELD (S-FIELD) - Driver Discomfort / Proximity Risk
# =============================================================================

def _get_gamma_x(v_ego: float) -> float:
    """
    Longitudinal scale factor (speed-dependent safety bubble length).
    Calibrated polynomial from Zuo et al., 2025.
    """
    return (5.1053e-4 * v_ego**3 
            - 3.7051e-2 * v_ego**2 
            + 1.0621 * v_ego 
            + 1.2925)


def _get_beta_x(v_ego: float) -> float:
    """
    Longitudinal shape factor (speed-dependent bubble steepness).
    Calibrated polynomial from Zuo et al., 2025.
    """
    return (2.2214e-5 * v_ego**3 
            - 1.4834e-3 * v_ego**2 
            + 9.6673e-3 * v_ego 
            + 3.2589)


def calculate_s_field(
    pos_i: np.ndarray,
    vel_i: np.ndarray,
    theta_i: float,
    pos_j: np.ndarray,
    gamma_y: float,
    beta_y: float
) -> float:
    """
    Calculate S-field: driver's psychological discomfort from proximity.
    
    Models elliptical "safety bubble" around ego vehicle. Longitudinal dimension
    scales with speed (faster = longer bubble), lateral dimension is constant.
    
    Formula: r_s = exp(-((|Δx|/γ_x)^β_x + (|Δy|/γ_y)^β_y))
    
    Args:
        pos_i, vel_i: Ego vehicle position [x,y] and velocity [vx,vy] (m, m/s)
        theta_i: Ego heading angle (radians)
        pos_j: Target vehicle position [x,y]
        gamma_y: Lateral scale (constant safety margin)
        beta_y: Lateral shape factor
        
    Returns:
        Risk value [0.0, 1.0] where ≥0.37 indicates safety bubble breach
    """
    # Relative position
    D_ij = pos_j - pos_i
    
    if np.linalg.norm(D_ij) < EPSILON:
        return 1.0  # Same location
    
    # Ego speed
    v_ego = np.linalg.norm(vel_i)
    
    # Ego's local coordinate axes (velocity direction or heading)
    if v_ego > EPSILON:
        e_long = vel_i / v_ego
        e_lat = np.array([-vel_i[1], vel_i[0]]) / v_ego
    else:
        e_long = np.array([np.cos(theta_i), np.sin(theta_i)])
        e_lat = np.array([-np.sin(theta_i), np.cos(theta_i)])
    
    # Project relative position onto ego's frame
    delta_x = np.dot(D_ij, e_long)  # Longitudinal (ahead/behind)
    delta_y = np.dot(D_ij, e_lat)   # Lateral (left/right)
    
    # Speed-dependent scale and shape
    gamma_x = _get_gamma_x(v_ego)
    beta_x = _get_beta_x(v_ego)
    
    # S-field risk calculation
    term_x = (abs(delta_x) / gamma_x) ** beta_x
    term_y = (abs(delta_y) / gamma_y) ** beta_y
    
    return np.exp(-(term_x + term_y))


# =============================================================================
# COMPOSITE RISK
# =============================================================================

def calculate_composite_risk(r_o: float, r_s: float, method: str = 'max') -> float:
    """
    Combine O-field and S-field into C-SPF composite risk.
    
    Args:
        r_o: Objective field risk [0.0, 1.0]
        r_s: Subjective field risk [0.0, 1.0]
        method: 'max' (conservative), 'probabilistic' (OR logic), 'weighted' (average)
        
    Returns:
        Composite risk [0.0, 1.0]
    """
    if method == 'max':
        return max(r_o, r_s)
    elif method == 'probabilistic':
        return 1.0 - (1.0 - r_o) * (1.0 - r_s)
    elif method == 'weighted':
        return (r_o + r_s) / 2
    else:
        raise ValueError(f"Unknown method: {method}")


def classify_risk_level(risk: float, thresholds: dict) -> str:
    """
    Classify risk into severity categories.
    
    Args:
        risk: Risk value [0.0, 1.0]
        thresholds: Dict with 'warning', 'danger', 'critical' keys
        
    Returns:
        'SAFE', 'WARNING', 'DANGER', or 'CRITICAL'
    """
    if risk >= thresholds['critical']:
        return 'CRITICAL'
    elif risk >= thresholds['danger']:
        return 'DANGER'
    elif risk >= thresholds['warning']:
        return 'WARNING'
    else:
        return 'SAFE'


# =============================================================================
# SPF DETECTION CLASS
# =============================================================================

class SafetyPotentialField:
    """
    SPF detector for general traffic conflicts (all geometry types).
    
    Uses pairs pre-filtered by utils.get_spf_pairs() with conflict types
    already classified. Calculates O-field, S-field, and composite C-SPF risk.
    """
    
    # Label mappings for output
    LABEL_NAMES = {
        1: 'pedestrian', 2: 'bicycle', 3: 'motorcycle', 4: 'car',
        5: 'escooter', 6: 'van', 7: 'truck', 8: 'bus'
    }
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize SPF detector.
        
        Args:
            config: Configuration dict (loads from CONFIG_PATH if None)
        """
        if config is None:
            config = load_config()
        
        self.config = config
        self.o_params = config['spf']['objective']
        self.s_params = config['spf']['subjective']
        self.thresholds = config['spf']['thresholds']
        self.min_risk = config['spf']['min_risk']
        self.composite_method = config['spf']['composite_method']
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main detection pipeline for SPF conflicts.
        
        Pipeline:
            1. Get filtered pairs (approaching, all conflict types)
            2. Calculate O-field and S-field for each pair
            3. Calculate composite C-SPF risk
            4. Filter by minimum threshold
            5. Classify severity
            6. Format output
        
        Args:
            df: Vehicle data (id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel, yaw)
            
        Returns:
            DataFrame with columns: timestamp, pair_id, interaction, conflict_type,
            distance, ttc, closing_speed, o_field, s_field, composite_risk, severity
        """
        # Step 1: Get SPF-specific pairs (all conflict types)
        pairs = get_spf_pairs(df, self.config)
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 2: Calculate O-field and S-field
        pairs = self.calculate_fields(pairs)
        
        # Step 3: Calculate composite risk
        pairs = self.calculate_composite(pairs)
        
        # Step 4: Filter by minimum threshold
        pairs = pairs[pairs['composite_risk'] >= self.min_risk]
        
        if len(pairs) == 0:
            return self._empty_output()
        
        # Step 5: Classify severity
        pairs = self.classify_severity(pairs)
        
        # Step 6: Format output
        return self.format_output(pairs)
    
    def calculate_fields(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate O-field and S-field for all pairs.
        
        Vectorized calculation across all pair rows. Uses vehicle widths,
        positions, velocities, and headings from pair data.
        
        Args:
            pairs: DataFrame from get_spf_pairs()
            
        Returns:
            DataFrame with added columns: o_field, s_field
        """
        o_risks = []
        s_risks = []
        
        for _, row in pairs.iterrows():
            # Extract vehicle states
            pos_i = np.array([row['pos1_x'], row['pos1_y']])
            vel_i = np.array([row['vel1_x'], row['vel1_y']])
            width_i = row.get('width1', 1.8)  # Default car width
            theta_i = row.get('yaw1', 0.0)
            
            pos_j = np.array([row['pos2_x'], row['pos2_y']])
            vel_j = np.array([row['vel2_x'], row['vel2_y']])
            width_j = row.get('width2', 1.8)
            
            # Calculate O-field
            r_o = calculate_o_field(
                pos_i, vel_i, width_i,
                pos_j, vel_j, width_j,
                self.o_params['beta_p'],
                self.o_params['beta_t'],
                self.o_params['t_star']
            )
            
            # Calculate S-field
            r_s = calculate_s_field(
                pos_i, vel_i, theta_i, pos_j,
                self.s_params['gamma_y'],
                self.s_params['beta_y']
            )
            
            o_risks.append(r_o)
            s_risks.append(r_s)
        
        pairs = pairs.copy()
        pairs['o_field'] = o_risks
        pairs['s_field'] = s_risks
        
        return pairs
    
    def calculate_composite(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate composite C-SPF risk from O-field and S-field.
        
        Args:
            pairs: DataFrame with o_field and s_field columns
            
        Returns:
            DataFrame with added column: composite_risk
        """
        pairs = pairs.copy()
        pairs['composite_risk'] = pairs.apply(
            lambda row: calculate_composite_risk(
                row['o_field'], 
                row['s_field'], 
                self.composite_method
            ),
            axis=1
        )
        return pairs
    
    def classify_severity(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Classify risk severity based on composite risk thresholds.
        
        Severity Levels:
            - CRITICAL: risk ≥ 0.90 (extreme danger)
            - DANGER: risk ≥ 0.70 (high risk)
            - WARNING: risk ≥ 0.37 (moderate risk)
            - SAFE: risk < 0.37 (low risk)
        
        Args:
            pairs: DataFrame with composite_risk column
            
        Returns:
            DataFrame with added column: severity
        """
        pairs = pairs.copy()
        pairs['severity'] = pairs['composite_risk'].apply(
            lambda r: classify_risk_level(r, self.thresholds)
        )
        return pairs
    
    def format_output(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Format output with clean, human-readable schema.
        
        Creates:
            - pair_id: "id1_id2"
            - interaction: "type1_type2" (e.g., "car_truck")
        
        Args:
            pairs: DataFrame with all calculated values
            
        Returns:
            DataFrame with simplified schema for analysis
        """
        # Create pair identifier
        pair_id = [f"{int(row['id1'])}_{int(row['id2'])}" 
                   for _, row in pairs.iterrows()]
        
        # Create human-readable interaction string
        interaction = [
            f"{self.LABEL_NAMES.get(int(row['label1']), str(row['label1']))}_"
            f"{self.LABEL_NAMES.get(int(row['label2']), str(row['label2']))}"
            for _, row in pairs.iterrows()
        ]
        
        # Build output DataFrame
        output = pd.DataFrame({
            'timestamp': pairs['timestamp'].values,
            'pair_id': pair_id,
            'interaction': interaction,
            'conflict_type': pairs['conflict_type'].values,
            'distance': pairs['distance'].values,
            'ttc': pairs['ttc'].values,
            'closing_speed': pairs['closing_speed'].values,
            'o_field': pairs['o_field'].values,
            's_field': pairs['s_field'].values,
            'composite_risk': pairs['composite_risk'].values,
            'severity': pairs['severity'].values
        })
        
        return output
    
    def _empty_output(self) -> pd.DataFrame:
        """Return empty DataFrame with correct output schema."""
        return pd.DataFrame(columns=[
            'timestamp', 'pair_id', 'interaction', 'conflict_type', 'distance',
            'ttc', 'closing_speed', 'o_field', 's_field', 'composite_risk', 'severity'
        ])


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == '__main__':
    """
    Example usage demonstrating SPF field calculations.
    """
    
    print("=" * 80)
    print(" SAFETY POTENTIAL FIELD (SPF) - EXAMPLES")
    print("=" * 80)
    
    # Load config
    config = load_config()
    o_params = config['spf']['objective']
    s_params = config['spf']['subjective']
    thresholds = config['spf']['thresholds']
    
    # Example 1: Head-on collision scenario
    print("\nExample 1: Head-on Collision")
    print("-" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([15.0, 0.0])
    theta_i = 0.0
    width_i = 1.8
    
    pos_j = np.array([100.0, 1.0])
    vel_j = np.array([-15.0, 0.0])
    width_j = 1.8
    
    r_o = calculate_o_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j,
                            o_params['beta_p'], o_params['beta_t'], o_params['t_star'])
    r_s = calculate_s_field(pos_i, vel_i, theta_i, pos_j,
                            s_params['gamma_y'], s_params['beta_y'])
    r_c = calculate_composite_risk(r_o, r_s)
    
    print(f"Ego:    pos={pos_i}, vel={vel_i} m/s")
    print(f"Target: pos={pos_j}, vel={vel_j} m/s")
    print(f"\nRisks:")
    print(f"  O-field: {r_o:.4f} [{classify_risk_level(r_o, thresholds)}]")
    print(f"  S-field: {r_s:.4f} [{classify_risk_level(r_s, thresholds)}]")
    print(f"  Composite: {r_c:.4f} [{classify_risk_level(r_c, thresholds)}]")
    
    # Example 2: Safe parallel driving
    print("\n" + "=" * 80)
    print("Example 2: Safe Parallel Driving")
    print("-" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([20.0, 0.0])
    pos_j = np.array([10.0, 3.5])
    vel_j = np.array([20.0, 0.0])
    
    r_o = calculate_o_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j,
                            o_params['beta_p'], o_params['beta_t'], o_params['t_star'])
    r_s = calculate_s_field(pos_i, vel_i, theta_i, pos_j,
                            s_params['gamma_y'], s_params['beta_y'])
    r_c = calculate_composite_risk(r_o, r_s)
    
    print(f"Ego:    pos={pos_i}, vel={vel_i} m/s")
    print(f"Target: pos={pos_j}, vel={vel_j} m/s")
    print(f"\nRisks:")
    print(f"  O-field: {r_o:.4f} [{classify_risk_level(r_o, thresholds)}]")
    print(f"  S-field: {r_s:.4f} [{classify_risk_level(r_s, thresholds)}]")
    print(f"  Composite: {r_c:.4f} [{classify_risk_level(r_c, thresholds)}]")
    
    print("\n" + "=" * 80)
    print("✓ SPF implementation complete!")
    print("=" * 80)


