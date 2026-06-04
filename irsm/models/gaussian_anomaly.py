"""
Multivariate Gaussian Anomaly Detection for IRSM

Uses 3D risk vector [mdrac, ttc, closing_speed] to detect anomalies based on
multivariate Gaussian probability distribution.

Usage:
    python irsm/models/gaussian_anomaly.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.stats import multivariate_normal, chi2
from scipy.spatial.distance import mahalanobis
import yaml


def load_irsm_config(config_path='irsm/irsm_config.yaml'):
    """Load IRSM configuration"""
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = REPO_ROOT / config_file
    with config_file.open('r') as f:
        return yaml.safe_load(f)


def resolve_repo_path(path_value):
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


class GaussianAnomalyDetector:
    """
    Multivariate Gaussian anomaly detection.
    
    Assumes normal interactions follow a Gaussian distribution.
    Anomalies have low probability density.
    """
    
    def __init__(self, contamination=0.1, method='percentile'):
        """
        Args:
            contamination: Expected fraction of anomalies (0.1 = 10%)
            method: 'percentile' or 'mahalanobis'
        """
        self.contamination = contamination
        self.method = method
        self.mu = None
        self.sigma = None
        self.sigma_inv = None
        self.threshold = None
        
    def fit(self, X):
        """
        Fit Gaussian distribution to data.
        
        Args:
            X: numpy array of shape (n_samples, n_features)
        """
        print(f"\nFitting Gaussian to {X.shape[0]} samples with {X.shape[1]} features...")
        
        # Calculate mean and covariance
        self.mu = np.mean(X, axis=0)
        self.sigma = np.cov(X, rowvar=False)
        
        # For Mahalanobis distance
        try:
            self.sigma_inv = np.linalg.inv(self.sigma)
        except np.linalg.LinAlgError:
            print("  Warning: Singular covariance matrix, using pseudo-inverse")
            self.sigma_inv = np.linalg.pinv(self.sigma)
        
        # Calculate probabilities for threshold
        model = multivariate_normal(mean=self.mu, cov=self.sigma)
        probabilities = model.pdf(X)
        
        if self.method == 'percentile':
            # Threshold at contamination percentile
            self.threshold = np.percentile(probabilities, self.contamination * 100)
            print(f"  Threshold (percentile): {self.threshold:.2e}")
        else:  # mahalanobis
            # Chi-squared critical value
            k = X.shape[1]
            confidence = 1 - self.contamination
            self.threshold = np.sqrt(chi2.ppf(confidence, k))
            print(f"  Threshold (Mahalanobis): {self.threshold:.2f}")
        
        print(f"  Mean: {self.mu}")
        print(f"  Covariance diagonal: {np.diag(self.sigma)}")
        
    def predict(self, X):
        """
        Predict anomalies.
        
        Returns:
            predictions: -1 for anomaly, 1 for normal
        """
        if self.method == 'percentile':
            model = multivariate_normal(mean=self.mu, cov=self.sigma)
            probabilities = model.pdf(X)
            predictions = np.where(probabilities < self.threshold, -1, 1)
        else:  # mahalanobis
            distances = np.array([mahalanobis(x, self.mu, self.sigma_inv) for x in X])
            predictions = np.where(distances > self.threshold, -1, 1)
        
        return predictions
    
    def predict_proba(self, X):
        """
        Get probability densities.
        
        Returns:
            probabilities: probability density for each sample
        """
        model = multivariate_normal(mean=self.mu, cov=self.sigma)
        return model.pdf(X)
    
    def get_mahalanobis_distances(self, X):
        """Get Mahalanobis distances (how many std devs from mean)"""
        return np.array([mahalanobis(x, self.mu, self.sigma_inv) for x in X])


def visualize_gaussian_results(df, normal_df, anomaly_df, output_dir):
    """Create visualization of Gaussian detection results"""
    
    # 3D scatter plot
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot normal pairs
    ax.scatter(
        normal_df['mdrac'],
        normal_df['ttc'],
        normal_df['closing_speed'],
        c='cornflowerblue',
        marker='o',
        s=50,
        alpha=0.6,
        label=f'Normal ({len(normal_df)})',
        edgecolors='navy',
        linewidth=0.5
    )
    
    # Plot anomalies
    ax.scatter(
        anomaly_df['mdrac'],
        anomaly_df['ttc'],
        anomaly_df['closing_speed'],
        c='crimson',
        marker='^',
        s=100,
        alpha=0.9,
        label=f'Anomaly ({len(anomaly_df)})',
        edgecolors='darkred',
        linewidth=1
    )
    
    ax.set_xlabel('MDRAC (m/s²)', fontsize=11, fontweight='bold')
    ax.set_ylabel('TTC (seconds)', fontsize=11, fontweight='bold')
    ax.set_zlabel('Closing Speed (m/s)', fontsize=11, fontweight='bold')
    ax.set_title(
        f'Multivariate Gaussian Anomaly Detection\n'
        f'{len(df)} pairs | {len(anomaly_df)} anomalies ({len(anomaly_df)/len(df)*100:.1f}%)',
        fontsize=13, fontweight='bold', pad=20
    )
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.view_init(elev=20, azim=45)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'gaussian_3d.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_dir / 'gaussian_3d.png'}")
    
    # Probability distribution histogram
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Log probability distribution
    axes[0].hist(df[df['prediction'] == 1]['log_probability'], 
                 bins=30, alpha=0.7, color='cornflowerblue', label='Normal', edgecolor='navy')
    axes[0].hist(df[df['prediction'] == -1]['log_probability'], 
                 bins=30, alpha=0.7, color='crimson', label='Anomaly', edgecolor='darkred')
    axes[0].axvline(np.log(df['probability'].iloc[0]), color='red', linestyle='--', 
                    linewidth=2, label='Threshold')
    axes[0].set_xlabel('Log Probability', fontweight='bold')
    axes[0].set_ylabel('Frequency', fontweight='bold')
    axes[0].set_title('Probability Distribution', fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Mahalanobis distance distribution
    axes[1].hist(df[df['prediction'] == 1]['mahalanobis_distance'], 
                 bins=30, alpha=0.7, color='cornflowerblue', label='Normal', edgecolor='navy')
    axes[1].hist(df[df['prediction'] == -1]['mahalanobis_distance'], 
                 bins=30, alpha=0.7, color='crimson', label='Anomaly', edgecolor='darkred')
    axes[1].set_xlabel('Mahalanobis Distance', fontweight='bold')
    axes[1].set_ylabel('Frequency', fontweight='bold')
    axes[1].set_title('Distance from Mean', fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.suptitle('Multivariate Gaussian Analysis', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / 'gaussian_distributions.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_dir / 'gaussian_distributions.png'}")


def run_gaussian_detection(data_path, output_dir, config):
    """
    Run Gaussian anomaly detection on IRSM data.
    
    Args:
        data_path: Path to lanes.csv
        output_dir: Directory for output
        config: IRSM configuration
    """
    print("\n" + "="*70)
    print("MULTIVARIATE GAUSSIAN ANOMALY DETECTION")
    print("="*70)
    
    # Load data
    print(f"\nLoading data from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"Loaded: {len(df)} pairs")
    
    # Select features
    features = ['mdrac', 'ttc', 'closing_speed']
    X = df[features].values
    
    print(f"\nUsing features: {features}")
    print(f"Feature ranges:")
    for i, feat in enumerate(features):
        print(f"  {feat}: [{X[:, i].min():.2f}, {X[:, i].max():.2f}]")
    
    # Initialize detector
    contamination = config['model']['contamination']
    detector = GaussianAnomalyDetector(contamination=contamination, method='percentile')
    
    # Fit and predict
    detector.fit(X)
    predictions = detector.predict(X)
    probabilities = detector.predict_proba(X)
    mahalanobis_dists = detector.get_mahalanobis_distances(X)
    
    # Add results to dataframe
    df['prediction'] = predictions
    df['probability'] = probabilities
    df['log_probability'] = np.log(probabilities + 1e-300)  # Avoid log(0)
    df['mahalanobis_distance'] = mahalanobis_dists
    
    # Statistics
    n_anomalies = (predictions == -1).sum()
    print(f"\nDetection Results:")
    print(f"  Anomalies detected: {n_anomalies} ({n_anomalies/len(df)*100:.2f}%)")
    print(f"  Expected: ~{int(len(df) * contamination)}")
    
    # Split data
    normal_df = df[df['prediction'] == 1]
    anomaly_df = df[df['prediction'] == -1]
    
    # Print statistics
    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    for feat in features:
        print(f"\n{feat.upper()}:")
        print(f"  Normal:  mean={normal_df[feat].mean():.2f}, std={normal_df[feat].std():.2f}")
        print(f"  Anomaly: mean={anomaly_df[feat].mean():.2f}, std={anomaly_df[feat].std():.2f}")
    
    # Save detections
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    detections_file = output_path / 'gaussian_detections.csv'
    anomaly_df.to_csv(detections_file, index=False)
    print(f"\n✓ Saved detections: {detections_file}")
    
    # Save all results with scores
    results_file = output_path / 'gaussian_results.csv'
    df.to_csv(results_file, index=False)
    print(f"✓ Saved results: {results_file}")
    
    # Visualize
    print("\nCreating visualizations...")
    visualize_gaussian_results(df, normal_df, anomaly_df, output_path)
    
    print("\n" + "="*70)
    print("DETECTION COMPLETE")
    print("="*70)


if __name__ == '__main__':
    # Load config
    config = load_irsm_config()
    
    region = config['region']
    date = config['date']
    output_base = resolve_repo_path(config['data']['output_base'])
    
    # Paths
    data_path = output_base / 'data' / region / date / 'lanes.csv'
    output_dir = output_base / 'results' / region / date
    
    # Run detection
    run_gaussian_detection(data_path, output_dir, config)
