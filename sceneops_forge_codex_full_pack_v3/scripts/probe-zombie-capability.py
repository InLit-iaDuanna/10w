"""One explicit real-model capability probe; no external editor execution."""
import asyncio
import json
from pathlib import Path
from pydantic import BaseModel
from sceneops_ai_provider import ProviderService
from sceneops_ai_agents.task_models import TASK_CAPABILITIES


class CapabilityAssessment(BaseModel):
    supported: bool
    missing: list[str]
    explanation: str


async def main():
    directory = Path('.local/mc-zombie-validation').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    provider = ProviderService(directory / 'sceneops.sqlite3')
    provider.update_settings(provider='codebuddycli', model='glm-5.3-flash')
    result = await provider.generate('用户目标：创建Unity第一人称方块世界打僵尸游戏，移动、射击、僵尸追击、受击、生命和胜负重开。'
        '只判断以下当前实际工具能否完成整个目标，不执行，不虚构工具：' + json.dumps(TASK_CAPABILITIES),
        schema=CapabilityAssessment.model_json_schema(), purpose='live-capability-probe')
    evidence = {'provider': result.provider, 'model': result.model, 'mode': 'live',
        'assessment': result.structured, 'latency_ms': result.latency_ms, 'usage': result.usage}
    (directory / 'initial-capability-probe.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps(evidence, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
