using System;
using System.IO;
using System.Linq;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsAgentPlacement
    {
        internal static void Validate(ImportAssetPayload payload, string root, SceneOpsImportManifest manifest)
        {
            if (string.IsNullOrEmpty(payload.destination_scene_path)) return;
            if (payload.destination_scene_path != "Assets/SceneOpsAgent.unity" ||
                string.IsNullOrWhiteSpace(payload.scene_instance_id) ||
                !SceneOpsAgentConnection.IsDedicatedProject(root) ||
                manifest.objects.Length != 1 || manifest.objects[0].sceneops_id != payload.sceneops_id)
                throw new SceneOpsCommandException("UNITY_AGENT_SCOPE_DENIED", "Placement requires the dedicated agent project and one matching manifest identity.");
            SceneOpsCommandSecurity.ResolveInsideProject(root, payload.destination_scene_path);
            var existing = SceneOpsIdentityEditorUtility.FindLoadedIdentity(payload.sceneops_id);
            if (existing != null && existing.SourceAssetId != payload.source_asset_id)
                throw new SceneOpsCommandException("UNITY_IDENTITY_CONFLICT", "Source identity is already mapped to another asset.");
        }

        internal static void Place(ImportAssetPayload payload, string root, SceneOpsImportManifest manifest)
        {
            if (string.IsNullOrEmpty(payload.destination_scene_path)) return;
            string scenePath = payload.destination_scene_path;
            string absolute = SceneOpsCommandSecurity.ResolveInsideProject(root, scenePath);
            Scene scene = SceneManager.GetActiveScene();
            if (scene.path != scenePath)
                scene = File.Exists(absolute)
                    ? EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single)
                    : EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            SceneOpsIdentity existing = SceneOpsIdentityEditorUtility.FindLoadedIdentity(payload.sceneops_id, payload.scene_instance_id);
            if (existing != null)
            {
                if (existing.SourceAssetId != payload.source_asset_id || existing.SourceAssetVersionId != payload.source_asset_version_id)
                    throw new SceneOpsCommandException("UNITY_IDENTITY_CONFLICT", "Existing instance belongs to another source asset version.");
                SaveVerified(scene, root, scenePath);
                return;
            }
            GameObject asset = AssetDatabase.LoadAssetAtPath<GameObject>(payload.destination_asset_path);
            GameObject instance = PrefabUtility.InstantiatePrefab(asset, scene) as GameObject;
            if (instance == null) throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "Imported FBX cannot be instantiated.");
            var identity = instance.GetComponent<SceneOpsIdentity>() ?? instance.AddComponent<SceneOpsIdentity>();
            SceneOpsIdentityEditorUtility.Apply(identity, payload.sceneops_id, payload.source_asset_id,
                payload.source_asset_version_id, manifest.objects[0].source_object_id,
                AssetDatabase.AssetPathToGUID(payload.destination_asset_path), "", payload.scene_instance_id);
            instance.transform.position = Vector3.zero;
            SaveVerified(scene, root, scenePath);
            Selection.activeGameObject = instance;
            SceneView.lastActiveSceneView?.FrameSelected();
        }

        internal static void SaveVerified(Scene scene, string root, string scenePath)
        {
            string absolute = SceneOpsCommandSecurity.ResolveInsideProject(root, scenePath);
            if (!EditorSceneManager.SaveScene(scene, scenePath) || !File.Exists(absolute) || scene.path != scenePath || scene.isDirty)
                throw new SceneOpsCommandException("UNITY_SCENE_SAVE_FAILED", "Agent scene did not persist successfully; the in-memory object is not completion evidence.");
        }

        internal static AgentObject[] Objects()
        {
            return Resources.FindObjectsOfTypeAll<SceneOpsIdentity>()
                .Where(item => !EditorUtility.IsPersistent(item) && item.gameObject.scene.IsValid())
                .Select(item => {
                    var renderers = item.GetComponentsInChildren<Renderer>();
                    var bounds = renderers.Length == 0 ? new Bounds() : renderers[0].bounds;
                    foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
                    return new AgentObject { sceneops_id = item.SceneOpsId, asset_id = item.SourceAssetId,
                        scene_instance_id = item.SceneInstanceId, unity_asset_guid = item.UnityAssetGuid,
                        unity_global_object_id = GlobalObjectId.GetGlobalObjectIdSlow(item.gameObject).ToString(),
                        name = item.gameObject.name, dimensions_meters = new[] {bounds.size.x, bounds.size.y, bounds.size.z} };
                }).ToArray();
        }
    }
    [Serializable] internal sealed class AgentObject
    {
        public string sceneops_id, asset_id, scene_instance_id, unity_asset_guid, unity_global_object_id, name;
        public float[] dimensions_meters;
    }
}
