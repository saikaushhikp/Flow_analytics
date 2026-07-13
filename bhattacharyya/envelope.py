"""
Bhattacharyya Envelope Near-Miss Detection Module

Ported from the AGC flowbyagc-main project (flow_post_processing/analytics/near_misses/envelope.py)
and adapted for standalone use in Flow_analytics.

This module implements the O(1) analytical Bhattacharyya Coefficient (BC) as a drop-in
replacement for the O(n^2) numerical grid overlap integration. The BC computes the
collision probability between two Gaussian safety envelopes built from each vehicle's
physical dimensions, heading, and position.

References:
    - AGC flowbyagc-main: flow_post_processing/analytics/near_misses/envelope.py
    - Bhattacharyya (1943): "On a measure of divergence between two statistical populations..."
    - BC ∈ [0, 1], where BC=1 means identical distributions (100% overlap / collision).
    - BC^2 is used as the final `overlap_prob` to approximate the numerical grid integral.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Object label constants (matching Flow_analytics ssm/m_drac.py)
# ---------------------------------------------------------------------------
PEDESTRIAN = 1
BICYCLE = 2
MOTORCYCLE = 3
CAR = 4
ESCOOTER = 5
VAN = 6
TRUCK = 7
BUS = 8

HEAVY_VEHICLES = {VAN, TRUCK, BUS}
TWO_WHEELERS = {BICYCLE, MOTORCYCLE}
VULNERABLE_ROAD_USERS = {PEDESTRIAN, ESCOOTER}


# ---------------------------------------------------------------------------
# Step 1: Compute Safety Envelope Parameters
# ---------------------------------------------------------------------------

def compute_safety_envelope_infos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-vehicle safety envelope parameters (longi_std, lateral_std, heading)
    from size, velocity, and label. Mirrors AGC envelope.py::compute_safety_envelope_infos.

    Inputs (per object suffix _obj1 / _obj2):
        - size_x_{obj}: length of bounding box (m)
        - size_y_{obj}: width of bounding box (m)
        - vel_x_{obj}, vel_y_{obj}: velocity components (m/s)
        - vel_{obj}: speed magnitude (m/s)
        - yaw_{obj}: sensor heading (rad)
        - label_{obj}: object type integer

    Outputs (added columns):
        - heading_{obj}: motion heading (rad), falls back to yaw if nearly static
        - longi_std_{obj}: longitudinal Gaussian std (m) — speed & type scaled
        - lateral_std_{obj}: lateral Gaussian std (m) — type scaled
    """
    df = df.copy()
    for suffix in ["obj1", "obj2"]:
        length = df[f"size_x_{suffix}"].to_numpy()
        width = df[f"size_y_{suffix}"].to_numpy()
        vel_x = df[f"vel_x_{suffix}"].to_numpy()
        vel_y = df[f"vel_y_{suffix}"].to_numpy()
        vel = df[f"vel_{suffix}"].to_numpy()
        yaw = df[f"yaw_{suffix}"].to_numpy()
        label = df[f"label_{suffix}"]

        # Heading: use velocity direction if moving, else fall back to yaw
        heading = np.where(vel > 0.1, np.arctan2(vel_y, vel_x), yaw)

        # Vulnerability factor by object type
        type_factor = np.ones(len(df))
        type_factor[label.isin(VULNERABLE_ROAD_USERS)] = 1.5   # pedestrian / e-scooter
        type_factor[label.isin(TWO_WHEELERS)] = 1.3             # bicycle / motorcycle
        type_factor[label.isin(HEAVY_VEHICLES)] = 1.0           # van / truck / bus

        # Speed factor: envelopes grow with speed (10% per √(m/s) unit)
        speed_factor = 1.0 + np.sqrt(np.maximum(vel, 0)) * 0.2

        # Gaussian standard deviations
        forward_size = np.maximum(1.0, length) * type_factor * speed_factor
        sideways_size = np.maximum(0.8, width) * type_factor

        df[f"heading_{suffix}"] = heading
        df[f"longi_std_{suffix}"] = forward_size * 0.5
        df[f"lateral_std_{suffix}"] = sideways_size * 0.5

    return df


# ---------------------------------------------------------------------------
# Step 2: Covariance Matrix Construction
# ---------------------------------------------------------------------------

def _build_covariance_matrices(
    longi: np.ndarray,
    lateral: np.ndarray,
    heading: np.ndarray,
    epsilon: float = 1e-6,
) -> np.ndarray:
    """
    Vectorised construction of N rotation-aware 2x2 covariance matrices.
    Shape: (N, 2, 2)

    cov = R @ diag([longi², lateral²]) @ R.T + epsilon*I
    where R = [[cos(θ), -sin(θ)], [sin(θ), cos(θ)]]
    """
    N = len(longi)
    cos_t = np.cos(heading)
    sin_t = np.sin(heading)

    rot = np.zeros((N, 2, 2))
    rot[:, 0, 0] = cos_t
    rot[:, 0, 1] = -sin_t
    rot[:, 1, 0] = sin_t
    rot[:, 1, 1] = cos_t

    diag = np.zeros((N, 2, 2))
    diag[:, 0, 0] = longi ** 2
    diag[:, 1, 1] = lateral ** 2

    cov = rot @ diag @ np.transpose(rot, (0, 2, 1))
    cov += np.eye(2)[None, :, :] * epsilon
    return cov


