# Experiment Assignment Library (Python)

A premium, high-performance, stateless, and deterministic experiment assignment and targeting library written in pure Python.

Designed for high-concurrency production environments, this library evaluates and assigns users to experiment variants in **under 50 microseconds** with **zero database queries, locks, or side-effects**.

---

## Key Features

- **Stateless & Deterministic**: Yields the exact same assignment for any given `(user_id, experiment_key)` combination without persistent databases or caching.
- **Zero Runtime Dependencies**: Written entirely in pure Python standard library to keep your application weight minimum and completely secure.
- **Microsecond Hot Path Latency**: Pre-computes cumulative bounds at initialization, making hot-path lookups incredibly fast ($< 50\,\mu\text{s}$).
- **Targeting Engine (AND-Logic)**: Supports robust attribute-based user targeting with operators: `EQUALS`, `NOT_EQUALS`, `IN`, `NOT_IN`, `GREATER_THAN`, `LESS_THAN`.
- **Concurrency & Thread Safety**: 100% thread-safe lock-free read operations ideal for ASGI/WSGI applications (FastAPI, Flask, Django, etc.).
- **Order Stability**: Alphabetically sorts variants before boundary mapping to guarantee deterministic assignment ranges independent of config ordering.

---

## Technical Architecture & Mathematical Engine

The core assignment engine maps any arbitrary user ID and experiment key to a uniform float ratio $R \in [0.0, 1.0]$ using cryptographic hashing:

```
                  ┌──────────────────────────────┐
                  │ experiment_key + ":" + user_id│
                  └──────────────┬───────────────┘
                                 │ UTF-8 Encode
                                 ▼
                     ┌───────────────────────┐
                     │ MD5 Hash (128-bit)    │
                     └───────────┬───────────┘
                                 │ First 8 Hex Characters
                                 ▼
                   ┌───────────────────────────┐
                   │ Unsigned 32-bit Integer   │
                   └───────────┬───────────┘
                                 │ / 4294967295 (0xffffffff)
                                 ▼
                   ┌───────────────────────────┐
                   │   Float Ratio R [0, 1]    │
                   └───────────┬───────────┘
                                 │
                 Linear Scan against Cumulative Bounds
                 ┌─────────────┼─────────────┐
                 ▼             ▼             ▼
             [0.0, 0.5)    [0.5, 0.8)    [0.8, 1.0]
              (control)   (treatment_a) (treatment_b)
```

### 1. Hash & Salt Concatenation
To prevent user alignment biases (which would result in a single user consistently landing in the same bucket across all experiments), we combine and salt the keys:
```text
Input String = experiment_key + ":" + user_id
```

### 2. Cryptographic Projection
We run an MD5 digest over the UTF-8 encoded string. To project it onto a float ratio without precision loss:
1. Extract the first **8 hexadecimal characters** (representing 32 bits).
2. Parse the hex chunk to an unsigned integer $I \in [0, 4294967295]$.
3. Scale the integer to a ratio:
   $$R = \frac{I}{\text{0xffffffff}} = \frac{I}{4294967295}$$

This mathematical projection guarantees $R$ is uniformly distributed in $[0.0, 1.0]$.

### 3. Pre-computed Cumulative Ranges
During configuration loading, the manager pre-normalizes variants and maps them to cumulative ranges.
To prevent upstream configuration key ordering changes from shifting variant boundaries, **variants are sorted alphabetically by `id`** prior to calculating bounds.

For variants $v_1, v_2, \dots, v_n$ with weights $w_1, w_2, \dots, w_n$:
1. Total Weight calculation:
   $$W_{\text{total}} = \sum_{j=1}^{n} w_j$$
2. Cumulative Upper Boundary $c_i$:
   $$c_i = \sum_{j=1}^{i} \frac{w_j}{W_{\text{total}}}$$
3. Variant $v_i$ matches if $R < c_i$. In case of float-rounding edge-cases where $R \approx 1.0$, it falls back safely to the last variant.

---

## Installation & Setup

We recommend using the **`uv`** package manager for fast, reliable python environment management.

### 1. Initialize Virtual Environment & Install Dev Dependencies
```bash
# Create a virtual environment
uv venv

# Activate the environment
source .venv/bin/activate

# Install development dependencies
uv pip install -r requirements-dev.txt
```

### 2. Local Editable Install
Install the project in editable mode so your local edits are reflected immediately:
```bash
uv pip install -e .
```

---

## Usage Guide

### Basic Variant Assignment

```python
from experiment_assignment import ExperimentManager

# 1. Define your experiment configurations
configs = [
    {
        "key": "onboarding_flow",
        "status": "active",
        "variants": [
            {"id": "control", "weight": 50},
            {"id": "treatment_split", "weight": 50}
        ]
    }
]

# 2. Instantiate and load configurations
manager = ExperimentManager(configs)

# 3. Request deterministic variant assignment
variant = manager.get_variant("onboarding_flow", "user_10283")
print(f"Assigned Variant: {variant}")
# Deterministically outputs: "control" or "treatment_split"
```

