import hashlib
from experiment_assignment.types import ExperimentConfig

def compute_ratio(experiment_key: str, user_id: str) -> float:
    """
    Computes a deterministic, uniform float ratio in range [0.0, 1.0]
    for a given experiment_key and user_id using MD5 hashing.
    """
    # 1. Validation checks
    if not isinstance(experiment_key, str) or not isinstance(user_id, str):
        raise TypeError("Both experiment_key and user_id must be strings.")
    
    if not experiment_key or not user_id:
        raise ValueError("Both experiment_key and user_id must be non-empty strings.")
        
    # 2. String concatenation and encoding
    hash_input = f"{experiment_key}:{user_id}".encode("utf-8")
    
    # 3. MD5 hex digest calculation
    hash_hex = hashlib.md5(hash_input).hexdigest()
    
    # 4. Extract first 8 hex characters (32 bits) and parse to integer
    hash_val = int(hash_hex[:8], 16)
    
    # 5. Divide by max 32-bit unsigned value to map to range [0.0, 1.0]
    ratio = hash_val / 4294967295  # 0xffffffff
    
    return ratio

def assign_variant(experiment: ExperimentConfig, ratio: float) -> str:
    """
    Given a computed float ratio in range [0.0, 1.0], maps it to
    a variant of the experiment using pre-computed cumulative boundaries.
    """
    for boundary in experiment.variants:
        if ratio < boundary.cumulative_upper:
            return boundary.variant_id
            
    # Fallback to last variant in case of micro-rounding precision limits
    return experiment.variants[-1].variant_id

