# Quick test script
from plotter import plot_conflict_analysis, load_data

# Load data
df = load_data(
    data_dir='/home/ubuntu/data/uploads/objects/clean',
    start_date="2025-06-01",
    end_date="2025-06-01"
)

print(f"Loaded {len(df)} records")

# Test with different ID pair
plot_conflict_analysis(
    df,
    id1=11017670,
    id2=11017862,
    output_dir='results/plots',
    show_plot=False  # Don't show plots, just save
)
