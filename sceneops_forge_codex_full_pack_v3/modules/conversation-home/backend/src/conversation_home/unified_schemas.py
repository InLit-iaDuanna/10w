from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator
from sceneops_codebuddy import MODEL_IDS

class AIContract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class AISettings(AIContract):
    model: str = 'cli-default'

    @field_validator('model')
    @classmethod
    def known_model(cls, value):
        if value != 'cli-default' and value not in MODEL_IDS:
            raise ValueError('Unknown CodeBuddy model')
        return value

class AIModel(AIContract):
    id: str
    label: str

class AIModels(AIContract):
    provider: Literal['codebuddycli'] = 'codebuddycli'
    available: bool
    mode: Literal['planned', 'blocked']
    models: list[AIModel]
    message: str

class AIMessage(AIContract):
    id: str
    role: Literal['user', 'assistant']
    text: str
    model: str
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
    provider: Literal['codebuddycli'] = 'codebuddycli'
    mode: Literal['live'] = 'live'
    model: str
    text: str
