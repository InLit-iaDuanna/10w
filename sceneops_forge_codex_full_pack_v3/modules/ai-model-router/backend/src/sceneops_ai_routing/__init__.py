"""Product model tiers are independent of the models used by Codex developers."""
import sqlite3
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import ModelRoutingDecision

ROLE_TIERS = {"producer": "reasoning", "game-designer": "standard", "technical-artist": "reasoning",
    "blender-specialist": "reasoning", "unity-engineer": "reasoning", "render-specialist": "vision",
    "qa": "standard", "ai-player": "player", "recovery": "reasoning", "reviewer": "reasoning"}

ModelTier = Literal['fast', 'standard', 'reasoning', 'vision', 'player']


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['codebuddycli', 'openai-compatible']
    tier: ModelTier
    model: str | None = Field(default=None, max_length=200)


class ModelProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str | None = Field(default=None, max_length=200)


class ModelRouter:
    def __init__(self, provider):
        self.provider = provider
        self.path = provider.database_path
        with sqlite3.connect(self.path) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS ai_model_profiles (provider TEXT NOT NULL, tier TEXT NOT NULL, model TEXT NOT NULL, PRIMARY KEY(provider,tier))')

    def profiles(self):
        provider = self.provider.settings().provider
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute('SELECT tier,model FROM ai_model_profiles WHERE provider=?', (provider,)).fetchall()
        values = dict(rows)
        return [ModelProfile(provider=provider, tier=tier, model=values.get(tier)) for tier in ('fast','standard','reasoning','vision','player')]

    def save_profile(self, tier: ModelTier, model: str | None):
        provider = self.provider.settings().provider
        value = model.strip() if model else ''
        if any(character in value for character in '\r\n\x00'):
            raise ValueError('模型 ID 不允许控制字符。')
        if provider == 'codebuddycli' and value and value not in {item.id for item in self.provider.models() if item.provider == provider}:
            raise ValueError('此模型不在当前 CLI 候选目录中。')
        with sqlite3.connect(self.path) as connection:
            if value:
                connection.execute('INSERT INTO ai_model_profiles VALUES(?,?,?) ON CONFLICT(provider,tier) DO UPDATE SET model=excluded.model', (provider,tier,value))
            else:
                connection.execute('DELETE FROM ai_model_profiles WHERE provider=? AND tier=?', (provider,tier))
        return ModelProfile(provider=provider, tier=tier, model=value or None)

    def route(self, role: str, attempts: int = 0):
        if role not in ROLE_TIERS:
            raise ValueError("未知的运行专家角色。")
        settings = self.provider.settings()
        profile = next(item for item in self.profiles() if item.tier == ROLE_TIERS[role])
        return ModelRoutingDecision(agent_role=role, tier=ROLE_TIERS[role],
            provider=settings.provider, model=profile.model or settings.model, escalation_count=max(0, attempts - 1),
            reason=("此角色需要 " + ROLE_TIERS[role] + " 级能力；使用用户当前配置的模型。"
                + ("已应用该层级的显式模型配置。" if profile.model else "未配置层级覆盖，使用全局模型，不擅自切换供应商。")
                + ("连续失败需人工检查后决定模型或路径调整。" if attempts >= 2 else "")))


__all__ = ["ModelRouter", "ROLE_TIERS", "ModelProfile", "ModelProfileUpdate", "ModelTier"]
