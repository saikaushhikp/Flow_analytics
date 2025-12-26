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
    
Optimizations:
    - Vectorized NumPy operations (no loops)
    - Numba JIT compilation with parallel processing
    - Batch processing for memory efficiency
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import sys
import os
from tqdm import tqdm
import gc

# Numba for JIT compilation and parallel processing
try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("Warning: Numba not available. Install with 'pip install numba' for 5-10x speedup.")

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ssm.utils import get_spf_pairs, load_config, CONFIG_PATH


# Numerical stability constant
EPSILON = 1e-2


# =============================================================================
# NUMBA JIT COMPILED FUNCTIONS (Parallel Processing)
# =============================================================================

if NUMBA_AVAILABLE:
    @jit(nopython=True, parallel=True, cache=True)
    def _calculate_o_field_batch_numba(
        pos1_x: np.ndarray, pos1_y: np.ndarray,
        vel1_x: np.ndarray, vel1_y: np.ndarray,
        width1: np.ndarray,
        pos2_x: np.ndarray, pos2_y: np.ndarray,
        vel2_x: np.ndarray, vel2_y: np.ndarray,
        width2: np.ndarray,
        beta_p: float, beta_t: float, t_star: float
    ) -> np.ndarray:
        """
        Numba JIT-compiled O-field calculation for all pairs in parallel.
        Uses prange for automatic parallelization across CPU cores.
        """
        n = len(pos1_x)
        result = np.zeros(n, dtype=np.float64)
        
        for i in prange(n):
            # Relative kinematics
            dx = pos2_x[i] - pos1_x[i]
            dy = pos2_y[i] - pos1_y[i]
            dvx = vel2_x[i] - vel1_x[i]
            dvy = vel2_y[i] - vel1_y[i]
            
            # Edge case: same position
            d_mag = np.sqrt(dx*dx + dy*dy)
            if d_mag < EPSILON:
                result[i] = 1.0
                continue
            
            # Edge case: no relative motion
            v_mag_sq = dvx*dvx + dvy*dvy
            if v_mag_sq < EPSILON:
                result[i] = 0.0
                continue
            
            # Check if approaching (Δv · Δr < 0)
            d_dot_v = dx*dvx + dy*dvy
            if d_dot_v >= 0:
                result[i] = 0.0
                continue
            
            # Miss distance (perpendicular distance)
            cross = dx * dvy - dy * dvx
            d_min = abs(cross) / np.sqrt(v_mag_sq)
            
            # Time to closest point
            t_min = -d_dot_v / v_mag_sq
            
            # Spatial and temporal risk
            d_star = 0.5 * (width1[i] + width2[i])
            P_ij = np.exp(-((d_min / d_star) ** beta_p))
            T_ij = np.exp(-((t_min / t_star) ** beta_t))
            
            result[i] = P_ij * T_ij
        
        return result

    @jit(nopython=True, parallel=True, cache=True)
    def _calculate_s_field_batch_numba(
        pos1_x: np.ndarray, pos1_y: np.ndarray,
        vel1_x: np.ndarray, vel1_y: np.ndarray,
        theta1: np.ndarray,
        pos2_x: np.ndarray, pos2_y: np.ndarray,
        gamma_y: float, beta_y: float
    ) -> np.ndarray:
        """
        Numba JIT-compiled S-field calculation for all pairs in parallel.
        """
        n = len(pos1_x)
        result = np.zeros(n, dtype=np.float64)
        
        for i in prange(n):
            # Relative position
            dx = pos2_x[i] - pos1_x[i]
            dy = pos2_y[i] - pos1_y[i]
            d_mag = np.sqrt(dx*dx + dy*dy)
            
            if d_mag < EPSILON:
                result[i] = 1.0
                continue
            
            # Ego speed
            v_ego = np.sqrt(vel1_x[i]*vel1_x[i] + vel1_y[i]*vel1_y[i])
            
            # Ego's local coordinate axes
            if v_ego > EPSILON:
                e_long_x = vel1_x[i] / v_ego
                e_long_y = vel1_y[i] / v_ego
                e_lat_x = -vel1_y[i] / v_ego
                e_lat_y = vel1_x[i] / v_ego
            else:
                e_long_x = np.cos(theta1[i])
                e_long_y = np.sin(theta1[i])
                e_lat_x = -np.sin(theta1[i])
                e_lat_y = np.cos(theta1[i])
            
            # Project onto ego's frame
            delta_x = dx * e_long_x + dy * e_long_y
            delta_y = dx * e_lat_x + dy * e_lat_y
            
            # Speed-dependent gamma_x and beta_x (polynomial approximation)
            gamma_x = (5.1053e-4 * v_ego**3 
                      - 3.7051e-2 * v_ego**2 
                      + 1.0621 * v_ego 
                      + 1.2925)
            beta_x = (2.2214e-5 * v_ego**3 
                     - 1.4834e-3 * v_ego**2 
                     + 9.6673e-3 * v_ego 
                     + 3.2589)
            
            # S-field calculation
            term_x = (abs(delta_x) / gamma_x) ** beta_x
            term_y = (abs(delta_y) / gamma_y) ** beta_y
            
            result[i] = np.exp(-(term_x + term_y))
        
        return result


