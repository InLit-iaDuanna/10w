from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .models import (
    Condition,
    ConditionOperator,
    Effect,
    EffectOperation,
    StateVariable,
    ValidationIssue,
    ValueType,
)
from .validation_support import add_issue


_CONDITION_OPERATORS = {
    ValueType.BOOLEAN: {
        ConditionOperator.EQUALS,
        ConditionOperator.NOT_EQUALS,
    },
    ValueType.INTEGER: {
        ConditionOperator.EQUALS,
        ConditionOperator.NOT_EQUALS,
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_THAN_OR_EQUAL,
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_THAN_OR_EQUAL,
    },
    ValueType.NUMBER: {
        ConditionOperator.EQUALS,
        ConditionOperator.NOT_EQUALS,
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_THAN_OR_EQUAL,
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_THAN_OR_EQUAL,
    },
    ValueType.STRING: {
        ConditionOperator.EQUALS,
        ConditionOperator.NOT_EQUALS,
    },
    ValueType.STRING_SET: {
        ConditionOperator.CONTAINS,
        ConditionOperator.NOT_CONTAINS,
    },
}

_EFFECT_OPERATIONS = {
    ValueType.BOOLEAN: {EffectOperation.SET, EffectOperation.TOGGLE},
    ValueType.INTEGER: {
        EffectOperation.SET,
        EffectOperation.INCREMENT,
        EffectOperation.DECREMENT,
    },
    ValueType.NUMBER: {
        EffectOperation.SET,
        EffectOperation.INCREMENT,
        EffectOperation.DECREMENT,
    },
    ValueType.STRING: {EffectOperation.SET},
    ValueType.STRING_SET: {
        EffectOperation.SET,
        EffectOperation.ADD,
        EffectOperation.REMOVE,
    },
}


def check_variable_initial_values(
    variables: Sequence[StateVariable], issues: List[ValidationIssue]
) -> None:
    for variable in variables:
        if not _value_matches(variable.value_type, variable.initial_value, for_set=True):
            add_issue(
                issues,
                "INVALID_INITIAL_VALUE",
                f"state_variables.{variable.variable_id}.initial_value",
                f"Initial value does not match {variable.value_type.value}.",
            )


def check_conditions(
    conditions: Iterable[Condition],
    variables: Mapping[str, StateVariable],
    location: str,
    issues: List[ValidationIssue],
) -> None:
    for condition in conditions:
        item_location = f"{location}.{condition.condition_id}"
        variable = variables.get(condition.variable_id)
        if variable is None:
            add_issue(
                issues,
                "MISSING_VARIABLE_REFERENCE",
                item_location,
                f"Variable '{condition.variable_id}' is not declared.",
            )
            continue
        if condition.operator not in _CONDITION_OPERATORS[variable.value_type]:
            add_issue(
                issues,
                "INVALID_CONDITION_OPERATOR",
                item_location,
                f"Operator '{condition.operator.value}' is invalid for {variable.value_type.value}.",
            )
        expected_type = (
            ValueType.STRING
            if variable.value_type == ValueType.STRING_SET
            else variable.value_type
        )
        if not _value_matches(expected_type, condition.value):
            add_issue(
                issues,
                "INVALID_CONDITION_VALUE",
                item_location,
                f"Condition value does not match {expected_type.value}.",
            )


def check_effects(
    effects: Iterable[Effect],
    variables: Mapping[str, StateVariable],
    location: str,
    issues: List[ValidationIssue],
) -> None:
    by_variable: Dict[str, List[Effect]] = defaultdict(list)
    for effect in effects:
        item_location = f"{location}.{effect.effect_id}"
        variable = variables.get(effect.variable_id)
        if variable is None:
            add_issue(
                issues,
                "MISSING_VARIABLE_REFERENCE",
                item_location,
                f"Variable '{effect.variable_id}' is not declared.",
            )
            continue
        by_variable[effect.variable_id].append(effect)
        if effect.operation not in _EFFECT_OPERATIONS[variable.value_type]:
            add_issue(
                issues,
                "INVALID_EFFECT_OPERATION",
                item_location,
                f"Operation '{effect.operation.value}' is invalid for {variable.value_type.value}.",
            )
        if not _effect_value_matches(variable.value_type, effect):
            add_issue(
                issues,
                "INVALID_EFFECT_VALUE",
                item_location,
                f"Effect value is invalid for '{effect.operation.value}'.",
            )

    for variable_id, variable_effects in by_variable.items():
        set_values = {
            _stable_value(effect.value)
            for effect in variable_effects
            if effect.operation == EffectOperation.SET
        }
        if len(set_values) > 1:
            add_issue(
                issues,
                "CONFLICTING_EFFECTS",
                location,
                f"Variable '{variable_id}' is set to conflicting values.",
            )
        adds = {
            _stable_value(effect.value)
            for effect in variable_effects
            if effect.operation == EffectOperation.ADD
        }
        removes = {
            _stable_value(effect.value)
            for effect in variable_effects
            if effect.operation == EffectOperation.REMOVE
        }
        if adds & removes:
            add_issue(
                issues,
                "CONFLICTING_EFFECTS",
                location,
                f"Variable '{variable_id}' adds and removes the same value.",
            )


def _value_matches(value_type: ValueType, value: Any, for_set: bool = False) -> bool:
    if value_type == ValueType.BOOLEAN:
        return isinstance(value, bool)
    if value_type == ValueType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == ValueType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == ValueType.STRING:
        return isinstance(value, str)
    if value_type == ValueType.STRING_SET:
        return for_set and isinstance(value, list) and all(
            isinstance(item, str) for item in value
        ) and len(value) == len(set(value))
    return False


def _effect_value_matches(value_type: ValueType, effect: Effect) -> bool:
    if effect.operation == EffectOperation.TOGGLE:
        return effect.value is None
    if effect.operation in {EffectOperation.ADD, EffectOperation.REMOVE}:
        return isinstance(effect.value, str)
    if effect.operation in {EffectOperation.INCREMENT, EffectOperation.DECREMENT}:
        return isinstance(effect.value, (int, float)) and not isinstance(
            effect.value, bool
        )
    return _value_matches(value_type, effect.value, for_set=True)


def _stable_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(sorted(str(item) for item in value)) + "]"
    return repr(value)
