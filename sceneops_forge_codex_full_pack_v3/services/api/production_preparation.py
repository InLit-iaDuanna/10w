"""Public catalogue adapters for the task-scoped production preparation service."""
from __future__ import annotations

import re

from sceneops_ai_context import CandidateDetail, CandidateIdentity, CandidateSummary


def _relevance(query: str, *values: str) -> float:
    haystack = "\n".join(value.casefold() for value in values if value)
    english = re.findall(r"[a-z][a-z0-9_.-]{2,}", query.casefold())
    chinese = []
    for phrase in re.findall(r"[\u3400-\u9fff]+", query):
        if len(phrase) == 2:
            chinese.append(phrase)
        else:
            chinese.extend(phrase[index:index + size]
                           for size in (3, 2)
                           for index in range(len(phrase) - size + 1))
    terms = [*english, *chinese]
    unique = list(dict.fromkeys(terms))[:128]
    if not unique:
        return 0.1
    matched_weight = sum(max(1, len(term) - 1) for term in unique if term in haystack)
    total_weight = sum(max(1, len(term) - 1) for term in unique)
    return min(1.0, 0.1 + .9 * matched_weight / total_weight)


def _asset_adoptions(production_kind: str, *, builtin: bool) -> list[str]:
    if production_kind == "planning":
        return ["reference"]
    if production_kind == "scene":
        return ["import"] if builtin else ["use"]
    if production_kind == "modeling":
        return ["import"]
    return ["import"] if builtin else ["use"]


def _skill_requirement(skill_id: str, request) -> tuple[bool, list[str]]:
    """Bind operational skills to one capability the current entry can execute."""
    available = request.available_capability_ids
    if request.production_kind == "planning":
        return True, []
    choices: tuple[str, ...] = ()
    if skill_id == "sceneops-blender-technical-artist":
        choices = tuple(item for item in available if item.startswith("blender.asset."))
    elif skill_id == "sceneops-unity-project-engineer":
        choices = tuple(item for item in available if item.startswith("unity."))
    elif skill_id == "sceneops-release-publish":
        choices = ("export.publish",) if "export.publish" in available else ()
    elif skill_id == "sceneops-export-environment":
        choices = ("export.environment.inspect",) if "export.environment.inspect" in available else ()
    elif skill_id in ("sceneops-export-android", "sceneops-export-desktop"):
        choices = ("export.package",) if "export.package" in available else ()
    elif skill_id.startswith("sceneops-threejs-") or skill_id == "sceneops-demo-composer":
        choices = tuple(item for item in ("agent.task.execute", "code.file.write")
                        if item in available)
    elif skill_id == "sceneops-editable-content":
        if request.production_kind in ("game_create", "game_modify"):
            choices = tuple(item for item in ("agent.task.execute", "code.file.write")
                            if item in available)
        elif request.production_kind == "modeling":
            choices = tuple(item for item in available
                            if item == "unity.asset.import" or item.startswith("blender.asset."))
        elif request.production_kind == "scene":
            choices = ("environment.object.place",) if "environment.object.place" in available else ()
    else:
        return True, []
    return (bool(choices), [choices[0]] if choices else [])


class BuiltinAssetCandidates:
    provider_id = "builtin-assets"

    def __init__(self, catalog):
        self.catalog = catalog

    async def list_candidates(self, request, query):
        entries = self.catalog.public_catalog().entries
        required = ({"game_create": ["code.demo_assets.install"],
                     "game_modify": ["code.demo_assets.install"],
                     "scene": ["builtin.asset.adopt"],
                     "modeling": ["unity.asset.import"]}.get(request.production_kind, []))
        return [CandidateSummary(
            provider_id=self.provider_id, candidate_id=f"builtin:{entry.asset_id}",
            kind="asset", title=entry.label,
            summary="；".join(filter(None, (entry.description, entry.category, entry.art_style,
                "适合：" + "、".join(entry.game_genres) if entry.game_genres else ""))),
            scope="builtin", version=f"{entry.pack_id}:{entry.pack_version}",
            production_kinds=["game_create", "game_modify", "modeling", "scene", "planning"],
            required_capability_ids=required,
            relevance=_relevance(query, entry.label, entry.description, entry.category,
                                 entry.art_style, *entry.game_genres),
            attributes={"catalog_asset_id": entry.asset_id, "kind": entry.kind,
                "dimensions_m": entry.dimensions_m, "footprint_m": entry.footprint_m,
                "animations": entry.animations, "triangle_count": entry.triangle_count,
                "supported_adoptions": _asset_adoptions(request.production_kind, builtin=True)},
        ) for entry in entries]

    async def get_candidate_detail(self, request, identity):
        prefix = "builtin:"
        if not identity.candidate_id.startswith(prefix):
            return None
        entry = self.catalog.entry(identity.candidate_id.removeprefix(prefix))
        if identity.version != f"{entry['pack_id']}:{entry['pack_version']}":
            return None
        return CandidateDetail(identity=identity, title=entry["label"], content=entry)


