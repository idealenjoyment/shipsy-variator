# Granular Checklist & Task Breakdown: Python Experiment Assignment Library

This checklist defines the step-by-step checklist of tasks required to build, test, and package the Experiment Assignment Library. 

> [!IMPORTANT]
> **Strict Incremental Execution Rule**: 
> You **MUST NOT** proceed to a subsequent task until the prior task's implementation and its corresponding test cases are fully completed, executed, and verified to be 100% working.

---

## 🟩 Phase 1: Environment Setup & Package Scaffolding

### [x] Task 1.1: Virtual Environment Initialisation
Create a Python 3 virtual environment in the root workspace directory.
* **Execution**:
  - Run the following terminal commands to create and activate:
    ```bash
    uv venv
    source .venv/bin/activate
    ```
  - Verify that the virtual environment is successfully created and active.

### [x] Task 1.2: Dependencies Configuration
Create a `requirements-dev.txt` file listing standard testing packages.
* **Target File**: [requirements-dev.txt](file:///Users/phenom/Documents/shipsy/requirements-dev.txt)
* **File Content**:
  ```text
  pytest>=7.4.0
  pytest-cov>=4.1.0
  ```
* **Execution**:
  - Create the file and run `uv pip install -r requirements-dev.txt`.
  - Verify `pytest` is executable within the virtual environment by running `pytest --version`.

### [x] Task 1.3: Package Directory Structure Creation
Create the physical directories and initialization files for the python source layout.
* **Execution**:
  - Run the directory generation command:
    ```bash
    mkdir -p experiment_assignment
    mkdir -p tests
    touch experiment_assignment/__init__.py
    touch experiment_assignment/types.py
    touch experiment_assignment/hash_engine.py
    touch experiment_assignment/targeting.py
    touch experiment_assignment/manager.py
    touch tests/__init__.py
    touch tests/test_assignment.py
    ```

### [x] Task 1.4: Define Package Metadata
Create a `pyproject.toml` file to enable clean standard package distribution and local testing installation.
* **Target File**: [pyproject.toml](file:///Users/phenom/Documents/shipsy/pyproject.toml)
* **Execution**:
  - Populate the `pyproject.toml` configuration content.
  - Install the package locally in editable mode: `uv pip install -e .`.
  - Verify package installation by executing `python -c "import experiment_assignment"` without error.

---

## 🟩 Phase 2: Domain Types Implementation

### [x] Task 2.1: Types Coding
Develop type interfaces and structures inside `types.py` using Python `dataclasses`.
* **Target File**: [types.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/types.py)
* **Execution Details**:
  - Implement class `VariantBoundary` with variables: `variant_id` (str), `cumulative_upper` (float). Add `@dataclass(frozen=True)` modifier.
  - Implement class `TargetingRule` with variables: `attribute` (str), `operator` (str), `value` (Any, default None), `values` (Optional[List[Any]], default None). Add `@dataclass(frozen=True)` modifier.
  - Implement class `ExperimentConfig` with variables: `key` (str), `status` (str), `variants` (List[VariantBoundary]), `targeting` (Optional[List[TargetingRule]], default None). Add `@dataclass` modifier.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add test methods in `tests/test_assignment.py` (e.g. `test_dataclass_instantiation`) to verify that all three dataclasses can be correctly instantiated, hold typed values, and that `VariantBoundary` and `TargetingRule` are immutable (`frozen=True`).
  - Run the test suite: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed to Phase 3 until all dataclass tests pass successfully.

---

## 🟩 Phase 3: Hash Calculation and Weight Accumulator

### [x] Task 3.1: Hashing Ratio Engine Coding
Implement MD5 conversion logic.
* **Target File**: [hash_engine.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/hash_engine.py)
* **Execution Details**:
  - Write method `compute_ratio(experiment_key: str, user_id: str) -> float`.
  - Implement UTF-8 string concatenation: `f"{experiment_key}:{user_id}"`.
  - Run MD5 digest, take first 8 hex characters, parse to 32-bit unsigned int, divide by `4294967295`.
  - Raise `TypeError` or `ValueError` if either input parameter is not a string or is empty.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add test methods in `tests/test_assignment.py` (e.g. `test_hash_ratio_calculation`) validating:
    - Ratios are strictly between `0.0` and `1.0`.
    - Outputs are completely deterministic (identical inputs yield identical ratios).
    - String validation logic raises errors on empty strings or incorrect types.
  - Run tests: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed until hashing tests pass successfully.

### [x] Task 3.2: Cumulative Bucket Allocator Coding
Implement variant bucket matching logic.
* **Target File**: [hash_engine.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/hash_engine.py)
* **Execution Details**:
  - Write method `assign_variant(experiment: ExperimentConfig, ratio: float) -> str`.
  - Implement linear scan over `experiment.variants`, check if `ratio < boundary.cumulative_upper`.
  - Fallback to returning `experiment.variants[-1].variant_id` for rounding safety.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add test methods in `tests/test_assignment.py` (e.g. `test_variant_bucket_assignment`) simulating different float ratios against loaded `ExperimentConfig` buckets (e.g., control: 0.8, treatment: 1.0) and assert the correct variant string is returned.
  - Run tests: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed until bucket assignment tests pass successfully.

---

## 🟩 Phase 4: Targeting Evaluation Implementation

### [x] Task 4.1: Targeting Operator Core Logic Coding
Build targeting comparisons handling all specifications and edge-case exceptions.
* **Target File**: [targeting.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/targeting.py)
* **Execution Details**:
  - Write method `evaluate_targeting(rules: List[TargetingRule], attributes: Optional[Dict[str, Any]]) -> bool`.
  - Implement boolean AND logic over all rules. If user attributes are missing/None, return `False`.
  - Support operators: `EQUALS`, `NOT_EQUALS`, `IN`, `NOT_IN`, `GREATER_THAN`, `LESS_THAN`.
  - Safeguard `GREATER_THAN` and `LESS_THAN` with float-try-casts, and membership checking against raw list inputs.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add test methods in `tests/test_assignment.py` (e.g. `test_targeting_operators`) covering:
    - Equality: `EQUALS`, `NOT_EQUALS`.
    - Containment: `IN`, `NOT_IN` (including non-list fallback safety).
    - Numeric bounds: `GREATER_THAN`, `LESS_THAN` (including string numeric coercions like `"25"` and cast-failure rejections like `"abc"`).
    - Missing attribute dictionaries.
  - Run tests: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed until all targeting engine tests pass successfully.

---

## 🟩 Phase 5: Manager API Implementation & Exposed Endpoints

### [x] Task 5.1: Build API Manager Engine
Implement configuration validation, parsing, normalization, and the `get_variant` router.
* **Target File**: [manager.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/manager.py)
* **Execution Details**:
  - Define class `ExperimentManager`.
  - Implement config loader: `load_configurations(self, configs: List[Dict[str, Any]]) -> None`.
    - Skip experiments with empty/non-string keys, non-"active" status, or negative variant weights.
    - Sort variants alphabetically by `id` to ensure ordering stability.
    - Pre-compute boundaries: normalizes weights and stores `VariantBoundary` lists.
  - Implement `get_variant(self, experiment_key: str, user_id: str, attributes: Optional[Dict[str, Any]] = None) -> Optional[str]`.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add test methods (e.g. `test_manager_integration`) loading a complete JSON-like experiment config structure.
  - Assert that `get_variant` accurately resolves active variants, handles inactive experiments by returning `None`, respects user targeting, and alphabetically sorts list configurations to maintain consistent boundaries.
  - Run tests: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed until manager tests pass.

### [x] Task 5.2: Module Entry Wiring
Expose package entry point clean interface in standard module format.
* **Target File**: [__init__.py](file:///Users/phenom/Documents/shipsy/experiment_assignment/__init__.py)
* **Execution Details**:
  - Expose `ExperimentManager`.
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Add a test method (e.g. `test_package_level_import`) asserting `from experiment_assignment import ExperimentManager` works perfectly and can be successfully instantiated.
  - Run tests: `pytest -v tests/test_assignment.py`.
  - **Verification Gate**: Do not proceed until package-level interface tests pass.

---

## 🟩 Phase 6: Rigorous Consistency & Statistical Testing

### [x] Task 6.1: Determinism and Consistency Verification
Assert 100% repeatability of the assignment library.
* **Target File**: [test_assignment.py](file:///Users/phenom/Documents/shipsy/tests/test_assignment.py)
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Implement `test_strict_determinism()`: call `get_variant` 1,000 times for 100 randomly generated user IDs. Assert that every user gets the exact same variant in all 1,000 runs without fail.
  - Run tests: `pytest -v -k test_strict_determinism`.

### [x] Task 6.2: Large-Population Statistical Distribution Verification
Validate uniform distribution splits mathematically.
* **Target File**: [test_assignment.py](file:///Users/phenom/Documents/shipsy/tests/test_assignment.py)
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Implement `test_distribution_50_50_split()`: simulate 100,000 assignments with a 50/50 split. Verify both variants fall within a 1% tolerance window (49,000 - 51,000).
  - Implement `test_distribution_skewed_split()`: simulate 100,000 assignments with an 80/20 split. Assert $80\% \pm 1\%$ and $20\% \pm 1\%$.
  - Implement `test_multi_variant_split()`: simulate 100,000 assignments with a 30/30/40 split. Verify weights are satisfied within the 1% threshold.
  - Run tests: `pytest -v -k "test_distribution"`.

### [x] Task 6.3: Cross-Experiment Independence Verification
Verify that experiment buckets are uncorrelated.
* **Target File**: [test_assignment.py](file:///Users/phenom/Documents/shipsy/tests/test_assignment.py)
* **[x] SUB-TASK: Add Test Cases & Verify**
  - Implement `test_cross_experiment_independence()`: run 100,000 simulated users across two independent 50/50 experiments. Assert that of the users in Experiment A's treatment pool, $50\% \pm 1\%$ land in Experiment B's treatment pool, proving complete statistical independence.
  - Run tests: `pytest -v -k test_cross_experiment_independence`.

---

## 🟩 Phase 7: Verification and Documentation

### [x] Task 7.1: Verify All Tests and Coverage
Execute the entire suite of functional, safety, consistency, and statistical tests, verifying 100% success and high coverage metrics.
* **Command**:
  ```bash
  pytest -v --cov=experiment_assignment
  ```

### [x] Task 7.2: Create README.md
Create a clean, elegant [README.md](file:///Users/phenom/Documents/shipsy/README.md) for the project, fully describing details of architecture, hash bucket mathematical equations, test runs, usage examples, and AI details.
* **Verification**: Verify that markdown formatting displays beautifully.

