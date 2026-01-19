"""
Near-Miss VLM Validation Script

Edit the variables below to validate a specific near-miss event.
The script will:
1. Load event data from CSV based on pair IDs
2. Find the corresponding trajectory plot
3. Validate using VLM (API first, local fallback on error)
4. Save results to output folder (description.txt + metadata.json)
"""

import os
import json
from pathlib import Path
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv(Path(__file__).parent.parent / '.env')

# =============================================================================
# CONFIGURATION - Edit these variables
# =============================================================================

# Pair IDs to validate (from your Brussels M-DRAC results)
id1 = 10520140
id2 = 10520195

# Path to CSV file containing detection results (Brussels M-DRAC schema)
csv_path = "/home/ubuntu/prem/results/brussels/mdrac/01/mdrac_01.csv"

# Path to folder containing trajectory plots
plots_path = f"/home/ubuntu/prem/results/brussels/mdrac/01/plots/{id1}_{id2}"

# Output folder for validation results
output_path = f"/home/ubuntu/prem/results/brussels/mdrac/01/plots/{id1}_{id2}"

# =============================================================================
# Main Validation Logic
# =============================================================================

def find_event_in_csv(csv_path: str, id1: int, id2: int) -> dict:
    """
    Find event row in CSV matching the pair IDs.
    
    Args:
        csv_path: Path to detection results CSV (Brussels M-DRAC schema)
        id1: First vehicle ID
        id2: Second vehicle ID
        
    Returns:
        Dictionary with event data (Brussels schema)
    """
    df = pd.read_csv(csv_path)
    
    # Brussels schema uses 'id1' and 'id2' columns
    # Try both orderings of IDs
    mask = ((df['id1'] == id1) & (df['id2'] == id2)) | \
           ((df['id1'] == id2) & (df['id2'] == id1))
    
    matching_rows = df[mask]
    
    if len(matching_rows) == 0:
        raise ValueError(f"No event found with pair IDs: {id1}, {id2}")
    
    if len(matching_rows) > 1:
        print(f"Warning: Found {len(matching_rows)} matching rows. Using first one.")
    
    row = matching_rows.iloc[0]
    
    # Extract event data
    event_data = {
        'timestamp': str(row['timestamp']),
        'id1': int(row['id1']),
        'id2': int(row['id2']),
        'zone': str(row['zone']),
        'interaction': str(row['interaction']),
        'leader': int(row['leader']),
        'dist': float(row['dist']),
        'TTC': float(row['TTC']),
        'MDRAC': float(row['MDRAC']),
        'closing_speed': float(row['closing_speed']),
        'speed_diff': float(row['speed_diff']),
        'yaw_diff': float(row['yaw_diff']),
        'link': str(row['link']),
    }
    
    return event_data


def find_plot_file(plots_path: str, id1: int, id2: int) -> str:
    """
    Find trajectory plot file matching the pair IDs.
    
    Args:
        plots_path: Path to plots folder (pair-specific folder)
        id1: First vehicle ID
        id2: Second vehicle ID
        
    Returns:
        Full path to trajectory plot file
    """
    plots_dir = Path(plots_path)
    
    if not plots_dir.exists():
        raise ValueError(f"Plots directory not found: {plots_path}")
    
    # Look for trajectory.png (main plot for VLM validation)
    trajectory_plot = plots_dir / "trajectory.png"
    if trajectory_plot.exists():
        return str(trajectory_plot)
    
    # Fallback: search for any PNG file
    png_files = list(plots_dir.glob("*.png"))
    if png_files:
        print(f"Warning: trajectory.png not found, using {png_files[0].name}")
        return str(png_files[0])
    
    raise ValueError(f"No plot files found in {plots_path}")


