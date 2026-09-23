using System;
using System.Net;
using System.Threading;
using BepInEx;
using BepInEx.Configuration;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilksongLiveBridge
{
    [BepInPlugin("dev.silksongtracker.livebridge", "Silksong Tracker Live Bridge", "0.2.0")]
    public sealed class LiveBridge : BaseUnityPlugin
    {
        private ConfigEntry<bool> bridgeEnabled;
        private ConfigEntry<string> token;
        private ConfigEntry<string> endpoint;
        private float nextSend;
        private int sending;

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
            var json = JsonUtility.ToJson(payload);
            var secret = token.Value;
            ThreadPool.QueueUserWorkItem(_ => Send(uri, secret, json));
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
        }
    }
}
