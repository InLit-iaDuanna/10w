"""Topic categorization and additive legacy migration regressions; no model calls."""
import json
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sceneops_ai_distiller import ExperienceService, create_experience_router
from sceneops_ai_distiller.experience_models import EntryUpdate
from sceneops_ai_distiller.experience_repository import ExperienceError


TOPICS = {
    "build_delivery": "构建与交付",
    "motion_interaction": "体感与交互",
    "scene_animation": "场景与动画",
    "asset_performance": "资产与性能",
    "runtime_lifecycle": "运行与播放",
    "engineering_workflow": "工程与协作",
}


class NeverCalledProvider:
    def settings(self):
        raise AssertionError("Categorization must not inspect a model")

    async def generate(self, *args, **kwargs):
        raise AssertionError("Categorization must not invoke a model")


class ExperienceTopicTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.database = Path(self.directory.name) / "topics.sqlite3"
        self.service = ExperienceService(self.database, NeverCalledProvider())

    async def asyncTearDown(self):
        await self.service.close()
        self.directory.cleanup()

    async def reopen(self):
        await self.service.close()
        self.service = ExperienceService(self.database, NeverCalledProvider())

    async def test_seed_topics_are_defined_and_multitopic_entries_keep_identity(self):
        seed = json.loads(files("sceneops_ai_distiller").joinpath(
            "resources/experience-seed-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(seed["bundle_id"], "sceneops-experience-20260908-v1")
        self.assertEqual(len(seed["entries"]), 26)
        for entry in seed["entries"]:
            with self.subTest(entry=entry["id"]):
                self.assertGreaterEqual(len(entry["topics"]), 1)
                self.assertLessEqual(len(entry["topics"]), 3)
                self.assertEqual(len(entry["topics"]), len(set(entry["topics"])))
                self.assertTrue(set(entry["topics"]) <= TOPICS.keys())
        entries = self.service.entries(None, scope="shared")
        self.assertEqual(len(entries), 26)
        self.assertEqual(len({entry.id for entry in entries}), 26)
        self.assertEqual({source.id for entry in entries for source in entry.evidence},
            {f"S{i:02d}" for i in range(1, 52)})
        decoding = self.service.get_entry("seed-exp-22", None)
        self.assertEqual(set(decoding.topics), {"asset_performance", "build_delivery", "runtime_lifecycle"})
        self.assertEqual(sum(entry.id == decoding.id for entry in entries), 1)
        self.assertEqual(len(self.service.revisions(decoding.id, None)), 1)

    async def test_public_catalog_exposes_all_topic_labels_and_descriptions(self):
        app = FastAPI()
        app.include_router(create_experience_router(self.service))
        with TestClient(app) as client:
            response = client.get("/api/experience/topics")
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()
        self.assertEqual({row["id"]: row["label"] for row in rows}, TOPICS)
        self.assertTrue(all(row["description"].strip() for row in rows))

    async def test_manual_recategorization_persists_and_stale_edit_conflicts(self):
        original = self.service.get_entry("seed-exp-06", None)
        updated = self.service.update_entry(original.id, None, EntryUpdate(
            expected_revision=original.revision, topics=["engineering_workflow", "motion_interaction"]))
        self.assertEqual(updated.revision, original.revision + 1)
        self.assertEqual(updated.content, original.content)
        with self.assertRaises(ExperienceError) as conflict:
            self.service.update_entry(original.id, None, EntryUpdate(
                expected_revision=original.revision, topics=["build_delivery"]))
        self.assertEqual(conflict.exception.code, "EXPERIENCE_REVISION_CONFLICT")
        await self.reopen()
        stored = self.service.get_entry(original.id, None)
        self.assertEqual(stored.topics, updated.topics)
        self.assertEqual(stored.revision, updated.revision)
        self.assertEqual(len(self.service.revisions(original.id, None)), 2)

    async def test_legacy_seed_migration_preserves_human_changes_and_only_runs_once(self):
        original = self.service.get_entry("seed-exp-22", None)
        human = self.service.update_entry(original.id, None, EntryUpdate(
            expected_revision=original.revision, title="用户维护的压缩经验",
            content="保留人工修订的正文，当前项目仍需验证。", applicability="人工限定范围",
            domains=["人工标签"], platforms=["ios"], status="disputed", enabled=False))
        old_body = human.model_dump()
        old_body.pop("topics")
        with self.service.repo.connect() as db:
            db.execute("UPDATE experience_entries SET body=? WHERE id=?",
                (json.dumps(old_body, ensure_ascii=False), human.id))
        await self.reopen()
        migrated = self.service.get_entry(human.id, None)
        self.assertEqual(migrated.topics, original.topics)
        self.assertEqual(migrated.revision, human.revision + 1)
        self.assertEqual(migrated.model_dump(exclude={"topics", "revision", "updated_at"}),
            human.model_dump(exclude={"topics", "revision", "updated_at"}))
        self.assertFalse(migrated.enabled)
        self.assertEqual(len(self.service.revisions(human.id, None)), 3)
        await self.reopen()
        repeated = self.service.get_entry(human.id, None)
        self.assertEqual(repeated.model_dump(), migrated.model_dump())
        self.assertEqual(len(self.service.revisions(human.id, None)), 3)

    async def test_explicit_empty_topics_are_not_replaced_by_seed_defaults(self):
        original = self.service.get_entry("seed-exp-22", None)
        empty = self.service.update_entry(original.id, None, EntryUpdate(
            expected_revision=original.revision, topics=[]))
        await self.reopen()
        persisted = self.service.get_entry(original.id, None)
        self.assertEqual(persisted.topics, [])
        self.assertEqual(persisted.revision, empty.revision)
        self.assertEqual(len(self.service.revisions(original.id, None)), 2)

    def test_topic_edit_rejects_unknown_topics_and_more_than_three(self):
        for topics in (["unknown-topic"], list(TOPICS)[:4]):
            with self.subTest(topics=topics):
                with self.assertRaises(ValidationError):
                    EntryUpdate(expected_revision=1, topics=topics)
