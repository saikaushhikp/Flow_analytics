# Composite Safety Potential Field (C-SPF) Framework
**Documentation & Implementation Guide**

## 1. Executive Summary
The Composite Safety Potential Field (C-SPF) is a risk assessment framework designed to quantify driving safety by integrating two distinct dimensions of risk:
1.  **Subjective Field (S-field):** Models "Driver Discomfort" and psychological pressure caused by spatial intrusion. It captures how drivers proactively maintain a "safety bubble" around their vehicles.
2.  **Objective Field (O-field):** Models "Physical Collision Probability" based on kinematic motion equations. It predicts imminent collision risks regardless of driver perception.

This composite structure allows for the detection of both **Near Misses** (High O-field) and **Aggressive/Unsafe Interactions** (High S-field) that may not result in a collision but trigger evasive maneuvers.

---

# C-SPF Theory: The Subjective Field (Section 3.1)

**Reference Paper:** *Composite Safety Potential Field for Highway Driving Risk Assessment* (Zuo et al., 2025)

## 1. Core Concept: "The Safety Bubble"
The Subjective Field (S-field) does not measure physical collision probability (which is the job of the O-field). Instead, it measures **Driver Discomfort** or **Psychological Pressure**.

The theory posits that every driver proactively maintains a "Safety Space" (or "Safety Bubble") around their vehicle.
* **Outside the Bubble:** Risk $\approx 0$.
* **Inside the Bubble:** Risk increases as the intruder gets closer.
* **Deep Intrusion:** As the distance approaches zero, the psychological pressure (Risk) approaches $1$.

---

## 2. Mathematical Formulation

To model this "bubble" mathematically, the paper uses the **Generalized Gaussian Distribution (GGD)**. Unlike a standard Bell Curve (Normal Distribution), the GGD allows us to tune the "sharpness" of the bubble's edge using a shape parameter ($\beta$).

### 2.1 Vehicle Proximity Risk (Dynamic)

#### A. The 1D Risk Function (Eq. 2)
First, consider the risk in a single dimension (e.g., just the following distance).

$$
r_{s,ij}^{1D} = \exp\left(-\left|\frac{\Delta x_{ij}}{\gamma}\right|^\beta\right)
$$

* **$\Delta x_{ij}$**: The absolute relative distance between the ego vehicle and the other object.
* **$\gamma$ (Gamma) - The Scale Factor**: Represents the **Radius of the Bubble**.
    * This is the "Critical Safety Distance."
    * When $\Delta x = \gamma$, the risk is exactly $e^{-1} \approx 0.37$ (the tipping point).
* **$\beta$ (Beta) - The Shape Factor**: Represents the **Hardness of the Bubble**.
    * Lower $\beta$ (e.g., 2): Smooth gradient (Normal distribution). Risk rises gradually.
    * Higher $\beta$ (e.g., 8+): "Boxy" shape. Risk is low until the limit is reached, then spikes.

#### B. The 2D Risk Function (Eq. 3)
Since driving occurs in two dimensions, we combine the longitudinal (front/back) and lateral (left/right) risks.

$$
r_{s,ij}^{v} = \exp\left(-\left|\frac{\Delta x_{ij}}{\gamma_x}\right|^{\beta_x} - \left|\frac{\Delta y_{ij}}{\gamma_y}\right|^{\beta_y}\right)
$$

* **$\gamma_x$ vs $\gamma_y$**:
    * **$\gamma_x$ (Longitudinal):** Typically large (e.g., 30m+ at highway speeds). Drivers need a lot of forward space.
    * **$\gamma_y$ (Lateral):** Typically small (e.g., ~1.5m). Drivers tolerate cars being close to their side.
    * *Result:* The safety bubble is an elongated ellipse.
* **$\beta_x$ vs $\beta_y$**: allows the model to have different sensitivities for front vs. side intrusions.

---

### 2.2 Static Environment Risk
Drivers also perceive risk from static road features, specifically lane markers and physical boundaries (walls/guardrails).

#### A. Lane Marker Risk (Eq. 4)
Risk caused by drifting too close to a lane line.

$$
r_{s,aj}^{l} = \exp\left(-\left|\frac{\Delta y_{aj}}{\gamma_{l}}\right|^{\beta_{l}}\right)
$$

* **$\Delta y_{aj}$**: Lateral distance to the lane marker.
* **$\gamma_l$**: Distance at which the driver feels uncomfortable drifting.

