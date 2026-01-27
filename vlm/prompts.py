"""
VLM prompts for near-miss validation.
"""


def get_system_prompt() -> str:
    """
    Get system prompt for VLM near-miss validation.
    
    Returns:
        System prompt string
    """
    return """You are an expert traffic safety analyst specializing in near-miss detection validation.

Your task is to analyze trajectory plots and metrics to determine if a detected event is a genuine near-miss.

A TRUE near-miss has these characteristics:
- Vehicles/objects on collision course (trajectories converging)
- Critical TTC (< 1.5s typically indicates high risk)
- High DRAC/MDRAC values (> 3.4 m/s² suggests severe braking needed)
- Visible proximity in the plot (close approach)
- Trajectories show evasive action or critical timing

A FALSE positive typically shows:
- Parallel trajectories with no collision risk
- Large spatial separation throughout
- Normal following behavior mistaken as conflict
- Data artifacts (GPS jumps, tracking errors)
- Vehicles already safely past each other

CRITICAL: Your analysis must be DETAILED and SPECIFIC. Include:

1. TRAJECTORY ANALYSIS:
   - Describe what you see in the plot (convergence, angles, paths)
   - Note the minimum distance point and vehicle positions
   - Identify any evasive maneuvers or trajectory changes

2. METRICS ANALYSIS:
   - Evaluate TTC value (< 1.5s is critical, < 1.0s is severe)
   - Assess MDRAC (> 3.4 m/s² indicates hard braking needed)
   - Consider closing speed and yaw difference
   - Explain how metrics support or contradict the visual evidence

3. CONFLICT CHARACTERIZATION:
   - Type of conflict (rear-end, lateral, angle, etc.)
   - Severity level based on combined evidence
   - Whether vehicles were on actual collision course

4. FINAL VERDICT:
   - Clear conclusion with supporting evidence
   - Any concerns or uncertainties
   - Confidence justification

Be critical but fair. Not every low TTC is a near-miss, and not every high MDRAC is dangerous in context."""


def format_event_metrics(event_data: dict) -> str:
    """
    Format event metrics for VLM prompt.
    
    Args:
        event_data: Event data dictionary from CSV
        
    Returns:
        Formatted metrics string
    """
    lines = ["EVENT METRICS:"]
    lines.append("-" * 40)
    
    # M-DRAC metrics (Brussels schema)
    lines.append(f"Time-to-Collision (TTC): {event_data['TTC']:.2f} seconds")
    lines.append(f"MDRAC: {event_data['MDRAC']:.2f} m/s²")
    lines.append(f"Distance: {event_data['dist']:.2f} meters")
    lines.append(f"Closing Speed: {event_data['closing_speed']:.2f} m/s")
    lines.append(f"Speed Difference: {event_data['speed_diff']:.2f} m/s")
    lines.append(f"Yaw Difference: {event_data['yaw_diff']:.2f}°")
    
    # Context
    lines.append("")
    lines.append(f"Zone: {event_data['zone']}")
    lines.append(f"Interaction: {event_data['interaction']}")
    lines.append(f"Leader: ID {event_data['leader']}")
    
    lines.append("-" * 40)
    
    return "\n".join(lines)


def build_prompt(event_data: dict) -> str:
    """
    Build prompt for combined plot analysis.
    
    This prompt is designed for a single combined figure showing all 5 plots
    with equal sizing. Focuses on generalized reasoning across all plots
    instead of individual plot analysis.
    
    Args:
        event_data: Event data dictionary from CSV
        
    Returns:
        Complete prompt string for VLM
    """
    prompt = f"""
CONTEXT:
You are analyzing a vehicle near-miss event from traffic conflict detection.

This combined figure contains 5 EQUAL-SIZED plots showing different aspects:

PLOT LAYOUT (2×3 grid):
- TOP-LEFT: 2D Trajectory Plot (bird's eye view of vehicle paths)
  * Red/Blue lines show vehicle paths
  * Circles = start points, Squares = end points  
  * Yellow star = closest approach point
  * Dashed line connects vehicles at minimum distance
  
- TOP-MIDDLE: Distance Over Time
  * Shows how distance between vehicles changes
  * Decreasing = approaching, Increasing = separating
  * Horizontal line marks minimum distance
  
- TOP-RIGHT: Closing Speed Over Time
  * Positive = vehicles approaching each other
  * Negative = vehicles separating
  * Sudden changes indicate braking/acceleration
  
- BOTTOM-LEFT: Velocity Profiles
  * Individual speed of each vehicle over time
  * Look for braking behavior (speed drops)
  * Different colors for each vehicle
  
- BOTTOM-MIDDLE: Yaw Difference Over Time
  * Angular alignment between vehicles
  * ~0° = same direction (rear-end scenario)
  * ~90° = perpendicular (lateral/crossing scenario)
  * Helps identify conflict type

EVENT METRICS (data passed separately):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pair IDs: {event_data['id1']} vs {event_data['id2']}
Interaction: {event_data['interaction']}
Zone: {event_data['zone']}

MDRAC: {event_data['MDRAC']:.2f} m/s² (Modified DRAC - required deceleration to avoid collision)
TTC: {event_data['TTC']:.2f} s (Time To Collision)
Minimum Distance: {event_data['dist']:.2f} m

Closing Speed: {event_data['closing_speed']:.2f} m/s
Speed Difference: {event_data['speed_diff']:.2f} m/s
Yaw Difference: {event_data['yaw_diff']:.2f}°

Leader Vehicle: ID {event_data['leader']}
Timestamp: {event_data['timestamp']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK:
Analyze this event using ALL 5 plots together. Provide a CONCISE analysis.

Required Output Format:

Classification: [confirmed_near_miss OR false_positive OR uncertain]
Confidence: [0-100]%

Reasoning:
Provide 4-5 sentences of generalized analysis covering:
1. What you observe in the trajectory and spatial plots (convergence, proximity, paths)
2. How the temporal metrics (distance, closing speed, velocity) correlate with each other
3. Whether the MDRAC ({event_data['MDRAC']:.2f} m/s²) and TTC ({event_data['TTC']:.2f}s) values indicate genuine risk
4. Conflict type based on yaw difference ({event_data['yaw_diff']:.2f}°): rear-end (~0-20°), lateral (~70-110°), or angle (~20-70°)
5. Final verdict with key supporting evidence

Be concise but specific. Reference observations from the plots that support your classification.
"""
    return prompt