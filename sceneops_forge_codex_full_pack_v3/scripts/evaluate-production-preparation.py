#!/usr/bin/env python3
"""Validate and summarize comparable legacy/prepared production runs."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


CASES = {"single-screen-collection", "character-survival", "existing-game-modification"}
FLOWS = {"legacy", "prepared"}


def score(run):
    return (2 * bool(run["playable"]) + 2 * bool(run["actual_asset_references"])
            + bool(run["style_scale_consistent"])
            + bool(run["preserved_existing_changes"]))


def validate_run(value, index):
    required = {"case_id", "flow", "repeat", "primary_model", "total_budget",
                "playable", "selected_assets", "actual_asset_references",
                "style_scale_consistent", "preserved_existing_changes",
                "elapsed_ms", "total_tokens", "user_interventions",
                "quality_observations"}
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"run {index} missing fields: {', '.join(missing)}")
    if value["case_id"] not in CASES or value["flow"] not in FLOWS:
        raise ValueError(f"run {index} has an unknown case_id or flow")
    if not isinstance(value["repeat"], int) or value["repeat"] < 1:
        raise ValueError(f"run {index} repeat must be a positive integer")
    if not isinstance(value["selected_assets"], list) or not isinstance(value["actual_asset_references"], list):
        raise ValueError(f"run {index} asset fields must be arrays")
    if not isinstance(value["quality_observations"], list):
        raise ValueError(f"run {index} quality_observations must be an array")
    for field in ("elapsed_ms", "total_tokens", "user_interventions"):
        if isinstance(value[field], bool) or not isinstance(value[field], (int, float)) or value[field] < 0:
            raise ValueError(f"run {index} {field} must be a non-negative number")
    return value


def evaluate(values):
    runs = [validate_run(value, index) for index, value in enumerate(values, 1)]
    grouped = defaultdict(list)
    for run in runs:
        grouped[(run["case_id"], run["flow"])].append(run)

    failures = []
    rows = []
    for case_id in sorted(CASES):
        legacy = grouped[(case_id, "legacy")]
        prepared = grouped[(case_id, "prepared")]
        if len(legacy) < 2 or len(prepared) < 2:
            failures.append(f"{case_id}: old/new each require at least two runs")
            continue
        models = {run["primary_model"] for run in legacy + prepared}
        budgets = {json.dumps(run["total_budget"], ensure_ascii=False, sort_keys=True)
                   for run in legacy + prepared}
        if len(models) != 1:
            failures.append(f"{case_id}: primary models are not identical")
        if len(budgets) != 1:
            failures.append(f"{case_id}: total budgets are not comparable")
        legacy_score = sum(score(run) for run in legacy) / len(legacy)
        prepared_score = sum(score(run) for run in prepared) / len(prepared)
        runs_without_actual = [run["repeat"] for run in prepared
                               if not run["actual_asset_references"]]
        runs_without_observation = [run["repeat"] for run in prepared
                                    if not any(str(item).strip()
                                               for item in run["quality_observations"])]
        observations = [str(item).strip().replace("|", "\\|") for run in prepared
                        for item in run["quality_observations"] if str(item).strip()]
        if runs_without_actual:
            failures.append(f"{case_id}: prepared repeats without actual asset references: "
                            + ", ".join(map(str, runs_without_actual)))
        if runs_without_observation:
            failures.append(f"{case_id}: prepared repeats without concrete quality observations: "
                            + ", ".join(map(str, runs_without_observation)))
        if prepared_score <= legacy_score:
            failures.append(f"{case_id}: prepared quality score did not improve")
        average = lambda values, field: sum(run[field] for run in values) / len(values)
        rows.append((case_id, legacy_score, prepared_score,
                     average(legacy, "elapsed_ms"), average(prepared, "elapsed_ms"),
                     average(legacy, "total_tokens"), average(prepared, "total_tokens"),
                     average(legacy, "user_interventions"),
                     average(prepared, "user_interventions"), "；".join(observations)))
    return rows, failures


def report(rows, failures):
    lines = ["# 制作准备 A/B 验收", "",
             "| 案例 | 旧/新质量 | 旧/新耗时 ms | 旧/新 Token | 旧/新用户介入 | 具体收益 |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for (case_id, old, new, old_elapsed, new_elapsed, old_tokens, new_tokens,
         old_interventions, new_interventions, observations) in rows:
        lines.append(
            f"| {case_id} | {old:.2f} / {new:.2f} | {old_elapsed:.0f} / {new_elapsed:.0f} | "
            f"{old_tokens:.0f} / {new_tokens:.0f} | {old_interventions:.2f} / "
            f"{new_interventions:.2f} | {observations} |")
    lines.extend(["", "## 结果", "", "通过" if not failures else "未通过"])
    if failures:
        lines.extend(["", *[f"- {failure}" for failure in failures]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    values = json.loads(arguments.input.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise SystemExit("input must be a JSON array of run records")
    rows, failures = evaluate(values)
    text = report(rows, failures)
    if arguments.output:
        arguments.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
