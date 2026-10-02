using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Reflection;
using System.Threading;
using BepInEx;
using BepInEx.Configuration;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilksongLiveBridge
{
    [BepInPlugin("dev.silksongtracker.livebridge", "Silksong Tracker Live Bridge", "0.3.5")]
    public sealed class LiveBridge : BaseUnityPlugin
    {
        private ConfigEntry<bool> bridgeEnabled;
        private ConfigEntry<string> token;
        private ConfigEntry<string> endpoint;
        private ConfigEntry<bool> overlayEnabled;
        private ConfigEntry<string> overlayToggleKey;
        private readonly Dictionary<string, NativeRoom> nativeRooms = new Dictionary<string, NativeRoom>(StringComparer.OrdinalIgnoreCase);
        private float[] lastMappedPosition;
        private float nextSend;
        private int sending;

        private void Awake()
        {
            bridgeEnabled = Config.Bind("Bridge", "Enabled", false, "Opt in to sending position to the local tracker.");
            token = Config.Bind("Bridge", "Token", "", "Copy from the tracker's .live-bridge-token file. Keep private.");
            endpoint = Config.Bind("Bridge", "Endpoint", "http://127.0.0.1:7397/api/live-position", "Loopback tracker endpoint only.");
            LoadNativeRooms();
            overlayEnabled = Config.Bind("Map Overlay", "Enabled", true, "Show the local tracker's map over the full menu map.");
            overlayToggleKey = Config.Bind("Map Overlay", "Toggle Key", "F8", "Keyboard shortcut for the full-map overlay.");
            try { TrackerMapOverlay.Attach(Logger, endpoint.Value, overlayEnabled.Value, overlayToggleKey.Value); }
            catch (Exception ex) { Logger.LogError("Could not initialize map overlay: " + ex); }
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
            var scene = hero.gameObject.scene.name;
            if (string.IsNullOrEmpty(scene)) scene = SceneManager.GetActiveScene().name;
            string mapMode;
            var mapPosition = NativeMapPosition(scene, world, out mapMode);
            var payload = new PositionMessage { scene = scene, x = world.x, y = world.y, map = mapPosition, mapMode = mapMode };
            if (string.IsNullOrEmpty(payload.scene)) { Interlocked.Exchange(ref sending, 0); return; }
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
                    if (stream == null) { Logger.LogWarning("Native map-room data is missing; using legacy room transforms."); return; }
                    using (var reader = new StreamReader(stream))
                    {
                        var data = JsonUtility.FromJson<NativeRoomSet>(reader.ReadToEnd());
                        if (data == null || data.rooms == null) return;
                        foreach (var room in data.rooms)
                            if (room != null && !string.IsNullOrWhiteSpace(room.name) && room.bounds != null && room.bounds.Length == 4 && room.sceneSize != null && room.sceneSize.Length == 2 && room.sceneSize[0] > 0f && room.sceneSize[1] > 0f)
                                nativeRooms[room.name] = room;
                    }
                }
                Logger.LogInfo("Loaded native map geometry for " + nativeRooms.Count + " rooms.");
            }
            catch (Exception ex) { Logger.LogWarning("Could not load native map geometry: " + ex.GetType().Name); }
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
            var width = room.sceneSize[0];
            var height = room.sceneSize[1];
            if (!room.anchorOnly && !room.inheritLastPosition &&
                (world.x < -0.5f || world.y < -0.5f || world.x > width + 0.5f || world.y > height + 0.5f)) return null;
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
        }
#pragma warning restore 0649
    }
}
