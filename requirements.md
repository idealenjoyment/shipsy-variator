# Comprehensive Requirements Specification: Experiment Assignment Library (Python)

## 1. Document Overview
This document describes the exhaustive, comprehensive requirements for the Experiment Assignment Library. The purpose is to serve as a strict, unambiguous specification that defines the functional limits, runtime behaviors, input validations, and test criteria for the final implementation.

---

## 2. Goals & Context

### 2.1 Problem Statement
When running A/B or multi-variant experiments at scale, a system must decide which variant of a feature to present to a user. This decision must satisfy three hard properties:
1. **Statelessness**: No central database lookup should be required to find a user's variant assignment.
2. **Determinism**: For a given experiment, a user must see the *same* variant on every single interaction across all servers, devices, and sessions, indefinitely.
3. **Distribution Quality**: The system must split users into variants in strict accordance with predefined relative weights, and there must be no statistical correlation of assignments across different experiments for the same user population.

### 2.2 Goals
* Implement a lightweight Python package exposing a clean, professional, and robust interface to solve deterministic experiment assignment.
* Ensure near-zero assignment latency to prevent degradation of application load times.
* Build a system that behaves perfectly in high-concurrency production environments (e.g. web servers running WSGI/ASGI apps).

---

## 3. Comprehensive Functional Requirements

### 3.1 R1: Stateless and Deterministic Mechanics
* **R1.1: No Persistent Storage**: The library **MUST NOT** write to or read from any local database, cache system (like Redis), disk storage, or cookie to fetch or store a user's variant assignment.
* **R1.2: Deterministic Output**: For any given input tuple `(experiment_key, user_id, config_state)`, the returned variant identifier **MUST** be identical. A sequence of 10,000 requests for the same tuple must return the same string value 10,000 times.
* **R1.3: Side-Effect Freedom**: Calling the assignment API must be a pure mathematical operation. It must not alter internal states, execute network calls, or write logs under normal operations, unless an exceptional malformed state is encountered.

### 3.2 R2: Public API Interface & Signature
The library must expose its core functionality via a class named `ExperimentManager`.
* **R2.1: Method Signature**: The primary interaction method must have the following Python signature:
  ```python
  def get_variant(
      self, 
      experiment_key: str, 
      user_id: str, 
      attributes: Optional[Dict[str, Any]] = None
  ) -> Optional[str]:
  ```
* **R2.2: Input Parameters Requirements**:
  - `experiment_key`: Must be a non-empty string. If empty or not a string, the library must return `None` or raise a clear validation error.
  - `user_id`: Must be a non-empty string. If empty or not a string, the library must return `None` or raise a clear validation error.
  - `attributes`: An optional dictionary containing user metadata (e.g. `{"region": "US", "age": 25}`). If omitted, it must default to `None`.
* **R2.3: Return Values**:
  - Returns a string value matching the active variant (e.g. `"control"`, `"treatment_a"`).
  - Returns `None` if the experiment key is not found in the configuration.
  - Returns `None` if the experiment status is not `"active"`.
  - Returns `None` if the user is excluded by the targeting criteria.

### 3.3 R3: Hashing, Scaling, & Mathematical Distribution
To map a user to a variant deterministically, we must use a hashing algorithm to map inputs to a uniform distribution range $[0.0, 1.0]$.
* **R3.1: Hashing Algorithm Selection**: The library **MUST** use `hashlib.md5` from the Python standard library. It provides high avalanche properties, avoiding similar assignments for slightly different keys.
* **R3.2: Hash Salt & Combinator**: The hash input **MUST** be created by concatenating the `experiment_key` and the `user_id` separated by a colon: `f"{experiment_key}:{user_id}"`. This prevents user alignment biases (where user `user_1` gets control in every single experiment across the application).
* **R3.3: Numeric Projection**: The hex representation of the MD5 hash must be parsed. The first 8 hex characters (32 bits of information) must be converted into an unsigned integer. This integer must be divided by $2^{32} - 1$ (`0xffffffff`, which is `4294967295`) to produce a float ratio $R$ in the range $[0.0, 1.0]$.
* **R3.4: Cumulative Weight Selection**:
  - The variant configurations must define relative weights (e.g., `50` and `50`, or `1` and `4`, or `0.1` and `0.9`).
  - The library must sum the weights of all variants for the given experiment to compute `total_weight`.
  - The float ratio $R$ must be scaled: `scaled_value = R * total_weight`.
  - The library must evaluate the cumulative weight threshold.
    - Example: Variant A (weight 30), Variant B (weight 70).
    - Cumulative ranges: Variant A occupies $[0.0, 30.0)$, Variant B occupies $[30.0, 100.0]$.
    - If `scaled_value` falls in $[0, 30)$, Variant A is returned.
    - If `scaled_value` falls in $[30, 100]$, Variant B is returned.
