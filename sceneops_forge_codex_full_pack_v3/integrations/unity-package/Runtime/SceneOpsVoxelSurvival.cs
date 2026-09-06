using System;
using System.Collections.Generic;
using UnityEngine;

namespace SceneOps.Forge.Unity.Runtime
{
    /// <summary>Trusted, parameterized survival recipe. Model inputs are data, never scripts.</summary>
    public sealed class SceneOpsVoxelSurvival : MonoBehaviour
    {
        public string prototype_id = "sobj_voxel_survival";
        public string title = "方块防线";
        public string project_revision = "";
        public const string ComponentVersion = "survival-shooter-2";
        public string ActiveRunId { get; private set; }
        public SurvivalInputDriver InputDriver { get; } = new SurvivalInputDriver();
        public int seed = 42, arena_size = 24, enemy_count = 5, player_health = 100;
        public int weapon_damage = 25, enemy_health = 50, enemy_damage = 10, goal_kills = 8;
        public float enemy_speed = 1.3f, player_speed = 5f, fire_interval = .25f;
        public bool AgentControlled;
        public Camera GameCamera { get; private set; }
        readonly List<Enemy> enemies = new List<Enemy>();
        readonly List<Material> materials = new List<Material>();
        readonly List<GameplayEvent> gameplayEvents = new List<GameplayEvent>();
        int eventSequence;
        CharacterController player;
        Transform world, gun;
        Light flash;
        AudioSource sound;
        AudioClip shotSound;
        Font font;
        Material zombieSkin, zombieShirt, zombiePants;
        Vector2 movement;
        float yaw, pitch, verticalSpeed, lastShot = -100, damageUntil, elapsed;
        bool firing, jumping, wallBlocked, guiRestart;
        int health, kills, shots, hits, spawned, round;
        string state = "not_started";

        sealed class Enemy
        {
            public string id;
            public CharacterController controller;
            public Transform leftLeg, rightLeg;
            public int health;
            public float lastAttack = -10;
        }
        [Serializable] public sealed class EnemyState { public string sceneops_id; public Vector3 position; public int health; }
        [Serializable] public sealed class GameplayEvent
        { public int sequence, frame, before, after; public string type, actor_id, target_id, run_id; }
        [Serializable] public sealed class Observation
        {
            public string prototype_id, state, project_revision, run_id, component_package_version;
            public bool playing, grounded, agent_controlled, wall_blocked;
            public int health, kills, shots, hits, enemy_count, goal_kills, round;
            public float elapsed, yaw, pitch;
            public Vector3 player_position;
            public EnemyState[] enemies;
            public SurvivalInputReceipt input_receipt;
            public GameplayEvent[] events;
        }

        void Awake()
        {
            if (!Application.isPlaying) return;
            Application.targetFrameRate = 60;
            Application.runInBackground = true;
            font = Font.CreateDynamicFontFromOSFont(new[] { "PingFang SC", "Arial" }, 18);
            BuildWorld();
            ResetRound();
        }

        Material Material(Color color)
        {
            var material = new Material(Shader.Find("Standard"));
            material.color = color;
            material.SetFloat("_Glossiness", .05f);
            materials.Add(material);
            return material;
        }

        GameObject Block(string name, Transform parent, Vector3 position, Vector3 size, Material material, bool solid = true)
        {
            var block = GameObject.CreatePrimitive(PrimitiveType.Cube);
            block.name = name;
            block.transform.SetParent(parent, false);
            block.transform.localPosition = position;
            block.transform.localScale = size;
            block.GetComponent<Renderer>().sharedMaterial = material;
            block.layer = solid ? 8 : 2;
            if (!solid) Destroy(block.GetComponent<Collider>());
            return block;
        }

