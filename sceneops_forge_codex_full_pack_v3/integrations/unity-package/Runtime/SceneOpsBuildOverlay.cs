using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    public sealed class SceneOpsBuildOverlay : MonoBehaviour
    {
        [SerializeField] private string title = "SceneOps Forge";
        [SerializeField] private string objective = "Use WASD to complete the objective.";

        public void Configure(string buildTitle, string buildObjective)
        {
            title = buildTitle;
            objective = buildObjective;
        }

        private void OnGUI()
        {
            GUI.Box(new Rect(16, 16, 420, 74), string.Empty);
            GUI.Label(new Rect(30, 26, 390, 24), title);
            GUI.Label(new Rect(30, 50, 390, 24), objective);
        }
    }
}
