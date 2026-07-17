"""

Interactive calibration helper for collecting pixel control points from the Brussels map image.

The script displays `regions/brussels/Brussels.png`, records four clicked corner points,
and prints a ready-to-paste NumPy array for homography setup.

Usage: 
    # install OpenCV and matplotlib since the current environment `flow_env` DONOT have them
    pip install opencv-python, matplotlib
    python helpers/get_pixels.py

"""

import cv2
import matplotlib.pyplot as plt
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Load the Brussels imagery
img = cv2.imread(str(REPO_ROOT / 'regions' / 'brussels' / 'Brussels.png'))
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

fig, ax = plt.subplots(figsize=(12, 12))
ax.imshow(img_rgb)
ax.set_title("1. ZOOM IN on Crosswalk Houba-North\n2. CLICK the 4 corners in exact order: P1, P2, P3, P4")

pixel_points = []

def onclick(event):
    if event.xdata is not None and event.ydata is not None:
        u, v = int(event.xdata), int(event.ydata)
        pixel_points.append([u, v])
        
        # Draw a visual marker where you clicked
        ax.plot(u, v, 'ro', markersize=5)
        ax.text(u + 8, v - 8, f"P{len(pixel_points)}", color='red', weight='bold', fontsize=12)
        fig.canvas.draw()
        
        print(f"Recorded Corner P{len(pixel_points)}: Pixel [{u}, {v}]")
        
        # Once 4 points are gathered, print out the final matrix setup
        if len(pixel_points) == 4:
            print("\n" + "="*60)
            print("STEP-1 COMPLETE! Copy and paste this block into your digitization script:")
            print("="*60)
            print("pixel_pts = np.array([")
            # the first click is gnored because it helps in ZOOM-IN
            print(f"    {pixel_points[0]},  # Corresponds to (-3.1, 4.7) [Inner-Left]")
            print(f"    {pixel_points[1]},  # Corresponds to (13.8, 19.3) [Outer-Left]")
            print(f"    {pixel_points[2]},  # Corresponds to (16.9, 16.1) [Outer-Right]")
            print(f"    {pixel_points[3]}   # Corresponds to (0.0, 1.4) [Inner-Right]")
            print("], dtype=np.float32)")
            print("="*60)

cid = fig.canvas.mpl_connect('button_press_event', onclick)
plt.show()
