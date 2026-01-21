"""
IRSM - Intelligent Risk Scoring Mechanism

Unsupervised near-miss classification using anomaly detection.
"""

__version__ = "0.1.0"

# Lazy imports to avoid circular dependencies when running scripts directly
__all__ = [
    'extract_risk_vector_instantaneous',
    'get_feature_names_instantaneous', 
    'generate_risk_vectors'
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == 'extract_risk_vector_instantaneous':
        from .risk_vector import extract_risk_vector_instantaneous
        return extract_risk_vector_instantaneous
    elif name == 'get_feature_names_instantaneous':
        from .risk_vector import get_feature_names_instantaneous
        return get_feature_names_instantaneous
    elif name == 'generate_risk_vectors':
        from .data_generation import generate_risk_vectors
        return generate_risk_vectors
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
