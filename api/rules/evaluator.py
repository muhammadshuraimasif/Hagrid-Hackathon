"""Safe, pure recursive JSONLogic evaluator with 3-valued logic (pass, fail, unknown).

Implements safe evaluation without `eval()` or code execution.
If required data fields are missing, evaluates to UNKNOWN rather than raising exceptions.
"""
from typing import Any, Dict, List, Tuple, Union

class _UnknownSentinel:
    def __repr__(self):
        return "<UNKNOWN>"

UNKNOWN = _UnknownSentinel()


def evaluate_expression(expr: Any, data: Dict[str, Any]) -> Any:
    """Evaluates a JSONLogic expression against a data dictionary.
    
    Returns the evaluated value, which may be a primitive (bool, int, float, str),
    a list, or UNKNOWN.
    """
    if not isinstance(expr, dict):
        # Primitive literal or list
        if isinstance(expr, list):
            return [evaluate_expression(item, data) for item in expr]
        return expr

    if len(expr) == 0:
        return True

    op, args = next(iter(expr.items()))

    # Normalize single argument into list if needed (except for var which can take a single string)
    if not isinstance(args, list) and op not in ("var",):
        args = [args]

    # 1. Variable extraction: {"var": "field_name"} or {"var": ["field_name", default]}
    if op == "var":
        if isinstance(args, list):
            var_name = args[0] if len(args) > 0 else ""
            default_val = args[1] if len(args) > 1 else UNKNOWN
        else:
            var_name = args
            default_val = UNKNOWN

        if not isinstance(var_name, str):
            return default_val

        # Support dotted paths if needed, e.g. "applicant.income"
        parts = var_name.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default_val

        if current is None:
            return default_val
        return current

    # 2. Logical AND: {"and": [...]}
    if op == "and":
        has_unknown = False
        for sub_expr in args:
            res = evaluate_expression(sub_expr, data)
            if res is UNKNOWN:
                has_unknown = True
            elif not bool(res):
                return False  # Definitive False dominates AND
        if has_unknown:
            return UNKNOWN
        return True

    # 3. Logical OR: {"or": [...]}
    if op == "or":
        has_unknown = False
        for sub_expr in args:
            res = evaluate_expression(sub_expr, data)
            if res is True:
                return True  # Definitive True dominates OR
            elif res is UNKNOWN:
                has_unknown = True
        if has_unknown:
            return UNKNOWN
        return False

    # 4. Logical NOT: {"!": [expr]}
    if op == "!":
        sub_expr = args[0] if isinstance(args, list) and len(args) > 0 else args
        res = evaluate_expression(sub_expr, data)
        if res is UNKNOWN:
            return UNKNOWN
        return not bool(res)

    # 5. Comparisons
    left = evaluate_expression(args[0], data) if len(args) > 0 else None
    right = evaluate_expression(args[1], data) if len(args) > 1 else None

    if left is UNKNOWN or right is UNKNOWN:
        return UNKNOWN

    try:
        if op in ("==", "==="):
            return left == right
        elif op in ("!=", "!=="):
            return left != right
        elif op == "<":
            return left < right
        elif op == "<=":
            return left <= right
        elif op == ">":
            return left > right
        elif op == ">=":
            return left >= right
        elif op == "in":
            if right is None:
                return False
            return left in right
    except Exception:
        return UNKNOWN

    return UNKNOWN


def evaluate_rule(rule_expr: Any, data: Dict[str, Any]) -> str:
    """Evaluates a single rule expression against case data.
    
    Returns:
        "pass": definitively evaluated to True
        "fail": definitively evaluated to False
        "unknown": missing data or unknown fields prevented definitive evaluation
    """
    res = evaluate_expression(rule_expr, data)
    if res is UNKNOWN:
        return "unknown"
    if bool(res):
        return "pass"
    return "fail"
