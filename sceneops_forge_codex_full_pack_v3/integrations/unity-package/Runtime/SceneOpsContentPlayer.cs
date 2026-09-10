using System;
using UnityEngine;
namespace SceneOps.Forge.Unity.Runtime
{
    [RequireComponent(typeof(CharacterController))]
    public sealed class SceneOpsContentPlayer : MonoBehaviour
    {
        public Transform key;
        public bool HasKey { get; private set; }
        public string LastAction { get; private set; } = "none";
        public string ActiveRequest { get; private set; } = "";
        public bool ReleaseConfirmed { get; private set; } = true;
        public int FramesConsumed { get; private set; }
        public int CollisionCount { get; private set; }
        private int remaining;
        private float moveX, moveZ;
        private bool interact;
        private CharacterController controller;
        private void Awake() { controller = GetComponent<CharacterController>(); }
        public void Begin(string request, float x, float z, bool press, int frames)
        {
            if (!ReleaseConfirmed) throw new InvalidOperationException("An input action is still active.");
            ActiveRequest = request; moveX = x; moveZ = z; interact = press;
            remaining = frames; FramesConsumed = 0; ReleaseConfirmed = false;
        }
        public void Cancel() { remaining = 0; moveX = moveZ = 0; interact = false; ReleaseConfirmed = true; }
        private void Update()
        {
            bool scripted = !ReleaseConfirmed;
            if (scripted && remaining == 0) { Cancel(); return; }
            float x = scripted ? moveX : Input.GetAxisRaw("Horizontal");
            float z = scripted ? moveZ : Input.GetAxisRaw("Vertical");
            bool press = scripted ? interact && FramesConsumed == 0 : Input.GetKeyDown(KeyCode.E);
            controller.SimpleMove(Vector3.ClampMagnitude(new Vector3(x, 0, z), 1f) * 3f);
            if (key != null && key.gameObject.activeSelf && Vector3.Distance(transform.position, key.position) < 1f)
            { HasKey = true; key.gameObject.SetActive(false); LastAction = "key_collected"; }
            if (press)
            {
                SceneOpsDoorActor nearest = null; float distance = float.PositiveInfinity;
                foreach (var door in FindObjectsOfType<SceneOpsDoorActor>())
                {
                    float candidate = Vector3.Distance(transform.position, door.hinge.position);
                    if (candidate < distance) { nearest = door; distance = candidate; }
                }
                if (nearest != null) { nearest.Interact(this); LastAction = nearest.LastInteraction; }
            }
            if (scripted) { remaining--; FramesConsumed++; }
        }
        private void OnGUI()
        {
            string status = "靠近钥匙拾取，再走到门前按 E。";
            if (LastAction == "key_collected") status = "已拾取钥匙，走到门前按 E。";
            else if (LastAction == "key_required") status = "门已锁住，需要先拾取钥匙。";
            else if (LastAction == "out_of_range") status = "距离太远，请靠近门再按 E。";
            else if (LastAction == "opened") status = "门已打开，可以穿过门框。";
            GUI.Box(new Rect(16, 16, 430, 94), "Unity 资产试玩");
            GUI.Label(new Rect(30, 42, 405, 22), "WASD / 方向键移动 · E 交互 · 钥匙：" + (HasKey ? "已获得" : "未获得"));
            GUI.Label(new Rect(30, 68, 405, 22), status);
        }
        private void OnControllerColliderHit(ControllerColliderHit hit)
        { if (Mathf.Abs(hit.normal.y) < .5f) CollisionCount++; }
    }
}
