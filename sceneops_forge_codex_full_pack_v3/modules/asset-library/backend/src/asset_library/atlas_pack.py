"""Adapt the shipped Atlas100 v2 catalog to SceneOps' builtin asset contract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ATLAS_CATEGORY_LABELS = {
    "architecture": "建筑",
    "equipment": "装备",
    "furnishing": "陈设",
    "machinery": "机械",
    "process_prop": "工艺道具",
    "sample": "样品",
    "tool": "工具",
    "utility": "设施",
}


@dataclass(frozen=True)
class ShippedBuiltinRecord:
    entry: dict[str, Any]
    files: dict[str, Path]


@dataclass(frozen=True)
class ShippedBuiltinPack:
    root: Path
    summary: dict[str, Any]
    records: tuple[ShippedBuiltinRecord, ...]


def _dimensions(record: dict[str, Any]) -> list[float]:
    dimensions = record.get("dimensions_m")
    if dimensions:
        return [float(value) for value in dimensions]
    bounds = record["bounds_m"]
    return [
        float(maximum) - float(minimum)
        for minimum, maximum in zip(bounds["min"], bounds["max"])
    ]


def _files(root: Path, record: dict[str, Any], preview_path: str) -> dict[str, Path]:
    files = {
        "glb": root / record["path"],
        "preview": root / preview_path,
    }
    for lod in record.get("lods", []):
        files[f"lod{lod['level']}"] = root / lod["path"]
    physics_path = record.get("physics_binding")
    if physics_path:
        files["physics"] = root / physics_path
    scene_path = record.get("manifest_path")
    if scene_path:
        files["scene"] = root / scene_path
    return files


def _lods(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "level": int(lod["level"]),
            "triangle_count": lod.get("triangle_count"),
            "distance_m": lod.get("distance_m"),
        }
        for lod in record.get("lods", [])
    ]


def _asset_entry(root: Path, document: dict[str, Any], record: dict[str, Any],
                 scene_previews: dict[str, str], license_name: str) -> ShippedBuiltinRecord:
    preview_path = record.get("preview_path")
    preview_source = "asset"
    if not preview_path:
        preview_path = scene_previews[record["scene_id"]]
        preview_source = "scene"
    dimensions = _dimensions(record)
    category = ATLAS_CATEGORY_LABELS.get(record["category"], record["category"])
    rigged = bool(record.get("rigged"))
    animation_names = "、".join(clip["name"] for clip in record.get("animations", []))
    animation_note = f"，含动作 {animation_names}" if animation_names else ""
    entry = {
        "asset_id": record["id"],
        "label": record["title"],
        "kind": "prop",
        "category": record["style_title"],
        "asset_category": category,
        "art_style": "PBR材质",
        "game_genres": [],
        "reusable_asset_ids": record.get("used_by_scenes", []),
        "generation_prompt": "",
        "style_prompts": {},
        "animations": record.get("animations", []),
        "description": (
            f"{record['style_title']}风格的{category}“{record['title']}”。"
            f"包含 UV0／UV1、切线、PBR 材质、三级 LOD 与物理绑定"
            f"{'，已绑定骨骼' if rigged else ''}{animation_note}。"
        ),
        "dimensions_m": dimensions,
        "footprint_m": [dimensions[0], dimensions[2]],
        "spawn_points": [],
        "lighting": {},
        "triangle_count": record.get("triangle_count"),
        "rig": {
            "status": "skinned" if rigged else "not-applicable",
            "rig_type": record.get("rig_type"),
            "applicability": record.get("rig_applicability"),
            "bone_count": int(record.get("joint_count", 0)),
            "shared_skeleton": False,
        },
        "pack_id": document["pack_id"],
        "pack_title": document["title"],
        "pack_version": str(document["version"]),
        "license": license_name,
        "tags": record.get("tags", []),
        "lods": _lods(record),
        "uv_sets": record.get("uv_sets", []),
        "material_channels": [
            "Base Color", "Normal", "Roughness", "Metallic",
            "AO", "Height", "Emissive", "ORM",
        ],
        "embedded_texture_resolution": record.get("embedded_texture_resolution"),
        "source_texture_resolution": record.get("source_texture_resolution"),
        "preview_source": preview_source,
        "preview_note": record.get("preview_revision", ""),
        "runtime": {
            "physics_binding_available": bool(record.get("physics_binding")),
            "physics_instantiated": False,
        },
        "provenance": document.get("provenance", {}),
        "mode": "cached",
    }
    return ShippedBuiltinRecord(entry=entry, files=_files(root, record, preview_path))


def _scene_entry(root: Path, document: dict[str, Any], record: dict[str, Any],
                 license_name: str) -> ShippedBuiltinRecord:
    dimensions = _dimensions(record)
    entry = {
        "asset_id": record["id"],
        "label": record["title"],
        "kind": "scene",
        "category": record["style_title"],
        "asset_category": "完整场景",
        "art_style": "PBR材质",
        "game_genres": [],
        "reusable_asset_ids": record.get("asset_ids", []),
        "generation_prompt": "",
        "style_prompts": {},
        "animations": [],
        "description": (
            f"{record['style_title']}风格的“{record['title']}”，采用{record['layout']}布局；"
            f"包含 {record['asset_count']} 类资产与 {record['instance_count']} 个场景实例。"
            "玩法、导航与碰撞实例化状态以运行时记录为准。"
        ),
        "dimensions_m": dimensions,
        "footprint_m": [dimensions[0], dimensions[2]],
        "spawn_points": [],
        "lighting": record.get("suggested_lighting", {}),
        "triangle_count": record.get("triangle_count"),
        "rig": {"status": "mixed"},
        "pack_id": document["pack_id"],
        "pack_title": document["title"],
        "pack_version": str(document["version"]),
        "license": license_name,
        "tags": [record["style_title"], record["layout"], "atlas100"],
        "lods": _lods(record),
        "uv_sets": ["TEXCOORD_0", "TEXCOORD_1"],
        "material_channels": [
            "Base Color", "Normal", "Roughness", "Metallic",
            "AO", "Height", "Emissive", "ORM",
        ],
        "embedded_texture_resolution": [128, 128],
        "source_texture_resolution": [512, 512],
        "preview_source": "asset",
        "preview_note": record.get("preview_revision", ""),
        "runtime": {
            "physics_runtime_available": bool(record.get("physics_runtime_available")),
            "physics_instantiated": bool(record.get("physics_colliders_instantiated")),
            "gameplay_implemented": bool(record.get("gameplay_implemented")),
            "navmesh": record.get("navmesh"),
        },
        "provenance": document.get("provenance", {}),
        "mode": "cached",
    }
    return ShippedBuiltinRecord(
        entry=entry,
        files=_files(root, record, record["preview_path"]),
    )


def load_atlas100_pack(root: Path) -> ShippedBuiltinPack | None:
    catalog_path = root / "catalog.json"
    if not catalog_path.is_file():
        return None
    document = json.loads(catalog_path.read_text(encoding="utf-8"))
    license_name = "MIT"
    scene_previews = {scene["id"]: scene["preview_path"] for scene in document["scenes"]}
    records: list[ShippedBuiltinRecord] = [
        _asset_entry(root, document, record, scene_previews, license_name)
        for record in document["assets"]
    ]
    records.extend(_scene_entry(root, document, record, license_name)
                   for record in document["scenes"])
    return ShippedBuiltinPack(
        root=root,
        summary={
            "pack_id": document["pack_id"],
            "version": str(document["version"]),
            "title": document["title"],
            "description": "100 个组合场景与 675 个可复用模型，含 PBR、LOD、物理及适用对象的骨骼动画。",
            "license": license_name,
            "entry_count": len(records),
        },
        records=tuple(records),
    )
