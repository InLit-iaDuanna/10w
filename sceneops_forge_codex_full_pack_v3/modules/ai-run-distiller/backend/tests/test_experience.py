"""Experience regressions using temporary SQLite and an in-process provider only.

Maintained as source; execution is reserved for the root agent's authorized checks.
"""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sceneops_ai_distiller import ExperienceService, create_experience_router
from sceneops_ai_distiller.experience_models import (
    EntryUpdate, ExperienceEntry, ExperienceSettingsUpdate, LearningBatch, RestoreRequest, utc_now,
)

from sceneops_ai_distiller.experience_repository import ExperienceError


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.proposal = {"changes": [], "needs_review": False, "review_reason": ""}
        self.failure = None

    def settings(self):
        return SimpleNamespace(provider="fixture", model="fixture", reasoning_effort="low")

    async def generate(self, prompt, model, schema, purpose, instructions, timeout):
        self.calls.append({"prompt": prompt, "purpose": purpose, "schema": schema})
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            text=json.dumps(self.proposal), structured=self.proposal,
            provider="fixture", model="fixture", usage=None,
        )


class WaitingProvider(FakeProvider):
    def __init__(self):
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.payload = None

    async def generate(self, prompt, model, schema, purpose, instructions, timeout):
        self.payload = json.loads(prompt)
        self.entered.set()
        await self.release.wait()
        return await super().generate(prompt, model, schema, purpose, instructions, timeout)


class ExperienceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.database = Path(self.directory.name) / "experience.sqlite3"
        self.provider = FakeProvider()
        self.waiting_learning = []
        self.service = ExperienceService(
            self.database, self.provider, project_exists=lambda p: p in {"project-a", "project-b"},
        )

    async def asyncTearDown(self):
        try:
            for provider, task in self.waiting_learning:
                await self.finish_waiting_learning(provider, task)
        finally:
            await self.service.close()
            self.directory.cleanup()

    async def test_metadata_edits_are_redacted_before_persistence(self):
        entry = self.service.update_entry('seed-exp-01', 'project-a', EntryUpdate(
            expected_revision=1, domains=['api_key=private-fixture-secret'],
            platforms=['person@example.test']))
        self.assertNotIn('private-fixture-secret', entry.model_dump_json())
        self.assertNotIn('person@example.test', entry.model_dump_json())
        self.assertNotIn('private-fixture-secret', self.service.revisions(entry.id, 'project-a')[-1].model_dump_json())

    async def test_review_resumes_after_daily_rollover_and_restart(self):
        self.service.update_settings(ExperienceSettingsUpdate(daily_call_limit=1))
        self.service.day = lambda: '2026-09-08'
        with patch.object(self.service, 'schedule'):
            self.service.record_sources('project-a', [self.source('review-source')])
        self.provider.proposal = {**self.proposal('review-source'), 'needs_review': True}
        batch = (await self.service.learn('project-a')).batches[0]
        self.assertEqual(batch.status, 'budget_wait')
        self.assertEqual(len(self.provider.calls), 1)
        await self.service.close()
        self.service = ExperienceService(self.database, self.provider)
        self.service.day = lambda: '2026-09-09'
        self.provider.proposal = self.proposal('review-source')
        batch = (await self.service.learn('project-a')).batches[0]
        self.assertEqual(batch.status, 'completed')
        self.assertEqual(batch.calls, 2)
        self.assertIn('review', json.loads(self.provider.calls[-1]['prompt']))
        self.assertEqual(self.service.status().pending_sources, 0)

    async def test_seed_import_is_durable_and_keeps_historical_evidence(self):
        entries = self.service.entries("project-a", scope="shared")
        self.assertEqual(len(entries), 26)
        self.assertEqual({item.id for item in entries}, {f"seed-exp-{i:02d}" for i in range(1, 27)})
        evidence = [source for item in entries for source in item.evidence]
        self.assertEqual({source.id for source in evidence}, {f"S{i:02d}" for i in range(1, 52)})
        self.assertTrue(all(source.verification == "historical" for source in evidence))
        correction = self.service.get_entry("seed-exp-07", "project-a")
        self.assertEqual((correction.kind, correction.status), ("case", "supported"))
        self.assertTrue(correction.evidence[0].source_ref.endswith(":417"))
        ground = self.service.get_entry("seed-exp-16", "project-a")
        self.assertEqual((ground.kind, ground.status), ("case", "disputed"))
        await self.service.close()
        self.service = ExperienceService(self.database, self.provider, project_exists=lambda p: True)
        self.assertEqual(len(self.service.entries("project-a", scope="shared")), 26)
        self.assertEqual(len(self.provider.calls), 0)
        self.assertEqual(self.service.status().pending_sources, 0)

    async def test_revision_restore_and_manual_disable_survive_restart(self):
        original = self.service.get_entry("seed-exp-06", "project-a")
        edited = self.service.update_entry(original.id, "project-a", EntryUpdate(
            expected_revision=original.revision, title="四元数链路的人工修订", enabled=False,
        ))
        self.assertEqual(edited.revision, original.revision + 1)
        self.assertFalse(edited.enabled)
        with self.assertRaises(ExperienceError) as conflict:
            self.service.update_entry(original.id, "project-a", EntryUpdate(
                expected_revision=original.revision, title="过期编辑",
            ))
        self.assertEqual(conflict.exception.code, "EXPERIENCE_REVISION_CONFLICT")
        self.assertEqual(self.service.get_entry(original.id, "project-a").title, edited.title)
        self.assertNotIn(original.id, {e.id for e in self.service.entries("project-a")})
        await self.service.close()
        self.service = ExperienceService(self.database, self.provider, project_exists=lambda p: True)
        persisted = self.service.get_entry(original.id, "project-a")
        self.assertFalse(persisted.enabled)
        restored = self.service.restore(original.id, "project-a", RestoreRequest(
            expected_revision=persisted.revision, revision=original.revision,
        ))
        self.assertEqual(restored.title, original.title)
        self.assertEqual(restored.revision, original.revision + 2)
        self.assertEqual(len(self.service.revisions(original.id, "project-a")), 3)

    async def test_unrelated_query_supplies_no_experience(self):
        context = self.service.context("project-a", "烘焙酸种面包配方", use_key="unrelated-query")
        self.assertEqual(context["items"], [])

    async def test_use_toggle_removes_context_without_disabling_learning(self):
        settings = self.service.update_settings(ExperienceSettingsUpdate(use_enabled=False))
        self.assertFalse(settings.use_enabled)
        self.assertTrue(settings.learn_enabled)
        context = self.service.context("project-a", "四元数 体感 threejs", use_key="usage-off")
        self.assertEqual(context["items"], [])
        self.assertEqual(self.service.ranked_entries("project-a", "四元数 体感 threejs"), [])


    def add_private_entry(self):
        entry = ExperienceEntry(
            id="private-project-a", project_id="project-a", scope="project", kind="case",
            title="私有水母渲染故障", content="仅 project-a 的水母内部资料。",
            applicability="水母渲染", domains=["水母", "render"], status="unverified",
        )
        with self.service.repo.connect() as db:
            self.service.repo._write(db, entry, "隔离测试夹具")
        return entry

    async def test_project_scope_protects_reads_revisions_and_edits(self):
        private = self.add_private_entry()
        self.assertIn(private.id, {e.id for e in self.service.entries("project-a")})
        self.assertNotIn(private.id, {e.id for e in self.service.entries("project-b")})
        self.assertNotIn(private.id, {e.id for e in self.service.entries(None)})
        for operation in (
            lambda: self.service.get_entry(private.id, "project-b"),
            lambda: self.service.revisions(private.id, "project-b"),
            lambda: self.service.update_entry(private.id, "project-b", EntryUpdate(
                expected_revision=1, content="跨项目覆盖")),
            lambda: self.service.restore(private.id, "project-b", RestoreRequest(
                expected_revision=1, revision=1)),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ExperienceError) as denied:
                    operation()
                self.assertEqual(denied.exception.status_code, 404)
        context = self.service.context("project-b", "私有水母渲染故障", use_key="isolation")
        self.assertNotIn(private.id, {item["id"] for item in context["items"]})
        self.assertEqual(self.service.get_entry(private.id, "project-a").revision, 1)

    async def test_failed_call_still_consumes_durable_daily_budget(self):
        self.service.update_settings(ExperienceSettingsUpdate(daily_call_limit=1))
        batch = LearningBatch(id="batch-failed", project_id="project-a", status="running")
        day = self.service.status().day
        call_id = self.service.repo.reserve_call(batch, day, "fixture", "fixture")
        self.service.repo.finish_call(call_id, error="provider request failed")
        await self.service.close()
        self.service = ExperienceService(self.database, self.provider, project_exists=lambda p: True)
        another = LearningBatch(id="batch-next", project_id="project-a", status="running")
        with self.assertRaises(ExperienceError) as exhausted:
            self.service.repo.reserve_call(another, day, "fixture", "fixture")
        self.assertEqual(exhausted.exception.code, "EXPERIENCE_BUDGET_EXHAUSTED")
        self.assertEqual(self.service.status().calls_used, 1)
        self.assertIsNone(self.service.status().cost_usd)

    def source(self, source_id, *, evidence_status="unknown", text="水母渲染在本项目仍需实测。"):
        return {
            "id": source_id, "kind": "message", "role": "assistant", "text": text,
            "created_at": utc_now(), "evidence_status": evidence_status,
        }

    def proposal(self, source_id, **updates):
        change = {
            "operation": "create", "scope": "project", "kind": "case",
            "title": "水母渲染实验", "content": "水母渲染方案尚待设备验证。",
            "applicability": "仅本项目水母渲染", "domains": ["水母", "render"],
            "platforms": ["web"], "status": "supported", "source_ids": [source_id],
            "reason": "汇总本轮记录",
        }
        change.update(updates)
        return {"changes": [change], "needs_review": False, "review_reason": ""}

    async def test_new_source_idempotence_and_unknown_claim_not_promoted(self):
        self.service.set_busy_provider(lambda project_id: True)
        source = self.source("message-a")
        self.provider.proposal = self.proposal(source["id"], kind="procedure")
        self.service.record_sources("project-a", [source, source])
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        learned = self.service.entries("project-a", scope="project")
        self.assertEqual(len(learned), 1)
        self.assertEqual(learned[0].status, "unverified")
        self.assertEqual(len(learned[0].evidence), 1)
        self.assertEqual(learned[0].evidence[0].source_project_id, "project-a")
        self.assertEqual(learned[0].evidence[0].verification, "unknown")
        calls = len(self.provider.calls)
        await self.service.close()
        self.service = ExperienceService(self.database, self.provider, project_exists=lambda p: True)
        self.service.set_busy_provider(lambda project_id: True)
        self.service.record_sources("project-a", [source])
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        self.assertEqual(len(self.provider.calls), calls)
        self.assertEqual(len(self.service.entries("project-a", scope="project")), 1)
        self.assertEqual(len(self.service.revisions(learned[0].id, "project-a")), 1)

    async def test_learning_links_result_message_and_cross_project_recall_after_correction(self):
        source = {**self.source('learning-event-source'), 'origin_key': 'message:learning-result'}
        with patch.object(self.service, 'schedule'):
            self.service.record_sources('project-a', [source])
        self.provider.proposal = self.proposal(source['id'], scope='shared', title='水母渲染故障排查',
            applicability='透明渲染故障排查', content='水母渲染需分别检查深度与透明排序，尚未验证。')
        await self.service.learn('project-a', manual=True)
        activity = self.service.memory_activity('project-a', 'message:learning-result')
        self.assertFalse(activity.pending)
        self.assertEqual(len(activity.events), 1)
        event = activity.events[0]
        self.assertEqual((event.operation, event.after.status), ('learn', 'unverified'))
        first = self.service.context('project-b', '水母渲染故障排查', use_key='message:another-task')
        self.assertIn(event.entry_id, {item['id'] for item in first['items']})
        self.service.update_entry(event.entry_id, 'project-a', EntryUpdate(expected_revision=1,
            content='水母渲染还需验证交叠物体；旧解释不能当作已验证修复。'))
        latest = self.service.context('project-b', '水母渲染故障排查', use_key='message:corrected-task')
        self.assertEqual(next(item for item in latest['items'] if item['id'] == event.entry_id)['revision'], 2)
        self.assertEqual(next(item for item in first['items'] if item['id'] == event.entry_id)['revision'], 1)
        self.assertEqual(self.service.memory_activity('project-b', 'message:learning-result').events, [])

    async def test_fabricated_source_reference_cannot_create_an_entry(self):
        self.service.set_busy_provider(lambda project_id: True)
        self.service.record_sources("project-a", [self.source("actual-message")])
        self.provider.proposal = self.proposal("fabricated-message")
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        self.assertEqual(self.service.entries("project-a", scope="project"), [])
        self.assertEqual(self.service.status().calls_used, 1)
        self.assertEqual(self.service.status().batches[0].status, "failed")
        self.assertEqual(self.service.status().pending_sources, 1)

    async def test_learning_revision_preserves_manual_disable(self):
        private = self.add_private_entry()
        disabled = self.service.update_entry(private.id, "project-a", EntryUpdate(
            expected_revision=1, enabled=False,
        ))
        self.service.set_busy_provider(lambda project_id: True)
        source = self.source("revision-message")
        self.service.record_sources("project-a", [source])
        self.provider.proposal = self.proposal(source["id"], operation="revise",
            entry_id=private.id, expected_revision=disabled.revision, content="水母渲染的新证据。")
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        latest = self.service.get_entry(private.id, "project-a")
        self.assertEqual(latest.revision, disabled.revision)
        self.assertEqual(latest.content, disabled.content)
        self.assertEqual(self.service.status().batches[0].status, "failed")
        self.assertFalse(latest.enabled)
        self.assertNotIn(private.id, {e.id for e in self.service.entries("project-a")})

    async def test_sources_before_enable_time_are_not_backfilled(self):
        self.service.set_busy_provider(lambda project_id: True)
        old_source = self.source("historical-message")
        old_source["created_at"] = "2000-01-01T00:00:00+00:00"
        self.service.record_sources("project-a", [old_source])
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        self.assertEqual(len(self.provider.calls), 0)
        self.assertEqual(self.service.status().pending_sources, 0)

    async def test_provider_failure_is_charged_before_retry(self):
        self.service.update_settings(ExperienceSettingsUpdate(daily_call_limit=1))
        self.service.set_busy_provider(lambda project_id: True)
        self.provider.failure = RuntimeError("fixture provider unavailable")
        self.service.record_sources("project-a", [self.source("failed-call-message")])
        self.service.set_busy_provider(lambda project_id: False)
        await self.service.learn("project-a", manual=True)
        failed = self.service.status()
        self.assertEqual((failed.calls_used, failed.pending_sources), (1, 1))
        self.assertEqual(failed.batches[0].status, "failed")
        self.provider.failure = None
        await self.service.learn("project-a", manual=True)
        waiting = self.service.status()
        self.assertEqual(waiting.batches[0].status, "budget_wait")
        self.assertEqual(waiting.calls_used, 1)
        self.assertEqual(len(self.provider.calls), 1)


    async def test_http_scope_does_not_leak_private_entries_or_revisions(self):
        private = self.add_private_entry()
        app = FastAPI()
        app.include_router(create_experience_router(self.service))
        with TestClient(app) as client:
            owner = client.get("/api/experience/entries", params={
                "project_id": "project-a", "scope": "project",
            })
            self.assertEqual(owner.status_code, 200, owner.text)
            self.assertIn(private.id, {entry["id"] for entry in owner.json()})
            for params in (
                {"project_id": "project-b", "scope": "all", "include_disabled": "true"},
                {"project_id": "project-b", "scope": "project", "q": "水母"},
                {"scope": "all"},
            ):
                with self.subTest(params=params):
                    response = client.get("/api/experience/entries", params=params)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertNotIn(private.id, {entry["id"] for entry in response.json()})
                    self.assertNotIn(private.content, response.text)
            base = f"/api/experience/entries/{private.id}"
            for method, path, body in (
                ("GET", base, None),
                ("GET", base + "/revisions", None),
                ("PATCH", base, {"expected_revision": 1, "content": "越权修改"}),
                ("POST", base + "/restore", {"expected_revision": 1, "revision": 1}),
            ):
                with self.subTest(method=method, path=path):
                    response = client.request(method, path, params={"project_id": "project-b"}, json=body)
                    self.assertEqual(response.status_code, 404, response.text)
                    self.assertEqual(response.json()["code"], "EXPERIENCE_NOT_FOUND")
                    self.assertNotIn(private.content, response.text)
            self.assertEqual(client.get("/api/experience/entries", params={
                "project_id": "project-b", "scope": "everything",
            }).status_code, 422)
        self.assertEqual(self.service.get_entry(private.id, "project-a").revision, 1)


    async def start_waiting_learning(self, source, proposal):
        provider = WaitingProvider()
        provider.proposal = proposal
        self.service.provider = provider
        # Exercise the in-flight commit race independently from worker scheduling.
        with patch.object(self.service, "schedule"):
            self.service.record_sources("project-a", [source])
        task = asyncio.create_task(self.service.learn("project-a", manual=True))
        self.waiting_learning.append((provider, task))
        await asyncio.wait_for(provider.entered.wait(), timeout=5)
        return provider, task

    async def finish_waiting_learning(self, provider, task):
        provider.release.set()
        await asyncio.wait_for(task, timeout=5)

    async def test_user_edit_during_generation_wins_revision_race(self):
        original = self.add_private_entry()
        source = self.source("concurrent-revision")
        proposal = self.proposal(source["id"], operation="revise", entry_id=original.id,
            expected_revision=original.revision, content="模型等待后返回的旧修订。")
        provider, task = await self.start_waiting_learning(source, proposal)
        self.assertIn(original.id, {entry["id"] for entry in provider.payload["existing"]})
        user = self.service.update_entry(original.id, "project-a", EntryUpdate(
            expected_revision=original.revision, content="用户在等待期间保存的新内容。"))
        provider.release.set()
        await asyncio.wait_for(task, timeout=5)
        latest = self.service.get_entry(original.id, "project-a")
        self.assertEqual((latest.revision, latest.content), (user.revision, user.content))
        self.assertEqual(len(self.service.revisions(original.id, "project-a")), 2)
        self.assertEqual(self.service.status().batches[0].status, "failed")
        self.assertEqual(self.service.status().pending_sources, 1)

    async def test_learning_disabled_during_generation_does_not_commit(self):
        source = self.source("paused-in-flight")
        provider, task = await self.start_waiting_learning(source, self.proposal(source["id"]))
        self.service.update_settings(ExperienceSettingsUpdate(learn_enabled=False))
        provider.release.set()
        await asyncio.wait_for(task, timeout=5)
        self.assertEqual(self.service.entries("project-a", scope="project"), [])
        status = self.service.status()
        self.assertEqual((status.pending_sources, status.calls_used), (1, 1))
        self.assertEqual(status.batches[0].status, "paused")

    async def test_context_caps_item_count_size_and_filters_explicit_platform(self):
        with self.service.repo.connect() as db:
            for index in range(11):
                entry = ExperienceEntry(id=f"context-limit-{index}", project_id="project-a",
                    scope="project", kind="procedure", title=f"contextbudgetfixture {index}",
                    content="contextbudgetfixture short evidence", domains=["contextbudgetfixture"],
                    platforms=["ios" if index < 10 else "web"])
                self.service.repo._write(db, entry, "上下文限制夹具")
        short = self.service.context("project-a", "contextbudgetfixture", use_key="limit-eight", platform="ios")
        self.assertEqual(len(short["items"]), 8)
        self.assertTrue(short["truncated"])
        self.assertTrue(all(item["platforms"] == ["ios"] for item in short["items"]))
        web = self.service.context("project-a", "contextbudgetfixture", use_key="only-web", platform="web")
        self.assertEqual([item["id"] for item in web["items"]], ["context-limit-10"])
        for item in short["items"]:
            self.service.update_entry(item["id"], "project-a", EntryUpdate(
                expected_revision=1, content="contextbudgetfixture " + "large content " * 700))
        large = self.service.context("project-a", "contextbudgetfixture", use_key="limit-size", platform="ios")
        self.assertLessEqual(len(large["items"]), 8)
        self.assertLessEqual(len(json.dumps(large, ensure_ascii=False, separators=(",", ":"))), 12000)
        self.assertTrue(large["truncated"])
        self.assertTrue(all(item["platforms"] == ["ios"] for item in large["items"]))

    async def test_shared_evidence_omits_private_source_and_fact_keeps_project_scope(self):
        private_text = "项目私有业务代号海豚账本，仅当前项目可见。"
        source = self.source("private-source-shared-method", text=private_text)
        method = self.proposal(source["id"], scope="shared", kind="procedure",
            title="通用渲染检查方法", content="逐层检查输入和渲染输出。", applicability="渲染检查")
        fact = self.proposal(source["id"], scope="shared", kind="fact",
            title="项目内部业务事实", content="本项目使用海豚账本。")
        self.provider.proposal = {"changes": method["changes"] + fact["changes"],
            "needs_review": False, "review_reason": ""}
        with patch.object(self.service, "schedule"):
            self.service.record_sources("project-a", [source])
        await self.service.learn("project-a", manual=True)
        shared = [e for e in self.service.entries("project-b", scope="shared") if e.title == "通用渲染检查方法"]
        self.assertEqual(len(shared), 1)
        self.assertIsNone(shared[0].project_id)
        self.assertEqual(len(shared[0].evidence), 1)
        self.assertNotIn(private_text, shared[0].evidence[0].summary)
        self.assertNotIn("海豚账本", shared[0].evidence[0].summary)
        self.assertIsNone(shared[0].evidence[0].source_project_id)
        facts = [e for e in self.service.entries("project-a", scope="project") if e.kind == "fact"]
        self.assertEqual(len(facts), 1)
        self.assertEqual((facts[0].scope, facts[0].project_id), ("project", "project-a"))
        self.assertNotIn(facts[0].id, {e.id for e in self.service.entries("project-b")})
