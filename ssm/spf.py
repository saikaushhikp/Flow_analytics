"""
Safety Potential Field (SPF) Module

Implementation of Composite Safety Potential Field (C-SPF) framework
based on "Composite Safety Potential Field for Highway Driving Risk Assessment"
by Zuo et al., 2025.

This module provides risk assessment combining:
- Objective Field (O-field): Physical collision probability
- Subjective Field (S-field): Driver discomfort
"""

import numpy as np
from typing import Tuple, Optional
import pandas as pd


# =============================================================================
# CONSTANTS
# =============================================================================

# Objective Field (O-field) Constants
BETA_P = 10  # Spatial shape factor (binary-like collision boundary)
BETA_T = 2  # Temporal shape factor (quadratic time pressure)
T_STAR = 7.5  # Time horizon in seconds (look-ahead limit)

# Subjective Field (S-field) Constants
GAMMA_Y = 1.4310  # Lateral scale (constant) [meters]
BETA_Y = 4.9956   # Lateral shape (constant) [dimensionless]

# Risk thresholds
RISK_THRESHOLD_WARNING = 0.37  # e^-1 threshold
RISK_THRESHOLD_DANGER = 0.70   # High danger level
RISK_THRESHOLD_CRITICAL = 0.90  # Critical level

# Numerical stability
EPSILON = 1e-2  # Small value to prevent division by zero


# =============================================================================
# OBJECTIVE FIELD (O-FIELD) - Physical Collision Probability
# =============================================================================

def calculate_objective_field(
    pos_i: np.ndarray,
    vel_i: np.ndarray,
    width_i: float,
    pos_j: np.ndarray,
    vel_j: np.ndarray,
    width_j: float,
    beta_p: float = BETA_P,
    beta_t: float = BETA_T,
    t_star: float = T_STAR
) -> float:
    """
    Calculate Objective Field (O-field) risk between two vehicles.
    
    The O-field quantifies the physical collision probability based on
    current trajectories using kinematic analysis. It combines:
    - Spatial Risk (P_ij): Will trajectories intersect?
    - Temporal Risk (T_ij): Is there enough time to react?
    
    Risk Interpretation:
        - Risk >= 0.37 (e^-1): High risk, imminent collision
        - Risk < 0.37: Low risk, safe interaction
        - Risk = 0.0: Vehicles diverging or no relative motion
        - Risk = 1.0: Collision imminent or already occurring
    
    Args:
        pos_i: Position vector of ego vehicle [x, y] in meters
        vel_i: Velocity vector of ego vehicle [vx, vy] in m/s
        width_i: Width of ego vehicle in meters
        pos_j: Position vector of target vehicle [x, y] in meters
        vel_j: Velocity vector of target vehicle [vx, vy] in m/s
        width_j: Width of target vehicle in meters (size_y)
        beta_p: Spatial shape factor (default: 10)
        beta_t: Temporal shape factor (default: 2)
        t_star: Time horizon in seconds (default: 7.5)
    
    Returns:
        float: O-field risk value in range [0.0, 1.0]
    
    Reference:
        Equation 19 from Zuo et al., 2025
    
    Example:
        >>> pos_i = np.array([0.0, 0.0])
        >>> vel_i = np.array([10.0, 0.0])
        >>> pos_j = np.array([50.0, 2.0])
        >>> vel_j = np.array([-10.0, 0.0])
        >>> risk = calculate_objective_field(pos_i, vel_i, 1.8, pos_j, vel_j, 1.8)
        >>> print(f"Collision risk: {risk:.4f}")
    """
    # Step 2: Calculate relative kinematics
    D_ij = pos_j - pos_i  # Relative position vector [Dx, Dy]
    V_ij = vel_j - vel_i  # Relative velocity vector [Vx, Vy]
    
    # Edge Case 1: Same location (collision already occurring)
    D_mag = np.linalg.norm(D_ij)
    if D_mag < EPSILON:
        return 1.0
    
    # Edge Case 2: No relative motion (stationary or same velocity)
    V_mag_sq = np.dot(V_ij, V_ij)
    if V_mag_sq < EPSILON:
        return 0.0
    
    # Step 3: Convergence check (are vehicles approaching?)
    D_dot_V = np.dot(D_ij, V_ij)
    if D_dot_V >= 0:
        return 0.0  # Vehicles are diverging or moving perpendicular
    
    # Step 4: Calculate miss distance (minimum future distance)
    # This is the perpendicular distance between trajectories
    cross_product = D_ij[0] * V_ij[1] - D_ij[1] * V_ij[0]  # 2D cross product
    d_min = abs(cross_product) / np.sqrt(V_mag_sq)
    
    # Step 5: Calculate time to closest point
    # Negative sign converts negative dot product to positive time
    t_min = -D_dot_V / V_mag_sq
    
    # Step 6: Calculate risk components
    # Spatial risk: Will they physically overlap?
    d_star = 0.5 * (width_i + width_j)  # Collision threshold distance
    P_ij = np.exp(-((d_min / d_star) ** beta_p))
    
    # Temporal risk: Is collision imminent?
    T_ij = np.exp(-((t_min / t_star) ** beta_t))
    
    # Total objective risk (product of spatial and temporal)
    r_o = P_ij * T_ij
    
    return r_o