# =============================================================================
# VECTORIZED NUMPY FUNCTIONS (Fallback when Numba not available)
# =============================================================================

def _calculate_o_field_batch_numpy(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    width1: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    vel2_x: np.ndarray, vel2_y: np.ndarray,
    width2: np.ndarray,
    beta_p: float, beta_t: float, t_star: float
) -> np.ndarray:
    """
    Fully vectorized O-field calculation using NumPy.
    No loops - processes all pairs in single array operations.
    """
    # Relative kinematics (all vectorized)
    dx = pos2_x - pos1_x
    dy = pos2_y - pos1_y
    dvx = vel2_x - vel1_x
    dvy = vel2_y - vel1_y
    
    # Distance magnitude
    d_mag = np.sqrt(dx**2 + dy**2)
    
    # Relative velocity magnitude squared
    v_mag_sq = dvx**2 + dvy**2
    
    # Dot product for approach check
    d_dot_v = dx*dvx + dy*dvy
    
    # Initialize result array
    result = np.zeros(len(pos1_x), dtype=np.float64)
    
    # Mask for valid calculations
    valid_mask = (d_mag >= EPSILON) & (v_mag_sq >= EPSILON) & (d_dot_v < 0)
    
    # Same position -> risk = 1.0
    result[d_mag < EPSILON] = 1.0
    
    # Calculate only for valid pairs (approaching, non-zero motion)
    if np.any(valid_mask):
        # Miss distance
        cross = dx[valid_mask] * dvy[valid_mask] - dy[valid_mask] * dvx[valid_mask]
        d_min = np.abs(cross) / np.sqrt(v_mag_sq[valid_mask])
        
        # Time to closest point
        t_min = -d_dot_v[valid_mask] / v_mag_sq[valid_mask]
        
        # Spatial and temporal risk
        d_star = 0.5 * (width1[valid_mask] + width2[valid_mask])
        P_ij = np.exp(-((d_min / d_star) ** beta_p))
        T_ij = np.exp(-((t_min / t_star) ** beta_t))
        
        result[valid_mask] = P_ij * T_ij
    
    return result