#### B. Road Boundary Risk (Eq. 5)
Risk caused by drifting close to a physical barrier (which is scarier than a painted line).

$$
r_{s,kj}^{b} = \exp\left(-\left|\frac{\Delta y_{kj}}{\gamma_{b}}\right|^{\beta_{b}}\right)
$$

* **Note:** Typically $\gamma_b > \gamma_l$, meaning the "danger zone" for a wall starts further away than for a lane line.

---

## 3. Parameter Influencing Factors (Section 3.1.4)
The paper explicitly identifies **Absolute Velocity** as the primary factor influencing the shape of the safety bubble.

1.  **Longitudinal Scale ($\gamma_x$):**
    * **Expands with Speed:** As velocity ($v$) increases, $\gamma_x$ increases significantly. You need more braking distance at high speeds.
    * *Implementation Note:* While the paper uses a cubic polynomial fit, a robust heuristic is the **2-Second Rule** ($\gamma_x \approx 2.0 \times v$).
2.  **Lateral Scale ($\gamma_y$):**
    * **Constant with Speed:** The paper finds that $\gamma_y$ stays relatively constant regardless of speed. Drivers always desire a small lateral buffer (~1.4m - 1.5m).

---

## 4. Aggregated Subjective Risk (Eq. 10)
In a real scenario, a driver might be facing multiple risks simultaneously (e.g., a car in front AND a truck to the side). The Total Subjective Risk ($r_{s,j}$) is the probability that *at least one* entity is intruding on the safety space.

$$
r_{s,j} = 1 - \left[ \prod_{i=1}^{N_{j}^{v}}(1 - r_{s,ij}^{v}) \cdot \prod_{a=1}^{N_{j}^{l}}(1 - \kappa_{l}r_{s,aj}^{l}) \cdot \prod_{k=1}^{N_{j}^{b}}(1 - \kappa_{b}r_{s,kj}^{b}) \right]
$$

* **The Logic:** We calculate the "Probability of Safety" for each object ($(1 - r)$) and multiply them.
    * If Car A is safe (0.9) and Car B is safe (0.9), Total Safety = $0.81$.
    * Total Risk = $1 - 0.81 = 0.19$.
* **$\kappa$ (Kappa):** Weighting coefficients ($0 < \kappa < 1$) used to reduce the impact of lane markers compared to physical vehicles (since crossing a line is less dangerous than hitting a car).
---

# C-SPF Theory: The Objective Field (Section 3.2)

**Reference Paper:** *Composite Safety Potential Field for Highway Driving Risk Assessment* (Zuo et al., 2025)

## 1. Core Concept: "The Physics of Collision"
The Objective Field (O-field) measures the **Physical Probability of Collision**. unlike the S-field (which measures driver discomfort), the O-field is purely kinematic. It predicts whether two vehicles will physically occupy the same space at the same time based on their current motion trajectories.

* **S-field:** "I feel unsafe."
* **O-field:** "A crash is mathematically imminent."

---

## 2. General Formulation (Eq. 11)
The O-field risk is defined as the product of two independent factors:
1.  **Spatial Proximity ($P_{ij}$):** Will the trajectories cross?
2.  **Temporal Proximity ($T_{ij}$):** Is there enough time to react?

$$
r_{o,ij} = P_{ij} \cdot T_{ij}
$$

### 2.1 Spatial Factor (Eq. 12)
Measures the risk based on the *predicted minimum future distance* ($\hat{d}_{m,ij}$) between two vehicles.

$$
P_{ij} = \exp\left[-\left(\frac{\hat{d}_{m,ij}}{d^{*}}\right)^{\beta_{p}}\right]
$$

* **$\hat{d}_{m,ij}$**: The smallest distance the two vehicles will ever reach if they continue on current paths.
* **$d^{*}$ (Collision Threshold)**: The physical boundary for collision.
    * *Implementation:* Typically set to the average width of the two vehicles: $0.5 \times (w_i + w_j)$.
* **$\beta_p$**: Shape factor (typically high, e.g., 10) to create a sharp "Hit or Miss" boundary.

### 2.2 Temporal Factor (Eq. 15)
Measures the risk based on the *time until* that minimum distance is reached ($\hat{t}_{m,ij}$).

$$
T_{ij} = \exp\left[-\left(\frac{\hat{t}_{m,ij}}{t^{*}}\right)^{\beta_{t}}\right]
$$

* **$\hat{t}_{m,ij}$**: The time (in seconds) until the "miss" or "crash" occurs.
* **$t^{*}$ (Time Horizon)**: The look-ahead limit (e.g., 7.5 seconds).
    * Collision risks further away than $t^*$ are considered negligible (Risk $\to$ 0).

