"""Public backend API for the Audio Studio module."""
def create_lab_router():
    from .lab_api import create_lab_router as factory
    return factory()

from .models import (AdapterCapabilities, AdapterHealth, AssetStatus, AudioAnalysis, AudioAsset, AudioMapping, AudioMetadata, AudioSpec,
                     ChangeSet, ChangeSetStatus, EngineUnityAudioAdapter, EventBinding, ExecutionMode,
                     MappingResult, ModuleState, Provenance)
from .service import (AnalysisJob, AudioStudioService, AudioValidationError, hero_audio_template,
                      warehouse_escape_template)

__all__ = ["AdapterCapabilities", "AdapterHealth", "AnalysisJob", "AssetStatus", "AudioAnalysis", "AudioAsset", "AudioMapping", "AudioMetadata", "AudioSpec",
           "AudioStudioService", "AudioValidationError", "ChangeSet", "ChangeSetStatus", "EngineUnityAudioAdapter",
           "EventBinding", "ExecutionMode", "MappingResult", "ModuleState", "Provenance", "hero_audio_template",
           "warehouse_escape_template"]
