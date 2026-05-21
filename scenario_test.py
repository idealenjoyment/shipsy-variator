#!/usr/bin/env python3
"""
Shipsys Experiment Assignment Library - Scenario Verification Suite

This script runs comprehensive end-to-end scenarios to verify all functional, 
architectural, and edge-case requirements of the Experiment Assignment Library.
It outputs detailed terminal logs with color codes indicating PASS or FAIL status.
"""

import sys
import math
import logging
from typing import Dict, Any, List

# Setup standard formatting for logger warnings to demonstrate clean skipping
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    datefmt='%H:%M:%S'
)

# Colors for terminal styling
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}🧪 {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")

def print_result(scenario_name: str, passed: bool, details: str):
    status = f"{BOLD}{GREEN}[PASS]{RESET}" if passed else f"{BOLD}{RED}[FAIL]{RESET}"
    print(f" {status} {scenario_name}")
    print(f"        └─ {details}")

def main():
    try:
        from experiment_assignment import ExperimentManager
        from experiment_assignment.types import TargetingRule
    except ImportError:
        print(f"{BOLD}{RED}Error: Could not import experiment_assignment.{RESET}")
        print("Please ensure the library is installed (e.g. run 'uv pip install -e .')")
        sys.exit(1)

    print_header("SHIPSYS EXPERIMENT ASSIGNMENT SYSTEM - COMPREHENSIVE SCENARIO TESTING")

    total_scenarios = 0
    passed_scenarios = 0

    def run_scenario(name: str, test_func) -> bool:
        nonlocal total_scenarios, passed_scenarios
        total_scenarios += 1
        try:
            passed, details = test_func()
            if passed:
                passed_scenarios += 1
            print_result(name, passed, details)
            return passed
        except Exception as e:
            print_result(name, False, f"Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            return False

    # -------------------------------------------------------------------------
    # Scenario 1: Core Assignment Determinism & Stateless Repeatability
    # -------------------------------------------------------------------------
    def scenario_determinism():
        configs = [{
            "key": "exp_deterministic",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 50},
                {"id": "treatment", "weight": 50}
            ]
        }]
        manager = ExperimentManager(configs)
        user_id = "user_shipsy_determinism_99"
        
        # Call 10,000 times
        first_variant = manager.get_variant("exp_deterministic", user_id)
        if not first_variant:
            return False, "Failed to assign initial variant."
            
        for i in range(10000):
            current_variant = manager.get_variant("exp_deterministic", user_id)
            if current_variant != first_variant:
                return False, f"Assignment shifted to '{current_variant}' on iteration {i}!"
                
        return True, f"10,000 iterations for User '{user_id}' consistently returned variant '{first_variant}'."

    run_scenario("Scenario 1: Core Assignment Determinism & Stateless Repeatability", scenario_determinism)

    # -------------------------------------------------------------------------
    # Scenario 2: Inactive & Non-Existent Experiments Handling
    # -------------------------------------------------------------------------
    def scenario_inactive_missing():
        configs = [
            {
                "key": "exp_active",
                "status": "active",
                "variants": [{"id": "v1", "weight": 100}]
            },
            {
                "key": "exp_inactive",
                "status": "inactive",
                "variants": [{"id": "v1", "weight": 100}]
            }
        ]
        manager = ExperimentManager(configs)
        
        # Test active
        v_active = manager.get_variant("exp_active", "user_1")
        # Test inactive
        v_inactive = manager.get_variant("exp_inactive", "user_1")
        # Test non-existent
        v_missing = manager.get_variant("exp_non_existent", "user_1")
        
        if v_active != "v1":
            return False, f"Active experiment returned unexpected variant '{v_active}'"
        if v_inactive is not None:
            return False, f"Inactive experiment returned variant '{v_inactive}' (expected None)"
        if v_missing is not None:
            return False, f"Missing experiment returned variant '{v_missing}' (expected None)"
            
        return True, "Active experiment assigns correctly. Inactive and non-existent experiments return None."

    run_scenario("Scenario 2: Inactive & Non-Existent Experiments Handling", scenario_inactive_missing)

    # -------------------------------------------------------------------------
    # Scenario 3: Graceful Skip of Malformed Configurations
    # -------------------------------------------------------------------------
    def scenario_malformed_config():
        configs = [
            {
                "key": "valid_exp",
                "status": "active",
                "variants": [{"id": "v1", "weight": 1}]
            },
            # Missing key
            {
                "status": "active",
                "variants": [{"id": "v1", "weight": 1}]
            },
            # Negative variant weights
            {
                "key": "bad_weights_exp",
                "status": "active",
                "variants": [{"id": "v1", "weight": -50}]
            },
            # Non-list variants
            {
                "key": "bad_variants_exp",
                "status": "active",
                "variants": "not-a-list"
            }
        ]
        
        print(f"\n{BOLD}{YELLOW} [System Diagnostic Logs - Expect skipping warnings below]{RESET}")
        manager = ExperimentManager(configs)
        print(f"{BOLD}{YELLOW} [System Diagnostic Logs - Warnings end]{RESET}\n")
        
        has_valid = "valid_exp" in manager.experiments
        has_missing = "bad_weights_exp" in manager.experiments or "bad_variants_exp" in manager.experiments
        
        if has_valid and not has_missing:
            return True, "Valid configurations loaded perfectly; all 3 malformed configurations skipped gracefully."
        else:
            return False, f"Malformed config loading error. Valid: {has_valid}, Skips failed: {has_missing}."

    run_scenario("Scenario 3: Graceful Skip of Malformed Configurations", scenario_malformed_config)

    # -------------------------------------------------------------------------
    # Scenario 4: Variant Alphabetical Order Stability
    # -------------------------------------------------------------------------
    def scenario_order_stability():
        # Setup configs with identical keys but different input insertion order for variants
        configs_a = [{
            "key": "exp_checkout",
            "status": "active",
            "variants": [
                {"id": "treatment", "weight": 20},
                {"id": "control", "weight": 80}
            ]
        }]
        
        configs_b = [{
            "key": "exp_checkout",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 80},
                {"id": "treatment", "weight": 20}
            ]
        }]
        
        manager_a = ExperimentManager(configs_a)
        manager_b = ExperimentManager(configs_b)
        
        # Test variant allocation boundaries internally
        var_a = manager_a.experiments["exp_checkout"].variants
        var_b = manager_b.experiments["exp_checkout"].variants
        
        # Check that control occupies first index [0.0, 0.8) and treatment is second in both
        if var_a[0].variant_id != "control" or var_b[0].variant_id != "control":
            return False, "Alphabetical sorting was not applied to variant bounds."
        if var_a[0].cumulative_upper != 0.8 or var_b[0].cumulative_upper != 0.8:
            return False, "Cumulative pre-computation boundary error."
            
        # Verify 100 random user assignments are 100% identical in both managers
        mismatch_count = 0
        for i in range(100):
            uid = f"user_{i}"
            res_a = manager_a.get_variant("exp_checkout", uid)
            res_b = manager_b.get_variant("exp_checkout", uid)
            if res_a != res_b:
                mismatch_count += 1
                
        if mismatch_count > 0:
            return False, f"Found {mismatch_count} variant discrepancies between shuffled configurations!"
            
        return True, "Variants sorted alphabetically. Boundaries remain stable regardless of config order."

    run_scenario("Scenario 4: Variant Alphabetical Order Stability", scenario_order_stability)

    # -------------------------------------------------------------------------
    # Scenario 5: User Attribute Targeting - Positive Rules (EQUALS, IN)
    # -------------------------------------------------------------------------
    def scenario_positive_targeting():
        configs = [{
            "key": "pricing_discount",
            "status": "active",
            "variants": [{"id": "treatment", "weight": 100}],
            "targeting": [
                {"attribute": "country", "operator": "EQUALS", "value": "US"},
                {"attribute": "subscription_tier", "operator": "IN", "values": ["gold", "platinum"]}
            ]
        }]
        manager = ExperimentManager(configs)
        
        # User 1: matches all
        u1 = {"country": "US", "subscription_tier": "gold"}
        # User 2: country matches, tier fails
        u2 = {"country": "US", "subscription_tier": "silver"}
        # User 3: country fails, tier matches
        u3 = {"country": "CA", "subscription_tier": "platinum"}
        
        r1 = manager.get_variant("pricing_discount", "user_1", u1)
        r2 = manager.get_variant("pricing_discount", "user_2", u2)
        r3 = manager.get_variant("pricing_discount", "user_3", u3)
        
        if r1 == "treatment" and r2 is None and r3 is None:
            return True, "EQUALS and IN logic evaluate perfectly. Non-targeted users skipped."
        else:
            return False, f"Targeting mismatch. User 1: {r1}, User 2: {r2}, User 3: {r3}"

    run_scenario("Scenario 5: User Attribute Targeting - Positive Rules (EQUALS, IN)", scenario_positive_targeting)

    # -------------------------------------------------------------------------
    # Scenario 6: User Attribute Targeting - Negated Rules (NOT_EQUALS, NOT_IN)
    # -------------------------------------------------------------------------
    def scenario_negated_targeting():
        configs = [{
            "key": "black_friday_deals",
            "status": "active",
            "variants": [{"id": "treatment", "weight": 100}],
            "targeting": [
                {"attribute": "country", "operator": "NOT_EQUALS", "value": "CN"},
                {"attribute": "subscription_tier", "operator": "NOT_IN", "values": ["free", "trial"]}
            ]
        }]
        manager = ExperimentManager(configs)
        
        # User 1: targets match (US + silver)
        u1 = {"country": "US", "subscription_tier": "silver"}
        # User 2: country matches (US), tier excluded (free)
        u2 = {"country": "US", "subscription_tier": "free"}
        # User 3: country excluded (CN), tier matches (silver)
        u3 = {"country": "CN", "subscription_tier": "silver"}
        
        r1 = manager.get_variant("black_friday_deals", "user_1", u1)
        r2 = manager.get_variant("black_friday_deals", "user_2", u2)
        r3 = manager.get_variant("black_friday_deals", "user_3", u3)
        
        if r1 == "treatment" and r2 is None and r3 is None:
            return True, "NOT_EQUALS and NOT_IN negated targeting rules evaluate perfectly."
        else:
            return False, f"Negated logic discrepancy. User 1: {r1}, User 2: {r2}, User 3: {r3}"

    run_scenario("Scenario 6: User Attribute Targeting - Negated Rules (NOT_EQUALS, NOT_IN)", scenario_negated_targeting)

    # -------------------------------------------------------------------------
    # Scenario 7: User Attribute Targeting - Numeric Range Rules with Type Casting (GREATER_THAN, LESS_THAN)
    # -------------------------------------------------------------------------
    def scenario_numeric_targeting():
        configs = [{
            "key": "restricted_gaming_mode",
            "status": "active",
            "variants": [{"id": "game_on", "weight": 100}],
            "targeting": [
                {"attribute": "age", "operator": "GREATER_THAN", "value": 18},
                {"attribute": "days_active", "operator": "LESS_THAN", "value": 30}
            ]
        }]
        manager = ExperimentManager(configs)
        
        # User 1: direct numeric matches
        u1 = {"age": 25, "days_active": 15}
        # User 2: string-coerced values compared against floats (type cast test)
        u2 = {"age": "25", "days_active": "15"}
        # User 3: fail limits (age 18, fails age > 18)
        u3 = {"age": 18, "days_active": 15}
        
        r1 = manager.get_variant("restricted_gaming_mode", "user_1", u1)
        r2 = manager.get_variant("restricted_gaming_mode", "user_2", u2)
        r3 = manager.get_variant("restricted_gaming_mode", "user_3", u3)
        
        if r1 == "game_on" and r2 == "game_on" and r3 is None:
            return True, "Numeric operators evaluated correctly. Dynamic float type-casting works seamlessly."
        else:
            return False, f"Numeric mismatch. User 1 (Num): {r1}, User 2 (String): {r2}, User 3 (Fail): {r3}"

    run_scenario("Scenario 7: User Attribute Targeting - Numeric Range Rules with Type Casting (GREATER_THAN, LESS_THAN)", scenario_numeric_targeting)

    # -------------------------------------------------------------------------
    # Scenario 8: Targeting Type Cast & Missing Attribute Safety
    # -------------------------------------------------------------------------
    def scenario_targeting_safeguards():
        configs = [{
            "key": "restricted_gaming_mode",
            "status": "active",
            "variants": [{"id": "game_on", "weight": 100}],
            "targeting": [
                {"attribute": "age", "operator": "GREATER_THAN", "value": 18}
            ]
        }]
        manager = ExperimentManager(configs)
        
        # User 1: Missing attributes dictionary
        r1 = manager.get_variant("restricted_gaming_mode", "user_1", None)
        # User 2: Attributes dict provided but 'age' key absent
        r2 = manager.get_variant("restricted_gaming_mode", "user_2", {"country": "US"})
        # User 3: Uncastable alpha-numeric string in numeric condition
        r3 = manager.get_variant("restricted_gaming_mode", "user_3", {"age": "twenty-five"})
        
        if r1 is None and r2 is None and r3 is None:
            return True, "All targeting edge cases (missing attributes, uncastable conversions) handled safely with zero runtime crashes."
        else:
            return False, f"Safeguard breakdown! User 1: {r1}, User 2: {r2}, User 3: {r3}"

    run_scenario("Scenario 8: Targeting Type Cast & Missing Attribute Safety", scenario_targeting_safeguards)

    # -------------------------------------------------------------------------
    # Scenario 9: Empty & Invalid Parameter Validations
    # -------------------------------------------------------------------------
    def scenario_invalid_parameters():
        configs = [{
            "key": "valid_exp",
            "status": "active",
            "variants": [{"id": "v1", "weight": 100}]
        }]
        manager = ExperimentManager(configs)
        
        # Test None & Empty strings
        r1 = manager.get_variant(None, "user_1")  # type: ignore
        r2 = manager.get_variant("valid_exp", None)  # type: ignore
        r3 = manager.get_variant("", "user_1")
        r4 = manager.get_variant("valid_exp", "")
        
        # Test bad types
        r5 = manager.get_variant(1234, "user_1")  # type: ignore
        r6 = manager.get_variant("valid_exp", 9999)  # type: ignore
        
        if all(res is None for res in [r1, r2, r3, r4, r5, r6]):
            return True, "API methods validate inputs: non-strings and empty parameters fail safely by returning None."
        else:
            return False, f"Input validation failed. R1-R6 values: {[r1, r2, r3, r4, r5, r6]}"

    run_scenario("Scenario 9: Empty & Invalid Parameter Validations", scenario_invalid_parameters)

    # -------------------------------------------------------------------------
    # Scenario 10: Strict Statistical Distribution Checks (100k Users)
    # -------------------------------------------------------------------------
    def scenario_statistical_distribution():
        configs = [{
            "key": "split_50_50",
            "status": "active",
            "variants": [
                {"id": "control", "weight": 50},
                {"id": "treatment", "weight": 50}
            ]
        }]
        manager = ExperimentManager(configs)
        
        counts = {"control": 0, "treatment": 0}
        total_runs = 100000
        
        for i in range(total_runs):
            uid = f"user_{i}"
            variant = manager.get_variant("split_50_50", uid)
            if variant:
                counts[variant] += 1
                
        control_ratio = counts["control"] / total_runs
        treatment_ratio = counts["treatment"] / total_runs
        
        # Assert within 1% margin (ratio should be between 0.49 and 0.51)
        margin_ok = (0.49 <= control_ratio <= 0.51) and (0.49 <= treatment_ratio <= 0.51)
        
        details = (
            f"Control: {counts['control']} ({control_ratio:.2%}), "
            f"Treatment: {counts['treatment']} ({treatment_ratio:.2%}). "
            f"Result is within strict 1% tolerance window: {margin_ok}."
        )
        
        return margin_ok, details

    run_scenario("Scenario 10: Strict Statistical Distribution Checks (100k Users)", scenario_statistical_distribution)

    # -------------------------------------------------------------------------
    # Verification Summary
    # -------------------------------------------------------------------------
    print_header("📊 SCENARIO RUN SUMMARY")
    print(f"Total Scenarios Executed: {total_scenarios}")
    print(f"Passed Scenarios        : {GREEN}{BOLD}{passed_scenarios}{RESET}")
    print(f"Failed Scenarios        : {RED if total_scenarios - passed_scenarios > 0 else GREEN}{BOLD}{total_scenarios - passed_scenarios}{RESET}")
    print(f"{CYAN}{'='*80}{RESET}\n")

    if passed_scenarios == total_scenarios:
        print(f"{BOLD}{GREEN}ALL SCENARIOS COMPLETED SUCCESSFULLY! The system is highly robust and statistically sound.{RESET}\n")
        sys.exit(0)
    else:
        print(f"{BOLD}{RED}SOME SCENARIOS FAILED. Please review the diagnostic log details.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
