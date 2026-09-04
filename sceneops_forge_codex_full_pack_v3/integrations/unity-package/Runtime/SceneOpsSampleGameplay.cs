using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    [DisallowMultipleComponent]
    public sealed class SceneOpsInventory : MonoBehaviour
    {
        public bool HasKey { get; private set; }
        public bool HasActivatedSwitch { get; private set; }

        public void CollectKey() => HasKey = true;
        public void ActivateSwitch() => HasActivatedSwitch = true;
    }

    [RequireComponent(typeof(CharacterController))]
    [RequireComponent(typeof(SceneOpsInventory))]
    public sealed class SceneOpsSimplePlayerController : MonoBehaviour
    {
        [SerializeField] private float speedMetersPerSecond = 4f;

        private CharacterController controller;

        private void Awake()
        {
            controller = GetComponent<CharacterController>();
        }

        private void Update()
        {
            Vector3 direction = new Vector3(Input.GetAxisRaw("Horizontal"), 0f, Input.GetAxisRaw("Vertical"));
            if (direction.sqrMagnitude > 1f)
            {
                direction.Normalize();
            }
            controller.SimpleMove(direction * speedMetersPerSecond);
        }
    }

    [RequireComponent(typeof(Collider))]
    public sealed class SceneOpsKeyPickup : MonoBehaviour
    {
        [SerializeField] private SceneOpsTelemetryBridge telemetry;

        private void OnTriggerEnter(Collider other)
        {
            SceneOpsInventory inventory = other.GetComponent<SceneOpsInventory>();
            SceneOpsIdentity identity = GetComponent<SceneOpsIdentity>();
            if (inventory == null || identity == null)
            {
                return;
            }

            inventory.CollectKey();
            telemetry?.Record("gameplay.key.collected", identity, "collected");
            gameObject.SetActive(false);
        }
    }

    [RequireComponent(typeof(Collider))]
    public sealed class SceneOpsSwitchTrigger : MonoBehaviour
    {
        [SerializeField] private SceneOpsTelemetryBridge telemetry;

        private void OnTriggerEnter(Collider other)
        {
            SceneOpsInventory inventory = other.GetComponent<SceneOpsInventory>();
            SceneOpsIdentity identity = GetComponent<SceneOpsIdentity>();
            if (inventory == null || identity == null)
            {
                return;
            }

            inventory.ActivateSwitch();
            telemetry?.Record("gameplay.switch.activated", identity, "activated");
        }
    }

    [RequireComponent(typeof(Collider))]
    public sealed class SceneOpsAccessDoor : MonoBehaviour
    {
        public enum Requirement
        {
            Key,
            Switch,
        }

        [SerializeField] private Requirement requirement = Requirement.Key;
        [SerializeField] private float openHeightMeters = 3f;
        [SerializeField] private SceneOpsTelemetryBridge telemetry;
        private bool opened;

        private void OnTriggerEnter(Collider other)
        {
            if (opened)
            {
                return;
            }
            SceneOpsInventory inventory = other.GetComponent<SceneOpsInventory>();
            bool permitted = inventory != null &&
                (requirement == Requirement.Key ? inventory.HasKey : inventory.HasActivatedSwitch);
            if (!permitted)
            {
                return;
            }

            opened = true;
            transform.position += Vector3.up * openHeightMeters;
            SceneOpsIdentity identity = GetComponent<SceneOpsIdentity>();
            if (identity != null)
            {
                telemetry?.Record("gameplay.door.opened", identity, "opened");
            }
        }
    }

    [RequireComponent(typeof(Collider))]
    public sealed class SceneOpsGoalExit : MonoBehaviour
    {
        [SerializeField] private SceneOpsTelemetryBridge telemetry;

        private void OnTriggerEnter(Collider other)
        {
            SceneOpsIdentity identity = GetComponent<SceneOpsIdentity>();
            if (other.GetComponent<SceneOpsInventory>() != null && identity != null)
            {
                telemetry?.Record("gameplay.goal.completed", identity, "completed");
            }
        }
    }
}