        void BuildWorld()
        {
            world = new GameObject("Voxel arena").transform;
            world.SetParent(transform, false);
            var grass = new[] { Material(new Color(.30f, .47f, .20f)), Material(new Color(.35f, .52f, .23f)), Material(new Color(.39f, .55f, .26f)) };
            var stone = Material(new Color(.37f, .39f, .36f));
            var wood = Material(new Color(.31f, .20f, .12f));
            var leaves = Material(new Color(.18f, .34f, .14f));
            zombieSkin = Material(new Color(.27f, .49f, .23f)); zombieShirt = Material(new Color(.24f, .37f, .53f)); zombiePants = Material(new Color(.28f, .22f, .35f));
            var random = new System.Random(seed);
            float half = arena_size / 2f;
            // Ground collision is one surface; visible tiles share three materials.
            Block("Ground collision", world, new Vector3(0, -.6f, 0), new Vector3(arena_size, 1, arena_size), stone);
            for (int x = 0; x < arena_size; x++)
                for (int z = 0; z < arena_size; z++)
                    Block("Grass", world, new Vector3(x - half + .5f, -.08f, z - half + .5f), new Vector3(.995f, .16f, .995f), grass[random.Next(3)], false);
            for (int side = 0; side < 4; side++)
            {
                bool alongX = side < 2;
                float coordinate = (side % 2 == 0 ? -1 : 1) * half;
                Block("Boundary", world, alongX ? new Vector3(coordinate, 1.4f, 0) : new Vector3(0, 1.4f, coordinate),
                    alongX ? new Vector3(1, 3, arena_size + 1) : new Vector3(arena_size + 1, 3, 1), stone);
            }
            for (int x = -1; x <= 1; x += 2)
                for (int z = -1; z <= 1; z += 2)
                {
                    var p = new Vector3(x * (half - 3), 0, z * (half - 3));
                    Block("Oak trunk", world, p + Vector3.up * 1.5f, new Vector3(1, 3, 1), wood);
                    Block("Oak crown", world, p + Vector3.up * 3.4f, new Vector3(3, 2, 3), leaves);
                    Block("Cover", world, new Vector3(x * 4, .5f, z * 4), new Vector3(2, 1.2f, 2), stone);
                }
            var body = new GameObject("Player");
            body.transform.SetParent(transform, false); body.layer = 9;
            player = body.AddComponent<CharacterController>();
            player.height = 1.8f; player.radius = .32f; player.center = Vector3.up * .9f; player.stepOffset = .35f;
            var cameraObject = new GameObject("Main Camera"); cameraObject.tag = "MainCamera";
            cameraObject.transform.SetParent(body.transform, false); cameraObject.transform.localPosition = Vector3.up * 1.6f;
            GameCamera = cameraObject.AddComponent<Camera>(); GameCamera.nearClipPlane = .05f; GameCamera.farClipPlane = 120;
            GameCamera.fieldOfView = 75; GameCamera.clearFlags = CameraClearFlags.SolidColor;
            GameCamera.backgroundColor = new Color(.59f, .73f, .76f);
            cameraObject.AddComponent<AudioListener>(); sound = cameraObject.AddComponent<AudioSource>();
            sound.spatialBlend = 0; sound.volume = .18f;
            shotSound = AudioClip.Create("Synthesized shot", 3308, 1, 22050, false);
            var samples = new float[3308];
            for (int i = 0; i < samples.Length; i++) samples[i] = (float)(random.NextDouble() * 2 - 1) * Mathf.Exp(-i / 450f);
            shotSound.SetData(samples, 0);
            gun = Block("Block rifle", GameCamera.transform, new Vector3(.30f, -.25f, .6f), new Vector3(.15f, .18f, .65f), Material(new Color(.2f, .22f, .24f)), false).transform;
            Block("Barrel", GameCamera.transform, new Vector3(.30f, -.19f, .99f), new Vector3(.08f, .08f, .3f), stone, false);
            var lamp = new GameObject("Muzzle flash"); lamp.transform.SetParent(GameCamera.transform, false); lamp.transform.localPosition = new Vector3(.3f, -.1f, .8f);
            flash = lamp.AddComponent<Light>(); flash.color = new Color(1, .75f, .3f); flash.range = 5; flash.intensity = 0;
            var sunlight = new GameObject("Sun").AddComponent<Light>(); sunlight.transform.SetParent(transform, false);
            sunlight.type = LightType.Directional; sunlight.color = new Color(1, .91f, .76f); sunlight.intensity = 1.15f;
            sunlight.transform.rotation = Quaternion.Euler(48, -30, 0);
            RenderSettings.ambientLight = new Color(.53f, .58f, .63f);
        }