def calculate_objective_field_batch(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    pos_cols: Tuple[str, str] = ('pos_x', 'pos_y'),
    vel_cols: Tuple[str, str] = ('vel_x', 'vel_y'),
    width_col: str = 'width',
    frame_col: str = 'frame'
) -> pd.DataFrame:
    """
    Calculate O-field risk for a pair of vehicles across multiple frames.
    
    This function computes the objective field risk at each timestamp where
    both vehicles are present in the data.
    
    Args:
        df: DataFrame with trajectory data
        id1: ID of first vehicle (ego)
        id2: ID of second vehicle (target)
        pos_cols: Column names for position (x, y)
        vel_cols: Column names for velocity (vx, vy)
        width_col: Column name for vehicle width
        frame_col: Column name for frame/timestamp
    
    Returns:
        DataFrame with columns:
            - frame: Frame number
            - timestamp: Time in seconds
            - o_field_risk: O-field risk value [0.0, 1.0]
            - d_min: Minimum future distance (meters)
            - t_min: Time to closest point (seconds)
            - is_approaching: Boolean, whether vehicles are converging
    
    Example:
        >>> result = calculate_objective_field_batch(df, 11332919, 11332806)
        >>> high_risk = result[result['o_field_risk'] >= 0.37]
        >>> print(f"High risk frames: {len(high_risk)}")
    """
    # Filter data for both vehicles
    df1 = df[df['track_id'] == id1].copy()
    df2 = df[df['track_id'] == id2].copy()
    
    # Merge on common frames
    merged = pd.merge(
        df1[[frame_col, *pos_cols, *vel_cols, width_col]],
        df2[[frame_col, *pos_cols, *vel_cols, width_col]],
        on=frame_col,
        suffixes=('_1', '_2')
    )
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    # Calculate O-field risk for each frame
    results = []
    
    for _, row in merged.iterrows():
        # Extract positions and velocities
        pos_i = np.array([row[f'{pos_cols[0]}_1'], row[f'{pos_cols[1]}_1']])
        vel_i = np.array([row[f'{vel_cols[0]}_1'], row[f'{vel_cols[1]}_1']])
        width_i = row[f'{width_col}_1']
        
        pos_j = np.array([row[f'{pos_cols[0]}_2'], row[f'{pos_cols[1]}_2']])
        vel_j = np.array([row[f'{vel_cols[0]}_2'], row[f'{vel_cols[1]}_2']])
        width_j = row[f'{width_col}_2']
        
        # Calculate relative kinematics for diagnostics
        D_ij = pos_j - pos_i
        V_ij = vel_j - vel_i
        D_dot_V = np.dot(D_ij, V_ij)
        is_approaching = D_dot_V < 0
        
        # Calculate miss distance and time (if approaching)
        if is_approaching and np.dot(V_ij, V_ij) > EPSILON:
            V_mag_sq = np.dot(V_ij, V_ij)
            cross_product = D_ij[0] * V_ij[1] - D_ij[1] * V_ij[0]
            d_min = abs(cross_product) / np.sqrt(V_mag_sq)
            t_min = -D_dot_V / V_mag_sq
        else:
            d_min = np.nan
            t_min = np.nan
        
        # Calculate O-field risk
        risk = calculate_objective_field(
            pos_i, vel_i, width_i,
            pos_j, vel_j, width_j
        )
        
        results.append({
            frame_col: row[frame_col],
            'o_field_risk': risk,
            'd_min': d_min,
            't_min': t_min,
            'is_approaching': is_approaching,
            'distance': np.linalg.norm(D_ij)
        })
    
    result_df = pd.DataFrame(results)
    
    # Add timestamp if available in original data
    if 'timestamp' in df.columns:
        result_df = result_df.merge(
            df[[frame_col, 'timestamp']].drop_duplicates(),
            on=frame_col,
            how='left'
        )
    
    return result_df


