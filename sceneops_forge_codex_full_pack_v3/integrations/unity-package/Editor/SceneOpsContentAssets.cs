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
    internal static class SceneOpsContentAssets
    {
        internal const string ScenePath = "Assets/SceneOpsContent/Content.unity";
        internal const string PrefabPath = "Assets/SceneOpsContent/DoorActor.prefab";

        internal static void Import(string root, ContentPayload p, string revision, string requestId, Action mark)
        {
            var head = SceneOpsContentCommands.Head(root);
            if (head.source_version != (p.expected_source_version ?? "") ||
                (head.asset_id != "" && head.asset_id != p.asset_id))
                throw new SceneOpsCommandException("UNITY_VERSION_CONFLICT", "The currently bound source differs from the expected asset version.");
            Scene scene = SceneManager.GetActiveScene();
            if (scene.isDirty) throw new SceneOpsCommandException("UNITY_UNSAVED_SCENE", "Save or resolve the current scene edits before importing.");
            string path = "Assets/SceneOpsContent/Models/" + p.asset_id + "/" + p.source_version + "/model.fbx";
            string source = SceneOpsCommandSecurity.ResolveInsideProject(root, p.source_path);
            string destination = SceneOpsCommandSecurity.ResolveInsideProject(root, path);
            if (!File.Exists(source)) throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "The approved FBX source is missing.");
            if (File.Exists(destination) && !File.ReadAllBytes(destination).SequenceEqual(File.ReadAllBytes(source)))
                throw new SceneOpsCommandException("UNITY_VERSION_CONFLICT", "This model version already contains different data.");
            mark();
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            if (!File.Exists(destination)) File.Copy(source, destination);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            var importer = AssetImporter.GetAtPath(path) as ModelImporter;
            if (importer == null) throw new SceneOpsCommandException("UNITY_IMPORTER_UNAVAILABLE", "FBX ModelImporter is unavailable.");
            GameObject model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            ValidateNodes(model, p.nodes);
            if (scene.path != ScenePath)
                scene = File.Exists(SceneOpsCommandSecurity.ResolveInsideProject(root, ScenePath))
                    ? EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single)
                    : EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var existing = Actors();
            if (existing.Length > 0 && (existing.Length != 2 || existing.Any(a => !p.instance_ids.Contains(a.GetComponent<SceneOpsIdentity>().SceneInstanceId))))
                throw new SceneOpsCommandException("UNITY_IDENTITY_CONFLICT", "The two existing scene instance identities differ from this operation.");
            Backup(root, requestId);
            bool hasPrefab = File.Exists(SceneOpsCommandSecurity.ResolveInsideProject(root, PrefabPath));
            GameObject outer = hasPrefab ? PrefabUtility.LoadPrefabContents(PrefabPath) : new GameObject("DoorActor");
            try
            {
                var actor = outer.GetComponent<SceneOpsDoorActor>();
                if (actor == null) actor = outer.AddComponent<SceneOpsDoorActor>();
                ReplaceModel(actor, model, p);
                var identity = outer.GetComponent<SceneOpsIdentity>();
                if (identity == null) identity = outer.AddComponent<SceneOpsIdentity>();
                ApplyIdentity(identity, p, path, "");
                PrefabUtility.SaveAsPrefabAsset(outer, PrefabPath, out bool success);
                if (!success) throw new SceneOpsCommandException("UNITY_PREFAB_FAILED", "The behavior prefab could not be saved.");
            }
            finally { if (hasPrefab) PrefabUtility.UnloadPrefabContents(outer); else UnityEngine.Object.DestroyImmediate(outer); }
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            if (existing.Length == 0)
            {
                for (int i = 0; i < 2; i++)
                {
                    var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                    instance.name = "DoorActor " + (i + 1);
                    instance.transform.position = new Vector3(i * 5f, 0, 0);
                    ApplyIdentity(instance.GetComponent<SceneOpsIdentity>(), p, path, p.instance_ids[i]);
                    PrefabUtility.RecordPrefabInstancePropertyModifications(instance.transform);
                }
                SetupPlayground(scene);
            }
            else foreach (var actor in Actors())
            {
                // Unity propagates the saved prefab model to connected instances while retaining their overrides.
                // Never destroy inherited prefab children in a scene instance.
                ValidatePropagatedModel(actor, p, path);
                ApplyIdentity(actor.GetComponent<SceneOpsIdentity>(), p, path, actor.GetComponent<SceneOpsIdentity>().SceneInstanceId);
            }
            SceneOpsAgentPlacement.SaveVerified(scene, root, ScenePath);
            head.previous_source_version = head.source_version; head.previous_model_guid = head.model_guid;
            head.asset_id = p.asset_id; head.source_version = p.source_version; head.revision = revision;
            head.model_guid = AssetDatabase.AssetPathToGUID(path); head.prefab_guid = AssetDatabase.AssetPathToGUID(PrefabPath);
            SceneOpsContentCommands.SaveHead(root, head);
        }

        internal static SceneOpsDoorActor[] Actors() => Resources.FindObjectsOfTypeAll<SceneOpsDoorActor>()
            .Where(a => !EditorUtility.IsPersistent(a) && a.gameObject.scene.path == ScenePath).ToArray();

        private static void ApplyIdentity(SceneOpsIdentity identity, ContentPayload p, string path, string instance)
        {
            SceneOpsIdentityEditorUtility.Apply(identity, p.nodes.frame, p.asset_id, p.source_version, p.nodes.frame,
                AssetDatabase.AssetPathToGUID(path), "prefab_" + p.asset_id, instance);
            if (PrefabUtility.IsPartOfPrefabInstance(identity)) PrefabUtility.RecordPrefabInstancePropertyModifications(identity);
        }
        internal static void ValidateNodes(GameObject model, ContentNodes nodes)
        {
            if (model == null) throw new SceneOpsCommandException("UNITY_MISSING_REFERENCE", "Imported model could not be loaded.");
            var all = model.GetComponentsInChildren<SceneOpsSourceNode>(true);
            foreach (string id in new[] { nodes.frame, nodes.leaf, nodes.hinge })
                if (all.Count(n => n.source_node_id == id) != 1)
                    throw new SceneOpsCommandException("UNITY_SOURCE_NODE_MISSING", "Expected exactly one FBX custom-property node: " + id);
            var frame = all.Single(n => n.source_node_id == nodes.frame);
            var leaf = all.Single(n => n.source_node_id == nodes.leaf);
            if (frame.GetComponentsInChildren<MeshFilter>().Length == 0 || leaf.GetComponentsInChildren<MeshFilter>().Length == 0)
                throw new SceneOpsCommandException("UNITY_SOURCE_GEOMETRY_MISSING", "Frame and leaf must contain actual mesh geometry.");
        }
        private static void ValidatePropagatedModel(SceneOpsDoorActor actor, ContentPayload p, string path)
        {
            if (actor.model == null || actor.frame == null || actor.leaf == null || actor.hinge == null)
                throw new SceneOpsCommandException("UNITY_MODEL_REBIND_FAILED", "Saved prefab did not propagate its model references to an instance.");
            var original = PrefabUtility.GetCorrespondingObjectFromOriginalSource(actor.model.gameObject);
            if (original == null || AssetDatabase.GetAssetPath(original) != path || actor.source_version != p.source_version ||
                !NodeMatches(actor.frame, p.nodes.frame) || !NodeMatches(actor.leaf, p.nodes.leaf) || !NodeMatches(actor.hinge, p.nodes.hinge))
                throw new SceneOpsCommandException("UNITY_MODEL_REBIND_FAILED", "Instance model or role references retain a conflicting local override; inspect the retained recovery files.");
            try { ValidateNodes(actor.model.gameObject, p.nodes); }
            catch (SceneOpsCommandException error)
            { throw new SceneOpsCommandException("UNITY_MODEL_REBIND_FAILED", error.Message); }
        }
        private static bool NodeMatches(Transform transform, string sourceId)
        {
            var node = transform.GetComponent<SceneOpsSourceNode>();
            return node != null && node.source_node_id == sourceId;
        }
        private static void ReplaceModel(SceneOpsDoorActor actor, GameObject model, ContentPayload p)
        {
            if (actor.model != null) UnityEngine.Object.DestroyImmediate(actor.model.gameObject);
            var child = (GameObject)PrefabUtility.InstantiatePrefab(model, actor.transform);
            child.name = "Model";
            child.transform.localPosition = Vector3.zero; child.transform.localRotation = Quaternion.identity; child.transform.localScale = Vector3.one;
            var nodes = child.GetComponentsInChildren<SceneOpsSourceNode>(true);
            actor.model = child.transform;
            actor.frame = nodes.Single(n => n.source_node_id == p.nodes.frame).transform;
            actor.leaf = nodes.Single(n => n.source_node_id == p.nodes.leaf).transform;
            actor.hinge = nodes.Single(n => n.source_node_id == p.nodes.hinge).transform;
            actor.asset_id = p.asset_id; actor.source_version = p.source_version;
            actor.frame_node_id = p.nodes.frame; actor.leaf_node_id = p.nodes.leaf; actor.hinge_node_id = p.nodes.hinge;
            foreach (var mesh in child.GetComponentsInChildren<MeshFilter>())
            {
                var collider = mesh.GetComponent<MeshCollider>();
                if (collider == null) collider = mesh.gameObject.AddComponent<MeshCollider>();
                collider.sharedMesh = mesh.sharedMesh;
            }
            EditorUtility.SetDirty(actor);
        }
        private static void Backup(string root, string requestId)
        {
            string backup = SceneOpsCommandSecurity.ResolveInsideProject(root, ".sceneops-agent/recovery/" + requestId);
            Directory.CreateDirectory(backup);
            foreach (string path in new[] { ScenePath, PrefabPath })
            {
                string absolute = SceneOpsCommandSecurity.ResolveInsideProject(root, path);
                if (File.Exists(absolute)) File.Copy(absolute, Path.Combine(backup, Path.GetFileName(path)), false);
            }
        }
        private static void SetupPlayground(Scene scene)
        {
            var floor = GameObject.CreatePrimitive(PrimitiveType.Cube); floor.name = "Playground Floor";
            floor.transform.position = new Vector3(2, -.15f, 0); floor.transform.localScale = new Vector3(20, .3f, 20);
            var player = new GameObject("Player"); player.transform.position = new Vector3(0, 1, -4);
            var controller = player.AddComponent<CharacterController>(); controller.height = 1.8f; controller.radius = .3f;
            var driver = player.AddComponent<SceneOpsContentPlayer>();
            var body = GameObject.CreatePrimitive(PrimitiveType.Capsule); body.name = "Player Body";
            UnityEngine.Object.DestroyImmediate(body.GetComponent<Collider>());
            body.transform.SetParent(player.transform, false);
            body.transform.localScale = new Vector3(.6f, .9f, .6f);
            var key = GameObject.CreatePrimitive(PrimitiveType.Cube); key.name = "Key";
            key.transform.position = new Vector3(-2, .6f, -3); key.transform.localScale = new Vector3(.25f, .25f, .5f);
            key.GetComponent<Collider>().isTrigger = true; driver.key = key.transform;
            var camera = new GameObject("Content Camera").AddComponent<Camera>();
            camera.transform.position = new Vector3(9, 8, -12); camera.transform.LookAt(new Vector3(2, 1, 0));
            camera.gameObject.tag = "MainCamera";
            var light = new GameObject("Sun").AddComponent<Light>(); light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(45, -30, 0);
            RenderSettings.ambientLight = new Color(.65f, .65f, .65f);
        }
    }
}
