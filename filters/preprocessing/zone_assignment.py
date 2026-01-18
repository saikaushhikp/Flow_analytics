"""
Zone assignment utilities - attach spatial zones to vehicles via spatial join.

This module provides the attach_zones_to_objects function used by footpath
and crosswalk filtering.
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import gc
from tqdm import tqdm


def attach_zones_to_objects(df, gdf_zones, how="inner", batch_size=100000):
    """
    Attach zone information to objects via spatial join.
    Handles duplicates when objects span multiple zones.
    
    FAST: Accumulates chunks in list, concatenates ONCE at end (matches old code)
    """
    columns = df.columns.tolist()
    num_chunks = len(df) // batch_size + 1
    output_chunks = []

    for i in tqdm(range(num_chunks), desc="Zone assignment batches"):
        chunk = df.iloc[i*batch_size : (i+1)*batch_size].copy()

        if len(chunk) == 0:
            continue

        gdf_chunk = gpd.GeoDataFrame(
            chunk,
            geometry=gpd.points_from_xy(chunk["pos_x"], chunk["pos_y"]),
        )

        joined = gpd.sjoin(gdf_chunk, gdf_zones, how=how, predicate="within")
        
        # Drop geometry immediately after join
        if 'geometry' in joined.columns:
            joined = joined.drop(columns=['geometry'])
        
        del gdf_chunk

        # Handle empty spatial joins
        if len(joined) == 0:
            if how == "left":
                chunk["zone"] = np.nan
                output_chunks.append(chunk)
            del joined
            continue

        # Rename columns
        joined = joined.rename(columns={
            "id_left": "id",
            "id_right": "zone"
        })

        # Remove duplicates (objects in multiple zones - keep first)
        joined = joined.drop_duplicates(subset=['id', 'timestamp'], keep='first')
        
        # Select only needed columns
        joined = joined[columns + ["zone"]]
        
        # Convert zone to category dtype (saves memory)
        joined['zone'] = joined['zone'].astype('category')

        output_chunks.append(joined)
        
        del joined
        
        # Force garbage collection every 5 batches
        if i % 5 == 0:
            gc.collect()

    # Handle case where no objects are in zones
    if len(output_chunks) == 0:
        result = df.copy()
        result["zone"] = np.nan
        return result

    # FAST: Concat once at end (not incrementally)
    result = pd.concat(output_chunks, ignore_index=True)
    
    del output_chunks
    gc.collect()
    
    return result