        void ResetRound()
        {
            if (player == null) return;
            foreach (var enemy in enemies) if (enemy.controller) { enemy.controller.enabled = false; Destroy(enemy.controller.gameObject); }
            enemies.Clear(); round++; health = player_health; kills = shots = hits = spawned = 0;
            elapsed = yaw = pitch = verticalSpeed = damageUntil = 0; lastShot = -100;
            movement = Vector2.zero; firing = jumping = false; state = "playing";
            player.enabled = false; player.transform.position = new Vector3(0, .1f, 0); player.transform.rotation = Quaternion.identity; player.enabled = true;
            GameCamera.transform.localRotation = Quaternion.identity;
            for (int i = 0; i < Mathf.Min(enemy_count, goal_kills); i++) SpawnEnemy();
            Physics.SyncTransforms();
        }

        void SpawnEnemy()
        {
            float angle = spawned == 0 ? 0 : (spawned * 137.5f + seed % 20) * Mathf.Deg2Rad;
            float radius = Mathf.Min(arena_size / 2f - 2, 9);
            var root = new GameObject("Zombie " + spawned); root.layer = 10; root.transform.SetParent(transform, false);
            root.transform.position = new Vector3(Mathf.Sin(angle) * radius, .1f, Mathf.Cos(angle) * radius);
            var controller = root.AddComponent<CharacterController>(); controller.height = 1.8f; controller.radius = .35f; controller.center = Vector3.up * .9f;
            var skin = zombieSkin; var shirt = zombieShirt; var pants = zombiePants;
            Block("Head", root.transform, new Vector3(0, 1.55f, 0), Vector3.one * .52f, skin, false);
            Block("Torso", root.transform, new Vector3(0, .96f, 0), new Vector3(.6f, .7f, .32f), shirt, false);
            for (int side = -1; side <= 1; side += 2)
            {
                Block("Arm", root.transform, new Vector3(side * .4f, 1.04f, .32f), new Vector3(.22f, .24f, .72f), skin, false);
                Block("Eye", root.transform, new Vector3(side * .12f, 1.59f, .267f), new Vector3(.08f, .07f, .02f), pants, false);
            }
            var enemy = new Enemy { id = prototype_id + "_round_" + round + "_enemy_" + spawned, controller = controller, health = enemy_health };
            enemy.leftLeg = Block("Left leg", root.transform, new Vector3(-.16f, .30f, 0), new Vector3(.26f, .60f, .28f), pants, false).transform;
            enemy.rightLeg = Block("Right leg", root.transform, new Vector3(.16f, .30f, 0), new Vector3(.26f, .60f, .28f), pants, false).transform;
            enemies.Add(enemy); spawned++;
        }

        public void BindRun(string runId, string revision)
        {
            if (revision != project_revision || string.IsNullOrEmpty(runId)) throw new InvalidOperationException("Run revision mismatch.");
            if (!string.IsNullOrEmpty(ActiveRunId) && ActiveRunId != runId) throw new InvalidOperationException("Another run is already bound.");
            ActiveRunId = runId; AgentControlled = true;
        }

        void ConsumeInput(SurvivalInputFrame input)
        {
            if (input.restart) { ResetRound(); RecordEvent("RestartConsumed", prototype_id, prototype_id, 0, round); }
            movement = Vector2.ClampMagnitude(new Vector2(input.move_x, input.move_z), 1);
            yaw += input.yaw_delta; pitch = Mathf.Clamp(pitch + input.pitch_delta, -80, 80);
            firing = input.fire; jumping = input.jump;
        }