### Advanced Variant Assignment with Targeting

```python
configs_with_targeting = [
    {
        "key": "pricing_discount_2026",
        "status": "active",
        "variants": [
            {"id": "control", "weight": 80},
            {"id": "discount_heavy", "weight": 20}
        ],
        "targeting": [
            {"attribute": "country", "operator": "EQUALS", "value": "US"},
            {"attribute": "days_active", "operator": "GREATER_THAN", "value": 30},
            {"attribute": "subscription_tier", "operator": "IN", "values": ["free", "silver"]}
        ]
    }
]

manager = ExperimentManager(configs_with_targeting)

# Case A: User does not satisfy targeting criteria (returns None)
user_a_attributes = {
    "country": "CA",
    "days_active": 45,
    "subscription_tier": "free"
}
variant_a = manager.get_variant("pricing_discount_2026", "user_101", user_a_attributes)
assert variant_a is None

# Case B: User satisfies all targeting criteria (gets assigned deterministically)
user_b_attributes = {
    "country": "US",
    "days_active": "100",  # Safe conversion handles stringified numbers beautifully!
    "subscription_tier": "silver"
}
variant_b = manager.get_variant("pricing_discount_2026", "user_102", user_b_attributes)
print(f"User B Assigned Variant: {variant_b}")
```

---

## Targeting Operator Specifications

All targeting rules evaluate using strict **AND-logic**. If any rule fails, the experiment is skipped (`None` is returned).

| Operator | Evaluates | Safe Guard Details |
| :--- | :--- | :--- |
| `EQUALS` | `user_value == rule_value` | Case-sensitive direct comparisons. |
| `NOT_EQUALS`| `user_value != rule_value` | Negated case-sensitive comparison. |
| `IN` | `user_value in rule_values` | Fails safely to `False` if `rule_values` is not a list. |
| `NOT_IN` | `user_value not in rule_values` | Fails safely to `False` if `rule_values` is not a list. |
| `GREATER_THAN`| `user_value > rule_value` | Safe float try-casts for both user/rule arguments. Fails safely on uncastable values (e.g. `"abc"`). |
| `LESS_THAN` | `user_value < rule_value` | Safe float try-casts. Fails safely on uncastable values. |

---

## Verifying Tests & Code Coverage

Our test suite guarantees strict correctness, perfect repeatability, mathematical split uniform accuracy, and zero multi-experiment correlation.

### Run All Tests
```bash
.venv/bin/pytest -v
```

### Check Coverage Report
Our library maintains a **strict 100% test coverage** requirement on all lines and branches of the source code.
```bash
.venv/bin/pytest -v --cov=experiment_assignment
```

**Coverage Report Output:**
```text
Name                                   Stmts   Miss  Cover
----------------------------------------------------------
experiment_assignment/__init__.py          2      0   100%
experiment_assignment/hash_engine.py      17      0   100%
experiment_assignment/manager.py          90      0   100%
experiment_assignment/targeting.py        37      0   100%
experiment_assignment/types.py            18      0   100%
----------------------------------------------------------
TOTAL                                    164      0   100%
```

---

## AI Assistant Development & Engineering Notes

This library was developed using a **spec-driven, strict Test-Driven Development (TDD)** approach in collaboration with Antigravity, an Advanced Agentic Coding assistant from Google DeepMind.

### Key Architectural Overrides & Rationale
1. **Pre-Computed Allocations vs. Running Calculations**: To meet the $<50\,\mu\text{s}$ latency requirements, variant boundaries are calculated once during configuration ingestion (`load_configurations`), converting weights into cumulative limits directly mapped to $[0.0, 1.0]$. The runtime `get_variant` hot path performs zero divisions, zero summing, and zero float boundary checks, executing purely with a fast linear array scan.
2. **Stable Alphabetical Ordering**: Variants are explicitly sorted by `id` before calculating bounds. This prevents shifts in variant assignments due to changes in dictionary key insertions or dynamic order fluctuations from API gateway backends.
3. **Lock-Free Concurrency**: Config structures are held in `self.experiments` and accessed as read-only. Worker threads on web servers can retrieve assignments simultaneously without locks or lock contentions.
4. **Resilient Numeric Try-Casts**: In high-velocity pipelines, client metrics might contain string-coerced integers (e.g. `{"age": "24"}`). The targeting engine safely handles numeric try-casting, allowing correct comparisons without crashing.

### Future Optimizations
- **Binary Search Bucket Matching**: If experiments regularly exceed 10+ variants, the linear scan in `assign_variant` could be replaced with `bisect.bisect_right` to achieve $O(\log N)$ matching.
- **Dynamic Thread-Safe Config Swaps**: In applications updating configs dynamically, standard thread-safety can be achieved by using an atomic reference swap of the internal dictionary (`self.experiments`), keeping the hot path lock-free.
