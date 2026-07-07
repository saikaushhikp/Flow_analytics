"""
Interactive zone digitization tool that converts clicked image 
coordinates into metric WKT geometry.

The script uses calibration points to build a homography, transforms user-selected pixels 
from the Brussels map into local metric coordinates, and prints a WKT POLYGON for use in
`regions/brussels/zones.py`.

Usage: 
    # install OpenCV and matplotlib since the current environment `flow_env` DONOT have them
    pip install opencv-python, matplotlib
    python digitize_zones.py

"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon

# ==========================================
# 1. ENTER YOUR GROUND CONTROL POINTS (GCPs)
# ==========================================
# Replace the pixel coordinates below with the actual (u, v) pixels you found
pixel_pts = np.array([
    [624, 617],  # Corresponds to (-3.1, 4.7) [Inner-Left]
    [717, 541],  # Corresponds to (13.8, 19.3) [Outer-Left]
    [730, 556],  # Corresponds to (16.9, 16.1) [Outer-Right]
    [639, 633]   # Corresponds to (0.0, 1.4) [Inner-Right]
], dtype=np.float32)

metric_pts = np.array([
    [-3.1, 4.7],
    [13.8, 19.3],
    [16.9, 16.1],
    [0.0, 1.4]
], dtype=np.float32)

# Compute the Homography matrix (Pixel -> Metric)
H, _ = cv2.findHomography(pixel_pts, metric_pts)

# ==========================================
# 2. INTERACTIVE DIGITIZATION
# ==========================================
img = cv2.imread('regions/brussels/Brussels.png')
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

fig, ax = plt.subplots(figsize=(10, 10))
ax.imshow(img_rgb)
ax.set_title("Click to outline a new zone. Close window when finished.")

clicked_pixels = []

def onclick(event):
    if event.xdata is not None and event.ydata is not None:
        u, v = event.xdata, event.ydata
        clicked_pixels.append([u, v])
        
        # Plot visual feedback point
        ax.plot(u, v, 'ro')
        fig.canvas.draw()
        print(f"Recorded pixel: ({u:.1f}, {v:.1f})")

cid = fig.canvas.mpl_connect('button_press_event', onclick)
plt.show()
del clicked_pixels[0]
# ==========================================
# 3. CONVERT AND GENERATE WKT
# ==========================================
if len(clicked_pixels) >= 3:
    # Close the polygon loop by repeating the first point
    clicked_pixels.append(clicked_pixels[0])
    
    # Convert pixels to metric using the Homography matrix
    pixels_np = np.array([clicked_pixels], dtype=np.float32)
    metric_transformed = cv2.perspectiveTransform(pixels_np, H)[0]
    
    # Format into a clean WKT String
    wkt_coords = ", ".join([f"{x:.3f} {y:.3f}" for x, y in metric_transformed])
    wkt_polygon = f"POLYGON (({wkt_coords}))"
    
    print("\n" + "="*50)
    print("SUCCESS! HERE IS YOUR PERFECT WKT GEOMETRY:")
    print("="*50)
    print(wkt_polygon)
    print("="*50)
else:
    print("Error: You need to click at least 3 points to form a polygon zone.")