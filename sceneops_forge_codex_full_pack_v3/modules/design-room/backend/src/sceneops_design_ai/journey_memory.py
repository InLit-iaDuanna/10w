"""Public memory views of planning-owned state; no second store of decisions."""
from uuid import uuid4
from fastapi import HTTPException
from .journey_models import JourneyCommand


DIRECTION_FIELDS = {
    "core_experience": ("核心体验", "decision"),
    "perspective_style": ("视角与风格", "decision"),
    "simplified_scope": ("初版范围", "constraint"),
    "code_architecture": ("工程架构", "constraint"),
    "target_platform": ("目标平台", "constraint"),
}


def message_groups(state):
    yield state.messages
    yield from state.card_messages.values()
    for conversations in state.card_conversations.values():
        for conversation in conversations:
            yield conversation.messages
    for session in state.modeling_sessions:
        yield session.messages


def memory_source(service, project_id, source_id):
    prefix = f"journey:{project_id}:message:"
    if not source_id.startswith(prefix):
        return None
    message_id = source_id[len(prefix):]
    state = service.get(project_id)
    for group in message_groups(state):
        for item in group:
            if item.id == message_id:
                return dict(id=source_id, kind="message", role=item.role, text=item.text,
                    created_at=item.created_at,
                    evidence_status="user_statement" if item.role == "user" else "reported",
                    origin_key=source_id)
    return None


def project_memory(service, project_id):
    state = service.get(project_id)
    direction = state.initial_demo_direction
    if direction is None or not direction.confirmed:
        return []
    return [dict(id=f"journey:direction:{field}", project_id=project_id,
        title=title, content=getattr(direction, field), category=category,
        revision=state.revision, source_ref=f"journey:{project_id}:direction:{direction.direction_id}",
        editable=field in {"core_experience", "perspective_style", "simplified_scope"})
        for field, (title, category) in DIRECTION_FIELDS.items()]


async def update_project_memory(service, project_id, reference_id, expected_revision, content, source):
    field = reference_id.removeprefix("journey:direction:")
    if reference_id != f"journey:direction:{field}" or field not in {
            "core_experience", "perspective_style", "simplified_scope"}:
        raise HTTPException(422, "该项目事实需通过原有工程操作修改。")
    state = service.get(project_id)
    if state.revision != expected_revision:
        raise HTTPException(409, "项目决定已更新，请重新读取后纠正。")
    direction = state.initial_demo_direction
    if direction is None or not direction.confirmed:
        raise HTTPException(409, "项目没有已确认的初版方向。")
    # Reuse the owning command's architecture checks, versioning and folder export.
    values = {key: getattr(direction, key) for key in (
        "core_experience", "perspective_style", "simplified_scope", "code_architecture", "camera_mode")}
    values[field] = content
    await service.command(project_id, JourneyCommand(request_id=f"memory_{uuid4().hex}",
        expected_revision=expected_revision, operation="confirm_demo_direction", **values))
    return next(item for item in project_memory(service, project_id) if item["id"] == reference_id)


class GenerationResult:
    """Preserve provider response fields while attaching the exact conversation identity."""
    def __init__(self, response, message_id, text):
        self.response, self.memory_message_id, self.text = response, message_id, text

    def __getattr__(self, name):
        return getattr(self.response, name)