def save_results(output_path: str, event_data: dict, validation_result: dict):
    """
    Save validation results to output folder.
    
    Args:
        output_path: Output directory path
        event_data: Event data from CSV
        validation_result: VLM validation result
    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create event identifier for filenames
    event_id = f"{event_data['id1']}_{event_data['id2']}"
    
    # Save description.txt
    description_path = output_dir / f"{event_id}_description.txt"
    with open(description_path, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("NEAR-MISS VALIDATION REPORT\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Event IDs: {event_data['id1']} vs {event_data['id2']}\n")
        f.write(f"Timestamp: {event_data['timestamp']}\n")
        f.write(f"Zone: {event_data['zone']}\n")
        f.write(f"Interaction: {event_data['interaction']}\n")
        f.write(f"Leader: ID {event_data['leader']}\n\n")
        
        f.write("-" * 60 + "\n")
        f.write("METRICS (M-DRAC)\n")
        f.write("-" * 60 + "\n")
        f.write(f"TTC: {event_data['TTC']:.2f} s\n")
        f.write(f"MDRAC: {event_data['MDRAC']:.2f} m/s²\n")
        f.write(f"Distance: {event_data['dist']:.2f} m\n")
        f.write(f"Closing Speed: {event_data['closing_speed']:.2f} m/s\n")
        f.write(f"Speed Diff: {event_data['speed_diff']:.2f} m/s\n")
        f.write(f"Yaw Diff: {event_data['yaw_diff']:.2f}°\n")
        f.write(f"Replay Link: {event_data['link']}\n")
        f.write("\n")
        
        f.write("-" * 60 + "\n")
        f.write("VLM VALIDATION\n")
        f.write("-" * 60 + "\n")
        f.write(f"Classification: {validation_result['classification'].upper()}\n")
        f.write(f"Confidence: {validation_result['confidence']}%\n")
        f.write(f"Backend Used: {validation_result['backend']}\n\n")
        
        f.write("Reasoning:\n")
        f.write(validation_result['reasoning'] + "\n\n")
        
        f.write("=" * 60 + "\n")
    
    # Save metadata.json
    metadata_path = output_dir / f"{event_id}_metadata.json"
    metadata = {
        'event_data': event_data,
        'validation': validation_result,
        'validation_timestamp': datetime.now().isoformat(),
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Results saved to {output_dir}/")
    print(f"  - {event_id}_description.txt")
    print(f"  - {event_id}_metadata.json")


def main():
    """Main validation workflow."""
    
    print("=" * 60)
    print("Near-Miss VLM Validation")
    print("=" * 60)
    print(f"\nValidating pair: {id1} vs {id2}")
    
    # Step 1: Load event data from CSV
    print("\n[1/4] Loading event data from CSV...")
    try:
        event_data = find_event_in_csv(csv_path, id1, id2)
        print(f"✓ Found event: {event_data['interaction']} in {event_data['zone']}")
        print(f"  TTC: {event_data['TTC']:.2f}s, MDRAC: {event_data['MDRAC']:.2f} m/s²")
    except Exception as e:
        print(f"✗ Error loading event data: {e}")
        return
    
    # Step 2: Find trajectory plot
    print("\n[2/4] Finding trajectory plot...")
    try:
        plot_path = find_plot_file(plots_path, id1, id2)
        print(f"✓ Found plot: {Path(plot_path).name}")
    except Exception as e:
        print(f"✗ Error finding plot: {e}")
        return
    
    # Step 3: VLM Validation
    print("\n[3/4] Running VLM validation...")
    try:
        from vlm_backend import validate_event
        validation_result = validate_event(plot_path, event_data)
        print(f"✓ Validation complete: {validation_result['classification']}")
        print(f"  Confidence: {validation_result['confidence']}%")
        print(f"  Backend: {validation_result['backend']}")
    except Exception as e:
        print(f"✗ Error during VLM validation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Save results
    print("\n[4/4] Saving results...")
    try:
        save_results(output_path, event_data, validation_result)
        print("\n" + "=" * 60)
        print("Validation completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"✗ Error saving results: {e}")
        return


if __name__ == "__main__":
    main()
