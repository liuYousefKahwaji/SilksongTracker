using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Reflection;
using System.Threading;
using BepInEx;
using BepInEx.Configuration;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilksongLiveBridge
{
    [BepInPlugin("dev.silksongtracker.livebridge", "Silksong Tracker Live Bridge", "0.3.6")]
    public sealed class LiveBridge : BaseUnityPlugin
    {
        private ConfigEntry<bool> bridgeEnabled;
        private ConfigEntry<string> token;
        private ConfigEntry<string> endpoint;
        private readonly Dictionary<string, NativeRoom> nativeRooms = new Dictionary<string, NativeRoom>(StringComparer.OrdinalIgnoreCase);
        private float[] lastMappedPosition;
        private string lastResolvedScene;
        private string lastReportedResolution;
        private float nextSend;
        private int sending;

        private void Awake()
        {
            bridgeEnabled = Config.Bind("Bridge", "Enabled", false, "Opt in to sending position to the local tracker.");
            token = Config.Bind("Bridge", "Token", "", "Copy from the tracker's .live-bridge-token file. Keep private.");
            endpoint = Config.Bind("Bridge", "Endpoint", "http://127.0.0.1:7397/api/live-position", "Loopback tracker endpoint only.");
            LoadNativeRooms();
        }

        private void Update()
        {
            if (!bridgeEnabled.Value || string.IsNullOrWhiteSpace(token.Value) || Time.unscaledTime < nextSend) return;
            nextSend = Time.unscaledTime + 0.5f;
            if (Interlocked.CompareExchange(ref sending, 1, 0) != 0) return;
            Uri uri;
            if (!Uri.TryCreate(endpoint.Value, UriKind.Absolute, out uri) ||
                uri.Scheme != Uri.UriSchemeHttp ||
                (uri.Host != "localhost" && uri.Host != "127.0.0.1" && uri.Host != "[::1]"))
            {
                Interlocked.Exchange(ref sending, 0);
                return;
            }
            var hero = HeroController.instance;
            if (hero == null)
            {
                Interlocked.Exchange(ref sending, 0);
                return;
            }
            var world = hero.transform.position;
            string activeScene;
            string heroScene;
            var scene = ResolveRoomScene(hero, world, out activeScene, out heroScene);
            string mapMode;
            var mapPosition = NativeMapPosition(scene, world, out mapMode);
            var payload = new PositionMessage { scene = scene, x = world.x, y = world.y, map = mapPosition, mapMode = mapMode };
            if (string.IsNullOrEmpty(payload.scene)) { Interlocked.Exchange(ref sending, 0); return; }
            var resolution = activeScene + "|" + heroScene + "|" + scene + "|" + mapMode;
            if (resolution != lastReportedResolution)
            {
                lastReportedResolution = resolution;
                Logger.LogInfo("Live room resolver: active='" + activeScene + "', hero='" + heroScene +
                               "', selected='" + scene + "', mode='" + mapMode + "'.");
            }
            var json = JsonUtility.ToJson(payload);
            var secret = token.Value;
            ThreadPool.QueueUserWorkItem(_ => Send(uri, secret, json));
        }

        private void LoadNativeRooms()
        {
            try
            {
                using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("SilksongLiveBridge.live_native_rooms.json"))
                {
                    if (stream == null) { Logger.LogError("Embedded live-room data is missing."); return; }
                    using (var reader = new StreamReader(stream))
                    {
                        var data = JsonConvert.DeserializeObject<NativeRoomSet>(reader.ReadToEnd());
                        if (data == null || data.rooms == null)
                        {
                            Logger.LogError("Embedded live-room data could not be parsed.");
                            return;
                        }
                        foreach (var room in data.rooms)
                            if (IsUsableRoom(room))
                                nativeRooms[room.name] = room;
                    }
                }
                var legacyCount = 0;
                foreach (var room in nativeRooms.Values) if (HasLegacyTransform(room)) legacyCount++;
                Logger.LogInfo("Loaded live-position mappings for " + nativeRooms.Count + " game rooms (" + legacyCount + " legacy transforms).");
                if (nativeRooms.Count < 549) Logger.LogWarning("Expected mappings for 549 room-size scenes; loaded " + nativeRooms.Count + ".");
            }
            catch (Exception ex) { Logger.LogError("Could not load embedded live-room data: " + ex); }
        }

        private static bool HasLegacyTransform(NativeRoom room)
        {
            return room != null && room.legacySource != null && room.legacySource.Length == 2 &&
                   room.legacySketchLonLat != null && room.legacySketchLonLat.Length == 2;
        }

        private static bool IsUsableRoom(NativeRoom room)
        {
            if (room == null || string.IsNullOrWhiteSpace(room.name) || room.sceneSize == null || room.sceneSize.Length != 2 ||
                room.sceneSize[0] <= 0f || room.sceneSize[1] <= 0f) return false;
            if (HasLegacyTransform(room)) return true;
            return room.bounds != null && room.bounds.Length == 4;
        }

        private string ResolveRoomScene(HeroController hero, Vector3 world, out string activeName, out string heroName)
        {
            activeName = NormalizeSceneName(SceneManager.GetActiveScene().name);
            heroName = NormalizeSceneName(hero.gameObject.scene.name);

            // HeroController is moved to Unity's persistent scene. That scene is not
            // the gameplay room and must never be used as the primary room key.
            if (HasRoom(activeName)) return RememberScene(activeName);
            if (HasRoom(heroName)) return RememberScene(heroName);

            var loaded = new List<string>();
            var spatial = new List<string>();
            for (var i = 0; i < SceneManager.sceneCount; i++)
            {
                var loadedScene = SceneManager.GetSceneAt(i);
                if (!loadedScene.IsValid() || !loadedScene.isLoaded) continue;
                var name = NormalizeSceneName(loadedScene.name);
                if (!HasRoom(name) || loaded.Contains(name)) continue;
                loaded.Add(name);
                NativeRoom room;
                if (nativeRooms.TryGetValue(name, out room) && !room.anchorOnly && !room.inheritLastPosition &&
                    world.x >= -0.5f && world.y >= -0.5f &&
                    world.x <= room.sceneSize[0] + 0.5f && world.y <= room.sceneSize[1] + 0.5f)
                    spatial.Add(name);
            }
            if (spatial.Count == 1) return RememberScene(spatial[0]);
            if (!string.IsNullOrEmpty(lastResolvedScene) && loaded.Contains(lastResolvedScene)) return lastResolvedScene;
            if (loaded.Count == 1) return RememberScene(loaded[0]);

            // Preserve the actual active-room name for diagnostics when the game
            // introduces a scene absent from the generated data.
            return activeName == "DontDestroyOnLoad" ? heroName : activeName;
        }

        private bool HasRoom(string name)
        {
            return !string.IsNullOrEmpty(name) && !string.Equals(name, "DontDestroyOnLoad", StringComparison.OrdinalIgnoreCase) &&
                   nativeRooms.ContainsKey(name);
        }

        private string RememberScene(string name)
        {
            lastResolvedScene = name;
            return name;
        }

        private static string NormalizeSceneName(string name)
        {
            if (string.IsNullOrWhiteSpace(name)) return "";
            name = name.Replace('\\', '/');
            var slash = name.LastIndexOf('/');
            if (slash >= 0) name = name.Substring(slash + 1);
            if (name.EndsWith(".unity", StringComparison.OrdinalIgnoreCase)) name = name.Substring(0, name.Length - 6);
            return name.Trim();
        }

        private float[] NativeMapPosition(string scene, Vector3 world, out string mode)
        {
            NativeRoom room;
            mode = "unmapped";
            if (!nativeRooms.TryGetValue(scene, out room)) return null;
            if (room.inheritLastPosition && lastMappedPosition != null)
            {
                mode = "last-known";
                return (float[])lastMappedPosition.Clone();
            }
            if (HasLegacyTransform(room))
            {
                var dx = world.x - room.legacySource[0];
                var dy = (world.y - room.legacySource[1]) * (room.reflected ? -1f : 1f);
                var legacyResult = new[]
                {
                    room.legacySketchLonLat[1] + room.imag * dx + room.real * dy,
                    room.legacySketchLonLat[0] + room.real * dx - room.imag * dy,
                };
                mode = "legacy-room-transform";
                lastMappedPosition = (float[])legacyResult.Clone();
                return legacyResult;
            }
            var width = room.sceneSize[0];
            var height = room.sceneSize[1];
            if (!room.anchorOnly && !room.inheritLastPosition &&
                (world.x < -0.5f || world.y < -0.5f || world.x > width + 0.5f || world.y > height + 0.5f))
            {
                mode = "out-of-room-range";
                return null;
            }
            var x = room.anchorOnly || room.inheritLastPosition ? 0f : Mathf.Clamp01(world.x / width);
            var y = room.anchorOnly || room.inheritLastPosition ? 0f : Mathf.Clamp01(world.y / height);
            var result = new[]
            {
                room.bounds[0] + (room.bounds[2] - room.bounds[0]) * x,
                room.bounds[1] + (room.bounds[3] - room.bounds[1]) * y,
            };
            if (room.inheritLastPosition) mode = "area-anchor";
            else if (room.anchorOnly) mode = string.IsNullOrEmpty(room.anchorSource) || room.anchorSource == "in-game-map-room-anchor"
                ? "room-anchor" : "area-anchor";
            else mode = "room-geometry";
            if (!room.inheritLastPosition) lastMappedPosition = (float[])result.Clone();
            return result;
        }

        private void Send(Uri uri, string secret, string json)
        {
            try
            {
                var request = (HttpWebRequest)WebRequest.Create(uri);
                request.Method = "POST";
                request.ContentType = "application/json";
                request.Headers["X-Silksong-Live-Token"] = secret;
                request.Timeout = 1500;
                var bytes = System.Text.Encoding.UTF8.GetBytes(json);
                using (var stream = request.GetRequestStream()) stream.Write(bytes, 0, bytes.Length);
                using (var response = (HttpWebResponse)request.GetResponse()) { }
            }
            catch (Exception) { /* Tracker may not be running. Never crash the game for telemetry. */ }
            finally { Interlocked.Exchange(ref sending, 0); }
        }

#pragma warning disable 0649 // Unity JsonUtility populates these DTO fields through native reflection.
        [Serializable]
        private sealed class PositionMessage
        {
            public string scene;
            public float x;
            public float y;
            public float[] map;
            public string mapMode;
        }

        [Serializable]
        private sealed class NativeRoomSet { public int format; public NativeRoom[] rooms; }

        [Serializable]
        private sealed class NativeRoom
        {
            public string name;
            public float[] bounds;
            public float[] sceneSize;
            public bool anchorOnly;
            public bool inheritLastPosition;
            public string anchorSource;
            public float[] legacySource;
            public float[] legacySketchLonLat;
            public float real;
            public float imag;
            public bool reflected;
        }
#pragma warning restore 0649
    }
}
