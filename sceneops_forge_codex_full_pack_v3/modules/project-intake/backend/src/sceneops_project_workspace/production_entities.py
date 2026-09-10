"""Versioned runtime definitions in the existing project database; no duplicate asset data."""
import json
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import Literal

from .production_domains import DOMAINS


class EntityModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProductionObjectReference(EntityModel):
    project_id: str
    workspace_id: str
    type: Literal['asset', 'entity']
    id: str
    version: int = Field(ge=1)
    part_id: str | None = None


class ProductionEntity(EntityModel):
    id: str
    project_id: str
    workspace_id: str
    title: str
    source_ids: list[str]
    feature_id: str
    asset_id: str
    adopted_asset_version: int = Field(ge=1)
    revision: int = Field(ge=1)
    required_node_ids: list[str]
    material_interfaces: dict[str, list[str]] = Field(default_factory=dict)
    adoptions: list[dict] = Field(default_factory=list)
    builds: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def asset_reference(self) -> ProductionObjectReference:
        return ProductionObjectReference(project_id=self.project_id, workspace_id=self.workspace_id,
            type='asset', id=self.asset_id, version=self.adopted_asset_version)


class EntityStore:
    def __init__(self, workspace):
        self.workspace = workspace
        with workspace.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS workspace_production_entities (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                source_key TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                UNIQUE(project_id, workspace_id, source_key))''')

    def list(self, project_id, workspace_id):
        self.workspace.get_project(project_id)
        with self.workspace.connect() as db:
            rows = db.execute('SELECT payload FROM workspace_production_entities WHERE project_id=? AND workspace_id=?',
                (project_id, workspace_id)).fetchall()
        return [ProductionEntity.model_validate_json(row[0]) for row in rows]

    def get(self, project_id, workspace_id, entity_id):
        entity = next((item for item in self.list(project_id, workspace_id) if item.id == entity_id), None)
        if entity is None:
            raise ValueError('实体不属于当前项目工作区。')
        return entity

    def register(self, project_id, workspace_id, source_key, **values):
        self.workspace.get_project(project_id)
        with self.workspace.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT payload FROM workspace_production_entities WHERE project_id=? AND workspace_id=? AND source_key=?',
                (project_id, workspace_id, source_key)).fetchone()
            if old:
                entity = ProductionEntity.model_validate_json(old[0])
                if any(getattr(entity, key) != value for key, value in values.items()):
                    raise ValueError('原对象已登记，不能通过重复规整改写；请读取现有版本。')
                return entity
            entity = ProductionEntity(id='entity_'+uuid4().hex, project_id=project_id,
                workspace_id=workspace_id, revision=1, **values)
            db.execute('INSERT INTO workspace_production_entities VALUES (?,?,?,?,?,?)',
                (entity.id, project_id, workspace_id, source_key, 1, entity.model_dump_json(exclude={'asset_reference'})))
        return entity

    def adopt(self, project_id, workspace_id, entity_id, version, expected_revision, request_id, candidate_id=None, material_interfaces=None):
        with self.workspace.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM workspace_production_entities WHERE id=? AND project_id=? AND workspace_id=?',
                (entity_id, project_id, workspace_id)).fetchone()
            if row is None:
                raise ValueError('实体不属于当前项目工作区。')
            entity = ProductionEntity.model_validate_json(row[0])
            prior = next((a for a in entity.adoptions if a['request_id'] == request_id), None)
            if prior:
                if prior['to_version'] != version or prior['from_revision'] != expected_revision:
                    raise ValueError('同一请求不能更换采用内容。')
                return entity
            if entity.revision != expected_revision:
                raise ValueError('实体已更新，请重新读取后采用。')
            entity.adoptions.append(dict(request_id=request_id, from_revision=entity.revision,
                from_version=entity.adopted_asset_version, to_version=version, previous_candidate_id=candidate_id))
            if material_interfaces is not None:
                entity.material_interfaces = material_interfaces
            entity.adopted_asset_version = version
            entity.revision += 1
            db.execute('UPDATE workspace_production_entities SET revision=?,payload=? WHERE id=?',
                (entity.revision, entity.model_dump_json(exclude={'asset_reference'}), entity.id))
        return entity

    def record_build(self, project_id, workspace_id, entity_id, revision, asset_version, candidate_id):
        with self.workspace.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM workspace_production_entities WHERE id=? AND project_id=? AND workspace_id=?',
                (entity_id, project_id, workspace_id)).fetchone()
            if row is None:
                raise ValueError('实体不属于当前项目工作区。')
            entity = ProductionEntity.model_validate_json(row[0])
            record = dict(entity_revision=revision, asset_version=asset_version, candidate_id=candidate_id)
            if record not in entity.builds:
                entity.builds.append(record)
                db.execute('UPDATE workspace_production_entities SET payload=? WHERE id=?',
                    (entity.model_dump_json(exclude={'asset_reference'}), entity.id))
        return entity
