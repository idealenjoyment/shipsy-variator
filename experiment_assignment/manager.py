import logging
from typing import List, Dict, Any, Optional

from experiment_assignment.types import ExperimentConfig, VariantBoundary, TargetingRule
from experiment_assignment.hash_engine import compute_ratio, assign_variant
from experiment_assignment.targeting import evaluate_targeting

logger = logging.getLogger("experiment_assignment")

class ExperimentManager:
    def __init__(self, configs: Optional[List[Dict[str, Any]]] = None):
        """
        Initializes the ExperimentManager and optionally loads configurations.
        """
        self.experiments: Dict[str, ExperimentConfig] = {}
        if configs:
            self.load_configurations(configs)

    def load_configurations(self, configs: List[Dict[str, Any]]) -> None:
        """
        Parses raw configuration lists into optimized ExperimentConfig objects,
        pre-computing cumulative ranges for variants and sorting variants by ID.
        """
        if not isinstance(configs, list):
            logger.warning("Invalid configuration type supplied: expected list of dicts.")
            return

        for item in configs:
            if not isinstance(item, dict):
                logger.warning(f"Skipping malformed configuration item: {item}")
                continue

            key = item.get("key")
            status = item.get("status")
            raw_variants = item.get("variants")
            raw_targeting = item.get("targeting")

            # 1. Basic configuration checks
            if not key or not isinstance(key, str):
                logger.warning("Skipping experiment configuration: missing or empty key string.")
                continue

            if status != "active":
                # Exp is skipped or stored as inactive. Skipping from self.experiments matches "inactive" -> returns None.
                logger.info(f"Skipping inactive experiment: {key}")
                continue

            if not isinstance(raw_variants, list) or not raw_variants:
                logger.warning(f"Skipping active experiment '{key}': missing or empty variants list.")
                continue

            # 2. Variants validation and weight pre-computation
            valid_variants = []
            has_malformed_variant = False
            for v in raw_variants:
                if not isinstance(v, dict) or "id" not in v or "weight" not in v:
                    has_malformed_variant = True
                    break
                try:
                    weight_val = float(v["weight"])
                    if weight_val < 0:
                        has_malformed_variant = True
                        break
                except (ValueError, TypeError):
                    has_malformed_variant = True
                    break
                valid_variants.append({"id": str(v["id"]), "weight": weight_val})

            if has_malformed_variant:
                logger.warning(f"Skipping active experiment '{key}': contains invalid, non-numeric, or negative variant weight.")
                continue

            # 3. Alphabetical sorting of variants to ensure order stability
            sorted_variants = sorted(valid_variants, key=lambda x: x["id"])

            total_weight = sum(v["weight"] for v in sorted_variants)
            if total_weight <= 0:
                logger.warning(f"Skipping active experiment '{key}': total variants weight must be greater than zero.")
                continue

            # 4. Precompute cumulative boundaries mapped to range [0.0, 1.0]
            boundaries = []
            cumulative_sum = 0.0
            for v in sorted_variants:
                cumulative_sum += v["weight"] / total_weight
                boundaries.append(VariantBoundary(
                    variant_id=v["id"],
                    cumulative_upper=cumulative_sum
                ))

            # 5. Parse targeting rules if present
            parsed_rules = []
            if raw_targeting:
                if not isinstance(raw_targeting, list):
                    logger.warning(f"Skipping active experiment '{key}': targeting rules must be supplied as a list.")
                    continue
                
                has_malformed_rule = False
                for rule in raw_targeting:
                    if not isinstance(rule, dict) or "attribute" not in rule or "operator" not in rule:
                        has_malformed_rule = True
                        break
                    
                    parsed_rules.append(TargetingRule(
                        attribute=str(rule["attribute"]),
                        operator=str(rule["operator"]),
                        value=rule.get("value"),
                        values=rule.get("values")
                    ))
                
                if has_malformed_rule:
                    logger.warning(f"Skipping active experiment '{key}': targeting list contains malformed rules.")
                    continue

            # Load into self.experiments
            self.experiments[key] = ExperimentConfig(
                key=key,
                status=status,
                variants=boundaries,
                targeting=parsed_rules if parsed_rules else None
            )

    def get_variant(
        self,
        experiment_key: str,
        user_id: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Determines variant assignment deterministically and statelessly.
        Returns a variant string id, or None if missing, inactive, or not targeted.
        """
        # Validate inputs
        if not isinstance(experiment_key, str) or not isinstance(user_id, str):
            return None
        
        if not experiment_key or not user_id:
            return None

        # Fetch experiment
        experiment = self.experiments.get(experiment_key)
        if not experiment or experiment.status != "active":
            return None

        # Evaluate targeting rules
        if experiment.targeting and not evaluate_targeting(experiment.targeting, attributes):
            return None

        # Deterministic assignment calculation
        try:
            ratio = compute_ratio(experiment_key, user_id)
            return assign_variant(experiment, ratio)
        except (ValueError, TypeError):
            return None
