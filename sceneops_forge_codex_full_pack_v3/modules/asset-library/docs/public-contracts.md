# Asset Library public contracts

`AssetRecord` is an aggregate read model. Its stable identity chain is:

```text
AssetSpec.asset_id
  -> SourceAsset.source_asset_id
  -> AssetObjectIdentity.sceneops_id
  -> AssetVersion.asset_version_id
  -> UsageReference.scene_instance_id
  -> UsageReference.unity_prefab_id / build_ids
```

The arrows express relationships, not identity aliases. Renames may change
display names and locators without changing `sceneops_id`; copies receive a new
`sceneops_id`; scene placement always receives a separate `scene_instance_id`.

The JSON Schemas in `contracts/` are versioned disk/event contracts. Pydantic
models in `asset_library.schemas` are the current backend and OpenAPI source of
truth. The generated shared TypeScript API client is planned until the parallel
`core-kernel`/`module-runtime` tasks land.

`PublicationRequest` deliberately carries neither a caller-selected candidate nor
a required-gate list. The catalog resolves the immutable candidate from injected
finalized-run storage using the requested asset, version, and ChangeSet IDs. It
reads required gates from its stored `AssetSpec`, then asks injected approval and
artifact authorities to verify the exact ChangeSet/version scope and stored
bytes. Missing candidate, approval, or artifact authorities deny publication.

## Shipped builtin packs

`BuiltinCatalog` is an aggregate read model. Each `BuiltinAsset` carries its own
`pack_id`, `pack_version`, and `license`; callers must use those fields for source
identity rather than the aggregate catalog revision. Asset IDs remain globally
unique across installed packs.

The catalog serves the registered LOD0 GLB and preview for every entry. Atlas100
v2 entries additionally expose LOD0–2 URLs, a physics binding URL, and a scene
definition URL for complete scenes. A scene-preview fallback is labelled through
`preview_source="scene"`; it is not represented as an asset-specific render.
Each pack summary provides a registered `catalog_url` and `resource_base_url` so
its source PBR textures and runtime modules can be consumed without exposing a
filesystem location.
All file routes resolve only registered paths below the module-owned shipped-data
root. Project adoption copies immutable source files and creates a distinct
project asset/version identity.
