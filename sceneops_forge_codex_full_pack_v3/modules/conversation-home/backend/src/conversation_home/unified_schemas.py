from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr

from sceneops_ai_provider import AlignmentDetail, ApiProtocol, ProviderId

class AIContract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class AISettings(AIContract):
    provider: ProviderId = 'codebuddycli'
    model: str = 'cli-default'
    base_url: str | None = None
    api_key_configured: bool = False
    api_protocol: ApiProtocol = 'chat-completions'
    streaming: bool = True
    alignment_detail: AlignmentDetail = 'standard'

class AISettingsUpdate(AIContract):
    provider: ProviderId | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=8192,
                                      json_schema_extra={'writeOnly': True})
    api_protocol: ApiProtocol | None = None
    streaming: bool | None = None
    alignment_detail: AlignmentDetail | None = None

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


class AIProviderModelsRequest(AIContract):
    provider: ProviderId
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=8192,
                                      json_schema_extra={'writeOnly': True})


class AIProviderModels(AIContract):
    provider: ProviderId
    mode: Literal['live', 'planned']
    models: list[AIModel]
    message: str


class AIConnectionRequest(AIProviderModelsRequest):
    model: str = Field(min_length=1, max_length=200)
    api_protocol: ApiProtocol = 'chat-completions'
    streaming: bool = True


class AIConnectionResult(AIContract):
    provider: ProviderId
    model: str
    api_protocol: ApiProtocol
    streaming: bool
    connected: Literal[True] = True
    mode: Literal['live'] = 'live'
    latency_ms: int = Field(ge=0)
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


class AIChatStreamEvent(AIContract):
    type: Literal['status', 'text_delta', 'complete', 'error']
    text: str | None = None
    code: str | None = None
    conversation: AIConversation | None = None

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
