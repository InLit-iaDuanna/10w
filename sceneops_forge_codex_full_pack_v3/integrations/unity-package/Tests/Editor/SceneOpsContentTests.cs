using NUnit.Framework;
using SceneOps.Forge.Unity.Runtime;
using UnityEngine;
namespace SceneOps.Forge.Unity.Editor.Tests
{
    public sealed class SceneOpsContentTests
    {
        [Test]
        public void NodesResolveByPersistentIdentityAfterRenameAndRejectDuplicates()
        {
            var model = new GameObject("Model");
            try
            {
                var frame = GameObject.CreatePrimitive(PrimitiveType.Cube); frame.transform.SetParent(model.transform);
                frame.name = "Renamed frame"; frame.AddComponent<SceneOpsSourceNode>().source_node_id = "source_frame";
                var leaf = GameObject.CreatePrimitive(PrimitiveType.Cube); leaf.transform.SetParent(model.transform);
                leaf.name = "Renamed leaf"; leaf.AddComponent<SceneOpsSourceNode>().source_node_id = "source_leaf";
                var hinge = new GameObject("Renamed pivot"); hinge.transform.SetParent(model.transform);
                hinge.AddComponent<SceneOpsSourceNode>().source_node_id = "source_hinge";
                var roles = new ContentNodes { frame = "source_frame", leaf = "source_leaf", hinge = "source_hinge" };
                Assert.DoesNotThrow(() => SceneOpsContentAssets.ValidateNodes(model, roles));
                hinge.GetComponent<SceneOpsSourceNode>().source_node_id = "source_leaf";
                var error = Assert.Throws<SceneOpsCommandException>(() => SceneOpsContentAssets.ValidateNodes(model, roles));
                Assert.That(error.Code, Is.EqualTo("UNITY_SOURCE_NODE_MISSING"));
                Assert.That(model.transform.childCount, Is.EqualTo(3));
            }
            finally { Object.DestroyImmediate(model); }
        }
    }
}
