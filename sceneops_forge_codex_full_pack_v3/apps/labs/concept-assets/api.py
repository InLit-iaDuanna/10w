import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
ROOT = Path(__file__).resolve().parents[3]
for path in ["modules/concept-lab/backend/src", "modules/asset-library/backend/src",
             "modules/asset-factory/backend/src", "integrations/blender-addon/src"]:
    sys.path.insert(0, str(ROOT / path))
from asset_factory import ConceptAssetLab, create_lab_router
from concept_lab import (ConceptLabError, concept_lab_error_handler,
    CodeBuddyConceptAdvisor, create_advisor_router)
sandbox = TemporaryDirectory(prefix="sceneops-concept-assets-")
app = FastAPI(title="Concept Assets Local Lab", version="1.0.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
lab = ConceptAssetLab(Path(sandbox.name))
app.include_router(create_lab_router(lab))
app.include_router(create_advisor_router(CodeBuddyConceptAdvisor(lab.concepts, Path(sandbox.name))))
