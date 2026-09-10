using UnityEngine;
namespace SceneOps.Forge.Unity.Runtime
{
    [DisallowMultipleComponent]
    public sealed class SceneOpsDoorActor : MonoBehaviour
    {
        public string asset_id, source_version, frame_node_id, leaf_node_id, hinge_node_id;
        public Transform model, frame, leaf, hinge;
        [Min(.2f)] public float interaction_distance = 2f;
        public bool requires_key = true;
        public bool Opened { get; private set; }
        public string LastInteraction { get; private set; } = "none";
        private float openAngle;

        public void Interact(SceneOpsContentPlayer player)
        {
            float distance = Vector3.Distance(player.transform.position, hinge.position);
            if (distance > interaction_distance) { LastInteraction = "out_of_range"; return; }
            if (requires_key && !player.HasKey) { LastInteraction = "key_required"; return; }
            Opened = true; LastInteraction = "opened";
        }
        private void Update()
        {
            if (!Opened || leaf == null || hinge == null || openAngle >= 95f) return;
            float step = Mathf.Min(95f - openAngle, 140f * Time.deltaTime);
            leaf.RotateAround(hinge.position, transform.up, step);
            openAngle += step;
        }
    }
}
