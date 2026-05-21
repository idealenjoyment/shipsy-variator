import pytest
from dataclasses import FrozenInstanceError
from experiment_assignment.types import VariantBoundary, TargetingRule, ExperimentConfig

def test_dataclass_instantiation():
    # 1. Test VariantBoundary
    boundary = VariantBoundary(variant_id="control", cumulative_upper=0.5)
    assert boundary.variant_id == "control"
    assert boundary.cumulative_upper == 0.5

    # Test immutability (frozen=True)
    with pytest.raises(FrozenInstanceError):
        boundary.cumulative_upper = 0.8

    # 2. Test TargetingRule
    rule = TargetingRule(attribute="region", operator="IN", values=["US", "EU"])
    assert rule.attribute == "region"
    assert rule.operator == "IN"
    assert rule.value is None
    assert rule.values == ["US", "EU"]

    # Test immutability (frozen=True)
    with pytest.raises(FrozenInstanceError):
        rule.operator = "EQUALS"

    # 3. Test ExperimentConfig
    config = ExperimentConfig(
        key="checkout_flow",
        status="active",
        variants=[boundary],
        targeting=[rule]
    )
    assert config.key == "checkout_flow"
    assert config.status == "active"
    assert len(config.variants) == 1
    assert config.variants[0] == boundary
    assert config.targeting[0] == rule

    # Test mutability of ExperimentConfig (not frozen)
    config.status = "inactive"
    assert config.status == "inactive"

def test_hash_ratio_calculation():
    from experiment_assignment.hash_engine import compute_ratio

    # Determinism
    r1 = compute_ratio("test_exp", "user_1")
    r2 = compute_ratio("test_exp", "user_1")
    assert r1 == r2

    # Ratio boundary
    for i in range(100):
        r = compute_ratio("test_exp", f"user_{i}")
        assert 0.0 <= r <= 1.0

    # Type validation
    with pytest.raises(TypeError):
        compute_ratio(123, "user_1") # type: ignore
    with pytest.raises(TypeError):
        compute_ratio("test_exp", None) # type: ignore

    # Value validation
    with pytest.raises(ValueError):
        compute_ratio("", "user_1")
    with pytest.raises(ValueError):
        compute_ratio("test_exp", "")

def test_variant_bucket_assignment():
    from experiment_assignment.hash_engine import assign_variant
    
    # Configure experiment with 3 variants: v1 (50%), v2 (30%), v3 (20%)
    # Cumulative upper bounds: v1: 0.5, v2: 0.8, v3: 1.0
    v1 = VariantBoundary(variant_id="v1", cumulative_upper=0.5)
    v2 = VariantBoundary(variant_id="v2", cumulative_upper=0.8)
    v3 = VariantBoundary(variant_id="v3", cumulative_upper=1.0)
    
    config = ExperimentConfig(
        key="test_exp",
        status="active",
        variants=[v1, v2, v3]
    )
    
    # Test ratios in different buckets
    assert assign_variant(config, 0.2) == "v1"
    assert assign_variant(config, 0.499) == "v1"
    assert assign_variant(config, 0.5) == "v2"
    assert assign_variant(config, 0.79) == "v2"
    assert assign_variant(config, 0.8) == "v3"
    assert assign_variant(config, 0.99) == "v3"
    
    # Test rounding safety fallback (ratio >= 1.0)
    assert assign_variant(config, 1.0) == "v3"
    assert assign_variant(config, 1.05) == "v3"

