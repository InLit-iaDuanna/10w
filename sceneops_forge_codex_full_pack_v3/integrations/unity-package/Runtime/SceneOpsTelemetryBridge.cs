using System;
using System.Collections.Generic;
using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    [Serializable]
    public sealed class SceneOpsTelemetryEvent
    {
        public string eventId = string.Empty;
        public string eventType = string.Empty;
        public string occurredAt = string.Empty;
        public string projectId = string.Empty;
        public string buildId = string.Empty;
        public string executionMode = string.Empty;
        public string sceneopsId = string.Empty;
        public string sourceAssetId = string.Empty;
        public string sourceAssetVersionId = string.Empty;
        public string prefabId = string.Empty;
        public string sceneInstanceId = string.Empty;
        public string outcome = string.Empty;
    }

    [DisallowMultipleComponent]
    [AddComponentMenu("SceneOps/Telemetry Bridge")]
    public sealed class SceneOpsTelemetryBridge : MonoBehaviour
    {
        [SerializeField] private string projectId = string.Empty;
        [SerializeField] private string buildId = string.Empty;
        [SerializeField] private string executionMode = "live";
        [SerializeField, Range(16, 4096)] private int capacity = 512;

        private readonly Queue<SceneOpsTelemetryEvent> events = new Queue<SceneOpsTelemetryEvent>();

        public event Action<SceneOpsTelemetryEvent> EventRecorded;

        public IReadOnlyCollection<SceneOpsTelemetryEvent> BufferedEvents => events;

        public SceneOpsTelemetryEvent Record(
            string eventType,
            SceneOpsIdentity identity,
            string outcome,
            string eventId = null)
        {
            if (identity == null)
            {
                throw new ArgumentNullException(nameof(identity));
            }

            SceneOpsIdentitySnapshot mapped = identity.Capture();
            SceneOpsTelemetryEvent telemetryEvent = new SceneOpsTelemetryEvent
            {
                eventId = string.IsNullOrWhiteSpace(eventId)
                    ? $"evt_{Guid.NewGuid():N}"
                    : eventId,
                eventType = eventType,
                occurredAt = DateTime.UtcNow.ToString("O"),
                projectId = projectId,
                buildId = buildId,
                executionMode = executionMode,
                sceneopsId = mapped.sceneopsId,
                sourceAssetId = mapped.sourceAssetId,
                sourceAssetVersionId = mapped.sourceAssetVersionId,
                prefabId = mapped.prefabId,
                sceneInstanceId = mapped.sceneInstanceId,
                outcome = outcome,
            };

            while (events.Count >= capacity)
            {
                events.Dequeue();
            }
            events.Enqueue(telemetryEvent);
            EventRecorded?.Invoke(telemetryEvent);
            return telemetryEvent;
        }

        public string ExportBufferedJson()
        {
            return JsonUtility.ToJson(new SceneOpsTelemetryBatch
            {
                schemaVersion = 1,
                events = events.ToArray(),
            });
        }
    }

    [Serializable]
    internal sealed class SceneOpsTelemetryBatch
    {
        public int schemaVersion;
        public SceneOpsTelemetryEvent[] events;
    }
}