# =============================================================================
# SUBJECTIVE FIELD (S-FIELD) - Driver Discomfort / Proximity Risk
# =============================================================================
def _calculate_gamma_x(v_ego: float) -> float:
    """
    Calculate longitudinal scale factor (gamma_x) based on ego velocity. 
    Needs to be calibrated with the traffic data inorder to get optimal values    
    Args:
        v_ego: Ego vehicle velocity magnitude in m/s
    Returns:
        float: Longitudinal scale factor in meters
    """
    gamma_x = (5.1053e-4 * v_ego**3 
               - 3.7051e-2 * v_ego**2 
               + 1.0621 * v_ego 
               + 1.2925)
    return gamma_x


def _calculate_beta_x(v_ego: float) -> float:
    """
    Calculate longitudinal shape factor (beta_x) based on ego velocity.    
    Args:
        v_ego: Ego vehicle velocity magnitude in m/s
    Returns:
        float: Longitudinal shape factor (dimensionless)
    """
    beta_x = (2.2214e-5 * v_ego**3 
              - 1.4834e-3 * v_ego**2 
              + 9.6673e-3 * v_ego 
              + 3.2589)
    return beta_x


def calculate_subjective_field(
    pos_i: np.ndarray,
    vel_i: np.ndarray,
    theta_i: float,
    pos_j: np.ndarray,
    return_diagnostics: bool = False
) -> float:
    """
    Calculate Subjective Field (S-field) proximity risk.
    
    The S-field quantifies driver's psychological discomfort caused by
    spatial proximity to nearby vehicles. It models the "safety bubble"
    that drivers maintain around their vehicle.
    
    The bubble is elliptical:
    - Longitudinal (front/back): Speed-dependent, larger at higher speeds
    - Lateral (left/right): Constant ~1.43m regardless of speed
    
    Risk Interpretation:
        - Risk >= 0.37 (e^-1): Safety bubble breached, driver discomfort
        - Risk < 0.37: Comfortable spacing
        - Risk = 1.0: Extreme proximity
    
    Args:
        pos_i: Position of ego vehicle [x, y] in meters
        vel_i: Velocity of ego vehicle [vx, vy] in m/s
        theta_i: Heading angle of ego vehicle in radians
        pos_j: Position of target vehicle [x, y] in meters
        return_diagnostics: If True, return (risk, diagnostics_dict)
    
    Returns:
        float: S-field risk value in range [0.0, 1.0]
        OR tuple: (risk, diagnostics) if return_diagnostics=True
    
    Reference:
        Equation 3 from Zuo et al., 2025
    
    Example:
        >>> pos_i = np.array([0.0, 0.0])
        >>> vel_i = np.array([20.0, 0.0])
        >>> theta_i = 0.0
        >>> pos_j = np.array([30.0, 1.5])
        >>> risk = calculate_subjective_field(pos_i, vel_i, theta_i, pos_j)
        >>> print(f"Proximity risk: {risk:.4f}")
    """
    # Step 1: Calculate relative position (global frame)
    D_ij = pos_j - pos_i
    
    # Edge case: Same location
    if np.linalg.norm(D_ij) < EPSILON:
        if return_diagnostics:
            return 1.0, {'reason': 'same_location'}
        return 1.0
    
    # Step 2: Calculate ego velocity magnitude
    v_ego = np.linalg.norm(vel_i)
    
    # Step 3: Determine ego's local coordinate axes
    if v_ego > EPSILON:
        # Use velocity direction (primary)
        e_long = vel_i / v_ego
        e_lat = np.array([-vel_i[1], vel_i[0]]) / v_ego
    else:
        # Fallback to heading angle (when stationary)
        e_long = np.array([np.cos(theta_i), np.sin(theta_i)])
        e_lat = np.array([-np.sin(theta_i), np.cos(theta_i)])
    
    # Step 4: Project relative position onto ego's local axes
    delta_x = np.dot(D_ij, e_long)  # Longitudinal (ahead/behind)
    delta_y = np.dot(D_ij, e_lat)   # Lateral (left/right)
    
    # Step 5: Calculate scale parameters
    gamma_x = _calculate_gamma_x(v_ego)  # Speed-dependent
    gamma_y = GAMMA_Y  # Constant
    
    # Step 6: Calculate shape parameters
    beta_x = _calculate_beta_x(v_ego)  # Speed-dependent
    beta_y = BETA_Y  # Constant
    
    # Step 7: Calculate S-field risk (Equation 3)
    term_x = (abs(delta_x) / gamma_x) ** beta_x
    term_y = (abs(delta_y) / gamma_y) ** beta_y
    
    r_s = np.exp(-(term_x + term_y))
    
    # Return with or without diagnostics
    if return_diagnostics:
        diagnostics = {
            'delta_x': delta_x,
            'delta_y': delta_y,
            'gamma_x': gamma_x,
            'gamma_y': gamma_y,
            'beta_x': beta_x,
            'beta_y': beta_y,
            'v_ego': v_ego,
            'term_x': term_x,
            'term_y': term_y
        }
        return r_s, diagnostics
    
    return r_s


