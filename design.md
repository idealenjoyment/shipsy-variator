# Exhaustive Technical Design Specification: Experiment Assignment Library (Python)

## 1. System Architecture & Internal Subcomponents
The Experiment Assignment Library is designed as a standalone, high-performance Python package. To guarantee the **latency constraint (< 50 microseconds)** and maintain **thread safety**, the library uses a pre-computation strategy during configuration ingestion.

```mermaid
graph TD
    subgraph Configuration Phase (Cold Path)
        A[Raw JSON/Dictionary Configs] --> B[load_configurations]
        B --> C[Validate Inputs & Active Status]
        C --> D[Normalize Weights & Pre-compute Cumulative Thresholds]
        D --> E[Store in Read-Only Memory: Dict of ExperimentConfig]
    end

    subgraph Assignment Phase (Hot Path - Concurrency Safe)
        F[get_variant experiment_key, user_id, attributes] --> G{Experiment exists & active?}
        G -- No --> H[Return None]
        G -- Yes --> I{Evaluate targeting rules?}
        I -- No/Pass --> J[Compute MD5 Hash of experiment_key + user_id]
        I -- Fail --> K[Return None]
        J --> L[Extract 32-bit float ratio R]
        L --> M[Binary/Linear search pre-computed cumulative boundaries]
        M --> N[Return selected variant_id]
    end
```

---

## 2. Core Hashing and Bucket Mathematics

### 2.1 The Assignment Formula
Deterministic assignment maps a variable-length string pair `(experiment_key, user_id)` to a uniformly distributed float $R \in [0.0, 1.0]$.

The combination formula is:
$$\text{Input String} = \text{experiment\_key} + \text{":"} + \text{user\_id}$$

This concatenated string is encoded to bytes using UTF-8:
$$\text{Bytes} = \text{utf8\_encode}(\text{Input String})$$

An MD5 digest is computed, resulting in a 128-bit hash represented as a 32-character hexadecimal string:
$$\text{MD5 Hex} = \text{hex}(\text{MD5}(\text{Bytes}))$$

### 2.2 Unsigned 32-bit Integer Extraction & Float Mapping
To convert the hexadecimal hash into a floating-point number without precision loss, we extract the first 8 characters (which represent a 32-bit unsigned integer) and divide it by the maximum 32-bit unsigned value ($2^{32} - 1$):

$$\text{Hex Chunk} = \text{MD5 Hex}[0:8]$$
$$\text{Integer Value } I = \text{parse\_hex}(\text{Hex Chunk})$$
$$\text{Float Ratio } R = \frac{I}{\text{0xffffffff}} = \frac{I}{4294967295}$$

Because $I \in [0, 4294967295]$, the ratio $R$ is strictly guaranteed to fall within the range $[0.0, 1.0]$. The MD5 hashing algorithm distributes outputs uniformly across this interval, satisfying our statistical distribution constraints.

### 2.3 Pre-computed Cumulative Weight Ranges
Rather than computing total weights and scaling factors on every API call (the hot path), the weights are pre-normalized and mapped to cumulative ranges during cold initialization.

For each active experiment, let the variants be $v_1, v_2, \dots, v_n$ with weights $w_1, w_2, \dots, w_n$.
1. **Filter**: Check for invalid configurations ($w_i < 0$). If any weight is negative, discard the experiment or mark it inactive.
2. **Total Weight**:
   $$W_{\text{total}} = \sum_{i=1}^{n} w_i$$
   If $W_{\text{total}} \le 0$, the experiment is marked inactive (returns `None`).
3. **Cumulative Boundaries Calculation**:
   We define cumulative bounds for each variant in a normalized space $[0.0, 1.0]$:
   - $c_0 = 0.0$
   - $c_i = c_{i-1} + \frac{w_i}{W_{\text{total}}}$ for $i = 1 \dots n$.
   Note that $c_n = 1.0$ (subject to minor floating-point precision, which is handled).

