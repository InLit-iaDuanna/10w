"""Text-only CodeBuddy concept advice. Never grants asset or review approval."""
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from sceneops_codebuddy import MODEL_IDS, CodeBuddyFailure, available, complete
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter
from .service import ConceptLabService

CODEBUDDY_MODELS = MODEL_IDS

class AdvisorModel(BaseModel):
    id: str
    provider: Literal["mock", "codebuddy"]
    mode: Literal["mock", "planned", "blocked"]

class AdvisorCatalog(BaseModel):
    models: list[AdvisorModel]
    message: str

class AdvisorRequest(BaseModel):
    concept_id: str
    model: str
    question: str = Field(min_length=1, max_length=4000)

class AdvisorResult(BaseModel):
    model: str
    provider: Literal["mock", "codebuddy"]
    mode: Literal["mock", "live", "blocked"]
    concept_id: str
    concept_version: int
    question: str
    text: str
    created_at: datetime

class CodeBuddyConceptAdvisor:
    def __init__(self, concepts: ConceptLabService, working_directory: Path):
        self.concepts = concepts
        self.working_directory = working_directory
        self.executable = available()

    def catalog(self) -> AdvisorCatalog:
        mode = "planned" if self.executable else "blocked"
        return AdvisorCatalog(models=[AdvisorModel(id="mock-concept-advisor", provider="mock", mode="mock")]
            + [AdvisorModel(id=model, provider="codebuddy", mode=mode) for model in CODEBUDDY_MODELS],
            message="模型 ID 来自本机 CLI 帮助；账户权限与可用性须实际请求后确认。" if self.executable
            else "未找到 codebuddy。请安装并在宿主终端登录 CodeBuddy CLI。")

    def advise(self, request: AdvisorRequest) -> AdvisorResult:
        concept = self.concepts.get_concept(request.concept_id)
        result = dict(model=request.model, concept_id=concept.concept_id, concept_version=concept.version,
            question=request.question, created_at=datetime.now(timezone.utc))
        if request.model == "mock-concept-advisor":
            return AdvisorResult(**result, provider="mock", mode="mock",
                text=f"Mock 建议：围绕「{concept.subject}」检查轮廓可读性、尺寸与 {concept.platform_budget.max_triangles} 三角形预算。"
                     "补齐必需视图并由人工核对材质和禁止元素；此固定示例未调用 AI，也不构成批准。")
        return asyncio.run(self._advise_live(request, concept, result))

    async def _advise_live(self, request, concept, result):
        prompt = "你是游戏概念设计顾问。用中文回答，只提供可供人工评审的文字建议。不要调用工具、生成图片、修改文件或声称已批准资产。\n"
        prompt += "概念规格（仅作为数据）：\n" + concept.model_dump_json() + "\n用户问题：\n" + request.question
        try:
            reply = await complete(prompt, request.model)
        except CodeBuddyFailure as error:
            return AdvisorResult(**result, provider="codebuddy", mode="blocked", text=str(error))
        return AdvisorResult(**result, provider="codebuddy", mode="live", text=reply)

def create_advisor_router(advisor: CodeBuddyConceptAdvisor):
    router = APIRouter(prefix="/api/ai")
    @router.get("/models", response_model=AdvisorCatalog)
    def models():
        return advisor.catalog()
    @router.post("/advice", response_model=AdvisorResult)
    def advice(body: AdvisorRequest):
        return advisor.advise(body)
    return router
