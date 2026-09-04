using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using SceneOps.Forge.Unity.Editor;

namespace SceneOps.Forge.Unity.Editor.Tests
{
    public sealed class SceneOpsSecurityTests
    {
        [Test]
        public void CommandAllowlistDoesNotExposeArbitraryCode()
        {
            Assert.That(SceneOpsCommandSecurity.CommandAllowlist, Has.Count.EqualTo(16));
            Assert.That(SceneOpsCommandSecurity.CommandAllowlist, Does.Not.Contain("unity.csharp.execute"));
            Assert.That(SceneOpsCommandSecurity.CommandAllowlist.Any(command =>
                command.Contains("shell") || command.Contains("script")), Is.False);
        }

        [Test]
        public void UnknownCommandIsRejected()
        {
            SceneOpsCommandException exception = Assert.Throws<SceneOpsCommandException>(() =>
                SceneOpsCommandSecurity.ValidateCommand("unity.csharp.execute"));
            Assert.That(exception.Code, Is.EqualTo("UNITY_COMMAND_NOT_ALLOWED"));
        }

        [Test]
        public void PathTraversalOutsideProjectIsRejected()
        {
            string projectRoot = Directory.GetParent(UnityEngine.Application.dataPath)?.FullName;
            SceneOpsCommandException exception = Assert.Throws<SceneOpsCommandException>(() =>
                SceneOpsCommandSecurity.ResolveInsideProject(projectRoot, "../../outside.txt"));
            Assert.That(exception.Code, Is.EqualTo("UNITY_PATH_OUTSIDE_PROJECT"));
        }

        [Test]
        public void ComponentScriptReferenceIsNotAllowlisted()
        {
            SceneOpsCommandException exception = Assert.Throws<SceneOpsCommandException>(() =>
                SceneOpsCommandSecurity.ValidateComponentProperty("MonoBehaviour", "m_Script"));
            Assert.That(exception.Code, Is.EqualTo("UNITY_COMMAND_NOT_ALLOWED"));
        }

        [Test]
        public void ApprovedMatchingChangeSetPasses()
        {
            BatchCommandRequest request = new BatchCommandRequest
            {
                command = "unity.collider.upsert",
                baseVersion = "git:test",
                payloadJson = "{}",
                changeSetJson = "{\"change_set_id\":\"chg_test\",\"base_version\":\"git:test\",\"approval_state\":\"approved\",\"command\":\"unity.collider.upsert\",\"target_object_ids\":[\"sobj_key\"],\"proposed_payload_json\":\"{}\"}",
            };
            Assert.DoesNotThrow(() => SceneOpsCommandSecurity.ValidateChangeSet(request));
        }

        [Test]
        public void PendingChangeSetCannotMutatePrefab()
        {
            BatchCommandRequest request = new BatchCommandRequest
            {
                command = "unity.prefab.upsert",
                baseVersion = "git:test",
                payloadJson = "{}",
                changeSetJson = "{\"change_set_id\":\"chg_test\",\"base_version\":\"git:test\",\"approval_state\":\"pending\",\"command\":\"unity.prefab.upsert\",\"target_object_ids\":[\"prefab_key\"],\"proposed_payload_json\":\"{}\"}",
            };
            SceneOpsCommandException exception = Assert.Throws<SceneOpsCommandException>(() =>
                SceneOpsCommandSecurity.ValidateChangeSet(request));
            Assert.That(exception.Code, Is.EqualTo("UNITY_APPROVAL_REQUIRED"));
        }

        [TestCase("Assets/Staging/Evil.cs", "Assets/Imported/Evil.cs")]
        [TestCase("Assets/Staging/Evil.dll", "Assets/Imported/Evil.dll")]
        [TestCase("Assets/Staging/Evil.asmdef", "Assets/Imported/Evil.asmdef")]
        [TestCase("Assets/Staging/Evil.rsp", "Assets/Imported/Evil.rsp")]
        [TestCase("Assets/Staging/Model.fbx", "Assets/Imported/Model.obj")]
        public void ModelImportRejectsExecutableOrMismatchedExtensions(
            string source,
            string destination)
        {
            SceneOpsCommandException exception = Assert.Throws<SceneOpsCommandException>(() =>
                SceneOpsCommandSecurity.ValidateModelImportPaths(
                    source,
                    destination,
                    "Assets/Staging/model.sceneops-unity.json"));
            Assert.That(exception.Code, Is.EqualTo("UNITY_COMMAND_NOT_ALLOWED"));
        }
    }
}