        SurvivalInputFrame ReadHumanInput()
        {
            if (Input.GetKeyDown(KeyCode.Escape)) { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
            if (Input.GetMouseButtonDown(0) && state == "playing") { Cursor.lockState = CursorLockMode.Locked; Cursor.visible = false; }
            bool active = Cursor.lockState == CursorLockMode.Locked;
            var value = new SurvivalInputFrame { move_x = active ? Input.GetAxisRaw("Horizontal") : 0,
                move_z = active ? Input.GetAxisRaw("Vertical") : 0,
                yaw_delta = active ? Input.GetAxis("Mouse X") * 2 : 0,
                pitch_delta = active ? -Input.GetAxis("Mouse Y") * 2 : 0,
                fire = active && Input.GetMouseButton(0), jump = active && Input.GetKeyDown(KeyCode.Space),
                restart = guiRestart || Input.GetKeyDown(KeyCode.R) };
            guiRestart = false; return value;
        }

        void Update()
        {
            if (player == null) return;
            ConsumeInput(AgentControlled ? InputDriver.Consume() : ReadHumanInput());
            player.transform.rotation = Quaternion.Euler(0, yaw, 0); GameCamera.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
            flash.intensity = Time.time - lastShot < .06f ? 2 : 0;
            gun.localPosition = new Vector3(.3f, -.25f, .6f - Mathf.Max(0, .1f - (Time.time - lastShot)) * .4f);
            if (state != "playing") { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; return; }
            elapsed += Time.deltaTime;
            if (player.isGrounded) verticalSpeed = jumping ? 7 : -2;
            jumping = false; verticalSpeed -= 22 * Time.deltaTime;
            Vector3 move = (player.transform.right * movement.x + player.transform.forward * movement.y) * player_speed;
            var collision = player.Move((move + Vector3.up * verticalSpeed) * Time.deltaTime);
            wallBlocked = movement.sqrMagnitude > .01f && (collision & CollisionFlags.Sides) != 0;
            if (AgentControlled) InputDriver.RecordCollision(wallBlocked);
            if (firing && Time.time - lastShot >= fire_interval) Fire();
            foreach (var enemy in enemies.ToArray()) AdvanceEnemy(enemy);
        }

        void LateUpdate() { if (AgentControlled) InputDriver.CompleteFrame(); }
        void FixedUpdate() { if (AgentControlled) InputDriver.PhysicsTick(); }

        void Fire()
        {
            lastShot = Time.time; shots++; sound.PlayOneShot(shotSound);
            RecordEvent("ShotFired", prototype_id + "_player", "", shots - 1, shots);
            RaycastHit hit;
            if (!Physics.Raycast(GameCamera.transform.position, GameCamera.transform.forward, out hit, 60, (1 << 8) | (1 << 10), QueryTriggerInteraction.Ignore)) return;
            var enemy = enemies.Find(item => item.controller == hit.collider);
            if (enemy == null) return;
            RecordEvent("Hit", prototype_id + "_player", enemy.id, enemy.health, enemy.health);
            hits++; int before = enemy.health; enemy.health = Mathf.Max(0, enemy.health - weapon_damage);
            RecordEvent("DamageApplied", prototype_id + "_player", enemy.id, before, enemy.health);
            if (enemy.health > 0) return;
            enemy.controller.enabled = false; Destroy(enemy.controller.gameObject); enemies.Remove(enemy); kills++;
            RecordEvent("EnemyDied", prototype_id + "_player", enemy.id, before, 0);
            if (kills >= goal_kills) { state = "won"; RecordEvent("Victory", prototype_id, prototype_id, kills, kills); }
            else if (spawned < goal_kills) SpawnEnemy();
        }

        void AdvanceEnemy(Enemy enemy)
        {
            if (state != "playing" || !enemy.controller) return;
            Vector3 delta = player.transform.position - enemy.controller.transform.position; delta.y = 0;
            Vector3 direction = delta.normalized;
            Vector3 origin = enemy.controller.transform.position + Vector3.up * .7f;
            if (Physics.SphereCast(origin, .36f, direction, out _, 1.1f, 1 << 8))
            {
                Vector3 left = Quaternion.Euler(0, 70, 0) * direction;
                Vector3 right = Quaternion.Euler(0, -70, 0) * direction;
                direction = !Physics.SphereCast(origin, .36f, left, out _, 1.1f, 1 << 8) ? left : right;
            }
            if (delta.magnitude > 1.1f) enemy.controller.Move((direction * enemy_speed + Vector3.down * 4) * Time.deltaTime);
            if (direction.sqrMagnitude > .01f) enemy.controller.transform.rotation = Quaternion.LookRotation(direction);
            float walk = Mathf.Sin(elapsed * 8 + enemies.IndexOf(enemy)) * 22;
            enemy.leftLeg.localRotation = Quaternion.Euler(walk, 0, 0); enemy.rightLeg.localRotation = Quaternion.Euler(-walk, 0, 0);
            if (delta.magnitude < 1.5f && Time.time - enemy.lastAttack >= 1 && !Physics.Raycast(origin, direction, delta.magnitude, 1 << 8))
            {
                enemy.lastAttack = Time.time; int before = health; health = Mathf.Max(0, health - enemy_damage); damageUntil = Time.time + .2f;
                RecordEvent("PlayerDamage", enemy.id, prototype_id + "_player", before, health);
                if (health == 0) { state = "lost"; RecordEvent("Defeat", enemy.id, prototype_id + "_player", before, health); }
            }
        }

        public string CaptureStateJson()
        {
            var list = new List<EnemyState>();
            foreach (var enemy in enemies) if (enemy.controller) list.Add(new EnemyState { sceneops_id = enemy.id, position = enemy.controller.transform.position, health = enemy.health });
            return JsonUtility.ToJson(new Observation { prototype_id = prototype_id, playing = Application.isPlaying,
                project_revision = project_revision, run_id = ActiveRunId, component_package_version = ComponentVersion,
                input_receipt = InputDriver.Receipt,
                events = gameplayEvents.ToArray(),
                state = state, health = health, kills = kills, shots = shots, hits = hits, elapsed = elapsed,
                player_position = player ? player.transform.position : Vector3.zero, yaw = yaw, pitch = pitch,
                enemy_count = enemies.Count, enemies = list.ToArray(), goal_kills = goal_kills,
                grounded = player && player.isGrounded, agent_controlled = AgentControlled, wall_blocked = wallBlocked, round = round });
        }

        void RecordEvent(string type, string actor, string target, int before, int after)
        {
            gameplayEvents.Add(new GameplayEvent { sequence = ++eventSequence, frame = Time.frameCount,
                type = type, actor_id = actor, target_id = target, before = before, after = after, run_id = ActiveRunId });
            if (gameplayEvents.Count > 256) gameplayEvents.RemoveAt(0);
        }

        void OnGUI()
        {
            if (player == null) return;
            var label = new GUIStyle(GUI.skin.label) { fontSize = 20, font = font, normal = { textColor = Color.white } };
            GUI.Box(new Rect(18, 18, 330, 88), "");
            GUI.Label(new Rect(30, 23, 310, 32), title, label);
            GUI.Label(new Rect(30, 60, 310, 34), "生命 " + health + "   击杀 " + kills + " / " + goal_kills, label);
            GUI.Label(new Rect(Screen.width / 2 - 8, Screen.height / 2 - 14, 24, 32), "+", label);
            GUI.Label(new Rect(24, Screen.height - 42, Screen.width - 40, 32), "WASD 移动  ·  鼠标瞄准 / 左键射击  ·  空格跳跃  ·  R 重开  ·  Esc 释放鼠标", new GUIStyle(label) { fontSize = 16 });
            if (Time.time < damageUntil) { var old = GUI.color; GUI.color = new Color(1, 0, 0, .18f); GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture); GUI.color = old; }
            if (state != "playing")
            {
                GUI.Box(new Rect(Screen.width / 2 - 180, Screen.height / 2 - 90, 360, 180), "");
                GUI.Label(new Rect(Screen.width / 2 - 120, Screen.height / 2 - 65, 300, 50), state == "won" ? "防线守住了！" : "你被僵尸击倒了", new GUIStyle(label) { fontSize = 28 });
                if (GUI.Button(new Rect(Screen.width / 2 - 90, Screen.height / 2, 180, 45), "重新开始 / R")) guiRestart = true;
            }
            else if (!AgentControlled && Cursor.lockState != CursorLockMode.Locked)
                GUI.Label(new Rect(Screen.width / 2 - 135, Screen.height / 2 + 45, 300, 35), "点击画面进入战斗", label);
        }

        void OnDestroy()
        {
            Cursor.lockState = CursorLockMode.None; Cursor.visible = true;
            foreach (var material in materials) if (material) Destroy(material);
            if (shotSound) Destroy(shotSound);
            if (font) Destroy(font);
        }
    }
}
