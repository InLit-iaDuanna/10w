"""Legacy conversation API delegates to the shared provider."""
from sceneops_codebuddy import CodeBuddyFailure, MODEL_IDS, available, complete as provider_complete
from .schemas import ChatRequest, ChatResponse, ModelCatalog, ModelOption

def model_catalog() -> ModelCatalog:
    installed = available()
    return ModelCatalog(available=installed,
        message='CLI 已安装；登录、权限和额度将在发送时检查。' if installed else '找不到 codebuddy；请安装并登录。',
        models=[ModelOption(id=model, mode='planned' if installed else 'blocked') for model in MODEL_IDS])

async def complete(request: ChatRequest) -> ChatResponse:
    return ChatResponse(model=request.model, text=await provider_complete(request.prompt, request.model))
