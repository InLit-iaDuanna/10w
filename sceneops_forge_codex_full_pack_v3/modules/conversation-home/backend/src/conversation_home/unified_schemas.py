from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr

ProviderId = Literal['codebuddycli', 'openai-compatible']

class AIContract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class AISettings(AIContract):
    provider: ProviderId = 'codebuddycli'
    model: str = 'cli-default'
    base_url: str | None = None
    api_key_configured: bool = False

class AISettingsUpdate(AIContract):
    provider: ProviderId | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=8192,
                                      json_schema_extra={'writeOnly': True})

class AIModel(AIContract):
    id: str
    label: str
    provider: ProviderId = 'codebuddycli'

class AIModels(AIContract):
    provider: ProviderId = 'codebuddycli'
    available: bool
    mode: Literal['planned', 'blocked']
    models: list[AIModel]
    message: str

class AIMessage(AIContract):
    id: str
    role: Literal['user', 'assistant']
    text: str
    model: str
    provider: ProviderId = 'codebuddycli'
    mode: Literal['live', 'planned']
    created_at: str

class AIConversation(AIContract):
    project_id: str | None
    messages: list[AIMessage]

class AIChatRequest(AIContract):
    project_id: str | None = None
    message: str = Field(min_length=1, max_length=16000)
    context: dict[str, JsonValue] = Field(default_factory=dict)

class AIAdviceRequest(AIContract):
    project_id: str | None = None
    module_id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=16000)
    context: dict[str, JsonValue] = Field(default_factory=dict)

class AIAdvice(AIContract):
    project_id: str | None
    module_id: str
    provider: ProviderId = 'codebuddycli'
    mode: Literal['live'] = 'live'
    model: str
    text: str