* **R3.5: Multi-Variant Consistency**: The sorting order of variants must be deterministic during evaluation. If the configuration list of variants is provided in a certain order, it must maintain that relative order, or be explicitly sorted by `id` to ensure no environment-specific dictionary order alterations affect variant boundaries.

### 3.4 R4: Targeting & Attribute Evaluation (Bonus Feature)
Targeting enables experiments to run only on a subset of the user population.
* **R4.1: Logic Operator Evaluation**: The engine must support AND-logic for lists of targeting rules. Every rule in the targeting list must evaluate to `True` for the user to be eligible. If any rule evaluates to `False`, the user is excluded, and `get_variant` must return `None`.
* **R4.2: Operators Support**:
  - `EQUALS`: Case-sensitive equality matching. Handles strings, booleans, and numbers.
  - `NOT_EQUALS`: Negated case-sensitive equality matching.
  - `IN`: Checks if the user's attribute is a member of the rule's specified list of values (e.g., region in `["US", "EU"]`).
  - `NOT_IN`: Checks if the user's attribute is NOT a member of the rule's specified list of values.
  - `GREATER_THAN`: Checks if the user's numeric attribute is strictly greater than the rule's value.
  - `LESS_THAN`: Checks if the user's numeric attribute is strictly less than the rule's value.
* **R4.3: Robustness and Type Safety in Evaluation**:
  - Missing Attributes: If a rule evaluates an attribute (e.g., `tier`), and the caller did not supply `tier` in `attributes` (or `attributes` is `None`), the rule must evaluate to `False` and not throw an exception.
  - Type Coercion: For numeric operators (`GREATER_THAN`, `LESS_THAN`), if a user's attribute is passed as a string representation of a number (e.g., `"25"` instead of `25`), the targeting engine should attempt to cast it to float safely before comparing. If parsing fails, it must evaluate to `False` and not raise an unhandled exception.

### 3.5 R5: Configuration Ingestion & Schema
* **R5.1: Declarative Configurations**: The library must ingest configurations structured as lists of dictionaries representing experiments.
* **R5.2: Validation of Configurations**:
  - An experiment must contain: `key` (str), `status` (str, active/inactive), and `variants` (list of dicts).
  - The variant dictionaries must contain `id` (str) and `weight` (numeric value $\ge 0$).
  - If a configuration has invalid elements (e.g., negative weights, missing keys), the library must handle this gracefully: ignore the specific malformed experiment and log a warning, rather than crashing the entire initialization.

---

## 4. Non-Functional Requirements

### 4.1 Latency Constraints
* **Latency**: Calling `get_variant` under normal operations must execute in **less than 0.05 milliseconds (50 microseconds)** on average. This is critical because experiments are checked on hot paths (e.g. page loads or payment processing).

### 4.2 Thread Safety and Concurrency
* **Multi-threading Ready**: In Python, configurations are loaded once during application startup. The `get_variant` method will be called concurrently by multiple worker threads (e.g., under gunicorn/uwsgi).
* The internal data structures of `ExperimentManager` (the dictionary of loaded experiments) **MUST** be treated as read-only after initialization, guaranteeing complete thread safety without requiring slow locking locks (mutexes).

### 4.3 Compatibility & Dependencies
* **Compatibility**: Must support Python versions `3.8`, `3.9`, `3.10`, `3.11`, and `3.12`.
* **Zero Runtime Dependencies**: The package must not require any external PyPI packages to run core variant assignments or targeting computations.
* **Dev Dependencies**: Only `pytest` (and optionally `pytest-cov`) is allowed for testing.

---

## 5. Explicit Edge-Case Requirements

| Edge Case | Expected Library Behavior |
| :--- | :--- |
| **Active status spelling** | If status is not exactly `"active"`, treat as inactive (return `None`). |
| **All variant weights sum to 0** | Treat experiment as inactive and return `None` (avoid divide-by-zero errors). |
| **Negative weights in variant** | Exclude this experiment from loading or treat it as inactive. |
| **Duplicate variants in config** | Raise validation error or overwrite preceding variant deterministic mapping. |
| **Empty string userId/experimentKey**| Return `None` immediately. |
| **Targeting rule references missing attribute** | Safe fallback: evaluate rule to `False`, returning `None` for assignment. |
| **Non-list supplied to `IN`/`NOT_IN` rule** | Evaluate to `False`. |
| **Float conversion failures** | String attribute `"abc"` evaluated against `GREATER_THAN` numeric rule evaluates safely to `False`. |
