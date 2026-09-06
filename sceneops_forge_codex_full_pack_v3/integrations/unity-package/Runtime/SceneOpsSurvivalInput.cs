using System;
using System.Collections.Generic;
using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    [Serializable]
    public struct SurvivalInputFrame
    {
        public float move_x, move_z, yaw_delta, pitch_delta;
        public bool fire, jump, restart;
        public bool IsNeutral => move_x == 0 && move_z == 0 && yaw_delta == 0 && pitch_delta == 0 && !fire && !jump && !restart;
    }

    [Serializable]
    public sealed class SurvivalInputReceipt
    {
        public string request_id, run_id;
        public int requested_frames, completed_frames, first_unity_frame = -1, last_unity_frame = -1, fixed_tick_count;
        public bool release_confirmed, cancelled, collided_side;
        public float simulation_elapsed, wall_elapsed;
        public SurvivalInputFrame last_consumed;
    }

    /// <summary>Feeds the same input consumer as keyboard/mouse. Counts completed player Update frames.</summary>
    public sealed class SurvivalInputDriver
    {
        public SurvivalInputReceipt Receipt { get; private set; }
        SurvivalInputFrame input;
        int lastConsumedFrame = -1;
        bool consumed;
        float startedAt;

        public void Begin(string requestId, string runId, int frames, SurvivalInputFrame value)
        {
            if (Receipt != null && !Receipt.release_confirmed) throw new InvalidOperationException("Input segment has not released.");
            if (frames < 1 || frames > 120) throw new ArgumentOutOfRangeException(nameof(frames));
            Receipt = new SurvivalInputReceipt { request_id = requestId, run_id = runId, requested_frames = frames };
            input = value; startedAt = Time.realtimeSinceStartup; consumed = false;
        }

        public SurvivalInputFrame Consume()
        {
            if (Receipt == null || Receipt.release_confirmed) return new SurvivalInputFrame();
            if (lastConsumedFrame == Time.frameCount) throw new InvalidOperationException("Duplicate input consumption in a game frame.");
            lastConsumedFrame = Time.frameCount; consumed = true;
            var value = Receipt.cancelled || Receipt.completed_frames >= Receipt.requested_frames ? new SurvivalInputFrame() : input;
            if (Receipt.completed_frames > 0) { value.yaw_delta = value.pitch_delta = 0; value.jump = value.restart = false; }
            Receipt.last_consumed = value;
            if (Receipt.first_unity_frame < 0) Receipt.first_unity_frame = Time.frameCount;
            return value;
        }

        public void CompleteFrame()
        {
            if (!consumed || Receipt == null || Receipt.release_confirmed) return;
            consumed = false; Receipt.last_unity_frame = Time.frameCount;
            Receipt.wall_elapsed = Time.realtimeSinceStartup - startedAt;
            Receipt.simulation_elapsed += Time.deltaTime;
            if (!Receipt.cancelled && Receipt.completed_frames < Receipt.requested_frames) Receipt.completed_frames++;
            else Receipt.release_confirmed = Receipt.last_consumed.IsNeutral;
        }

        public void PhysicsTick() { if (Receipt != null && !Receipt.release_confirmed) Receipt.fixed_tick_count++; }
        public void RecordCollision(bool collided) { if (Receipt != null && !Receipt.release_confirmed) Receipt.collided_side |= collided; }
        public void Cancel() { if (Receipt != null && !Receipt.release_confirmed) Receipt.cancelled = true; }
    }
}