# ---------------------------------------------------------------------------
# Step 3: Bhattacharyya Coefficient (Vectorised)
# ---------------------------------------------------------------------------

def compute_bc_vectorized(df: pd.DataFrame, cov_epsilon: float = 1e-6) -> np.ndarray:
    """
    Compute BC² (Bhattacharyya Coefficient squared) for all pairs in df.

    BC = exp(-D_B) where D_B is the Bhattacharyya distance between two 2D Gaussians.
    BC² empirically approximates the numerical grid-integration overlap area (see AGC code).

    Pairs with inter-centre distance > 4 * max_std are short-circuited to 0.0
    (no meaningful overlap possible).

    Formula:
        D_B = (1/8) * (μ₁-μ₂)ᵀ Σ⁻¹ (μ₁-μ₂)  +  (1/2) * ln(det(Σ) / √(det(Σ₁)·det(Σ₂)))
        where Σ = (Σ₁ + Σ₂) / 2

    Returns:
        overlap_approx: np.ndarray of shape (N,), values in [0, 1]
    """
    if len(df) == 0:
        return np.array([])

    longi1 = df["longi_std_obj1"].values
    lateral1 = df["lateral_std_obj1"].values
    heading1 = df["heading_obj1"].values
    pos1 = df[["pos_x_obj1", "pos_y_obj1"]].values

    longi2 = df["longi_std_obj2"].values
    lateral2 = df["lateral_std_obj2"].values
    heading2 = df["heading_obj2"].values
    pos2 = df[["pos_x_obj2", "pos_y_obj2"]].values

    cov1 = _build_covariance_matrices(longi1, lateral1, heading1, cov_epsilon)
    cov2 = _build_covariance_matrices(longi2, lateral2, heading2, cov_epsilon)

    # Average covariance
    Sigma = (cov1 + cov2) / 2.0
    diff = pos1 - pos2  # (N, 2)

    # Invert Sigma  (robust to singular matrices via epsilon regularization)
    try:
        inv_Sigma = np.linalg.inv(Sigma)
    except np.linalg.LinAlgError:
        inv_Sigma = np.linalg.inv(Sigma + np.eye(2)[None] * cov_epsilon)

    # Term 1: Mahalanobis component — (1/8) * diff^T * Sigma^-1 * diff
    tmp = inv_Sigma @ diff[:, :, None]           # (N, 2, 1)
    term1 = 0.125 * (diff[:, None, :] @ tmp)[:, 0, 0]  # (N,)

    # Term 2: Determinant ratio component
    det_Sigma = np.maximum(np.linalg.det(Sigma), cov_epsilon)
    det_cov1 = np.maximum(np.linalg.det(cov1), cov_epsilon)
    det_cov2 = np.maximum(np.linalg.det(cov2), cov_epsilon)
    term2 = 0.5 * np.log(det_Sigma / np.sqrt(det_cov1 * det_cov2))

    # Bhattacharyya Coefficient
    D_B = term1 + term2
    BC = np.exp(-D_B)

    # BC² approximates the numerical grid integral (empirical finding from AGC)
    overlap_approx = BC ** 2

    # Short-circuit pairs that are too far apart
    dist = np.linalg.norm(diff, axis=1)
    max_std = np.maximum.reduce([longi1, lateral1, longi2, lateral2])
    mask = dist <= 4 * max_std

    return np.where(mask, overlap_approx, 0.0)


# ---------------------------------------------------------------------------
# Step 4: Full Envelope Near-Miss Detection
# ---------------------------------------------------------------------------

