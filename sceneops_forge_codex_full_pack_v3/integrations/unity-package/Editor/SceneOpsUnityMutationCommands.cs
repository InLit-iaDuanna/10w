using System;
using SceneOps.Forge.Unity.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace SceneOps.Forge.Unity.Editor
{
    internal static class SceneOpsUnityMutationCommands
    {
        internal static string SetComponentProperty(string payloadJson)
        {
            SetComponentPropertyPayload payload = JsonUtility.FromJson<SetComponentPropertyPayload>(payloadJson);
            if (payload == null)
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Component property payload is required.");
            }
            SceneOpsCommandSecurity.ValidateComponentProperty(payload.component_type, payload.property_path);
            SceneOpsIdentity identity = FindIdentity(payload.sceneops_id, payload.scene_instance_id);
            Component component = ResolveComponent(identity.gameObject, payload.component_type);
            if (component == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE",
                    $"Component '{payload.component_type}' is missing on the mapped GameObject.");
            }

            SerializedObject serialized = new SerializedObject(component);
            SerializedProperty property = serialized.FindProperty(payload.property_path);
            if (property == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", $"Serialized property '{payload.property_path}' is missing.");
            }
            string previous = SerializeProperty(property);
            Undo.RecordObject(component, "SceneOps approved component property change");
            ApplyJsonValue(property, payload.value_json);
            serialized.ApplyModifiedProperties();
            EditorUtility.SetDirty(component);
            MarkSceneDirty(identity.gameObject);

            return JsonUtility.ToJson(new ComponentPropertyResult
            {
                sceneopsId = identity.SceneOpsId,
                componentType = payload.component_type,
                propertyPath = payload.property_path,
                previousValueJson = previous,
                proposedValueJson = payload.value_json,
                executionMode = "live",
            });
        }

        internal static string UpsertCollider(string payloadJson)
        {
            UpsertColliderPayload payload = JsonUtility.FromJson<UpsertColliderPayload>(payloadJson);
            if (payload == null || payload.center_meters == null || payload.center_meters.Length != 3 ||
                payload.size_meters == null || payload.size_meters.Length != 3)
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Collider payload is invalid.");
            }
            SceneOpsIdentity identity = FindIdentity(payload.sceneops_id, payload.scene_instance_id);
            Collider collider = ResolveOrAddCollider(identity.gameObject, payload.collider_type);
            Undo.RecordObject(collider, "SceneOps approved collider change");
            collider.isTrigger = payload.is_trigger;
            Vector3 center = Vector(payload.center_meters);
            Vector3 size = Vector(payload.size_meters);
            switch (collider)
            {
                case BoxCollider box:
                    box.center = center;
                    box.size = size;
                    break;
                case SphereCollider sphere:
                    sphere.center = center;
                    sphere.radius = Mathf.Max(size.x, size.y, size.z) * 0.5f;
                    break;
                case CapsuleCollider capsule:
                    capsule.center = center;
                    capsule.radius = Mathf.Max(size.x, size.z) * 0.5f;
                    capsule.height = size.y;
                    break;
                case MeshCollider mesh:
                    mesh.convex = payload.is_trigger;
                    break;
            }
            EditorUtility.SetDirty(collider);
            MarkSceneDirty(identity.gameObject);
            return JsonUtility.ToJson(new ColliderResult
            {
                sceneopsId = identity.SceneOpsId,
                sceneInstanceId = identity.SceneInstanceId,
                colliderType = collider.GetType().Name,
                executionMode = "live",
            });
        }

        private static SceneOpsIdentity FindIdentity(string sceneopsId, string sceneInstanceId)
        {
            SceneOpsIdentity identity = SceneOpsIdentityEditorUtility.FindLoadedIdentity(
                sceneopsId, sceneInstanceId);
            if (identity == null)
            {
                throw new SceneOpsCommandException(
                    "UNITY_MISSING_REFERENCE", "Mapped scene GameObject was not found.");
            }
            return identity;
        }

        private static Component ResolveComponent(GameObject target, string componentType)
        {
            switch (componentType)
            {
                case "Transform": return target.transform;
                case "BoxCollider": return target.GetComponent<BoxCollider>();
                case "SphereCollider": return target.GetComponent<SphereCollider>();
                case "CapsuleCollider": return target.GetComponent<CapsuleCollider>();
                case "MeshCollider": return target.GetComponent<MeshCollider>();
                case "Rigidbody": return target.GetComponent<Rigidbody>();
                case "Light": return target.GetComponent<Light>();
                default: return null;
            }
        }

        private static Collider ResolveOrAddCollider(GameObject target, string colliderType)
        {
            switch (colliderType)
            {
                case "BoxCollider": return target.GetComponent<BoxCollider>() ?? target.AddComponent<BoxCollider>();
                case "SphereCollider": return target.GetComponent<SphereCollider>() ?? target.AddComponent<SphereCollider>();
                case "CapsuleCollider": return target.GetComponent<CapsuleCollider>() ?? target.AddComponent<CapsuleCollider>();
                case "MeshCollider": return target.GetComponent<MeshCollider>() ?? target.AddComponent<MeshCollider>();
                default:
                    throw new SceneOpsCommandException(
                        "UNITY_COMMAND_NOT_ALLOWED", $"Collider '{colliderType}' is not allowlisted.");
            }
        }

        private static void ApplyJsonValue(SerializedProperty property, string valueJson)
        {
            if (string.IsNullOrWhiteSpace(valueJson))
            {
                throw new SceneOpsCommandException("UNITY_INVALID_PAYLOAD", "Component property value is required.");
            }
            switch (property.propertyType)
            {
                case SerializedPropertyType.Boolean:
                    property.boolValue = JsonUtility.FromJson<BoolValue>($"{{\"value\":{valueJson}}}").value;
                    break;
                case SerializedPropertyType.Integer:
                    property.intValue = JsonUtility.FromJson<IntValue>($"{{\"value\":{valueJson}}}").value;
                    break;
                case SerializedPropertyType.Float:
                    property.floatValue = JsonUtility.FromJson<FloatValue>($"{{\"value\":{valueJson}}}").value;
                    break;
                case SerializedPropertyType.Vector3:
                    property.vector3Value = JsonUtility.FromJson<Vector3Value>($"{{\"value\":{valueJson}}}").value;
                    break;
                case SerializedPropertyType.Quaternion:
                    property.quaternionValue = JsonUtility.FromJson<QuaternionValue>($"{{\"value\":{valueJson}}}").value;
                    break;
                case SerializedPropertyType.Color:
                    property.colorValue = JsonUtility.FromJson<ColorValue>($"{{\"value\":{valueJson}}}").value;
                    break;
                default:
                    throw new SceneOpsCommandException(
                        "UNITY_COMMAND_NOT_ALLOWED",
                        $"Serialized property type '{property.propertyType}' is not allowlisted.");
            }
        }

        private static string SerializeProperty(SerializedProperty property)
        {
            switch (property.propertyType)
            {
                case SerializedPropertyType.Boolean: return property.boolValue ? "true" : "false";
                case SerializedPropertyType.Integer: return property.intValue.ToString();
                case SerializedPropertyType.Float: return property.floatValue.ToString("R");
                case SerializedPropertyType.Vector3: return JsonUtility.ToJson(new Vector3Value { value = property.vector3Value });
                case SerializedPropertyType.Quaternion: return JsonUtility.ToJson(new QuaternionValue { value = property.quaternionValue });
                case SerializedPropertyType.Color: return JsonUtility.ToJson(new ColorValue { value = property.colorValue });
                default: return "null";
            }
        }

        private static Vector3 Vector(float[] values) => new Vector3(values[0], values[1], values[2]);

        private static void MarkSceneDirty(GameObject target)
        {
            if (target.scene.IsValid())
            {
                EditorSceneManager.MarkSceneDirty(target.scene);
            }
        }

        [Serializable] private sealed class BoolValue { public bool value; }
        [Serializable] private sealed class IntValue { public int value; }
        [Serializable] private sealed class FloatValue { public float value; }
        [Serializable] private sealed class Vector3Value { public Vector3 value; }
        [Serializable] private sealed class QuaternionValue { public Quaternion value; }
        [Serializable] private sealed class ColorValue { public Color value; }
    }
}
