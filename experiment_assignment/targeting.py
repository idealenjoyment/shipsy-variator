from typing import List, Dict, Any, Optional
from experiment_assignment.types import TargetingRule

def evaluate_targeting(rules: List[TargetingRule], attributes: Optional[Dict[str, Any]]) -> bool:
    """
    Evaluates a list of targeting rules against user attributes.
    All rules must match (AND condition) for this to return True.
    """
    if not rules:
        return True  # No targeting rules means all users pass
        
    if not attributes:
        return False  # Rules exist but no attributes supplied
        
    for rule in rules:
        attr = rule.attribute
        if attr not in attributes:
            return False  # Missing required attribute fails immediately
            
        user_val = attributes[attr]
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
                # Safe type conversion for comparison
                user_num = float(user_val)  # type: ignore
                rule_num = float(rule.value)  # type: ignore
            except (ValueError, TypeError):
                return False  # Type conversion failed, fail rule safely
                
            if op == "GREATER_THAN" and not (user_num > rule_num):
                return False
            elif op == "LESS_THAN" and not (user_num < rule_num):
                return False
                
        else:
            return False  # Fail-safe for unsupported operator
            
    return True
