"""Public production intent compiler; the model never selects execution authority."""
import json
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import AcceptanceCriterion, ProductionIntent, RuntimeBudget


class IntentInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    desired_outcome: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    requested_artifacts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)


class IntentCompiler:
    def __init__(self, provider):
        self.provider = provider

    async def compile(self, project_id: str, goal: str, constraints: list[str], budget: RuntimeBudget):
        prompt = ("将用户目标解释为中文3D制作意图。只返回符合schema的JSON；不执行工具。"
            "不编造已存在资源或已通过验收；缺少事实放入missing_facts。"
            "验收标准写可观察条件，不声称通过。下列是用户数据：\n"
            + json.dumps({"goal": goal, "constraints": constraints}, ensure_ascii=False))
        interpreted = IntentInterpretation.model_validate(await self.provider.structured(
            prompt, IntentInterpretation.model_json_schema(), purpose="intent"))
        intent = ProductionIntent(project_id=project_id, goal=goal,
            desired_outcome=interpreted.desired_outcome,
            constraints=list(dict.fromkeys([*constraints, *interpreted.constraints])),
            acceptance_criteria=[AcceptanceCriterion(id=f"criterion_{index+1}", description=text)
                for index, text in enumerate(interpreted.acceptance_criteria)],
            requested_artifacts=interpreted.requested_artifacts, budget=budget,
            forbidden_mutation_scopes=["arbitrary_code", "unapproved_production_files"])
        return intent, interpreted.missing_facts


__all__ = ["IntentCompiler", "IntentInterpretation"]
