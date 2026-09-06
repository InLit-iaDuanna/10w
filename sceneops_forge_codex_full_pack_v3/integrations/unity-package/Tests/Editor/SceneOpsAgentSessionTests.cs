using System;
using System.IO;
using System.Runtime.InteropServices;
using NUnit.Framework;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SceneOps.Forge.Unity.Editor.Tests
{
    public sealed class SceneOpsAgentSessionTests
    {
        [DllImport("libc", SetLastError = true)]
        private static extern int symlink(string target, string link);

        [Test]
        public void SavedSceneAndResultSymlinksCannotEscapeProject()
        {
            if (Application.platform == RuntimePlatform.WindowsEditor) Assert.Ignore("POSIX symlink regression.");
            string root = Path.Combine(Path.GetTempPath(), "sceneops-agent-paths-" + Guid.NewGuid().ToString("N"));
            string outside = root + ".outside";
            Directory.CreateDirectory(Path.Combine(root, "Assets"));
            File.WriteAllText(outside, "unchanged");
            try
            {
                string scene = Path.Combine(root, "Assets", "SceneOpsAgent.unity");
                string result = Path.Combine(root, "reply.json");
                Assert.That(symlink(outside, scene), Is.Zero);
                Assert.That(symlink(outside, result), Is.Zero);
                Assert.Throws<SceneOpsCommandException>(() => SceneOpsCommandSecurity.ResolveInsideProject(root, scene));
                Assert.Throws<SceneOpsCommandException>(() => SceneOpsAgentConnection.WriteReply(root, result, new AgentReply { status = "succeeded" }));
                Assert.That(File.ReadAllText(outside), Is.EqualTo("unchanged"));
                File.Delete(outside);
                Assert.Throws<SceneOpsCommandException>(() => SceneOpsCommandSecurity.ResolveInsideProject(root, scene));
                Assert.Throws<SceneOpsCommandException>(() => SceneOpsAgentConnection.WriteReply(root, result, new AgentReply { status = "succeeded" }));
                Assert.That(File.Exists(outside), Is.False);
            }
            finally { Directory.Delete(root, true); File.Delete(outside); }
        }

        [Test]
        public void ReplyWriterRetainsExistingResultInsteadOfOverwriting()
        {
            string root = Path.Combine(Path.GetTempPath(), "sceneops-agent-reply-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            try
            {
                string result = Path.Combine(root, "reply.json");
                SceneOpsAgentConnection.WriteReply(root, result, new AgentReply { status = "failed", error_code = "UNITY_OUTCOME_UNCERTAIN" });
                Assert.Throws<IOException>(() => SceneOpsAgentConnection.WriteReply(root, result, new AgentReply { status = "succeeded" }));
                Assert.That(File.ReadAllText(result), Does.Contain("UNITY_OUTCOME_UNCERTAIN"));
            }
            finally { Directory.Delete(root, true); }
        }

        [Test]
        public void ExistingInstanceMustBeSavedBeforePlacementReturns()
        {
            string scenePath = "Assets/SceneOpsAgentTest_" + Guid.NewGuid().ToString("N") + ".unity";
            Scene previous = SceneManager.GetActiveScene();
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            SceneManager.SetActiveScene(scene);
            try
            {
                var gameObject = new GameObject("Existing agent instance");
                var identity = gameObject.AddComponent<SceneOpsIdentity>();
                SceneOpsIdentityEditorUtility.Apply(identity, "obj_test", "ast_test", "astv_test", "obj_test", "", "", "inst_test");
                Assert.That(EditorSceneManager.SaveScene(scene, scenePath), Is.True);
                gameObject.transform.position = Vector3.one;
                EditorSceneManager.MarkSceneDirty(scene);
                SceneOpsAgentPlacement.Place(new ImportAssetPayload { destination_scene_path = scenePath,
                    sceneops_id = "obj_test", scene_instance_id = "inst_test", source_asset_id = "ast_test",
                    source_asset_version_id = "astv_test" }, Directory.GetParent(Application.dataPath).FullName,
                    new SceneOpsImportManifest());
                Assert.That(scene.isDirty, Is.False);
                Assert.That(File.Exists(Path.Combine(Directory.GetParent(Application.dataPath).FullName, scenePath)), Is.True);
            }
            finally
            {
                EditorSceneManager.CloseScene(scene, true);
                SceneManager.SetActiveScene(previous);
                AssetDatabase.DeleteAsset(scenePath);
            }
        }
    }
}