def test_targeting_operators():
    from experiment_assignment.targeting import evaluate_targeting
    
    # 1. Test EQUALS & NOT_EQUALS
    r_equals = TargetingRule(attribute="country", operator="EQUALS", value="US")
    r_not_equals = TargetingRule(attribute="tier", operator="NOT_EQUALS", value="free")
    
    # Matches both rules (country is US, tier is premium)
    assert evaluate_targeting([r_equals, r_not_equals], {"country": "US", "tier": "premium"}) is True
    # Fails EQUALS (country is CA)
    assert evaluate_targeting([r_equals, r_not_equals], {"country": "CA", "tier": "premium"}) is False
    # Fails NOT_EQUALS (tier is free)
    assert evaluate_targeting([r_equals, r_not_equals], {"country": "US", "tier": "free"}) is False
    
    # 2. Test IN & NOT_IN
    r_in = TargetingRule(attribute="region", operator="IN", values=["US", "EU"])
    r_not_in = TargetingRule(attribute="device", operator="NOT_IN", values=["tablet"])
    
    # Matches both rules
    assert evaluate_targeting([r_in, r_not_in], {"region": "US", "device": "mobile"}) is True
    assert evaluate_targeting([r_in, r_not_in], {"region": "EU", "device": "desktop"}) is True
    # Fails IN
    assert evaluate_targeting([r_in, r_not_in], {"region": "AS", "device": "mobile"}) is False
    # Fails NOT_IN
    assert evaluate_targeting([r_in, r_not_in], {"region": "US", "device": "tablet"}) is False
    # Safeguard when values is not a list
    r_bad_in = TargetingRule(attribute="region", operator="IN", values="not-a-list") # type: ignore
    assert evaluate_targeting([r_bad_in], {"region": "US"}) is False
    r_bad_notin = TargetingRule(attribute="region", operator="NOT_IN", values="not-a-list") # type: ignore
    assert evaluate_targeting([r_bad_notin], {"region": "US"}) is False
    
    # 3. Test GREATER_THAN & LESS_THAN
    r_gt = TargetingRule(attribute="age", operator="GREATER_THAN", value=18)
    r_lt = TargetingRule(attribute="days_active", operator="LESS_THAN", value=30)
    
    # Direct number comparison matches
    assert evaluate_targeting([r_gt, r_lt], {"age": 25, "days_active": 15}) is True
    # Direct number fails bounds
    assert evaluate_targeting([r_gt, r_lt], {"age": 18, "days_active": 15}) is False
    assert evaluate_targeting([r_gt, r_lt], {"age": 25, "days_active": 30}) is False
    
    # Coercion matching (string user values compared to numeric boundaries)
    assert evaluate_targeting([r_gt], {"age": "25"}) is True
    assert evaluate_targeting([r_lt], {"days_active": "15"}) is True
    # Coercion fails safely on non-numeric strings without throwing an exception
    assert evaluate_targeting([r_gt], {"age": "abc"}) is False
    
    # Rules exist, but attributes dictionary is None or empty
    assert evaluate_targeting([r_equals], None) is False
    assert evaluate_targeting([r_equals], {}) is False
    # Rule references attribute not provided in user dictionary
    assert evaluate_targeting([r_equals], {"tier": "premium"}) is False

def test_manager_integration():
    from experiment_assignment.manager import ExperimentManager
    
    # 1. Full JSON-like config structure
    configs = [
        {
            "key": "exp_checkout",
            "status": "active",
            "variants": [
                {"id": "treatment", "weight": 20},
                {"id": "control", "weight": 80}
            ],
            "targeting": [
                {"attribute": "country", "operator": "EQUALS", "value": "US"}
            ]
        },
        {
            "key": "exp_inactive",
            "status": "inactive",
            "variants": [
                {"id": "v1", "weight": 50},
                {"id": "v2", "weight": 50}
            ]
        },
        {
            "key": "exp_malformed",
            "status": "active",
            "variants": [
                {"id": "v1", "weight": -10} # negative weight should skip
            ]
        }
    ]
    
    manager = ExperimentManager(configs)
    
    # 2. Test inactive experiment
    assert manager.get_variant("exp_inactive", "user_1") is None
    
    # 3. Test missing experiment
    assert manager.get_variant("exp_non_existent", "user_1") is None
    
    # 4. Test malformed experiment skipped
    assert manager.get_variant("exp_malformed", "user_1") is None
    
    # 5. Test active experiment with missing targeting attributes
    assert manager.get_variant("exp_checkout", "user_1") is None # missing 'country' attribute
    assert manager.get_variant("exp_checkout", "user_1", {"country": "CA"}) is None # country is CA
    
    # 6. Test active experiment with correct targeting (should deterministic return control or treatment)
    v_us_1 = manager.get_variant("exp_checkout", "user_123", {"country": "US"})
    assert v_us_1 in ("control", "treatment")
    
    # Assert determinism
    assert manager.get_variant("exp_checkout", "user_123", {"country": "US"}) == v_us_1
    
    # 7. Test variant alphabetical sorting stability
    # In configs, "treatment" is specified first, then "control".
    # Alphabetically, "control" is first, "treatment" is second.
    # Therefore, cumulative boundaries are: control: 0.8, treatment: 1.0.
    # If alphabetical sorting wasn't done, treatment would be 0.2, control: 1.0.
    # Let's assert that the sorted boundary is applied.
    # We can inspect the loaded config in the manager directly
    loaded_exp = manager.experiments["exp_checkout"]
    assert loaded_exp.variants[0].variant_id == "control"
    assert loaded_exp.variants[0].cumulative_upper == 0.8
    assert loaded_exp.variants[1].variant_id == "treatment"
    assert loaded_exp.variants[1].cumulative_upper == 1.0

def test_package_level_import():
    from experiment_assignment import ExperimentManager
    manager = ExperimentManager()
    assert isinstance(manager, ExperimentManager)

