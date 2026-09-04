from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ModelId = Literal['hy4-preview', 'hy3', 'hy3-x', 'glm-5.3', 'glm-5.3-flash', 'glm-5.2', 'glm-5.1', 'glm-5v-turbo', 'minimax-m3', 'minimax-m2.7', 'kimi-k3-1', 'kimi-k2.7', 'kimi-k2.6', 'deepseek-v4-pro', 'deepseek-v4-flash']

class ModelOption(BaseModel):
    id: ModelId
    mode: Literal['planned', 'blocked']

class ModelCatalog(BaseModel):
    adapter: Literal['codebuddycli'] = 'codebuddycli'
    available: bool
    message: str
    models: list[ModelOption]

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: ModelId
    prompt: str = Field(min_length=1, max_length=16000)

class ChatResponse(BaseModel):
    mode: Literal['live'] = 'live'
    model: ModelId
    text: str

class AdapterError(BaseModel):
    mode: Literal['blocked'] = 'blocked'
    code: str
    message: str
    retryable: bool = True
