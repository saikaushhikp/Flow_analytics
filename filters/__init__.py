"""
Filters package for Road Event Monitoring.

Organized into:
- preprocessing/: Data cleaning filters (lifetime, zones, static, ghost, overlap)
- postprocessing/: Post-detection filters (teleportation, duration)
"""

# This __init__.py is now just a package marker
# Import from subpackages directly:
# from filters.preprocessing import filter_by_lifetime, ...
# from filters.postprocessing import ...

__all__ = []