def test_strict_determinism():
    from experiment_assignment import ExperimentManager
    configs = [{
        "key": "exp_det",
        "status": "active",
        "variants": [
            {"id": "v1", "weight": 1},
            {"id": "v2", "weight": 1},
            {"id": "v3", "weight": 1}
        ]
    }]
    manager = ExperimentManager(configs)
    
    # Run 100 users, 1,000 times each
    for i in range(100):
        user_id = f"user_random_id_{i}_hash_suffix"
        first_variant = manager.get_variant("exp_det", user_id)
        assert first_variant is not None
        
        for _ in range(1000):
            assert manager.get_variant("exp_det", user_id) == first_variant

def test_distribution_quality():
    from experiment_assignment import ExperimentManager
    
    configs = [
        {
            "key": "exp_50_50",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 50},
                {"id": "treatment", "weight": 50}
            ]
        },
        {
            "key": "exp_80_20",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 80},
                {"id": "treatment", "weight": 20}
            ]
        },
        {
            "key": "exp_30_30_40",
            "status": "active",
            "variants": [
                {"id": "v1", "weight": 30},
                {"id": "v2", "weight": 30},
                {"id": "v3", "weight": 40}
            ]
        }
    ]
    manager = ExperimentManager(configs)
    
    counts_50_50 = {"control": 0, "treatment": 0}
    counts_80_20 = {"control": 0, "treatment": 0}
    counts_30_30_40 = {"v1": 0, "v2": 0, "v3": 0}
    
    # Run 100,000 simulated users
    for i in range(100000):
        user_id = f"user_{i}"
        
        # 50/50
        v_50 = manager.get_variant("exp_50_50", user_id)
        if v_50:
            counts_50_50[v_50] += 1
            
        # 80/20
        v_80 = manager.get_variant("exp_80_20", user_id)
        if v_80:
            counts_80_20[v_80] += 1
            
        # 30/30/40
        v_30 = manager.get_variant("exp_30_30_40", user_id)
        if v_30:
            counts_30_30_40[v_30] += 1
            
    # Verify 50/50 split (expected ~50,000, 1% tolerance = 49,000 to 51,000)
    assert 49000 <= counts_50_50["control"] <= 51000
    assert 49000 <= counts_50_50["treatment"] <= 51000
    
    # Verify 80/20 split (expected ~80,000 / 20,000, 1% tolerance = 79,000 - 81,000 / 19,000 - 21,000)
    assert 79000 <= counts_80_20["control"] <= 81000
    assert 19000 <= counts_80_20["treatment"] <= 21000
    
    # Verify 30/30/40 split (1% tolerance: v1, v2: 29,000 - 31,000; v3: 39,000 - 41,000)
    assert 29000 <= counts_30_30_40["v1"] <= 31000
    assert 29000 <= counts_30_30_40["v2"] <= 31000
    assert 39000 <= counts_30_30_40["v3"] <= 41000

def test_cross_experiment_independence():
    from experiment_assignment import ExperimentManager
    configs = [
        {
            "key": "exp_A",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 50},
                {"id": "treatment", "weight": 50}
            ]
        },
        {
            "key": "exp_B",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 50},
                {"id": "treatment", "weight": 50}
            ]
        }
    ]
    manager = ExperimentManager(configs)
    
    # Trace users who land in treatment in exp_A
    treatment_A_users_count = 0
    treatment_A_and_treatment_B_count = 0
    
    # Run 100,000 simulated users
    for i in range(100000):
        user_id = f"user_{i}"
        
        v_A = manager.get_variant("exp_A", user_id)
        if v_A == "treatment":
            treatment_A_users_count += 1
            
            v_B = manager.get_variant("exp_B", user_id)
            if v_B == "treatment":
                treatment_A_and_treatment_B_count += 1
                
    # Proportions of exp_A treatment users who are also treatment in exp_B
    overlap_ratio = treatment_A_and_treatment_B_count / treatment_A_users_count
    
    # Assert statistical independence (should be 50% overlap ± 1% tolerance: 0.49 to 0.51)
    assert 0.49 <= overlap_ratio <= 0.51

