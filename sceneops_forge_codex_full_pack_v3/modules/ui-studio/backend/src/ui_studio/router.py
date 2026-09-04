"""Composition-root-friendly route descriptors; FastAPI remains a host concern."""
ROUTES = (
    ("POST", "/ui-studio/flows/validate", "ui.flow.validate"),
    ("POST", "/ui-studio/mappings/propose", "ui.mapping.propose"),
    ("POST", "/ui-studio/changesets/{id}/approve", "ui.changeset.approve"),
    ("POST", "/ui-studio/changesets/{id}/publish", "ui.changeset.publish"),
)
