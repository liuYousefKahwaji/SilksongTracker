using System;
using System.Net;
using System.Reflection;
using System.Threading;
using BepInEx;
using BepInEx.Configuration;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilksongLiveBridge
{
    [BepInPlugin("dev.silksongtracker.livebridge", "Silksong Tracker Live Bridge", "0.1.0")]
    public sealed class LiveBridge : BaseUnityPlugin
    {
        private ConfigEntry<bool> bridgeEnabled;
        private ConfigEntry<string> token;
        private ConfigEntry<string> endpoint;
        private float nextSend;
        private int sending;
        private GameMap gameMap;
        private static readonly BindingFlags Fields = BindingFlags.Instance | BindingFlags.NonPublic;

        private void Awake()
        {
            bridgeEnabled = Config.Bind("Bridge", "Enabled", false, "Opt in to sending position to the local tracker.");
            token = Config.Bind("Bridge", "Token", "", "Copy from the tracker's .live-bridge-token file. Keep private.");
            endpoint = Config.Bind("Bridge", "Endpoint", "http://127.0.0.1:7397/api/live-position", "Loopback tracker endpoint only.");
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
            var payload = new PositionMessage { scene = SceneManager.GetActiveScene().name, x = world.x, y = world.y };
            if (string.IsNullOrEmpty(payload.scene)) { Interlocked.Exchange(ref sending, 0); return; }
            Vector2 native;
            if (TryMapPosition(world, out native)) payload.map = new[] { native.x, native.y };
            var json = JsonUtility.ToJson(payload);
            var secret = token.Value;
            ThreadPool.QueueUserWorkItem(_ => Send(uri, secret, json));
        }

        private bool TryMapPosition(Vector3 world, out Vector2 native)
        {
            native = default(Vector2);
            try
            {
                if (gameMap == null)
                {
                    var maps = Resources.FindObjectsOfTypeAll<GameMap>();
                    foreach (var candidate in maps)
                        if (candidate != null && typeof(GameMap).GetField("currentScene", Fields)?.GetValue(candidate) != null)
                        { gameMap = candidate; break; }
                }
                if (gameMap == null) return false;
                var type = typeof(GameMap);
                var method = type.GetMethod("GetMapPosition", Fields);
                if (method == null) return false;
                var args = new object[] {
                    (Vector2)world,
                    type.GetField("currentScene", Fields)?.GetValue(gameMap),
                    type.GetField("currentSceneObj", Fields)?.GetValue(gameMap),
                    type.GetField("currentScenePos", Fields)?.GetValue(gameMap),
                    type.GetField("currentSceneSize", Fields)?.GetValue(gameMap)
                };
                if (args[1] == null || args[2] == null || args[3] == null || args[4] == null) return false;
                native = (Vector2)method.Invoke(gameMap, args);
                return !float.IsNaN(native.x) && !float.IsNaN(native.y) && !float.IsInfinity(native.x) && !float.IsInfinity(native.y);
            }
            catch { gameMap = null; return false; }
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

        [Serializable]
        private sealed class PositionMessage
        {
            public string scene;
            public float x;
            public float y;
            public float[] map;
        }
    }
}