def test_edge_cases_and_uncovered_paths(caplog):
    import logging
    from experiment_assignment.targeting import evaluate_targeting
    from experiment_assignment.types import TargetingRule
    from experiment_assignment import ExperimentManager
    
    # --- Targeting Edge Cases ---
    # 1. Empty rules list should return True
    assert evaluate_targeting([], {"some_attr": "val"}) is True
    
    # 2. Unsupported operator should return False
    bad_rule = TargetingRule(attribute="age", operator="UNKNOWN_OP", value=20)
    assert evaluate_targeting([bad_rule], {"age": 25}) is False
    
    # --- Manager Configuration Loading Edge Cases ---
    # Setup caplog to capture warnings
    with caplog.at_level(logging.WARNING, logger="experiment_assignment"):
        # 1. configs is not a list
        manager = ExperimentManager()
        manager.load_configurations("not-a-list")  # type: ignore
        assert "Invalid configuration type supplied" in caplog.text
        caplog.clear()

        # 2. Config item is not a dict
        manager.load_configurations(["not-a-dict"])  # type: ignore
        assert "Skipping malformed configuration item" in caplog.text
        caplog.clear()

        # 3. Missing/empty or non-str key
        manager.load_configurations([{"status": "active"}])
        assert "Skipping experiment configuration: missing or empty key string" in caplog.text
        caplog.clear()
        
        manager.load_configurations([{"key": 123, "status": "active"}])
        assert "Skipping experiment configuration: missing or empty key string" in caplog.text
        caplog.clear()

        # 4. Inactive experiment (logs at INFO, not WARNING)
        with caplog.at_level(logging.INFO, logger="experiment_assignment"):
            manager.load_configurations([{"key": "exp_in", "status": "inactive"}])
            assert "Skipping inactive experiment: exp_in" in caplog.text
        caplog.clear()

        # 5. Missing or empty variants list
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": "not-a-list"}])
        assert "missing or empty variants list" in caplog.text
        caplog.clear()

        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": []}])
        assert "missing or empty variants list" in caplog.text
        caplog.clear()

        # 6. Malformed variant dict or non-numeric/negative weight
        # Variant is not a dict
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": ["not-a-dict"]}])
        assert "contains invalid, non-numeric, or negative variant weight" in caplog.text
        caplog.clear()

        # Variant missing id
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": [{"weight": 10}]}])
        assert "contains invalid, non-numeric, or negative variant weight" in caplog.text
        caplog.clear()

        # Variant missing weight
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": [{"id": "v1"}]}])
        assert "contains invalid, non-numeric, or negative variant weight" in caplog.text
        caplog.clear()

        # Variant weight is negative
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": [{"id": "v1", "weight": -5}]}])
        assert "contains invalid, non-numeric, or negative variant weight" in caplog.text
        caplog.clear()

        # Variant weight is non-numeric string
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": [{"id": "v1", "weight": "abc"}]}])
        assert "contains invalid, non-numeric, or negative variant weight" in caplog.text
        caplog.clear()

        # 7. Total weight is 0 or less
        manager.load_configurations([{"key": "exp_v", "status": "active", "variants": [{"id": "v1", "weight": 0}]}])
        assert "total variants weight must be greater than zero" in caplog.text
        caplog.clear()

        # 8. Targeting rules not list
        manager.load_configurations([
            {
                "key": "exp_t", 
                "status": "active", 
                "variants": [{"id": "v1", "weight": 10}],
                "targeting": "not-a-list"
            }
        ])
        assert "targeting rules must be supplied as a list" in caplog.text
        caplog.clear()

        # 9. Targeting list contains malformed rules (not dict)
        manager.load_configurations([
            {
                "key": "exp_t", 
                "status": "active", 
                "variants": [{"id": "v1", "weight": 10}],
                "targeting": ["not-a-dict"]
            }
        ])
        assert "targeting list contains malformed rules" in caplog.text
        caplog.clear()

        # 10. Targeting rule missing attribute or operator
        manager.load_configurations([
            {
                "key": "exp_t", 
                "status": "active", 
                "variants": [{"id": "v1", "weight": 10}],
                "targeting": [{"attribute": "age"}]
            }
        ])
        assert "targeting list contains malformed rules" in caplog.text
        caplog.clear()

    # --- get_variant Edge Cases ---
    # 1. Non-string experiment_key or user_id
    manager = ExperimentManager()
    assert manager.get_variant(123, "user_1") is None  # type: ignore
    assert manager.get_variant("exp_key", 123) is None  # type: ignore

    # 2. Empty experiment_key or user_id
    assert manager.get_variant("", "user_1") is None
    assert manager.get_variant("exp_key", "") is None

    # 3. Exception caught in get_variant
    # We can mock compute_ratio to raise TypeError/ValueError
    import unittest.mock as mock
    with mock.patch("experiment_assignment.manager.compute_ratio", side_effect=ValueError("mocked error")):
        # Load a valid experiment config
        manager.load_configurations([
            {
                "key": "exp_valid", 
                "status": "active", 
                "variants": [{"id": "control", "weight": 10}]
            }
        ])
        assert manager.get_variant("exp_valid", "user_1") is None
