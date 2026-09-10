"""Deterministic contracts for bounded, task-scoped production preparation."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sceneops_ai_context import (
    CANDIDATE_CHARACTER_BUDGET, CandidateDetail, CandidateDetailRequest, CandidateIdentity,
    CandidateSearchRequest, CandidateSummary, PreparationRepository,
    ProductionPreparationRequest, ProductionPreparationService,
    RecommendationProviderResponse, create_preparation_router,
)


def request(key="request-1", project_id="project-1"):
    return ProductionPreparationRequest(project_id=project_id, request_key=key,
        production_kind="game_create", requirement="做一个一屏收集游戏", target_platform="web",
        available_capability_ids=["game.asset.import"])


def candidates(project_id="project-1"):
    return [
        CandidateSummary(provider_id="catalog", candidate_id="asset-hero", kind="asset",
            title="主角", summary="带待机和行走动画的低多边形角色", scope="builtin", version="v2",
            production_kinds=["game_create"], platforms=["web"],
            required_capability_ids=["game.asset.import"], relevance=1.0),
        CandidateSummary(provider_id="catalog", candidate_id="experience-camera", kind="experience",
            title="一屏镜头", summary="根据可玩区域边界计算取景", scope="shared", revision=3,
            production_kinds=["game_create"], relevance=.9),
        CandidateSummary(provider_id="catalog", candidate_id="skill-game", kind="skill",
            title="网页游戏制作", summary="创建可运行的 Three.js 游戏", scope="builtin", version="1",
            production_kinds=["game_create"], relevance=.8),
        CandidateSummary(provider_id="catalog", candidate_id="game.asset.import", kind="capability",
            title="导入游戏资产", summary="按选择导入已登记资产", scope="builtin",
            production_kinds=["game_create"], relevance=.7),
        CandidateSummary(provider_id="catalog", candidate_id="private-other", kind="asset",
            title="其他项目资产", summary="不应泄露", scope="current_project", project_id="project-2",
            version="v1", production_kinds=["game_create"]),
    ]


class Catalog:
    provider_id = "catalog"

    def __init__(self, values=None):
        self.values = candidates() if values is None else values

    async def list_candidates(self, production_request, query):
        return self.values

    async def get_candidate_detail(self, production_request, identity):
        return CandidateDetail(identity=identity, title="主角详情",
            content={"registered_path": "assets/hero.glb", "animation_names": ["idle", "walk"]})


class Selector:
    def __init__(self, structured):
        self.structured = structured
        self.calls = []
        self.snapshot = SimpleNamespace(provider="fixture", model="economy")

    def selector_settings(self):
        return self.snapshot

    async def generate_for_selector(self, prompt, *, schema, snapshot, instructions, timeout):
        self.calls.append({"prompt": prompt, "schema": schema, "snapshot": snapshot,
                           "instructions": instructions, "timeout": timeout})
        return RecommendationProviderResponse(structured=self.structured,
            provider_id="fixture", model="economy", usage={"total_tokens": 42})


class WaitingSelector(Selector):
    async def generate_for_selector(self, prompt, *, schema, snapshot, instructions, timeout):
        self.calls.append({"timeout": timeout})
        await asyncio.Future()


class CameraSelector(Selector):
    async def generate_for_selector(self, prompt, *, schema, snapshot, instructions, timeout):
        payload = json.loads(prompt.split("\n", 1)[1])
        requirement = payload["request"]["requirement"]
        candidate_id = ("camera-single-screen" if "一屏" in requirement
                        else "camera-exploration")
        self.calls.append(candidate_id)
        return RecommendationProviderResponse(structured={
            "assets": [],
            "experiences": [{"candidate_id": candidate_id, "version": None,
                "revision": 1, "purpose": "镜头", "adoption": "reference",
                "reason": "与关卡范围匹配"}],
            "skills": [], "capability_ids": [], "production_advice": [],
            "conflicts": [], "gaps": [],
        }, provider_id="fixture", model="economy")


class ProductionPreparationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = PreparationRepository(Path(self.temporary.name) / "preparation.sqlite3")

    def tearDown(self):
        self.temporary.cleanup()

    def service(self, selector, catalog=None):
        return ProductionPreparationService(candidate_providers=[catalog or Catalog()],
            recommendation_provider=selector, repository=self.repository)

    async def test_selects_valid_versions_once_and_reuses_persisted_result(self):
        selector = Selector({
            "assets": [{"candidate_id": "asset-hero", "version": "v2", "revision": None,
                "purpose": "玩家角色", "adoption": "import", "reason": "动画和风格匹配"}],
            "experiences": [{"candidate_id": "experience-camera", "version": None, "revision": 3,
                "purpose": "首版镜头", "adoption": "reference", "reason": "适用于一屏玩法"}],
            "skills": [{"candidate_id": "skill-game", "version": "1", "revision": None,
                "purpose": "制作游戏", "adoption": "use", "reason": "能力匹配"}],
            "capability_ids": ["game.asset.import"], "production_advice": ["先完成可玩循环"],
            "conflicts": [], "gaps": [],
        })
        service = self.service(selector)

        first = await service.prepare(request())
        second = await service.prepare(request())

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(first.recommendation.assets[0].candidate_id, "asset-hero")
        self.assertEqual(first.call.usage, {"total_tokens": 42})
        self.assertIsNone(first.call.cost_usd)
        self.assertTrue(second.reused)
        self.assertEqual(second.preparation_id, first.preparation_id)
        self.assertEqual(len(selector.calls), 1)
        self.assertEqual(selector.calls[0]["timeout"], 30)
        self.assertIs(selector.calls[0]["snapshot"], selector.snapshot)
        self.assertFalse(selector.calls[0]["schema"]["additionalProperties"])
        self.assertNotIn("private-other", {item.candidate_id for item in first.candidate_directory.candidates})

        detail = await service.candidate_detail(CandidateDetailRequest(request=request(),
            identity=CandidateIdentity(provider_id="catalog", candidate_id="asset-hero",
                kind="asset", version="v2")))
        self.assertEqual(detail.content["registered_path"], "assets/hero.glb")

    async def test_invalid_model_selection_fails_with_directory_and_is_not_retried(self):
        selector = Selector({"assets": [{"candidate_id": "invented", "version": "v1", "revision": None,
            "purpose": "角色", "adoption": "import", "reason": "模型虚构的选择"}],
            "experiences": [], "skills": [], "capability_ids": [],
            "production_advice": [], "conflicts": [], "gaps": []})
        service = self.service(selector)

        failed = await service.prepare(request("invalid"))
        repeated = await service.prepare(request("invalid"))

        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.failure_code, "RECOMMENDATION_INVALID")
        self.assertGreater(len(failed.candidate_directory.candidates), 0)
        self.assertIsNone(failed.recommendation)
        self.assertTrue(repeated.reused)
        self.assertEqual(len(selector.calls), 1)

    async def test_candidate_rejects_an_execution_mode_it_does_not_support(self):
        values = [item.model_copy(update={"attributes": {"supported_adoptions": ["import"]}})
                  if item.candidate_id == "asset-hero" else item for item in candidates()]
        selector = Selector({"assets": [{"candidate_id": "asset-hero", "version": "v2",
            "revision": None, "purpose": "角色", "adoption": "modify",
            "reason": "尝试使用未提供的修改路径"}],
            "experiences": [], "skills": [], "capability_ids": ["game.asset.import"],
            "production_advice": [], "conflicts": [], "gaps": []})

        result = await self.service(selector, Catalog(values)).prepare(request("bad-adoption"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "RECOMMENDATION_INVALID")
        self.assertIn("unsupported adoption", result.failure_message)

    async def test_candidate_budget_omits_whole_items_without_truncation(self):
        values = [CandidateSummary(provider_id="catalog", candidate_id=f"asset-{index}", kind="asset",
            title=f"资产 {index}", summary=str(index) * 3_900, scope="builtin", version="v1",
            production_kinds=["game_create"], relevance=1 - index / 100)
            for index in range(8)]
        service = self.service(Selector({}), Catalog(values))

        directory = await service.search_candidates(CandidateSearchRequest(request=request()))

        self.assertLessEqual(directory.character_count, CANDIDATE_CHARACTER_BUDGET)
        self.assertGreater(directory.omitted_count, 0)
        self.assertTrue(all(len(item.summary) == 3_900 for item in directory.candidates))

    async def test_large_asset_catalog_keeps_experience_and_skill_choices(self):
        values = [CandidateSummary(provider_id="catalog", candidate_id=f"asset-{index}", kind="asset",
            title=f"资产 {index}", summary="大型素材目录" * 550, scope="builtin", version="v1",
            production_kinds=["game_create"], relevance=1 - index / 100)
            for index in range(12)]
        values.extend(CandidateSummary(provider_id="catalog", candidate_id=f"experience-{index}",
            kind="experience", title=f"经验 {index}", summary="完整经验摘要" * 30,
            scope="shared", revision=1, production_kinds=["game_create"], relevance=.4)
            for index in range(6))
        values.extend(CandidateSummary(provider_id="catalog", candidate_id=f"skill-{index}",
            kind="skill", title=f"技能 {index}", summary="现有制作方式" * 20,
            scope="builtin", version="1", production_kinds=["game_create"], relevance=.3)
            for index in range(4))
        service = self.service(Selector({}), Catalog(values))

        directory = await service.search_candidates(CandidateSearchRequest(request=request()))

        kinds = [item.kind for item in directory.candidates]
        self.assertGreater(directory.omitted_count, 0)
        self.assertGreaterEqual(kinds.count("experience"), 6)
        self.assertGreaterEqual(kinds.count("skill"), 4)
        self.assertGreaterEqual(kinds.count("asset"), 1)

    async def test_timeout_is_recorded_once_and_preserves_directory(self):
        selector = WaitingSelector({})
        service = self.service(selector)
        limited = request("timeout").model_copy(update={"remaining_time_seconds": .01})

        result = await service.prepare(limited)
        repeated = await service.prepare(limited)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "RECOMMENDATION_TIMEOUT")
        self.assertEqual(result.call.status, "failed")
        self.assertGreater(len(result.candidate_directory.candidates), 0)
        self.assertTrue(repeated.reused)
        self.assertEqual(len(selector.calls), 1)

    async def test_missing_selector_is_skipped_with_readable_directory(self):
        service = ProductionPreparationService(candidate_providers=[Catalog()],
            recommendation_provider=None, repository=self.repository)

        result = await service.prepare(request("no-selector"))

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.failure_code, "RECOMMENDATION_MODEL_NOT_CONFIGURED")
        self.assertGreater(len(result.candidate_directory.candidates), 0)
        self.assertEqual(result.call.status, "skipped")
        context = await service.selected_context(request("no-selector"), result)
        self.assertGreater(len(context["candidate_directory"]["candidates"]), 0)
        self.assertEqual(context["selected_details"], [])

    async def test_task_shape_selects_different_camera_experience(self):
        values = [CandidateSummary(provider_id="catalog", candidate_id=candidate_id,
            kind="experience", title=title, summary=summary, scope="shared", revision=1,
            production_kinds=["game_create"], platforms=["web"], relevance=.9)
            for candidate_id, title, summary in (
                ("camera-single-screen", "一屏镜头", "固定看到完整可玩区域"),
                ("camera-exploration", "探索镜头", "跟随玩家并控制远景加载"),
            )]
        selector = CameraSelector({})
        service = self.service(selector, Catalog(values))

        compact = await service.prepare(request("single-screen"))
        exploration_request = request("exploration").model_copy(
            update={"requirement": "做一个大型探索游戏"})
        exploration = await service.prepare(exploration_request)

        self.assertEqual(compact.recommendation.experiences[0].candidate_id,
                         "camera-single-screen")
        self.assertEqual(exploration.recommendation.experiences[0].candidate_id,
                         "camera-exploration")
        self.assertEqual(len(selector.calls), 2)

    async def test_filters_disabled_wrong_platform_and_other_project_candidates(self):
        values = [
            CandidateSummary(provider_id="catalog", candidate_id="enabled-web", kind="experience",
                title="网页经验", summary="网页", scope="shared", revision=1,
                production_kinds=["game_create"], platforms=["web"]),
            CandidateSummary(provider_id="catalog", candidate_id="disabled", kind="experience",
                title="停用经验", summary="停用", scope="shared", revision=1, enabled=False,
                production_kinds=["game_create"]),
            CandidateSummary(provider_id="catalog", candidate_id="android", kind="experience",
                title="安卓经验", summary="安卓", scope="shared", revision=1,
                production_kinds=["game_create"], platforms=["android"]),
            CandidateSummary(provider_id="catalog", candidate_id="other-project", kind="asset",
                title="其他项目", summary="私有", scope="current_project", project_id="project-2",
                version="1", production_kinds=["game_create"]),
        ]
        service = self.service(Selector({}), Catalog(values))

        directory = await service.search_candidates(CandidateSearchRequest(request=request()))

        self.assertEqual({item.candidate_id for item in directory.candidates}, {"enabled-web"})

    async def test_selected_context_reads_only_selected_detail(self):
        selector = Selector({"assets": [{"candidate_id": "asset-hero", "version": "v2",
            "revision": None, "purpose": "玩家", "adoption": "import", "reason": "匹配"}],
            "experiences": [], "skills": [], "capability_ids": ["game.asset.import"],
            "production_advice": [], "conflicts": [], "gaps": []})
        service = self.service(selector)
        production_request = request("details")
        result = await service.prepare(production_request)

        context = await service.selected_context(production_request, result)

        self.assertNotIn("candidate_directory", context)
        self.assertEqual(len(context["selected_details"]), 1)
        self.assertEqual(context["selected_details"][0]["content"]["registered_path"],
                         "assets/hero.glb")

    async def test_memory_snapshot_is_exact_and_staging_does_not_record_use(self):
        from unittest.mock import Mock
        selector = Selector({"assets": [], "experiences": [{"candidate_id": "experience-camera",
            "version": None, "revision": 3, "purpose": "镜头", "adoption": "reference", "reason": "匹配"}],
            "skills": [], "capability_ids": [], "production_advice": [], "conflicts": [], "gaps": []})
        service = self.service(selector)
        service.context_recorder = Mock(return_value={"items": [{"content": "有界正文"}], "project_memories": []})
        production_request = request("memory-details")
        result = await service.prepare(production_request)
        staged = await service.selected_context(production_request, result, record_memory=False)
        self.assertEqual(len(staged["selected_details"]), 1)
        service.context_recorder.assert_not_called()
        supplied = await service.selected_context(production_request, result)
        self.assertEqual(supplied["selected_details"], [])
        self.assertEqual(supplied["memory_context"]["items"][0]["content"], "有界正文")
        self.assertEqual(service.context_recorder.call_args.args[:2], ("project-1", "memory-details"))

    async def test_cancellation_persists_failed_call_and_candidate_directory(self):
        selector = WaitingSelector({})
        service = self.service(selector)
        task = asyncio.create_task(service.prepare(request("cancelled")))
        while not selector.calls:
            await asyncio.sleep(0)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        result = service.result("project-1", "cancelled")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.call.status, "cancelled")
        self.assertGreater(len(result.candidate_directory.candidates), 0)


class ProductionPreparationRouterTests(unittest.TestCase):
    def test_router_exposes_only_preparation_read_and_selection_routes(self):
        router = create_preparation_router(object())

        paths = {(route.path, next(iter(route.methods))) for route in router.routes}

        self.assertIn(("/api/production-preparation/prepare", "POST"), paths)
        self.assertIn(("/api/production-preparation/candidates/search", "POST"), paths)
        self.assertIn(("/api/production-preparation/candidates/detail", "POST"), paths)
        self.assertIn(("/api/production-preparation/results/{request_key}", "GET"), paths)


if __name__ == "__main__":
    unittest.main()