def calculate_subjective_field_batch(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    pos_cols: Tuple[str, str] = ('pos_x', 'pos_y'),
    vel_cols: Tuple[str, str] = ('vel_x', 'vel_y'),
    heading_col: str = 'heading',
    frame_col: str = 'frame'
) -> pd.DataFrame:
    """
    Calculate S-field risk for a pair of vehicles across multiple frames.
    
    This function computes the subjective field risk at each timestamp where
    both vehicles are present, treating id1 as the ego vehicle.
    
    Args:
        df: DataFrame with trajectory data
        id1: ID of ego vehicle (whose perspective we take)
        id2: ID of target vehicle
        pos_cols: Column names for position (x, y)
        vel_cols: Column names for velocity (vx, vy)
        heading_col: Column name for heading angle (radians)
        frame_col: Column name for frame/timestamp
    
    Returns:
        DataFrame with columns:
            - frame: Frame number
            - timestamp: Time in seconds (if available)
            - s_field_risk: S-field risk value [0.0, 1.0]
            - delta_x: Longitudinal distance (ahead/behind)
            - delta_y: Lateral distance (left/right)
            - gamma_x: Longitudinal scale used
            - v_ego: Ego velocity magnitude
    
    Example:
        >>> result = calculate_subjective_field_batch(df, 11332919, 11332806)
        >>> high_risk = result[result['s_field_risk'] >= 0.37]
        >>> print(f"High risk frames: {len(high_risk)}")
    """
    # Filter data for both vehicles
    df1 = df[df['track_id'] == id1].copy()
    df2 = df[df['track_id'] == id2].copy()
    
    # Merge on common frames
    merged = pd.merge(
        df1[[frame_col, *pos_cols, *vel_cols, heading_col]],
        df2[[frame_col, *pos_cols]],
        on=frame_col,
        suffixes=('_1', '_2')
    )
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    # Calculate S-field risk for each frame
    results = []
    
    for _, row in merged.iterrows():
        # Extract ego (id1) state
        pos_i = np.array([row[f'{pos_cols[0]}_1'], row[f'{pos_cols[1]}_1']])
        vel_i = np.array([row[f'{vel_cols[0]}_1'], row[f'{vel_cols[1]}_1']])
        theta_i = row[f'{heading_col}_1']
        
        # Extract target (id2) position
        pos_j = np.array([row[f'{pos_cols[0]}_2'], row[f'{pos_cols[1]}_2']])
        
        # Calculate S-field risk with diagnostics
        risk, diag = calculate_subjective_field(
            pos_i, vel_i, theta_i, pos_j,
            return_diagnostics=True
        )
        
        results.append({
            frame_col: row[frame_col],
            's_field_risk': risk,
            'delta_x': diag.get('delta_x', np.nan),
            'delta_y': diag.get('delta_y', np.nan),
            'gamma_x': diag.get('gamma_x', np.nan),
            'gamma_y': diag.get('gamma_y', np.nan),
            'v_ego': diag.get('v_ego', np.nan),
            'distance': np.linalg.norm(pos_j - pos_i)
        })
    
    result_df = pd.DataFrame(results)
    
    # Add timestamp if available in original data
    if 'timestamp' in df.columns:
        result_df = result_df.merge(
            df[[frame_col, 'timestamp']].drop_duplicates(),
            on=frame_col,
            how='left'
        )
    
    return result_df


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def classify_risk_level(risk: float) -> str:
    """
    Classify risk level based on threshold.
    
    Applies to both O-field and S-field risk values.
    
    Args:
        risk: Risk value [0.0, 1.0]
    
    Returns:
        str: Risk level ('SAFE', 'WARNING', 'DANGER', 'CRITICAL')
    
    Reference:
        Section 5.1 from Zuo et al., 2025
        Critical threshold at e^-1 ≈ 0.3679
    """
    if risk >= RISK_THRESHOLD_CRITICAL:
        return 'CRITICAL'
    elif risk >= RISK_THRESHOLD_DANGER:
        return 'DANGER'
    elif risk >= RISK_THRESHOLD_WARNING:
        return 'WARNING'
    else:
        return 'SAFE'


