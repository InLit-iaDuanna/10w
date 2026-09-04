from __future__ import annotations

from collections import defaultdict

from .errors import PlannerDomainError
from .graph import downstream_task_ids
from .models import FeatureChangeImpact, FeaturePlanningSnapshot, ProductionPlan, Workstream


def analyze_feature_change(
    old_snapshot: FeaturePlanningSnapshot,
    new_snapshot: FeaturePlanningSnapshot,
    old_plan: ProductionPlan,
    new_plan: ProductionPlan,
) -> FeatureChangeImpact:
    if old_snapshot.feature_ref.feature_id != new_snapshot.feature_ref.feature_id:
        raise PlannerDomainError("FEATURE_ID_MISMATCH", "只能比较同一功能的修订。")
    old_criteria = {item.criterion_id: item for item in old_snapshot.acceptance_criteria}
    new_criteria = {item.criterion_id: item for item in new_snapshot.acceptance_criteria}
    changed = sorted(
        criterion_id
        for criterion_id in old_criteria.keys() | new_criteria.keys()
        if old_criteria.get(criterion_id) != new_criteria.get(criterion_id)
    )
    direct: set[str] = set()
    reasons: dict[str, list[str]] = defaultdict(list)
    for plan in (old_plan, new_plan):
        for task in plan.tasks:
            linked = sorted({link.criterion_id for link in task.acceptance} & set(changed))
            if linked:
                direct.add(task.task_id)
                reasons[task.task_id].extend(f"acceptance:{criterion_id}" for criterion_id in linked)
    if old_snapshot.title != new_snapshot.title or old_snapshot.summary != new_snapshot.summary:
        design_ids = {task.task_id for task in new_plan.tasks if task.workstream == Workstream.DESIGN}
        direct.update(design_ids)
        for task_id in design_ids:
            reasons[task_id].append("feature-definition")
    affected = downstream_task_ids(new_plan, direct)
    for task_id in affected - direct:
        reasons[task_id].append("downstream-dependency")
    return FeatureChangeImpact(
        feature_id=new_snapshot.feature_ref.feature_id,
        from_revision=old_snapshot.feature_ref.revision,
        to_revision=new_snapshot.feature_ref.revision,
        changed_criterion_ids=changed,
        affected_task_ids=sorted(affected),
        reasons={task_id: sorted(set(values)) for task_id, values in sorted(reasons.items())},
    )
