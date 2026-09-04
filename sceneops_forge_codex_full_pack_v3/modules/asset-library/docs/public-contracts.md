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