def get_envelope_near_misses(
    pairs_df: pd.DataFrame,
    prob_thresh: float = 0.05,
    time_horizon_s: float = 3.0,
    time_steps: int = 30,
    uncertainty_growth_per_s: float = 0.1,
    cov_epsilon: float = 1e-6,
) -> pd.DataFrame:
    """
    Run the full envelope near-miss pipeline on a pairs DataFrame.

    1. Build safety envelopes for both objects.
    2. Compute BC overlap at t=0 and at future time steps (linear projection with
       growing uncertainty).
    3. Keep the time horizon that maximises BC overlap for each pair-timestamp.
    4. Filter pairs where max overlap_prob >= prob_thresh.

    Args:
        pairs_df: DataFrame with columns for pos_x/y, vel_x/y, size_x/y, yaw, vel, label
                  (suffixed _obj1 / _obj2), plus timestamp, id_obj1, id_obj2.
        prob_thresh: Minimum BC² value to flag as a near-miss.
        time_horizon_s: How far into the future to project envelopes (seconds).
        time_steps: Number of time steps in [0, time_horizon_s].
        uncertainty_growth_per_s: Fractional std growth per second (default 10%).
        cov_epsilon: Regularisation added to all covariance matrices.

    Returns:
        DataFrame of detected near-misses with columns:
            timestamp, id_obj1, id_obj2, label_obj1, label_obj2,
            pos_x_obj1, pos_y_obj1, pos_x_obj2, pos_y_obj2,
            vel_obj1, vel_obj2, rel_dist, rel_vel,
            bc_overlap_prob (= max BC²),
            bc_time_horizon, bc_severity_score,
            pair_id
    """
    if pairs_df.empty:
        return pd.DataFrame()

    df = pairs_df.copy()
    df = compute_safety_envelope_infos(df)

    # Store original positions (will be overwritten in future projections)
    df["_pos_x_obj1_t0"] = df["pos_x_obj1"]
    df["_pos_y_obj1_t0"] = df["pos_y_obj1"]
    df["_pos_x_obj2_t0"] = df["pos_x_obj2"]
    df["_pos_y_obj2_t0"] = df["pos_y_obj2"]

    times = np.linspace(0, time_horizon_s, time_steps)
    all_frames = []

    for t in times:
        df_t = df.copy()

        # Project positions linearly with current velocity
        if t > 0:
            df_t["pos_x_obj1"] = df["_pos_x_obj1_t0"] + df["vel_x_obj1"] * t
            df_t["pos_y_obj1"] = df["_pos_y_obj1_t0"] + df["vel_y_obj1"] * t
            df_t["pos_x_obj2"] = df["_pos_x_obj2_t0"] + df["vel_x_obj2"] * t
            df_t["pos_y_obj2"] = df["_pos_y_obj2_t0"] + df["vel_y_obj2"] * t

            # Envelope grows with uncertainty over time
            growth = 1.0 + t * uncertainty_growth_per_s
            df_t["longi_std_obj1"] *= growth
            df_t["lateral_std_obj1"] *= growth
            df_t["longi_std_obj2"] *= growth
            df_t["lateral_std_obj2"] *= growth

        df_t["bc_overlap_prob"] = compute_bc_vectorized(df_t, cov_epsilon)
        df_t["bc_time_horizon"] = t
        all_frames.append(df_t)

    df_all = pd.concat(all_frames, ignore_index=True)

    # For each (id_obj1, id_obj2, timestamp), keep the time-horizon with max overlap
    idx = df_all.groupby(["id_obj1", "id_obj2", "timestamp"])["bc_overlap_prob"].idxmax()
    df_best = df_all.loc[idx].copy()

    # Apply detection threshold
    df_detected = df_best[df_best["bc_overlap_prob"] >= prob_thresh].copy()

    if df_detected.empty:
        return pd.DataFrame()

    # Compute relative distance and velocity at t=0
    dx = df_detected["_pos_x_obj1_t0"] - df_detected["_pos_x_obj2_t0"]
    dy = df_detected["_pos_y_obj1_t0"] - df_detected["_pos_y_obj2_t0"]
    df_detected["rel_dist"] = np.sqrt(dx ** 2 + dy ** 2)

    dvx = df_detected["vel_x_obj1"] - df_detected["vel_x_obj2"]
    dvy = df_detected["vel_y_obj1"] - df_detected["vel_y_obj2"]
    df_detected["rel_vel"] = np.sqrt(dvx ** 2 + dvy ** 2)

    # Vulnerability factor (matching AGC post-processing)
    vulnerability = np.ones(len(df_detected))
    idx_vru = df_detected["label_obj1"].isin(VULNERABLE_ROAD_USERS) | df_detected["label_obj2"].isin(VULNERABLE_ROAD_USERS)
    idx_2w = df_detected["label_obj1"].isin(TWO_WHEELERS) | df_detected["label_obj2"].isin(TWO_WHEELERS)
    vulnerability[idx_vru.values] = 3.0
    vulnerability[idx_2w.values & ~idx_vru.values] = 2.0

    time_factor = 1.0 / (1.0 + df_detected["bc_time_horizon"])
    df_detected["bc_severity_score"] = (
        df_detected["bc_overlap_prob"] * df_detected["rel_vel"] * vulnerability * time_factor / 5.0
    )

    # Create pair_id
    min_ids = np.minimum(df_detected["id_obj1"].values, df_detected["id_obj2"].values)
    max_ids = np.maximum(df_detected["id_obj1"].values, df_detected["id_obj2"].values)
    df_detected["pair_id"] = [f"{a}_{b}" for a, b in zip(min_ids.astype(int), max_ids.astype(int))]

    # Final columns
    keep_cols = [
        "timestamp", "pair_id", "id_obj1", "id_obj2",
        "label_obj1", "label_obj2",
        "pos_x_obj1", "pos_y_obj1", "pos_x_obj2", "pos_y_obj2",
        "vel_x_obj1", "vel_y_obj1", "vel_x_obj2", "vel_y_obj2",
        "size_x_obj1", "size_y_obj1", "size_x_obj2", "size_y_obj2",
        "vel_obj1", "vel_obj2", "rel_dist", "rel_vel",
        "bc_overlap_prob", "bc_time_horizon", "bc_severity_score",
    ]
    keep_cols = [c for c in keep_cols if c in df_detected.columns]

    return df_detected[keep_cols].reset_index(drop=True)