def get_risk_statistics(risk_df: pd.DataFrame, field_type: str = 'o_field') -> dict:
    """
    Calculate summary statistics for risk assessment.
    Args:
        risk_df: DataFrame from calculate_*_field_batch()
        field_type: 'o_field' or 's_field'
    Returns:
        dict: Statistics including max risk, warning frames, etc.
    """
    if len(risk_df) == 0:
        return {}
    
    risk_col = f'{field_type}_risk'
    
    if risk_col not in risk_df.columns:
        return {}
    
    stats = {
        'max_risk': risk_df[risk_col].max(),
        'mean_risk': risk_df[risk_col].mean(),
        'total_frames': len(risk_df),
        'warning_frames': len(risk_df[risk_df[risk_col] >= RISK_THRESHOLD_WARNING]),
        'danger_frames': len(risk_df[risk_df[risk_col] >= RISK_THRESHOLD_DANGER]),
        'critical_frames': len(risk_df[risk_df[risk_col] >= RISK_THRESHOLD_CRITICAL])
    }
    
    # Add field-specific stats
    if field_type == 'o_field':
        stats['min_distance'] = risk_df['d_min'].min()
        stats['min_time'] = risk_df['t_min'].min()
        stats['approaching_frames'] = risk_df['is_approaching'].sum()
    elif field_type == 's_field':
        stats['min_delta_x'] = risk_df['delta_x'].abs().min()
        stats['min_delta_y'] = risk_df['delta_y'].abs().min()
        stats['mean_gamma_x'] = risk_df['gamma_x'].mean()
    
    return stats


def calculate_composite_risk(r_o: float, r_s: float, method: str = 'max') -> float:
    """
    Combine O-field and S-field into composite C-SPF risk.
    Args:
        r_o: O-field risk [0.0, 1.0]
        r_s: S-field risk [0.0, 1.0]
        method: Combination method ('max', 'probabilistic', 'weighted')
    Returns:
        float: Composite risk [0.0, 1.0]
    Methods:
        - 'max': r_c = max(r_o, r_s) - Most conservative
        - 'probabilistic': r_c = 1 - (1-r_o)(1-r_s) - Probabilistic OR
        - 'weighted': r_c = 0.5*r_o + 0.5*r_s - Equal weighting
    """
    if method == 'max':
        return max(r_o, r_s)
    elif method == 'probabilistic':
        return 1.0 - (1.0 - r_o) * (1.0 - r_s)
    elif method == 'weighted':
        return (r_o + r_s) / 2
    else:
        raise ValueError(f"Unknown method: {method}")

# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == '__main__':
    """
    Example usage demonstrating both O-field and S-field implementations.
    """
    
    print("=" * 80)
    print(" COMPOSITE SAFETY POTENTIAL FIELD (C-SPF) - EXAMPLES")
    print("=" * 80)
    
    # ==========================================================================
    # EXAMPLE 1: Head-on Collision (High O-field, High S-field)
    # ==========================================================================
    print("\n" + "=" * 80)
    print("Example 1: Head-on Collision Scenario")
    print("=" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([15.0, 0.0])
    theta_i = 0.0
    width_i = 1.8
    
    pos_j = np.array([100.0, 1.0])
    vel_j = np.array([-15.0, 0.0])
    width_j = 1.8
    
    r_o = calculate_objective_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j)
    r_s = calculate_subjective_field(pos_i, vel_i, theta_i, pos_j)
    r_c = calculate_composite_risk(r_o, r_s, method='max')
    
    print(f"Ego Vehicle:    Position={pos_i}, Velocity={vel_i} m/s")
    print(f"Target Vehicle: Position={pos_j}, Velocity={vel_j} m/s")
    print(f"\nRisk Assessment:")
    print(f"  O-field (Collision): {r_o:.4f} [{classify_risk_level(r_o)}]")
    print(f"  S-field (Proximity): {r_s:.4f} [{classify_risk_level(r_s)}]")
    print(f"  Composite (C-SPF):   {r_c:.4f} [{classify_risk_level(r_c)}]")
    
    # ==========================================================================
    # EXAMPLE 2: Safe Parallel Driving (Low O-field, Low S-field)
    # ==========================================================================
    print("\n" + "=" * 80)
    print("Example 2: Safe Parallel Driving")
    print("=" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([20.0, 0.0])
    theta_i = 0.0
    
    pos_j = np.array([10.0, 3.5])
    vel_j = np.array([20.0, 0.0])
    
    r_o = calculate_objective_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j)
    r_s = calculate_subjective_field(pos_i, vel_i, theta_i, pos_j)
    r_c = calculate_composite_risk(r_o, r_s, method='max')
    
    print(f"Ego Vehicle:    Position={pos_i}, Velocity={vel_i} m/s")
    print(f"Target Vehicle: Position={pos_j}, Velocity={vel_j} m/s")
    print(f"\nRisk Assessment:")
    print(f"  O-field (Collision): {r_o:.4f} [{classify_risk_level(r_o)}]")
    print(f"  S-field (Proximity): {r_s:.4f} [{classify_risk_level(r_s)}]")
    print(f"  Composite (C-SPF):   {r_c:.4f} [{classify_risk_level(r_c)}]")
    
    # ==========================================================================
    # EXAMPLE 3: Close Following (Low O-field, High S-field)
    # ==========================================================================
    print("\n" + "=" * 80)
    print("Example 3: Close Following (Same Lane)")
    print("=" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([20.0, 0.0])
    theta_i = 0.0
    
    pos_j = np.array([15.0, 0.0])  # 15m ahead, same lane
    vel_j = np.array([20.0, 0.0])   # Same speed
    
    r_o = calculate_objective_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j)
    r_s, diag = calculate_subjective_field(pos_i, vel_i, theta_i, pos_j, return_diagnostics=True)
    r_c = calculate_composite_risk(r_o, r_s, method='max')
    
    print(f"Ego Vehicle:    Position={pos_i}, Velocity={vel_i} m/s")
    print(f"Target Vehicle: Position={pos_j}, Velocity={vel_j} m/s")
    print(f"\nS-field Details:")
    print(f"  Longitudinal distance: {diag['delta_x']:.2f} m")
    print(f"  Lateral distance:      {diag['delta_y']:.2f} m")
    print(f"  Safety bubble (γ_x):   {diag['gamma_x']:.2f} m")
    print(f"\nRisk Assessment:")
    print(f"  O-field (Collision): {r_o:.4f} [{classify_risk_level(r_o)}] - No collision (same speed)")
    print(f"  S-field (Proximity): {r_s:.4f} [{classify_risk_level(r_s)}] - Too close for comfort!")
    print(f"  Composite (C-SPF):   {r_c:.4f} [{classify_risk_level(r_c)}]")
    
    # ==========================================================================
    # EXAMPLE 4: Stationary Vehicle Ahead (High S-field)
    # ==========================================================================
    print("\n" + "=" * 80)
    print("Example 4: Stationary Vehicle Ahead")
    print("=" * 80)
    
    pos_i = np.array([0.0, 0.0])
    vel_i = np.array([15.0, 0.0])
    theta_i = 0.0
    
    pos_j = np.array([20.0, 0.0])  # 20m ahead
    vel_j = np.array([0.0, 0.0])   # Stationary
    
    r_o = calculate_objective_field(pos_i, vel_i, width_i, pos_j, vel_j, width_j)
    r_s = calculate_subjective_field(pos_i, vel_i, theta_i, pos_j)
    r_c = calculate_composite_risk(r_o, r_s, method='max')
    
    print(f"Ego Vehicle:    Position={pos_i}, Velocity={vel_i} m/s")
    print(f"Target Vehicle: Position={pos_j}, Velocity={vel_j} m/s (STOPPED)")
    print(f"\nRisk Assessment:")
    print(f"  O-field (Collision): {r_o:.4f} [{classify_risk_level(r_o)}]")
    print(f"  S-field (Proximity): {r_s:.4f} [{classify_risk_level(r_s)}]")
    print(f"  Composite (C-SPF):   {r_c:.4f} [{classify_risk_level(r_c)}]")
    
    print("\n" + "=" * 80)
    print("✓ C-SPF implementation complete!")
    print("  - O-field: Physical collision probability")
    print("  - S-field: Driver proximity discomfort")
    print("  - Composite: Combined risk assessment")
    print("=" * 80)

