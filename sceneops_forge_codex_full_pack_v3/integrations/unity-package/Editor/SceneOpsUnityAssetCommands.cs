using System;
using System.IO;
using System.Linq;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsUnityAssetCommands
    {
        internal static string ImportAsset(
            string payloadJson,
            string projectRoot,
            string projectId)
        {
            ImportAssetPayload payload = JsonUtility.FromJson<ImportAssetPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.source_asset_id) ||
                string.IsNullOrWhiteSpace(payload.source_asset_version_id) ||
                string.IsNullOrWhiteSpace(payload.source_path) ||
                string.IsNullOrWhiteSpace(payload.destination_asset_path) ||
                string.IsNullOrWhiteSpace(payload.manifest_path))
            {
                throw new SceneOpsCommandException(
                    "UNITY_INVALID_PAYLOAD", "Import identities and paths are required.");
            }

            SceneOpsCommandSecurity.ValidateModelImportPaths(
                payload.source_path,
                payload.destination_asset_path,
                payload.manifest_path);
            string source = SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.source_path);
            string destination = SceneOpsCommandSecurity.ResolveInsideProject(
                projectRoot, payload.destination_asset_path);
            string manifestPath = SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.manifest_path);
            if (!File.Exists(source) || !File.Exists(manifestPath))
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", "The staged source asset or import manifest is missing.");
            }

            SceneOpsImportManifest manifest;
            try
            {
                manifest = JsonUtility.FromJson<SceneOpsImportManifest>(
                    File.ReadAllText(manifestPath));
            }
            catch (Exception exception)
            {
                throw new SceneOpsCommandException(
                    "UNITY_INVALID_PAYLOAD",
                    $"Unity import manifest could not be parsed: {exception.Message}");
            }
            if (manifest == null || manifest.schema_version != 1 ||
                !string.Equals(manifest.project_id, projectId, StringComparison.Ordinal) ||
                !string.Equals(
                    manifest.source_asset_id,
                    payload.source_asset_id,
                    StringComparison.Ordinal) ||
                !string.Equals(
                    manifest.source_asset_version_id,
                    payload.source_asset_version_id,
                    StringComparison.Ordinal) ||
                !string.Equals(
                    SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, manifest.source_file),
                    source,
                    StringComparison.Ordinal) ||
                manifest.objects == null ||
                manifest.objects.Any(item =>
                    item == null ||
                    string.IsNullOrWhiteSpace(item.source_object_id) ||
                    string.IsNullOrWhiteSpace(item.sceneops_id)))
            {
                throw new SceneOpsCommandException(
                    "UNITY_INVALID_PAYLOAD",
                    "Unity import manifest does not match the project, source identity, or source file.");
            }

            SceneOpsAgentPlacement.Validate(payload, projectRoot, manifest);
            string destinationDirectory = Path.GetDirectoryName(destination);
            if (!string.IsNullOrWhiteSpace(destinationDirectory))
            {
                Directory.CreateDirectory(destinationDirectory);
            }
            if (!string.Equals(source, destination, StringComparison.Ordinal))
            {
                File.Copy(source, destination, true);
            }
            AssetDatabase.ImportAsset(
                payload.destination_asset_path,
                ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);

            ModelImporter importer = AssetImporter.GetAtPath(payload.destination_asset_path) as ModelImporter;
            if (importer == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_IMPORTER_UNAVAILABLE",
                    "Unity did not create a ModelImporter for the approved model file.");
            }
            importer.globalScale = payload.import_scale;
            importer.addCollider = payload.generate_colliders;
            importer.materialImportMode = string.Equals(payload.material_mode, "none", StringComparison.Ordinal)
                ? ModelImporterMaterialImportMode.None
                : ModelImporterMaterialImportMode.ImportStandard;
            importer.materialLocation = string.Equals(payload.material_mode, "external", StringComparison.Ordinal)
                ? ModelImporterMaterialLocation.External
                : ModelImporterMaterialLocation.InPrefab;
            importer.SaveAndReimport();
            SceneOpsAgentPlacement.Place(payload, projectRoot, manifest);
            return JsonUtility.ToJson(new ImportAssetResult
            {
                assetGuid = AssetDatabase.AssetPathToGUID(payload.destination_asset_path),
                assetPath = payload.destination_asset_path,
                sourceAssetId = manifest.source_asset_id,
                sourceAssetVersionId = manifest.source_asset_version_id,
                manifestObjectCount = manifest.objects?.Length ?? 0,
                executionMode = "live",
            });
        }

        internal static string MapIdentity(string payloadJson)
        {
            MapIdentityPayload payload = JsonUtility.FromJson<MapIdentityPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.sceneops_id))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Identity payload is required.");
            }

            SceneOpsIdentity identity;
            if (string.Equals(payload.relationship, "copy", StringComparison.Ordinal))
            {
                SceneOpsIdentity original = SceneOpsIdentityEditorUtility.FindLoadedIdentity(
                    payload.sceneops_id, payload.copied_from_scene_instance_id);
                SceneOpsIdentity copy = FindGlobalIdentity(payload.unity_global_object_id);
                if (original == null || copy == null || ReferenceEquals(original, copy) ||
                    !string.Equals(
                        copy.SceneInstanceId,
                        payload.copied_from_scene_instance_id,
                        StringComparison.Ordinal))
                {
                    throw new SceneOpsCommandException(
                        "UNITY_MISSING_REFERENCE",
                        "The exact copied GameObject sharing the source instance ID was not found.");
                }
                SceneOpsIdentityEditorUtility.AssignCopyIdentity(
                    original, copy, payload.scene_instance_id);
                identity = copy;
            }
            else
            {
                identity = FindGlobalIdentity(payload.unity_global_object_id)
                    ?? SceneOpsIdentityEditorUtility.FindLoadedIdentity(
                        payload.sceneops_id, payload.scene_instance_id);
                if (identity == null)
                {
                    if (string.Equals(payload.relationship, "prefab_instance", StringComparison.Ordinal))
                    {
                        throw new SceneOpsCommandException(
                            "UNITY_MISSING_REFERENCE",
                            "The target Prefab scene instance was not found in a loaded scene.");
                    }
                    identity = MapPrefab(payload);
                }
                else
                {
                    SceneOpsIdentityEditorUtility.Apply(
                        identity,
                        payload.sceneops_id,
                        payload.source_asset_id,
                        payload.source_asset_version_id,
                        payload.source_object_id,
                        payload.unity_asset_guid,
                        payload.prefab_id,
                        payload.scene_instance_id,
                        payload.copied_from_scene_instance_id);
                    if (string.Equals(payload.relationship, "rename", StringComparison.Ordinal) &&
                        !string.IsNullOrWhiteSpace(payload.display_name))
                    {
                        identity.gameObject.name = payload.display_name;
                    }
                    EditorSceneManager.MarkSceneDirty(identity.gameObject.scene);
                }
            }
            return IdentityJson(identity);
        }

        private static SceneOpsIdentity FindGlobalIdentity(string globalObjectId)
        {
            if (string.IsNullOrWhiteSpace(globalObjectId) ||
                !GlobalObjectId.TryParse(globalObjectId, out GlobalObjectId parsed))
            {
                return null;
            }
            UnityEngine.Object target = GlobalObjectId.GlobalObjectIdentifierToObjectSlow(parsed);
            if (target is GameObject gameObject)
            {
                return gameObject.GetComponent<SceneOpsIdentity>();
            }
            if (target is Component component)
            {
                return component.GetComponent<SceneOpsIdentity>();
            }
            return null;
        }

        internal static string UpsertPrefab(string payloadJson, string projectRoot)
        {
            UpsertPrefabPayload payload = JsonUtility.FromJson<UpsertPrefabPayload>(payloadJson);
            if (payload == null || string.IsNullOrWhiteSpace(payload.source_asset_guid) ||
                string.IsNullOrWhiteSpace(payload.prefab_asset_path))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Prefab payload is required.");
            }
            SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, payload.prefab_asset_path);
            string sourcePath = AssetDatabase.GUIDToAssetPath(payload.source_asset_guid);
            GameObject source = AssetDatabase.LoadAssetAtPath<GameObject>(sourcePath);
            if (source == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", "Prefab source asset GUID was not found.");
            }
            string directory = Path.GetDirectoryName(payload.prefab_asset_path)?.Replace('\\', '/');
            EnsureAssetDirectory(directory);

            GameObject instance = PrefabUtility.InstantiatePrefab(source) as GameObject;
            if (instance == null)
            {
                throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "Source asset cannot form a Prefab.");
            }
            try
            {
                SceneOpsIdentity identity = instance.GetComponent<SceneOpsIdentity>()
                    ?? instance.AddComponent<SceneOpsIdentity>();
                SceneOpsIdentityEditorUtility.Apply(
                    identity,
                    payload.sceneops_id,
                    payload.source_asset_id,
                    payload.source_asset_version_id,
                    payload.sceneops_id,
                    payload.source_asset_guid,
                    payload.prefab_id,
                    string.Empty);
                foreach (string componentType in payload.component_types ?? Array.Empty<string>())
                {
                    AddAllowlistedComponent(instance, componentType);
                }
                ConfigureLodGroup(instance, payload.lod_screen_percentages);
                ValidatePrefab(instance);
                GameObject prefab = PrefabUtility.SaveAsPrefabAsset(
                    instance, payload.prefab_asset_path, out bool success);
                if (!success || prefab == null)
                {
                    throw new SceneOpsCommandException("UNITY_PREFAB_FAILED", "Unity could not save the Prefab.");
                }
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(instance);
            }
            return JsonUtility.ToJson(new PrefabResult
            {
                prefabPath = payload.prefab_asset_path,
                prefabGuid = AssetDatabase.AssetPathToGUID(payload.prefab_asset_path),
                prefabId = payload.prefab_id,
                sceneopsId = payload.sceneops_id,
                executionMode = "live",
            });
        }

        private static SceneOpsIdentity MapPrefab(MapIdentityPayload payload)
        {
            string path = AssetDatabase.GUIDToAssetPath(payload.unity_asset_guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null || !path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", "Mapped Unity Prefab GUID was not found.");
            }
            GameObject contents = PrefabUtility.LoadPrefabContents(path);
            try
            {
                SceneOpsIdentity identity = contents.GetComponent<SceneOpsIdentity>()
                    ?? contents.AddComponent<SceneOpsIdentity>();
                SceneOpsIdentityEditorUtility.Apply(
                    identity,
                    payload.sceneops_id,
                    payload.source_asset_id,
                    payload.source_asset_version_id,
                    payload.source_object_id,
                    payload.unity_asset_guid,
                    payload.prefab_id,
                    string.Empty,
                    string.Empty);
                if (string.Equals(payload.relationship, "rename", StringComparison.Ordinal) &&
                    !string.IsNullOrWhiteSpace(payload.display_name))
                {
                    contents.name = payload.display_name;
                }
                PrefabUtility.SaveAsPrefabAsset(contents, path);
                return AssetDatabase.LoadAssetAtPath<GameObject>(path).GetComponent<SceneOpsIdentity>();
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(contents);
            }
        }

        private static string IdentityJson(SceneOpsIdentity identity)
        {
            return JsonUtility.ToJson(new IdentityResult
            {
                sceneopsId = identity.SceneOpsId,
                sourceAssetId = identity.SourceAssetId,
                sourceAssetVersionId = identity.SourceAssetVersionId,
                prefabId = identity.PrefabId,
                sceneInstanceId = identity.SceneInstanceId,
                copiedFromSceneInstanceId = identity.CopiedFromSceneInstanceId,
                executionMode = "live",
            });
        }

        private static void ValidatePrefab(GameObject instance)
        {
            if (SceneOpsUnityInspectionCommands.CountMissingScripts(instance) > 0)
            {
                throw new SceneOpsCommandException("UNITY_MISSING_SCRIPT", "Prefab contains a missing script.");
            }
            if (SceneOpsUnityInspectionCommands.CountMissingMaterials(instance) > 0)
            {
                throw new SceneOpsCommandException("UNITY_MISSING_MATERIAL", "Prefab contains a missing material.");
            }
        }

        private static void AddAllowlistedComponent(GameObject target, string componentType)
        {
            switch (componentType)
            {
                case "SceneOpsIdentity":
                    if (target.GetComponent<SceneOpsIdentity>() == null) target.AddComponent<SceneOpsIdentity>();
                    break;
                case "BoxCollider":
                    if (target.GetComponent<BoxCollider>() == null) target.AddComponent<BoxCollider>();
                    break;
                case "SphereCollider":
                    if (target.GetComponent<SphereCollider>() == null) target.AddComponent<SphereCollider>();
                    break;
                case "CapsuleCollider":
                    if (target.GetComponent<CapsuleCollider>() == null) target.AddComponent<CapsuleCollider>();
                    break;
                case "MeshCollider":
                    if (target.GetComponent<MeshCollider>() == null) target.AddComponent<MeshCollider>();
                    break;
                case "Rigidbody":
                    if (target.GetComponent<Rigidbody>() == null) target.AddComponent<Rigidbody>();
                    break;
                case "LODGroup":
                    if (target.GetComponent<LODGroup>() == null) target.AddComponent<LODGroup>();
                    break;
                default:
                    throw new SceneOpsCommandException(
                        "UNITY_COMMAND_NOT_ALLOWED", $"Component '{componentType}' is not allowlisted.");
            }
        }

        private static void ConfigureLodGroup(GameObject target, float[] percentages)
        {
            if (percentages == null || percentages.Length == 0)
            {
                return;
            }
            LOD[] levels = new LOD[percentages.Length];
            for (int index = 0; index < percentages.Length; index++)
            {
                string prefix = $"LOD{index}";
                Renderer[] renderers = target.GetComponentsInChildren<Renderer>(true)
                    .Where(renderer => renderer.gameObject.name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    .ToArray();
                if (renderers.Length == 0)
                {
                    throw new SceneOpsCommandException(
                        "UNITY_MISSING_REFERENCE",
                        $"LOD level {index} has no renderer named with prefix '{prefix}'.");
                }
                levels[index] = new LOD(percentages[index], renderers);
            }
            LODGroup group = target.GetComponent<LODGroup>() ?? target.AddComponent<LODGroup>();
            group.SetLODs(levels);
            group.RecalculateBounds();
        }

        private static void EnsureAssetDirectory(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || AssetDatabase.IsValidFolder(path))
            {
                return;
            }
            string parent = Path.GetDirectoryName(path)?.Replace('\\', '/');
            EnsureAssetDirectory(parent);
            string name = Path.GetFileName(path);
            AssetDatabase.CreateFolder(parent, name);
        }
    }
}