Each variant $v_i$ is mapped to a range:
$$\text{Range}(v_i) = [c_{i-1}, c_i)$$

**Deterministic Sorting Strategy**:
To guarantee consistent behavior across diverse execution environments, variants are sorted alphabetically by their `id` string prior to calculating cumulative ranges. This ensures that the variant assignment bounds remain perfectly stable even if the config list ordering fluctuates dynamically in upstream inputs.

---

## 3. Class Definitions and Data Models
The library's internal models are designed with Python `dataclasses` for speed, memory efficiency, and readability.

```python
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class VariantBoundary:
    variant_id: str
    cumulative_upper: float  # Cumulative range boundary R < cumulative_upper

@dataclass(frozen=True)
class TargetingRule:
    attribute: str
    operator: str  # 'EQUALS', 'NOT_EQUALS', 'IN', 'NOT_IN', 'GREATER_THAN', 'LESS_THAN'
    value: Any = None
    values: Optional[List[Any]] = None

@dataclass
class ExperimentConfig:
    key: str
    status: str
    variants: List[VariantBoundary]  # Pre-computed cumulative boundaries
    targeting: Optional[List[TargetingRule]] = None
```

---

## 4. Detailed Component Interfaces & Pseudo-code

### 4.1 Configuration Loader (Cold Path Optimizer)
The parsing logic translates raw JSON-like lists into highly optimized domain objects.

```python
def load_configurations(self, configs: List[Dict[str, Any]]) -> None:
    for item in configs:
        key = item.get("key")
        status = item.get("status")
        raw_variants = item.get("variants", [])
        raw_targeting = item.get("targeting")

        # Validation checks
        if not key or not isinstance(key, str):
            continue  # Skip invalid keys
        
        if status != "active":
            continue  # Skip or register inactive

        # Sort variants to ensure order stability
        try:
            sorted_variants = sorted(raw_variants, key=lambda x: x["id"])
        except (KeyError, TypeError):
            continue  # Malformed variant structures
        
        # Calculate Total Weights
        try:
            total_weight = sum(float(v["weight"]) for v in sorted_variants)
        except (ValueError, TypeError, KeyError):
            continue  # Invalid non-numeric weights

        if total_weight <= 0:
            continue  # Treat as inactive

        # Pre-compute Boundaries
        boundaries = []
        cumulative_sum = 0.0
        for v in sorted_variants:
            weight = float(v["weight"])
            cumulative_sum += weight / total_weight
            boundaries.append(VariantBoundary(
                variant_id=v["id"],
                cumulative_upper=cumulative_sum
            ))
        
        # Parse Targeting Rules
        parsed_rules = []
        if raw_targeting and isinstance(raw_targeting, list):
            for rule in raw_targeting:
                parsed_rules.append(TargetingRule(
                    attribute=rule.get("attribute"),
                    operator=rule.get("operator"),
                    value=rule.get("value"),
                    values=rule.get("values")
                ))

        self.experiments[key] = ExperimentConfig(
            key=key,
            status=status,
            variants=boundaries,
            targeting=parsed_rules if parsed_rules else None
        )
```

### 4.2 Hashing and Bucket Resolution Engine
```python
import hashlib

def _assign_variant(self, experiment: ExperimentConfig, user_id: str) -> str:
    # 1. Salt and construct hash input
    hash_input = f"{experiment.key}:{user_id}".encode("utf-8")
    
    # 2. Compute MD5 Hex digest
    hash_hex = hashlib.md5(hash_input).hexdigest()
    
    # 3. Extract 32-bit unsigned int from first 8 hex characters
    hash_val = int(hash_hex[:8], 16)
    
    # 4. Map to ratio [0.0, 1.0]
    ratio = hash_val / 4294967295  # 0xffffffff
    
    # 5. Resolve bucket using cumulative boundaries
    # Linear scan works exceptionally fast for standard number of variants (usually < 5)
    for boundary in experiment.variants:
        if ratio < boundary.cumulative_upper:
            return boundary.variant_id
            
    # Fallback to the last variant in case of micro-rounding floating point edge cases
    return experiment.variants[-1].variant_id
```

