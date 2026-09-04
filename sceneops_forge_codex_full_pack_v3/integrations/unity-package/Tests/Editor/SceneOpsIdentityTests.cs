using NUnit.Framework;
using SceneOps.Forge.Unity.Editor;
using SceneOps.Forge.Unity.Runtime;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor.Tests
{
    public sealed class SceneOpsIdentityTests
    {
        private GameObject original;

        [SetUp]
        public void SetUp()
        {
            original = new GameObject("Home Key");
            SceneOpsIdentity identity = original.AddComponent<SceneOpsIdentity>();
            SceneOpsIdentityEditorUtility.Apply(
                identity,
                "sobj_home_key",
                "ast_home_key",
                "astv_home_key_001",
                "blobj_home_key",
                "11111111111111111111111111111111",
                "prefab_home_key",
                "sinst_home_key_a");
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(original);
        }

        [Test]
        public void RenamePreservesStableIdentity()
        {
            SceneOpsIdentity identity = original.GetComponent<SceneOpsIdentity>();
            SceneOpsIdentitySnapshot before = identity.Capture();
            original.name = "Entrance Key";
            SceneOpsIdentitySnapshot after = identity.Capture();

            Assert.That(after.sceneopsId, Is.EqualTo(before.sceneopsId));
            Assert.That(after.sourceAssetVersionId, Is.EqualTo(before.sourceAssetVersionId));
            Assert.That(after.prefabId, Is.EqualTo(before.prefabId));
            Assert.That(after.sceneInstanceId, Is.EqualTo(before.sceneInstanceId));
        }

        [Test]
        public void CopyReceivesNewSceneInstanceIdentityAndPreservesLineage()
        {
            GameObject copy = Object.Instantiate(original);
            try
            {
                SceneOpsIdentityEditorUtility.AssignCopyIdentity(
                    original.GetComponent<SceneOpsIdentity>(),
                    copy.GetComponent<SceneOpsIdentity>(),
                    "sinst_home_key_b");
                SceneOpsIdentitySnapshot mapped = copy.GetComponent<SceneOpsIdentity>().Capture();
                Assert.That(mapped.sceneopsId, Is.EqualTo("sobj_home_key"));
                Assert.That(mapped.prefabId, Is.EqualTo("prefab_home_key"));
                Assert.That(mapped.sceneInstanceId, Is.EqualTo("sinst_home_key_b"));
                Assert.That(mapped.copiedFromSceneInstanceId, Is.EqualTo("sinst_home_key_a"));
            }
            finally
            {
                Object.DestroyImmediate(copy);
            }
        }

        [Test]
        public void CopyCannotReuseOriginalSceneInstanceIdentity()
        {
            GameObject copy = Object.Instantiate(original);
            try
            {
                Assert.Throws<SceneOpsCommandException>(() =>
                    SceneOpsIdentityEditorUtility.AssignCopyIdentity(
                        original.GetComponent<SceneOpsIdentity>(),
                        copy.GetComponent<SceneOpsIdentity>(),
                        "sinst_home_key_a"));
            }
            finally
            {
                Object.DestroyImmediate(copy);
            }
        }

        [Test]
        public void TelemetryContainsTheEntireIdentityChain()
        {
            SceneOpsTelemetryBridge bridge = original.AddComponent<SceneOpsTelemetryBridge>();
            SceneOpsTelemetryEvent recorded = bridge.Record(
                "gameplay.key.collected",
                original.GetComponent<SceneOpsIdentity>(),
                "collected",
                "evt_identity_test");

            Assert.That(recorded.executionMode, Is.EqualTo("live"));
            Assert.That(recorded.sourceAssetId, Is.EqualTo("ast_home_key"));
            Assert.That(recorded.sourceAssetVersionId, Is.EqualTo("astv_home_key_001"));
            Assert.That(recorded.prefabId, Is.EqualTo("prefab_home_key"));
            Assert.That(recorded.sceneInstanceId, Is.EqualTo("sinst_home_key_a"));
        }
    }
}
