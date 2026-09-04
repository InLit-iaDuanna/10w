from __future__ import annotations

from .contracts import (ChangeSet, ExecutionMode, Provenance, ResolutionProfile,
                        UiFlow, ValidationIssue, ValidationReport)


class UiStudioService:
    """Validates UI specs; it never writes Unity files directly."""

    def validate_flow(self, flow: UiFlow, profile: ResolutionProfile,
                      character_limit: int, provenance: Provenance) -> ValidationReport:
        provenance.validate()
        issues: list[ValidationIssue] = []
        screen_ids = {screen.id for screen in flow.screens}
        if not flow.screens or flow.entry_screen_id not in screen_ids:
            issues.append(ValidationIssue("FLOW_ENTRY_INVALID", "入口界面不存在。"))
        if len(screen_ids) != len(flow.screens):
            issues.append(ValidationIssue("FLOW_SCREEN_DUPLICATE", "界面 ID 必须唯一。"))
        for screen in flow.screens:
            for target in screen.next_screen_ids:
                if target not in screen_ids:
                    issues.append(ValidationIssue("FLOW_TARGET_MISSING", "流程指向了不存在的界面。", screen.id))
            for locale, text in screen.localized_text.items():
                if len(text) > character_limit:
                    issues.append(ValidationIssue("LOCALIZATION_OVERFLOW", f"{locale} 文案超过 {character_limit} 字符。", screen.id))
        safe = profile.safe_area
        if profile.width <= 0 or profile.height <= 0 or min(safe.left, safe.top, safe.right, safe.bottom) < 0:
            issues.append(ValidationIssue("RESOLUTION_INVALID", "分辨率或安全区域无效。"))
        elif safe.left + safe.right >= profile.width or safe.top + safe.bottom >= profile.height:
            issues.append(ValidationIssue("SAFE_AREA_EMPTY", "安全区域没有可用界面空间。"))
        else:
            for screen in flow.screens:
                for element in screen.elements:
                    if not self._inside_safe_area(element, profile):
                        issues.append(ValidationIssue("SAFE_AREA_ELEMENT_OUT_OF_BOUNDS", "界面元素超出安全区域。", screen.id))
        return ValidationReport(flow.id, tuple(issues), ExecutionMode.MOCK, provenance)

    @staticmethod
    def _inside_safe_area(element, profile: ResolutionProfile) -> bool:
        safe = profile.safe_area
        left, top = safe.left, safe.top
        right, bottom = profile.width - safe.right, profile.height - safe.bottom
        anchors = {
            "safe-top-left": (left, top), "safe-top-right": (right, top),
            "safe-top-center": ((left + right) // 2, top),
            "safe-bottom-left": (left, bottom), "safe-bottom-right": (right, bottom),
            "safe-bottom-center": ((left + right) // 2, bottom),
            "safe-center": ((left + right) // 2, (top + bottom) // 2),
        }
        if element.anchor not in anchors or element.width <= 0 or element.height <= 0:
            return False
        x, y = anchors[element.anchor]
        if "right" in element.anchor: x -= element.width
        elif element.anchor.endswith("center"): x -= element.width // 2
        if "bottom" in element.anchor: y -= element.height
        elif element.anchor == "safe-center": y -= element.height // 2
        x += element.offset_x
        y += element.offset_y
        return left <= x and top <= y and x + element.width <= right and y + element.height <= bottom

    def propose_mapping(self, change_set: ChangeSet, adapter) -> ChangeSet:
        if change_set.state.value != "proposed":
            raise ValueError("only proposed ChangeSets may be previewed")
        change_set.validate()
        if not adapter.capability_report().get("ui_mapping", False):
            raise ValueError("Unity adapter does not support UI mapping")
        result = adapter.dry_run_ui_mapping(change_set.request)
        request = change_set.request
        if (result.mapping_id != request.mapping_id or result.prefab_id != request.prefab_id
                or result.unity_canvas_path != request.unity_canvas_path):
            raise ValueError("adapter dry-run output does not match the proposed mapping target")
        if result.mode is ExecutionMode.BLOCKED:
            raise ValueError("Unity adapter blocked the UI mapping dry-run")
        if result.provenance is not None:
            result.provenance.validate()
            if (result.provenance.adapter_version != result.adapter_version or
                    result.provenance.mode is not result.mode or
                    result.provenance.source_project_id != request.source_project_id or
                    result.provenance.source_version != request.base_version or
                    set(result.provenance.related_sceneops_ids) != set(request.target_sceneops_ids)):
                raise ValueError("adapter dry-run provenance does not match the proposed mapping")
        change_set.mapping_result = result
        return change_set
