from typing import List

from .models import ValidationIssue


def add_issue(
    issues: List[ValidationIssue],
    code: str,
    location: str,
    message: str,
    severity: str = "error",
) -> None:
    issues.append(
        ValidationIssue(
            code=code,
            severity=severity,
            location=location,
            message=message,
        )
    )
