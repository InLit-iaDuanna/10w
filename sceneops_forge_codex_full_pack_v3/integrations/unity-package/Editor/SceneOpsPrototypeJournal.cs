using System;
using System.IO;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using SceneOps.Forge.Unity.Runtime;

namespace SceneOps.Forge.Unity.Editor
{
    [Serializable] internal sealed class PrototypeHead
    {
        public string revision_id = "empty", base_revision = "empty", scene_path = "", component_version = "";
        public string run_id = "", phase = "READY";
        public bool drifted;
    }

    [InitializeOnLoad]
    internal static class SceneOpsPrototypeJournal
    {
        internal static bool Saving;
        static string Root => Directory.GetParent(Application.dataPath).FullName;
        static string HeadPath => SceneOpsCommandSecurity.ResolveInsideProject(Root, ".sceneops-agent/prototype-head.json");
        static SceneOpsPrototypeJournal()
        {
            CompilationPipeline.compilationStarted += _ => MarkDrift();
            EditorSceneManager.sceneSaved += scene => { if (!Saving && scene.path == Read().scene_path) MarkDrift(); };
        }
        internal static PrototypeHead Read()
        {
            if (!File.Exists(HeadPath)) return new PrototypeHead();
            return JsonUtility.FromJson<PrototypeHead>(File.ReadAllText(HeadPath));
        }
        internal static void Write(PrototypeHead value)
        {
            WriteJson(HeadPath, JsonUtility.ToJson(value));
        }
        internal static void WriteJson(string path, string json)
        {
            path = SceneOpsCommandSecurity.ResolveInsideProject(Root, path);
            string temp = SceneOpsCommandSecurity.ResolveInsideProject(Root, path + "." + Guid.NewGuid().ToString("N") + ".tmp");
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (var writer = new StreamWriter(stream)) { writer.Write(json); writer.Flush(); stream.Flush(true); }
            if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
        }
        static void MarkDrift()
        {
            if (!File.Exists(HeadPath)) return;
            var head = Read(); head.drifted = true; Write(head);
        }
        internal static void RequireCurrent(string revision, SceneOpsVoxelSurvival game)
        {
            var head = Read();
            if (head.drifted || string.IsNullOrEmpty(revision) || head.revision_id != revision || game == null ||
                game.project_revision != revision || head.component_version != SceneOpsVoxelSurvival.ComponentVersion ||
                SceneManager.GetActiveScene().path != head.scene_path || (!Application.isPlaying && SceneManager.GetActiveScene().isDirty))
                throw new SceneOpsCommandException("UNITY_REVISION_DRIFT", "Current scene, component revision or compilation state differs from the committed version.");
        }
    }
}