---

## 5. Targeting Rule Evaluation Logic
Targeting rule evaluation must be completely robust. It evaluates a user's local dictionary of attributes against the target schema constraints.

### 5.1 Comprehensive Operator Specification

* **`EQUALS`**:
  Checks if `user_val == rule_val`. Handles direct matches.
* **`NOT_EQUALS`**:
  Checks if `user_val != rule_val`.
* **`IN`**:
  Rule configuration specifies a list in `values`. Checks if `user_val` is in `rule_values`. If `values` is not a list, evaluates to `False`.
* **`NOT_IN`**:
  Checks if `user_val` is NOT in `rule_values`.
* **`GREATER_THAN`**:
  For numeric comparisons. Checks `user_val > rule_val`. Attempt float-casting on both inputs to handle safe string-to-number boundary comparison, resolving to `False` if cast fails.
* **`LESS_THAN`**:
  Numeric comparison checking `user_val < rule_val`. Identical cast-safety guards as `GREATER_THAN`.

### 5.2 Python Implementation Architecture
```python
def _evaluate_targeting(self, rules: List[TargetingRule], attributes: Optional[Dict[str, Any]]) -> bool:
    if not attributes:
        return False  # Targeting rules exist but user supplied no attributes

    for rule in rules:
        attr_name = rule.attribute
        if attr_name not in attributes:
            return False  # Missing required attribute fails immediately (AND logic)
            
        user_val = attributes[attr_name]
        op = rule.operator

        if op == "EQUALS":
            if user_val != rule.value:
                return False
        elif op == "NOT_EQUALS":
            if user_val == rule.value:
                return False
        elif op == "IN":
            if not isinstance(rule.values, list) or user_val not in rule.values:
                return False
        elif op == "NOT_IN":
            if not isinstance(rule.values, list) or user_val in rule.values:
                return False
        elif op in ("GREATER_THAN", "LESS_THAN"):
            try:
                user_num = float(user_val)
                rule_num = float(rule.value)
            except (ValueError, TypeError):
                return False  # Numeric conversion failed: fail rule safely
                
            if op == "GREATER_THAN" and not (user_num > rule_num):
                return False
            elif op == "LESS_THAN" and not (user_num < rule_num):
                return False
        else:
            return False  # Unsupported operator: fail-safe default

    return True  # All AND conditions passed
```

---

## 6. Optimization, Thread Safety, and Latency Strategies

### 6.1 Performance and Latency
1. **Pre-Computed Allocations**: By dividing the variant weights once at load time, the assignment phase does not need to perform sum reductions or divide-by-zero checks.
2. **Minimal String Conversions**: MD5 is computed natively on Python bytes. Hexadecimal decoding is restricted to the first 8 characters, which is extremely lightweight.

### 6.2 Concurrent Execution Without Locks
* **Mutable State Isolation**: The configurations are stored in an internal dictionary: `self.experiments`.
* **Read-Only Safety**: During execution of `get_variant`, the library performs read-only dictionary lookups and math calculations.
* **Result**: Multiple threads calling `get_variant` simultaneously under web servers (e.g. FastAPI, Django, Flask, gunicorn) are completely safe, since no lock contention or mutating operations are run.

---

## 7. Package Layout

```
shipsy/
├── requirements.md
├── design.md
├── tasks.md
├── README.md
├── pyproject.toml
├── experiment_assignment/
│   ├── __init__.py
│   ├── types.py
│   ├── hash_engine.py
│   ├── targeting.py
│   └── manager.py
└── tests/
    ├── __init__.py
    └── test_assignment.py
```