def _calculate_s_field_batch_numpy(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    theta1: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    gamma_y: float, beta_y: float
) -> np.ndarray:
    """
    Fully vectorized S-field calculation using NumPy.
    No loops - processes all pairs in single array operations.
    """
    # Relative position
    dx = pos2_x - pos1_x
    dy = pos2_y - pos1_y
    d_mag = np.sqrt(dx**2 + dy**2)
    
    # Ego speed
    v_ego = np.sqrt(vel1_x**2 + vel1_y**2)
    
    # Initialize result
    result = np.zeros(len(pos1_x), dtype=np.float64)
    
    # Same position -> risk = 1.0
    result[d_mag < EPSILON] = 1.0
    
    # Valid pairs (non-zero distance)
    valid_mask = d_mag >= EPSILON
    
    if np.any(valid_mask):
        # Extract valid data
        v = v_ego[valid_mask]
        dx_v = dx[valid_mask]
        dy_v = dy[valid_mask]
        theta_v = theta1[valid_mask]
        vel1_x_v = vel1_x[valid_mask]
        vel1_y_v = vel1_y[valid_mask]
        
        # Moving vs stationary mask
        moving = v > EPSILON
        
        # Local coordinate axes
        e_long_x = np.where(moving, vel1_x_v / np.maximum(v, EPSILON), np.cos(theta_v))
        e_long_y = np.where(moving, vel1_y_v / np.maximum(v, EPSILON), np.sin(theta_v))
        e_lat_x = np.where(moving, -vel1_y_v / np.maximum(v, EPSILON), -np.sin(theta_v))
        e_lat_y = np.where(moving, vel1_x_v / np.maximum(v, EPSILON), np.cos(theta_v))
        
        # Project onto ego's frame
        delta_x = dx_v * e_long_x + dy_v * e_long_y
        delta_y = dx_v * e_lat_x + dy_v * e_lat_y
        
        # Speed-dependent gamma_x and beta_x
        gamma_x = (5.1053e-4 * v**3 
                  - 3.7051e-2 * v**2 
                  + 1.0621 * v 
                  + 1.2925)
        beta_x = (2.2214e-5 * v**3 
                 - 1.4834e-3 * v**2 
                 + 9.6673e-3 * v 
                 + 3.2589)
        
        # S-field calculation
        term_x = (np.abs(delta_x) / gamma_x) ** beta_x
        term_y = (np.abs(delta_y) / gamma_y) ** beta_y
        
        result[valid_mask] = np.exp(-(term_x + term_y))
    
    return result


# =============================================================================
# DISPATCHER FUNCTIONS (Choose best available method)
# =============================================================================

def calculate_o_field_batch(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    width1: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    vel2_x: np.ndarray, vel2_y: np.ndarray,
    width2: np.ndarray,
    beta_p: float, beta_t: float, t_star: float
) -> np.ndarray:
    """
    Calculate O-field for all pairs using best available method.
    Uses Numba JIT if available (5-10x faster), otherwise falls back to NumPy.
    """
    if NUMBA_AVAILABLE:
        return _calculate_o_field_batch_numba(
            pos1_x.astype(np.float64), pos1_y.astype(np.float64),
            vel1_x.astype(np.float64), vel1_y.astype(np.float64),
            width1.astype(np.float64),
            pos2_x.astype(np.float64), pos2_y.astype(np.float64),
            vel2_x.astype(np.float64), vel2_y.astype(np.float64),
            width2.astype(np.float64),
            beta_p, beta_t, t_star
        )
    else:
        return _calculate_o_field_batch_numpy(
            pos1_x, pos1_y, vel1_x, vel1_y, width1,
            pos2_x, pos2_y, vel2_x, vel2_y, width2,
            beta_p, beta_t, t_star
        )


