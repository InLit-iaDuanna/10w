from .router import router
from .schemas import ChatRequest, ChatResponse, ModelCatalog
from .generated_manifest import GENERATED_MODULE_MANIFEST

backend_module_contribution = {
    'manifest': GENERATED_MODULE_MANIFEST,
    'router': router,
    'jobs': (),
    'event_handlers': (),
    'policy_gates': (),
}
__all__ = ['router', 'ChatRequest', 'ChatResponse', 'ModelCatalog', 'backend_module_contribution']