---

## 3. Simplified Implementation (Constant Velocity)
To avoid computationally expensive trajectory simulations, the paper derives a **Closed-Form Solution** assuming vehicles maintain constant velocity for the short prediction horizon. This allows for instantaneous risk calculation using Vector Algebra.

### 3.1 Vector Definitions
* **$D_{ij}$**: Relative Position Vector ($[x_i - x_j, y_i - y_j]^T$).
* **$V_{ij}$**: Relative Velocity Vector ($[v_{xi} - v_{xj}, v_{yi} - v_{yj}]^T$).
* **$\hat{V}_{ij}$**: Normalized Relative Velocity Vector ($V_{ij} / |V_{ij}|$).
* **$A$**: Transformation Matrix $\begin{bmatrix} 0 & 1 \\ -1 & 0 \end{bmatrix}$.

### 3.2 The Master Equation (Eq. 19)
Substituting the vector derivations into the general formula yields the final implementable equation:

$$
r_{o,ij} = 
\begin{cases} 
1 & \text{if } |D_{ij}| = 0 \\
\underbrace{\exp\left[-\left(\frac{1}{d^{*}} |D_{ij}^{T} A \hat{V}_{ij}|\right)^{\beta_{p}}\right]}_{\text{Spatial Part}} \cdot \underbrace{\exp\left[-\left(\frac{1}{t^{*}} \frac{-D_{ij}^{T}V_{ij}}{|V_{ij}|^2}\right)^{\beta_{p}}\right]}_{\text{Temporal Part}} & \text{if } D_{ij}^{T}V_{ij} < 0 \\
0 & \text{otherwise}
\end{cases}
$$

**Logic Check:**
* **$D_{ij}^{T}V_{ij} < 0$**: This dot product check ensures risk is only calculated if vehicles are **approaching** each other. If they are moving apart, Risk = 0.

---

## 4. Aggregated Objective Risk (Eq. 20)
In multi-vehicle scenarios, the total objective risk for the ego vehicle ($j$) is the aggregated probability of colliding with *any* surrounding vehicle ($i$).

$$
r_{o,j} = 1 - \sum_{i \in N_j} (1 - r_{o,ij})
$$

---

## 5. Parameter Guidelines (Section 4.2.2)
Based on the highD dataset calibration:

* **$\beta_p$ (Spatial Shape):** Set to **10**.
    * *Reason:* Collision is binary. You either hit or you don't. A high beta makes the risk function act like a steep step function.
* **$\beta_t$ (Temporal Shape):** Set to **2**.
    * *Reason:* Time pressure increases quadratically as the deadline approaches.
* **$t^*$ (Time Horizon):** Set to **7.5 seconds**.
    * *Reason:* Represents the 5th percentile of positive TTC values; a generous reaction horizon.
* **$d^*$ (Collision Distance):** Set to **$0.5 \times (w_{ego} + w_{target})$**.
    * *Reason:* Explicit physical width overlap.

## 5. Risk Interpretation & Thresholds
**When does "Risk" become "Danger"?**

The C-SPF model outputs continuous risk values between $0$ and $1$. For binary decision-making (e.g., "Near Miss Detected" or "Warning Triggered"), the paper establishes a critical threshold.

### 5.1 The Critical Threshold ($e^{-1}$)
The paper consistently identifies **$e^{-1} \approx 0.368$** as the critical tipping point for both fields.

* **S-field:** When risk $> e^{-1}$, it indicates the intruder has breached the "Critical Safety Distance" ($\gamma$). The paper observes that drivers typically initiate evasive maneuvers (braking or steering) when the risk crosses this threshold.
* **O-field:** When risk $> e^{-1}$, it indicates a collision is not only geometrically possible but effectively imminent within the critical time horizon.

**Implementation Rule:**
* **Safe / Normal:** Risk $< 0.37$
* **Warning / Near-Miss:** Risk $\ge 0.37$

---

## 6. Implementation Notes & Constants Summary

### 6.1 Coordinate Transformation Matrix
The O-field calculation (Eq. 18 & 19) relies on a rotation matrix $A$ to project the distance vector perpendicular to the velocity vector (calculating the "miss distance").

$$
A = \begin{bmatrix} 
0 & 1 \\ 
-1 & 0 
\end{bmatrix}
$$