class ProjectAssetCandidates:
    provider_id = "project-assets"

    def __init__(self, catalog):
        self.catalog = catalog

    async def list_candidates(self, request, query):
        result = []
        required = ({"game_create": ["project.asset.provide"],
                     "game_modify": ["project.asset.provide"],
                     "scene": ["environment.object.place"],
                     "modeling": ["unity.asset.import"]}.get(request.production_kind, []))
        for entry in self.catalog.list(request.project_id):
            version = next(item for item in entry.versions
                           if item.source_version == entry.current_version)
            if request.production_kind in ("game_create", "game_modify") and not version.preview_path:
                continue
            result.append(CandidateSummary(
                provider_id=self.provider_id, candidate_id=f"project:{entry.id}",
                kind="asset", title=entry.title,
                summary=f"当前项目资产；版本 {entry.current_version}；尺寸 {version.dimensions_m} 米",
                scope="current_project", project_id=request.project_id,
                version=str(entry.current_version),
                production_kinds=["game_create", "game_modify", "modeling", "scene", "planning"],
                required_capability_ids=required,
                relevance=_relevance(query, entry.title, entry.source_title or "", entry.source_type),
                attributes={"project_asset_id": entry.id, "source_asset_id": entry.source_asset_id,
                    "source_type": entry.source_type, "dimensions_m": version.dimensions_m,
                    "supported_adoptions": _asset_adoptions(request.production_kind, builtin=False)},
            ))
        return result

    async def get_candidate_detail(self, request, identity):
        if not identity.candidate_id.startswith("project:"):
            return None
        entry = self.catalog.get(request.project_id, identity.candidate_id.removeprefix("project:"))
        if identity.version != str(entry.current_version):
            return None
        if request.production_kind in ("game_create", "game_modify"):
            version = next(item for item in entry.versions
                           if item.source_version == entry.current_version)
            return CandidateDetail(identity=identity, title=entry.title, content={
                "project_asset_id": entry.id, "source_asset_id": entry.source_asset_id,
                "asset_version": entry.current_version,
                "asset_version_id": version.asset_version_id,
                "title": entry.title, "dimensions_m": version.dimensions_m,
                "model_rotation_quaternion_xyzw": version.model_rotation_quaternion_xyzw,
                "node_ids": version.node_ids,
                "provisioning": "运行路径由已授权的项目资产提供服务生成。",
            })
        return CandidateDetail(identity=identity, title=entry.title,
                               content=entry.model_dump(mode="json"))


class ExperienceCandidates:
    provider_id = "experience"

    def __init__(self, experience):
        self.experience = experience

    async def list_candidates(self, request, query):
        entries = self.experience.ranked_entries(request.project_id, query, matched_only=True)
        rank = {entry.id: index for index, entry in enumerate(entries)}
        disputed = [entry for entry in entries if entry.status == "disputed"]
        result = []
        for entry in entries:
            evidence_ids = {evidence.id for evidence in entry.evidence}
            related = [other.title for other in disputed if other.id != entry.id
                       and evidence_ids.intersection(evidence.id for evidence in other.evidence)]
            is_disputed = entry.status == "disputed"
            counterexamples = related or ([f"“{entry.title}”当前标记为有争议。"] if is_disputed else [])
            text_relevance = _relevance(query, entry.title, entry.applicability,
                                        entry.content, *entry.domains)
            ranked_relevance = max(.1, 1 - rank[entry.id] / max(1, len(entries)))
            result.append(CandidateSummary(
                provider_id=self.provider_id, candidate_id=f"experience:{entry.id}",
                kind="experience", title=entry.title,
                # The directory is an index. The complete, uncut experience body is
                # available through get_candidate_detail after selection.
                summary=(entry.applicability or
                         f"适用范围见 topics/domains；正文按需读取（{len(entry.content)} 字符）。"),
                scope="current_project" if entry.scope == "project" else "shared",
                project_id=request.project_id if entry.scope == "project" else None,
                revision=entry.revision, enabled=entry.enabled,
                production_kinds=["game_create", "game_modify", "modeling", "scene", "planning", "export"],
                platforms=entry.platforms, disputed=is_disputed,
                counterexamples=counterexamples,
                relevance=(max(text_relevance, ranked_relevance)
                           if text_relevance > .1 else .1),
                attributes={"entry_id": entry.id, "status": entry.status,
                    "topics": entry.topics, "domains": entry.domains,
                    "supported_adoptions": ["reference"]},
            ))
        return result

    async def get_candidate_detail(self, request, identity):
        if not identity.candidate_id.startswith("experience:"):
            return None
        entry = self.experience.get_entry(
            identity.candidate_id.removeprefix("experience:"), request.project_id)
        if identity.revision != entry.revision:
            return None
        return CandidateDetail(identity=identity, title=entry.title,
                               content=entry.model_dump(mode="json"))


class SkillCandidates:
    provider_id = "production-skills"

    def __init__(self, catalog, detail):
        self.catalog = catalog
        self.detail = detail

    async def list_candidates(self, request, query):
        result = []
        for item in self.catalog():
            available, required = _skill_requirement(item["id"], request)
            if not available:
                continue
            result.append(CandidateSummary(
                provider_id=self.provider_id, candidate_id=item["id"], kind="skill",
                title=item["id"], summary=item["summary"], scope="builtin", version="1",
                production_kinds=item["production_kinds"], platforms=item.get("platforms", []),
                required_capability_ids=required,
                relevance=_relevance(query, item["id"], item["summary"]),
                attributes={"supported_adoptions": ["use", "reference"]},
            ))
        return result

    async def get_candidate_detail(self, request, identity):
        if identity.version != "1":
            return None
        try:
            content = self.detail(identity.candidate_id)
        except KeyError:
            return None
        return CandidateDetail(identity=identity, title=identity.candidate_id, content=content)


class CapabilityCandidates:
    provider_id = "production-capabilities"

    async def list_candidates(self, request, query):
        return [CandidateSummary(provider_id=self.provider_id, candidate_id=capability_id,
            kind="capability", title=capability_id, summary="本次请求已授权并公开的制作能力。",
            scope="current_project", project_id=request.project_id,
            production_kinds=[request.production_kind], relevance=1.0)
            for capability_id in request.available_capability_ids]

    async def get_candidate_detail(self, request, identity):
        if identity.candidate_id not in request.available_capability_ids:
            return None
        return CandidateDetail(identity=identity, title=identity.candidate_id,
            content={"capability_id": identity.candidate_id, "available": True})
