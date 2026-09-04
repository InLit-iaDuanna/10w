from __future__ import annotations

from typing import Dict, List, Protocol

from .regression import ComparisonIdentityConflictError
from .schemas import Issue, PlaytestRun, RegressionComparison


class PlaytestRepository(Protocol):
    def save_run(self, run: PlaytestRun) -> None: ...

    def get_run(self, run_id: str) -> PlaytestRun: ...

    def save_issue(self, issue: Issue) -> None: ...

    def get_issue(self, issue_id: str) -> Issue: ...

    def list_issues(self, run_id: str) -> List[Issue]: ...

    def save_comparison(self, comparison: RegressionComparison) -> None: ...

    def get_comparison(self, comparison_id: str) -> RegressionComparison: ...


class InMemoryPlaytestRepository:
    def __init__(self) -> None:
        self.runs: Dict[str, PlaytestRun] = {}
        self.comparisons: Dict[str, RegressionComparison] = {}

    def save_run(self, run: PlaytestRun) -> None:
        if run.run_id in self.runs:
            if self.runs[run.run_id] == run:
                return
            raise ValueError(f"run {run.run_id} is append-only")
        self.runs[run.run_id] = run.model_copy(deep=True)

    def get_run(self, run_id: str) -> PlaytestRun:
        return self.runs[run_id].model_copy(deep=True)

    def save_issue(self, issue: Issue) -> None:
        run = self.runs[issue.run_id]
        if issue.issue_id not in {item.issue_id for item in run.issues}:
            raise KeyError(issue.issue_id)
        issues = [
            issue if item.issue_id == issue.issue_id else item
            for item in run.issues
        ]
        payload = run.model_dump(mode="python")
        payload["issues"] = issues
        self.runs[run.run_id] = PlaytestRun.model_validate(payload)

    def get_issue(self, issue_id: str) -> Issue:
        for run in self.runs.values():
            for issue in run.issues:
                if issue.issue_id == issue_id:
                    return issue.model_copy(deep=True)
        raise KeyError(issue_id)

    def list_issues(self, run_id: str) -> List[Issue]:
        return [issue.model_copy(deep=True) for issue in self.runs[run_id].issues]

    def save_comparison(self, comparison: RegressionComparison) -> None:
        if comparison.comparison_id in self.comparisons:
            if self.comparisons[comparison.comparison_id] == comparison:
                return
            raise ComparisonIdentityConflictError(
                f"comparison {comparison.comparison_id} is append-only"
            )
        self.comparisons[comparison.comparison_id] = comparison.model_copy(deep=True)

    def get_comparison(self, comparison_id: str) -> RegressionComparison:
        return self.comparisons[comparison_id].model_copy(deep=True)