**Usage in Code:**
When calculating the term $D_{ij}^T A \hat{V}_{ij}$:
1.  Let $D_{ij} = [dx, dy]^T$
2.  Let $\hat{V}_{ij} = [vx, vy]^T$ (Normalized)
3.  $A \cdot \hat{V}_{ij} = [vy, -vx]^T$
4.  Dot Product: $dx \cdot vy - dy \cdot vx$
*(This is effectively the 2D cross product magnitude)*.


# C-SPF Theory: Parameters & Calibration (Section 4)

**Reference Paper:** *Composite Safety Potential Field for Highway Driving Risk Assessment* (Zuo et al., 2025)

## 1. Parameter Derivation Method
The authors derived these parameters using **Maximum Likelihood Estimation (MLE)** on the **highD dataset** (German Highway Traffic).

* **Logic:** The parameters are tuned such that the "Subjective Risk" is minimized for the most frequently observed natural driving behaviors.
* **Implication:** These values represent the "Safety Culture" of German highway drivers. While they serve as a robust baseline, they may need adjustment for urban environments (where drivers naturally tolerate smaller gaps).

---

## 2. Subjective Field (S-Field) Parameters
The shape of the "Safety Bubble" is defined by Scale ($\gamma$) and Shape ($\beta$) factors.

### 2.1 Longitudinal Parameters (Dynamic)
The safety distance ($\gamma_x$) and sensitivity ($\beta_x$) change dynamically based on the ego vehicle's **Absolute Velocity ($v$)** (in $m/s$).

**A. Scale Factor ($\gamma_x$):**
Determines the length of the safety bubble.
$$
\gamma_x = 5.1053 \times 10^{-4} \cdot v^3 - 3.7051 \times 10^{-2} \cdot v^2 + 1.0621 \cdot v + 1.2925
$$

**B. Shape Factor ($\beta_x$):**
Determines the "hardness" of the longitudinal boundary.
$$
\beta_x = 2.2214 \times 10^{-5} \cdot v^3 - 1.4834 \times 10^{-3} \cdot v^2 + 9.6673 \times 10^{-3} \cdot v + 3.2589
$$

### 2.2 Lateral Parameters (Constant)
Drivers maintain a consistent lateral safety buffer regardless of speed.

| Parameter | Symbol | Value | Description |
| :--- | :---: | :---: | :--- |
| **Lateral Scale** | $\gamma_y$ | **1.4310 m** | Critical side buffer distance. |
| **Lateral Shape** | $\beta_y$ | **4.9956** | High value indicates a sharp risk boundary. |

### 2.3 Static Environment Parameters (Constant)
Risk perception regarding lane markings and physical road boundaries.

| Parameter | Symbol | Value | Description |
| :--- | :---: | :---: | :--- |
| **Lane Marker Scale** | $\gamma_l$ | **1.18 m** | Distance to line causing discomfort. |
| **Lane Marker Shape** | $\beta_l$ | **2.46** | Softer boundary (crossing a line is "okay"). |
| **Boundary Scale** | $\gamma_b$ | **1.64 m** | Distance to wall causing discomfort. |
| **Boundary Shape** | $\beta_b$ | **5.17** | Sharp boundary (hitting a wall is critical). |

---

## 3. Objective Field (O-Field) Parameters
These parameters define the physics-based collision horizon.

| Parameter | Symbol | Value | Logic / Derivation |
| :--- | :---: | :---: | :--- |
| **Spatial Shape** | $\beta_p$ (or $\beta_d$) | **10** | Creates a binary-like "Hit/Miss" boundary. |
| **Temporal Shape** | $\beta_t$ | **2** | Time pressure rises quadratically. |
| **Time Horizon** | $t^*$ (or $\gamma_t$) | **7.5 s** | The 95th percentile of reaction times. |
| **Collision Dist** | $d^*$ (or $\gamma_d$) | $\frac{w_i + w_j}{2}$ | Exact physical overlap distance. |

---

## 4. Risk Interpretation Thresholds
The model outputs a continuous risk probability $r \in [0, 1]$. To interpret this as a distinct event (e.g., "Near Miss"), the paper identifies a critical tipping point.

### The $e^{-1}$ Threshold
$$\text{Critical Risk} \approx 0.3679$$

* **Safe State:** Risk $< 0.3679$
* **Critical State (Warning):** Risk $\ge 0.3679$

> **Note:** In the case studies (Section 4.4), the authors observed that drivers typically initiate evasive maneuvers (braking/steering) exactly when the Subjective Risk crosses this $0.3679$ threshold.