def calculate_s_field_batch(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    theta1: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    gamma_y: float, beta_y: float
) -> np.ndarray:
    """
    Calculate S-field for all pairs using best available method.
    Uses Numba JIT if available (5-10x faster), otherwise falls back to NumPy.
    """
    if NUMBA_AVAILABLE:
        return _calculate_s_field_batch_numba(
            pos1_x.astype(np.float64), pos1_y.astype(np.float64),
            vel1_x.astype(np.float64), vel1_y.astype(np.float64),
            theta1.astype(np.float64),
            pos2_x.astype(np.float64), pos2_y.astype(np.float64),
            gamma_y, beta_y
        )
    else:
        return _calculate_s_field_batch_numpy(
            pos1_x, pos1_y, vel1_x, vel1_y, theta1,
            pos2_x, pos2_y, gamma_y, beta_y
        )


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
    
    def detect(self, data: pd.DataFrame, is_pairs_data: bool = False, batch_size: int = 50000) -> pd.DataFrame:
        """
        Main detection pipeline for SPF conflicts.
        
        ⚡ OPTIMIZED: Batch processing for memory efficiency on large datasets.
        Processes pairs in chunks to avoid memory overflow while maintaining
        vectorized operations within each batch.
        
        Pipeline:
            1. Get filtered pairs (approaching, all conflict types) - SKIPPED if is_pairs_data=True
            2. Process in batches:
               - Calculate O-field and S-field
               - Calculate composite C-SPF risk
               - Filter by minimum threshold
               - Classify severity
            3. Combine results and format output
        
        Args:
            data: Vehicle data (id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel, yaw)
                  OR pre-filtered pairs DataFrame (timestamp, id1, id2, pos_x1, vel_x1, ...)
            is_pairs_data: If True, data is already pairs (skip pair generation).
                          If False, data is vehicle data (default - backward compatible).
            batch_size: Number of pairs to process at once (default 50k)
            
        Returns:
            DataFrame with columns: timestamp, pair_id, zone, conflict_type, interaction,
            distance, ttc, closing_speed, o_field, s_field, composite_risk, severity
            
        Usage:
            # Traditional (generates pairs internally):
            conflicts = detector.detect(vehicle_df)
            
            # Optimized (reuse base pairs):
            pairs = get_spf_pairs(vehicle_df, config)
            conflicts = detector.detect(pairs, is_pairs_data=True)
        """
        # Step 1: Get SPF-specific pairs (with skip flag)
        pairs = get_spf_pairs(data, self.config, skip_pair_generation=is_pairs_data)
        
        if len(pairs) == 0:
            return self._empty_output()
        
        n_pairs = len(pairs)
        print(f"  Processing {n_pairs:,} pairs in batches of {batch_size:,}...")
        
        # Step 2-5: Process in batches
        result_chunks = []
        n_batches = (n_pairs + batch_size - 1) // batch_size
        
        for i in tqdm(range(0, n_pairs, batch_size), total=n_batches, desc="  SPF calculation"):
            batch = pairs.iloc[i:i+batch_size].copy()
            
            # Calculate O-field and S-field (vectorized)
            batch = self.calculate_fields(batch)
            
            # Calculate composite risk (vectorized)
            batch = self.calculate_composite(batch)
            
            # Filter by minimum threshold (early rejection for memory savings)
            batch = batch[batch['composite_risk'] >= self.min_risk]
            
            if len(batch) > 0:
                # Classify severity (vectorized)
                batch = self.classify_severity(batch)
                result_chunks.append(batch)
            
            # Memory cleanup
            del batch
        
        # Cleanup original pairs
        del pairs
        gc.collect()
        
        # Combine all batches
        if len(result_chunks) == 0:
            return self._empty_output()
        
        all_results = pd.concat(result_chunks, ignore_index=True)
        del result_chunks
        gc.collect()
        
        print(f"  ✓ {len(all_results):,} conflicts detected")
        
        # Step 6: Format output
        return self.format_output(all_results)
    
    def calculate_fields(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate O-field and S-field for all pairs.
        
        ⚡ OPTIMIZED: Uses vectorized NumPy/Numba batch processing.
        - Numba JIT: ~5-10x faster with parallel processing
        - NumPy fallback: ~50-100x faster than iterrows loop
        
        Args:
            pairs: DataFrame from get_spf_pairs()
            
        Returns:
            DataFrame with added columns: o_field, s_field
        """
        if len(pairs) == 0:
            pairs = pairs.copy()
            pairs['o_field'] = []
            pairs['s_field'] = []
            return pairs
        
        # Extract arrays for vectorized calculation
        # Note: Column names are pos_x1, pos_y1, etc. (suffix comes after underscore)
        pos1_x = pairs['pos_x1'].values
        pos1_y = pairs['pos_y1'].values
        vel1_x = pairs['vel_x1'].values
        vel1_y = pairs['vel_y1'].values
        pos2_x = pairs['pos_x2'].values
        pos2_y = pairs['pos_y2'].values
        vel2_x = pairs['vel_x2'].values
        vel2_y = pairs['vel_y2'].values
        
        # Vehicle widths (default 1.8m if not available)
        width1 = pairs['width1'].values if 'width1' in pairs.columns else np.full(len(pairs), 1.8)
        width2 = pairs['width2'].values if 'width2' in pairs.columns else np.full(len(pairs), 1.8)
        
        # Heading (yaw) for S-field
        theta1 = pairs['yaw1'].values if 'yaw1' in pairs.columns else np.zeros(len(pairs))
        
        # Calculate O-field (vectorized)
        o_risks = calculate_o_field_batch(
            pos1_x, pos1_y, vel1_x, vel1_y, width1,
            pos2_x, pos2_y, vel2_x, vel2_y, width2,
            self.o_params['beta_p'],
            self.o_params['beta_t'],
            self.o_params['t_star']
        )
        
        # Calculate S-field (vectorized)
        s_risks = calculate_s_field_batch(
            pos1_x, pos1_y, vel1_x, vel1_y, theta1,
            pos2_x, pos2_y,
            self.s_params['gamma_y'],
            self.s_params['beta_y']
        )
        
        pairs = pairs.copy()
        pairs['o_field'] = o_risks
        pairs['s_field'] = s_risks
        
        return pairs
    
    def calculate_composite(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate composite C-SPF risk from O-field and S-field.
        
        ⚡ OPTIMIZED: Uses vectorized NumPy operations instead of apply().
        
        Args:
            pairs: DataFrame with o_field and s_field columns
            
        Returns:
            DataFrame with added column: composite_risk
        """
        pairs = pairs.copy()
        
        o_vals = pairs['o_field'].values
        s_vals = pairs['s_field'].values
        
        if self.composite_method == 'max':
            pairs['composite_risk'] = np.maximum(o_vals, s_vals)
        elif self.composite_method == 'probabilistic':
            pairs['composite_risk'] = 1.0 - (1.0 - o_vals) * (1.0 - s_vals)
        elif self.composite_method == 'weighted':
            pairs['composite_risk'] = (o_vals + s_vals) / 2
        else:
            raise ValueError(f"Unknown method: {self.composite_method}")
        
        return pairs
    
    def classify_severity(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Classify risk severity based on composite risk thresholds.
        
        ⚡ OPTIMIZED: Uses vectorized np.select instead of apply().
        
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
        
        risk = pairs['composite_risk'].values
        
        # Vectorized severity classification using np.select
        conditions = [
            risk >= self.thresholds['critical'],
            risk >= self.thresholds['danger'],
            risk >= self.thresholds['warning']
        ]
        choices = ['CRITICAL', 'DANGER', 'WARNING']
        
        pairs['severity'] = np.select(conditions, choices, default='SAFE')
        
        return pairs
    
    def format_output(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        Format output with clean, human-readable schema.
        
        ⚡ OPTIMIZED: Uses vectorized string operations instead of iterrows.
        
        Schema: timestamp, id1, id2, [label1]_v_[label2], dist, TTC, composite_risk,
                closing_speed, speed_diff, yaw_diff, link
        
        Args:
            pairs: DataFrame with all calculated values
            
        Returns:
            DataFrame with simplified schema for analysis
        """
        # Vectorized interaction string creation
        label1_names = pairs['label1'].map(self.LABEL_NAMES).fillna(pairs['label1'].astype(str))
        label2_names = pairs['label2'].map(self.LABEL_NAMES).fillna(pairs['label2'].astype(str))
        interaction = label1_names + '_v_' + label2_names
        
        # Calculate yaw difference (absolute)
        yaw_diff = np.abs(pairs['yaw1'].values - pairs['yaw2'].values)
        # Normalize to [0, pi]
        yaw_diff = np.where(yaw_diff > np.pi, 2*np.pi - yaw_diff, yaw_diff)
        yaw_diff = np.degrees(yaw_diff)  # Convert to degrees
        
        # Calculate speed difference (absolute)
        speed_diff = np.abs(pairs['vel1'].values - pairs['vel2'].values)
        
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
            'dist': pairs['distance'].values,
            'TTC': pairs['ttc'].values,
            'composite_risk': pairs['composite_risk'].values,
            'closing_speed': pairs['closing_speed'].values,
            'speed_diff': speed_diff,
            'yaw_diff': yaw_diff,
            'link': links.values
        })
        
        return output
    
    def _empty_output(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(columns=[
            'timestamp', 'id1', 'id2', 'interaction', 'dist', 'TTC', 
            'composite_risk', 'closing_speed', 'speed_diff', 'yaw_diff', 'link'
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


