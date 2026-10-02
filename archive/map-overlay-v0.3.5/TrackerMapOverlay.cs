using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using Newtonsoft.Json;
using UnityEngine;

namespace SilksongLiveBridge
{
    /// <summary>
    /// Read-only, in-game presentation of the local tracker's real map. It only
    /// appears over InventoryMapManager (the full menu map), never Quick Map.
    /// </summary>
    internal sealed class TrackerMapOverlay : MonoBehaviour
    {
        private const int MaxResponseBytes = 8 * 1024 * 1024;
        private const float RequestTimeout = 3f;
        private static readonly HashSet<string> DefaultHidden = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "permFlags", "rosary", "shard", "rosaryitem", "sharditem", "tradable", "memento",
            "silkeater", "npc", "wish", "questitem", "arena", "shortcut"
        };

        private static TrackerMapOverlay instance;
        private static readonly Regex SafeIconName = new Regex("^[A-Za-z0-9_.-]{1,100}$", RegexOptions.Compiled);

        private Uri trackerRoot;
        private ManualLogSource logger;
        private bool enabledOverlay;
        private KeyCode toggleKey = KeyCode.F8;
        private bool open;
        private bool mapFocus = true;
        private bool toolbarFocus;
        private int toolbarIndex;
        private bool onlyLeft;
        private bool useSketch = true;
        private bool dragging;
        private bool controllerCursorInitialized;
        private bool previousCursorVisible;
        private CursorLockMode previousCursorLock;
        private bool cursorStateCaptured;
        private bool searchFieldFocused;
        private bool hasLive;
        private string statusMessage = "Waiting for the local tracker…";
        private string search = "";
        private string selectedId = "";
        private float nextLivePoll;
        private float nextStatusRetry;
        private float nextMapRefresh;
        private float centreLat;
        private float centreLng;
        private float suppressInputUntil;
        private float ignoreMenuExtraUntil;
        private int controlIndex;
        private Vector2 layerScroll;
        private Vector2 controllerCursor;
        private Vector2 mapViewportSize;
        private Vector2 liveMap = new Vector2(float.NaN, float.NaN);
        private string liveScene = "";
        private string controllerHoverId = "";
        private Texture2D pixel;
        private MapData data;
        private readonly HashSet<string> visibleCategories = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> visibleShortcutFilters = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, string> shortcutFilterNames = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, Texture2D> textures = new Dictionary<string, Texture2D>(StringComparer.OrdinalIgnoreCase);
        private readonly Queue<string> tileTextureOrder = new Queue<string>();
        private readonly Queue<string> iconTextureOrder = new Queue<string>();
        private readonly Dictionary<string, DateTime> retryAfter = new Dictionary<string, DateTime>();
        private readonly HashSet<string> requestsInFlight = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, byte[]> pendingImages = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        private readonly object requestLock = new object();
        private byte[] pendingMapJson;
        private string pendingMapError;
        private bool pendingLiveFailed;
        private float lastManagerLookup;
        private InventoryMapManager mapManager;
        private InputHandler inputHandler;
        private float nextInputLookup;

        internal static bool IsOpen { get { return instance != null && instance.open; } }

        internal static void Attach(ManualLogSource log, string endpoint, bool isEnabled, string key)
        {
            var host = new GameObject("Silksong Tracker Map Overlay");
            DontDestroyOnLoad(host);
            instance = host.AddComponent<TrackerMapOverlay>();
            instance.logger = log;
            instance.enabledOverlay = isEnabled;
            instance.toggleKey = ParseKey(key);
            instance.SetEndpoint(endpoint);
            var harmony = new Harmony("dev.silksongtracker.livebridge.mapoverlay");
            harmony.PatchAll(Assembly.GetExecutingAssembly());
        }

        private static KeyCode ParseKey(string value)
        {
            KeyCode key;
            return Enum.TryParse(value, true, out key) ? key : KeyCode.F8;
        }

        private void SetEndpoint(string endpoint)
        {
            Uri parsed;
            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out parsed) || parsed.Scheme != Uri.UriSchemeHttp ||
                (parsed.Host != "127.0.0.1" && parsed.Host != "localhost" && parsed.Host != "[::1]"))
            {
                statusMessage = "Overlay needs a loopback tracker endpoint.";
                return;
            }
            trackerRoot = new UriBuilder(parsed.Scheme, parsed.Host, parsed.Port, "/").Uri;
        }

        internal static bool PaneUpdatePrefix()
        {
            var self = instance;
            if (self == null || !self.enabledOverlay) return true;
            if (Time.unscaledTime < self.suppressInputUntil) return false;
            if (self.open) return false;
            if (!self.IsFullMapVisible()) return true;
            if (Input.GetKeyDown(self.toggleKey) || self.WasPressed("MenuExtra"))
            {
                self.Open();
                return false; // consume the opening action before the game can use it.
            }
            return true;
        }

        internal static bool GameMapUpdatePrefix()
        {
            var self = instance;
            return self == null || (!self.open && Time.unscaledTime >= self.suppressInputUntil);
        }

        internal static bool MapMarkerMenuUpdatePrefix()
        {
            var self = instance;
            return self == null || (!self.open && Time.unscaledTime >= self.suppressInputUntil);
        }

        internal static bool InputHandlerUpdatePrefix()
        {
            var self = instance;
            // InputHandler owns global pause/game actions. Keep its action set alive
            // (InControl updates it separately), but do not let this Update route
            // those same presses into the game while our modal overlay is visible.
            return self == null || !self.enabledOverlay || (!self.open && Time.unscaledTime >= self.suppressInputUntil);
        }

        private bool IsFullMapVisible()
        {
            if (Time.unscaledTime >= lastManagerLookup)
            {
                lastManagerLookup = Time.unscaledTime + 0.35f;
                mapManager = FindAnyObjectByType<InventoryMapManager>();
            }
            return mapManager != null && mapManager.isActiveAndEnabled && mapManager.gameObject.activeInHierarchy;
        }

        private void Open()
        {
            if (!enabledOverlay || !IsFullMapVisible()) return;
            open = true;
            dragging = false;
            mapFocus = true;
            toolbarFocus = false;
            controllerCursorInitialized = false;
            controllerHoverId = "";
            ignoreMenuExtraUntil = Time.unscaledTime + 0.15f;
            previousCursorVisible = Cursor.visible;
            previousCursorLock = Cursor.lockState;
            cursorStateCaptured = true;
            Cursor.lockState = CursorLockMode.None;
            // The game has no mouse support. Use the overlay's controller reticle
            // instead of showing an OS cursor that cannot control the map.
            Cursor.visible = false;
            PlayCursorSound();
            if (data == null) RequestMap();
        }

        private void Close()
        {
            if (!open) return;
            open = false;
            dragging = false;
            // Discard the close-frame input too: held cancel/stick input must not
            // leak into the game's map or close the inventory beneath the panel.
            suppressInputUntil = Time.unscaledTime + 0.18f;
            if (cursorStateCaptured)
            {
                Cursor.lockState = previousCursorLock;
                Cursor.visible = previousCursorVisible;
                cursorStateCaptured = false;
            }
            PlayCursorSound();
        }

        private void PlayCursorSound()
        {
            try
            {
                var manager = mapManager != null ? mapManager : FindAnyObjectByType<InventoryMapManager>();
                var menu = manager != null ? manager.GetComponentInChildren<MapMarkerMenu>(true) : null;
                if (menu != null && menu.audioSource != null && menu.cursorClip != null)
                    menu.audioSource.PlayOneShot(menu.cursorClip);
            }
            catch { /* Sound is optional; never make the overlay depend on a menu prefab. */ }
        }

        private void Update()
        {
            if (!enabledOverlay) return;
            if (open && !IsFullMapVisible()) { Close(); return; }
            DrainAsyncResults();
            if (!open) return;

            if (Input.GetKeyDown(KeyCode.Escape) || WasPressed("MenuCancel")) { Close(); return; }
            if (Input.GetKeyDown(toggleKey) || Input.GetKeyDown(KeyCode.Tab) ||
                (Time.unscaledTime >= ignoreMenuExtraUntil && WasPressed("MenuExtra")))
            {
                CycleFocus();
            }
            if (!searchFieldFocused && Input.GetKeyDown(KeyCode.M)) ToggleStyle();
            if (!searchFieldFocused && (Input.GetKeyDown(KeyCode.Equals) || Input.GetKeyDown(KeyCode.KeypadPlus) || WasPressed("MenuSuper"))) Zoom(1);
            if (!searchFieldFocused && (Input.GetKeyDown(KeyCode.Minus) || Input.GetKeyDown(KeyCode.KeypadMinus))) Zoom(-1);
            if (!searchFieldFocused && Input.GetKeyDown(KeyCode.Home)) FitMap();

            if (data == null && (WasPressed("MenuSubmit") || Input.GetKeyDown(KeyCode.Return)))
            {
                RequestMap(force: true);
                PlayCursorSound();
            }
            else if (toolbarFocus)
            {
                if (WasPressed("Left") || WasPressed("Up") || Input.GetKeyDown(KeyCode.LeftArrow) || Input.GetKeyDown(KeyCode.UpArrow)) MoveToolbarControl(-1);
                if (WasPressed("Right") || WasPressed("Down") || Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.DownArrow)) MoveToolbarControl(1);
                if (WasPressed("MenuSubmit") || Input.GetKeyDown(KeyCode.Return)) ActivateToolbarControl();
            }
            else if (mapFocus)
            {
                var leftStick = GetActionVector("MoveVector");
                if (leftStick.sqrMagnitude > 0.025f) Pan(leftStick.x, leftStick.y, Time.unscaledDeltaTime * 620f / CurrentScale());
                var rightStick = GetActionVector("RightStick");
                if (controllerCursorInitialized && rightStick.sqrMagnitude > 0.04f)
                {
                    var cursorDelta = Vector2.ClampMagnitude(rightStick, 1f) * (Time.unscaledDeltaTime * 560f);
                    controllerCursor += new Vector2(cursorDelta.x, -cursorDelta.y);
                    controllerCursor.x = Mathf.Clamp(controllerCursor.x, 12f, Mathf.Max(12f, mapViewportSize.x - 12f));
                    controllerCursor.y = Mathf.Clamp(controllerCursor.y, 12f, Mathf.Max(12f, mapViewportSize.y - 12f));
                }
                if (WasPressed("Left")) Pan(-1, 0, 46f / CurrentScale());
                if (WasPressed("Right")) Pan(1, 0, 46f / CurrentScale());
                if (WasPressed("Up")) Pan(0, -1, 46f / CurrentScale());
                if (WasPressed("Down")) Pan(0, 1, 46f / CurrentScale());
                if (WasPressed("MenuSubmit")) SelectHoveredMarker();
                if (WasPressed("PaneRight")) Zoom(1);
                if (WasPressed("PaneLeft")) Zoom(-1);
            }
            else
            {
                if (WasPressed("Up") || Input.GetKeyDown(KeyCode.UpArrow)) MoveControl(-1);
                if (WasPressed("Down") || Input.GetKeyDown(KeyCode.DownArrow)) MoveControl(1);
                if (WasPressed("MenuSubmit")) ToggleControl();
                if (WasPressed("Left") || WasPressed("Right")) ToggleControl();
            }

            if (mapFocus && !searchFieldFocused)
            {
                var keyX = (Input.GetKey(KeyCode.RightArrow) ? 1f : 0f) - (Input.GetKey(KeyCode.LeftArrow) ? 1f : 0f);
                var keyY = (Input.GetKey(KeyCode.DownArrow) ? 1f : 0f) - (Input.GetKey(KeyCode.UpArrow) ? 1f : 0f);
                if (keyX != 0 || keyY != 0) Pan(keyX, keyY, Time.unscaledDeltaTime * 620f / CurrentScale());
            }

            if (data == null && Time.unscaledTime >= nextStatusRetry) RequestMap();
            else if (data != null && Time.unscaledTime >= nextMapRefresh) RequestMap(true);
            if (data != null && useSketch && Time.unscaledTime >= nextLivePoll)
            {
                nextLivePoll = Time.unscaledTime + 0.75f;
                RequestLivePosition();
            }
        }

        private void OnGUI()
        {
            if (!enabledOverlay || !IsFullMapVisible()) return;
            GUI.depth = -10000;
            EnsurePixel();
            if (!open)
            {
                var launch = new Rect(Screen.width - 225, 14, 210, 38);
                DrawPanel(launch, new Color(0.055f, 0.075f, 0.085f, 0.94f));
                if (GUI.Button(launch, "TRACKER MAP   ·   " + toggleKey, GUI.skin.button)) Open();
                return;
            }
            DrawOverlay();
        }

        private void DrawOverlay()
        {
            DrawPanel(new Rect(0, 0, Screen.width, Screen.height), new Color(0.025f, 0.035f, 0.04f, 0.96f));
            var title = "PHARLOOM  /  SILKSONG TRACKER";
            GUI.Label(new Rect(18, 12, Mathf.Min(470, Screen.width - 100), 27), title, HeaderStyle());
            var sub = data == null ? statusMessage : (data.hasSave ? "SAVE SLOT " + data.slot : "NO SAVE LOADED") + "  ·  " + statusMessage;
            GUI.Label(new Rect(20, 39, Mathf.Min(640, Screen.width - 120), 22), sub, MutedStyle());
            if (GUI.Button(new Rect(Screen.width - 118, 12, 100, 36), "CLOSE  Esc")) { Close(); return; }

            var layerWidth = Mathf.Clamp(Screen.width * 0.19f, 220f, 310f);
            var detailWidth = Screen.width >= 1180 ? Mathf.Clamp(Screen.width * 0.19f, 230f, 310f) : 0f;
            var panelY = 70f;
            var panelH = Mathf.Max(180f, Screen.height - 87f);
            var layerRect = new Rect(14, panelY, layerWidth, panelH);
            var mapRect = new Rect(layerRect.xMax + 10, panelY, Screen.width - layerWidth - detailWidth - 48, panelH);
            var detailRect = detailWidth > 0 ? new Rect(mapRect.xMax + 10, panelY, detailWidth, panelH) : new Rect(0, 0, 0, 0);
            DrawPanel(layerRect, new Color(0.07f, 0.09f, 0.10f, 0.98f));
            DrawPanel(mapRect, new Color(0.025f, 0.035f, 0.04f, 1f));
            if (detailWidth > 0) DrawPanel(detailRect, new Color(0.07f, 0.09f, 0.10f, 0.98f));

            DrawToolbar(mapRect);
            DrawLayers(layerRect);
            if (data == null)
            {
                GUI.Label(new Rect(mapRect.x + 22, mapRect.y + 70, mapRect.width - 44, 80),
                    "Start the Silksong Tracker. Map and tiles are read from its local data folder; nothing is downloaded by the mod.",
                    HeaderStyle());
                GUI.Label(new Rect(mapRect.x + 22, mapRect.y + 148, 430, 34),
                    "RETRY  ·  PRESS SUBMIT (XBOX A / PS ×)   ·   AUTO-RETRYING", FocusStyle());
            }
            else
            {
                DrawMap(mapRect);
                DrawDetail(detailRect);
            }
            GUI.Label(new Rect(20, Screen.height - 21, Screen.width - 40, 17),
                "F8 / Menu Extra: open · Tab / Menu Extra: focus · left stick: pan · right stick: cursor · D-pad: pan/navigate · Submit: inspect/activate · shoulders: zoom · Cancel: close",
                MutedStyle());
        }

        private void DrawToolbar(Rect mapRect)
        {
            var y = mapRect.y + 8;
            var x = mapRect.x + 8;
            var h = 31f;
            var styleName = useSketch ? "SKETCH MAP" : "SCREENSHOTS";
            if (GUI.Button(new Rect(x, y, 124, h), ToolbarLabel(0, styleName + "  ·  M"))) ToggleStyle();
            x += 128;
            if (GUI.Button(new Rect(x, y, 34, h), ToolbarLabel(1, "−"))) Zoom(-1);
            x += 37;
            if (GUI.Button(new Rect(x, y, 34, h), ToolbarLabel(2, "+"))) Zoom(1);
            x += 38;
            if (GUI.Button(new Rect(x, y, 78, h), ToolbarLabel(3, "Whole map"))) FitMap();
            x += 82;
            if (GUI.Button(new Rect(x, y, 93, h), ToolbarLabel(4, "Hornet"))) CenterOnHornet();
            x += 96;
            onlyLeft = GUI.Toggle(new Rect(x, y + 6, 105, 22), onlyLeft, ToolbarLabel(5, "Only left"));
            var focusText = mapFocus ? "FOCUS: MAP" : toolbarFocus ? "FOCUS: CONTROLS" : "FOCUS: LAYERS";
            GUI.Label(new Rect(mapRect.xMax - 160, y + 4, 152, 24), focusText, mapFocus ? MutedStyle() : FocusStyle());

            var searchRect = new Rect(mapRect.x + 8, y + h + 6, mapRect.width - 16, 27);
            GUI.SetNextControlName("tracker-map-search");
            search = GUI.TextField(searchRect, search ?? "");
            searchFieldFocused = GUI.GetNameOfFocusedControl() == "tracker-map-search";
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.Return && search.Length > 0)
            {
                FocusFirstSearchResult();
                Event.current.Use();
            }
        }

        private void DrawLayers(Rect rect)
        {
            GUI.Label(new Rect(rect.x + 10, rect.y + 8, rect.width - 20, 22), "MAP LAYERS", HeaderStyle());
            if (data == null) return;
            var layerFocus = !mapFocus && !toolbarFocus;
            if (GUI.Button(new Rect(rect.x + 10, rect.y + 35, 58, 25), (layerFocus && controlIndex == 0 ? "> " : "") + "All"))
            {
                foreach (var category in data.categories) visibleCategories.Add(category.id);
                foreach (var id in shortcutFilterNames.Keys) visibleShortcutFilters.Add(id);
            }
            if (GUI.Button(new Rect(rect.x + 73, rect.y + 35, 58, 25), (layerFocus && controlIndex == 1 ? "> " : "") + "None"))
            {
                visibleCategories.Clear(); visibleShortcutFilters.Clear();
            }
            if (GUI.Button(new Rect(rect.x + 136, rect.y + 35, 70, 25), (layerFocus && controlIndex == 2 ? "> " : "") + "Reset")) ResetLayers();
            var viewport = new Rect(rect.x + 7, rect.y + 68, rect.width - 14, rect.height - 76);
            var contentH = 0f;
            foreach (var group in data.groups)
            {
                contentH += 31;
                foreach (var category in data.categories)
                {
                    if (category.group != group.id) continue;
                    contentH += 25;
                    if (category.id == "shortcut") contentH += shortcutFilterNames.Count * 21;
                }
            }
            layerScroll = GUI.BeginScrollView(viewport, layerScroll, new Rect(0, 0, viewport.width - 18, Mathf.Max(viewport.height, contentH + 8)));
            float y = 4;
            var targetIndex = 3;
            foreach (var group in data.groups)
            {
                var members = Array.FindAll(data.categories, c => c.group == group.id);
                var total = 0;
                var active = 0;
                foreach (var c in members)
                {
                    if (c.id == "shortcut") { total += shortcutFilterNames.Count; active += visibleShortcutFilters.Count; }
                    else { total++; if (visibleCategories.Contains(c.id)) active++; }
                }
                var marker = active == 0 ? "[ ]" : active == total ? "[x]" : "[-]";
                var groupSelected = layerFocus && controlIndex == targetIndex;
                if (GUI.Button(new Rect(4, y, viewport.width - 28, 27), (groupSelected ? "> " : "  ") + marker + "  " + group.name, active > 0 ? GroupStyle() : MutedButtonStyle()))
                {
                    var show = active < total;
                    foreach (var c in members)
                    {
                        if (c.id == "shortcut")
                        {
                            foreach (var id in shortcutFilterNames.Keys) if (show) visibleShortcutFilters.Add(id); else visibleShortcutFilters.Remove(id);
                        }
                        else if (show) visibleCategories.Add(c.id); else visibleCategories.Remove(c.id);
                    }
                }
                targetIndex++;
                y += 30;
                foreach (var category in members)
                {
                    var enabled = category.id == "shortcut" ? visibleShortcutFilters.Count > 0 : visibleCategories.Contains(category.id);
                    var count = category.id == "shortcut" ? shortcutFilterNames.Count : CountCategory(category.id);
                    var categorySelected = layerFocus && controlIndex == targetIndex;
                    if (GUI.Button(new Rect(13, y, viewport.width - 40, 23), (categorySelected ? "> " : "  ") + (enabled ? "[x] " : "[ ] ") + category.name + "  ·  " + count,
                        enabled ? LayerStyle() : MutedButtonStyle()))
                    {
                        if (category.id == "shortcut")
                        {
                            var show = visibleShortcutFilters.Count != shortcutFilterNames.Count;
                            foreach (var id in shortcutFilterNames.Keys) if (show) visibleShortcutFilters.Add(id); else visibleShortcutFilters.Remove(id);
                        }
                        else if (!visibleCategories.Remove(category.id)) visibleCategories.Add(category.id);
                    }
                    targetIndex++;
                    y += 24;
                    if (category.id == "shortcut")
                    {
                        foreach (var filter in OrderedShortcutFilters())
                        {
                            var on = visibleShortcutFilters.Contains(filter.Key);
                            var filterSelected = layerFocus && controlIndex == targetIndex;
                            if (GUI.Button(new Rect(26, y, viewport.width - 54, 20), (filterSelected ? "> " : "  ") + (on ? "[x] " : "[ ] ") + filter.Value,
                                on ? LayerStyle() : MutedButtonStyle()))
                            {
                                if (!visibleShortcutFilters.Remove(filter.Key)) visibleShortcutFilters.Add(filter.Key);
                            }
                            targetIndex++;
                            y += 21;
                        }
                    }
                }
            }
            GUI.EndScrollView();
        }

        private void DrawMap(Rect rect)
        {
            var viewportRect = new Rect(rect.x + 6, rect.y + 75, rect.width - 12, rect.height - 83);
            GUI.BeginGroup(viewportRect);
            var mapRect = new Rect(0, 0, viewportRect.width, viewportRect.height);
            mapViewportSize = mapRect.size;
            if (!controllerCursorInitialized)
            {
                controllerCursor = mapRect.center;
                controllerCursorInitialized = true;
            }
            var spec = CurrentStyle();
            if (spec == null) { GUI.EndGroup(); return; }
            var e = Event.current;
            if (e.type == EventType.ScrollWheel && mapRect.Contains(e.mousePosition))
            {
                Zoom(e.delta.y < 0 ? 1 : -1); e.Use();
            }
            var fit = Mathf.Min(mapRect.width / Mathf.Max(1f, spec.maxLng - spec.minLng), mapRect.height / Mathf.Max(1f, spec.maxLat - spec.minLat));
            var zoomScale = Mathf.Pow(2f, CurrentZoom());
            var scale = fit * zoomScale;
            var topPx = centreLng * zoomScale;
            var topPy = -centreLat * zoomScale;
            var worldWidth = Mathf.CeilToInt((spec.maxLng - spec.minLng) * zoomScale / spec.tileSize);
            var worldHeight = Mathf.CeilToInt((spec.maxLat - spec.minLat) * zoomScale / spec.tileSize);
            var leftPx = topPx + (mapRect.xMin - mapRect.center.x) / fit;
            var rightPx = topPx + (mapRect.xMax - mapRect.center.x) / fit;
            var topY = topPy + (mapRect.yMin - mapRect.center.y) / fit;
            var bottomY = topPy + (mapRect.yMax - mapRect.center.y) / fit;
            int minX = Mathf.Clamp(Mathf.FloorToInt(leftPx / spec.tileSize), 0, worldWidth - 1);
            int maxX = Mathf.Clamp(Mathf.FloorToInt(rightPx / spec.tileSize), 0, worldWidth - 1);
            int minY = Mathf.Clamp(Mathf.FloorToInt(topY / spec.tileSize), 0, worldHeight - 1);
            int maxY = Mathf.Clamp(Mathf.FloorToInt(bottomY / spec.tileSize), 0, worldHeight - 1);
            var mapStyle = useSketch ? "sketch" : "screenshots";
            for (int ty = minY; ty <= maxY; ty++)
            for (int tx = minX; tx <= maxX; tx++)
            {
                var key = CurrentZoom() + "/" + tx + "_" + ty;
                if (!spec.valid.Contains(key)) continue;
                var cacheKey = "tile:" + mapStyle + ":" + key;
                Texture2D tile;
                if (!textures.TryGetValue(cacheKey, out tile)) { RequestImage(cacheKey, "/api/game-map-tile?style=" + mapStyle + "&z=" + CurrentZoom() + "&x=" + tx + "&y=" + ty, 4 * 1024 * 1024); continue; }
                var x = mapRect.center.x + (tx * spec.tileSize - topPx) * fit;
                var y = mapRect.center.y + (ty * spec.tileSize - topPy) * fit;
                var tileRect = new Rect(x, y, spec.tileSize * fit, spec.tileSize * fit);
                GUI.DrawTexture(tileRect, tile, ScaleMode.StretchToFill, false);
            }

            DrawMapLabels(mapRect, spec, fit, zoomScale);
            controllerHoverId = "";
            var hoverDistance = 38f * 38f;
            MapMarker hoverMarker = null;
            Vector2 hoverPosition = Vector2.zero;
            foreach (var marker in data.markers)
            {
                var pos = Position(marker);
                if (pos == null || !MarkerVisible(marker)) continue;
                var x = mapRect.center.x + (pos[1] * zoomScale - topPx) * fit;
                var y = mapRect.center.y + (-pos[0] * zoomScale - topPy) * fit;
                if (x < mapRect.xMin - 20 || x > mapRect.xMax + 20 || y < mapRect.yMin - 20 || y > mapRect.yMax + 20) continue;
                DrawMarker(marker, x, y);
                if (controllerCursorInitialized)
                {
                    var dx = x - controllerCursor.x;
                    var dy = y - controllerCursor.y;
                    var dist = dx * dx + dy * dy;
                    if (dist < hoverDistance) { hoverDistance = dist; hoverMarker = marker; hoverPosition = new Vector2(x, y); }
                }
            }
            if (hoverMarker != null)
            {
                controllerHoverId = hoverMarker.id;
                var markerSize = CurrentZoom() >= 2 ? 25f : 20f;
                DrawOutline(new Rect(hoverPosition.x - markerSize / 2 - 3, hoverPosition.y - markerSize / 2 - 3,
                    markerSize + 6, markerSize + 6), new Color(0.45f, 0.96f, 1f, 1f), 2f);
                GUI.Label(new Rect(controllerCursor.x + 15, controllerCursor.y - 18, 230, 28), hoverMarker.name, FocusStyle());
            }
            if (mapFocus) DrawControllerCursor(mapRect);
            if (useSketch && hasLive && !float.IsNaN(liveMap.x))
            {
                Texture2D hornetIcon;
                if (!textures.TryGetValue("hornet-head", out hornetIcon)) RequestImage("hornet-head", "/hornet-head-source.png", 2 * 1024 * 1024);
                var lx = mapRect.center.x + (liveMap.y * zoomScale - topPx) * fit;
                var ly = mapRect.center.y + (-liveMap.x * zoomScale - topPy) * fit;
                if (mapRect.Contains(new Vector2(lx, ly)))
                {
                    if (textures.TryGetValue("hornet-head", out hornetIcon))
                    {
                        var old = GUI.color;
                        GUI.color = new Color(0.48f, 1f, 0.78f, 1f);
                        GUI.DrawTexture(new Rect(lx - 15, ly - 40, 30, 40), hornetIcon, ScaleMode.ScaleToFit, true);
                        GUI.color = old;
                    }
                    else DrawPanel(new Rect(lx - 6, ly - 6, 12, 12), new Color(0.2f, 1f, 0.7f, 1f));
                    GUI.Label(new Rect(lx + 10, ly - 12, 140, 22), "HORNET  ·  " + liveScene, FocusStyle());
                }
            }
            HandleMapMouse(mapRect, fit, zoomScale);
            var viewName = useSketch ? "Sketch" : "Screenshots";
            GUI.Label(new Rect(mapRect.x + 7, mapRect.yMax - 24, 180, 20), viewName + "  ·  zoom " + CurrentZoom() + "/" + spec.maxZoom, MutedStyle());
            GUI.EndGroup();
        }

        private void DrawMapLabels(Rect mapRect, MapStyle spec, float fit, float zoomScale)
        {
            if (CurrentZoom() < 1 || data.labels == null || useSketch) return;
            int count = 0;
            foreach (var label in data.labels)
            {
                if (label.pos == null || label.pos.Length != 2 || count > 36) continue;
                var x = mapRect.center.x + (label.pos[1] * zoomScale - centreLng * zoomScale) * fit;
                var y = mapRect.center.y + (-label.pos[0] * zoomScale + centreLat * zoomScale) * fit;
                if (mapRect.Contains(new Vector2(x, y))) { GUI.Label(new Rect(x - 65, y - 10, 130, 20), label.name, MutedStyle()); count++; }
            }
        }

        private void DrawMarker(MapMarker marker, float x, float y)
        {
            var size = CurrentZoom() >= 2 ? 25f : 20f;
            var key = "icon:" + marker.icon;
            Texture2D icon;
            if (!textures.TryGetValue(key, out icon))
            {
                if (SafeIconName.IsMatch(marker.icon ?? "")) RequestImage(key, "/map/icons/" + Uri.EscapeDataString(marker.icon), 1024 * 1024);
            }
            var rect = new Rect(x - size / 2, y - size / 2, size, size);
            var old = GUI.color;
            if (marker.status == "complete") GUI.color = new Color(1, 1, 1, 0.42f);
            if (icon != null) GUI.DrawTexture(rect, icon, ScaleMode.ScaleToFit, true);
            else
            {
                DrawPanel(rect, marker.id == selectedId ? new Color(0.55f, 0.93f, 0.79f, 1) : new Color(0.92f, 0.76f, 0.49f, 0.95f));
                GUI.Label(rect, "•", HeaderStyle());
            }
            GUI.color = old;
            if (marker.id == selectedId)
            {
                DrawOutline(rect, new Color(0.60f, 1f, 0.85f, 1f), 2f);
                if (mapRectContainsMouse(rect)) GUI.Label(new Rect(x + size / 2 + 3, y - 14, 190, 22), marker.name, FocusStyle());
            }
            var e = Event.current;
            if (e.type == EventType.MouseDown && e.button == 0 && rect.Contains(e.mousePosition))
            {
                selectedId = marker.id;
                mapFocus = true;
                dragging = false;
                e.Use();
            }
        }

        private bool mapRectContainsMouse(Rect markerRect) { return markerRect.Contains(Event.current.mousePosition); }

        private void HandleMapMouse(Rect mapRect, float fit, float zoomScale)
        {
            var e = Event.current;
            if (e.type == EventType.MouseDown && e.button == 0 && mapRect.Contains(e.mousePosition))
            {
                dragging = true; mapFocus = true; GUI.FocusControl(""); e.Use();
            }
            else if (e.type == EventType.MouseDrag && dragging)
            {
                centreLng -= e.delta.x / Mathf.Max(0.001f, fit * zoomScale);
                centreLat += e.delta.y / Mathf.Max(0.001f, fit * zoomScale);
                e.Use();
            }
            else if (e.type == EventType.MouseUp && dragging) { dragging = false; e.Use(); }
        }

        private void DrawDetail(Rect rect)
        {
            if (rect.width <= 0 || data == null) return;
            var marker = FindMarker(selectedId);
            GUI.Label(new Rect(rect.x + 12, rect.y + 10, rect.width - 24, 25), "LOCATION", HeaderStyle());
            if (marker == null)
            {
                GUI.Label(new Rect(rect.x + 12, rect.y + 40, rect.width - 24, 60), "Click a map pin, search, or place the map center on a pin and press Submit.", MutedStyle());
                return;
            }
            var cat = FindCategory(marker.cat);
            var icon = TextureForIcon(marker.icon);
            if (icon != null) GUI.DrawTexture(new Rect(rect.x + 13, rect.y + 42, 44, 44), icon, ScaleMode.ScaleToFit, true);
            GUI.Label(new Rect(rect.x + 62, rect.y + 40, rect.width - 72, 50), marker.name, HeaderStyle());
            GUI.Label(new Rect(rect.x + 14, rect.y + 92, rect.width - 28, 34), cat == null ? marker.cat : cat.name, MutedStyle());
            GUI.Label(new Rect(rect.x + 14, rect.y + 125, rect.width - 28, 28), "SAVE STATUS: " + (marker.status ?? "unknown").ToUpperInvariant(),
                marker.status == "complete" ? FocusStyle() : MutedStyle());
            GUI.Label(new Rect(rect.x + 14, rect.y + 155, rect.width - 28, rect.height - 230), marker.trackingNote ?? "", MutedStyle());
            if (GUI.Button(new Rect(rect.x + 12, rect.yMax - 62, rect.width - 24, 31), "Center on selected pin")) CenterOn(marker);
            if (GUI.Button(new Rect(rect.x + 12, rect.yMax - 27, rect.width - 24, 25), "Focus map  ·  Tab")) mapFocus = true;
        }

        private Texture2D TextureForIcon(string filename)
        {
            if (!SafeIconName.IsMatch(filename ?? "")) return null;
            var key = "icon:" + filename;
            Texture2D texture;
            if (!textures.TryGetValue(key, out texture)) RequestImage(key, "/map/icons/" + Uri.EscapeDataString(filename), 1024 * 1024);
            return textures.TryGetValue(key, out texture) ? texture : null;
        }

        private void RequestMap(bool refresh = false, bool force = false)
        {
            if (trackerRoot == null || (!force && Time.unscaledTime < nextStatusRetry) || (data != null && !refresh)) return;
            nextStatusRetry = Time.unscaledTime + 2f;
            lock (requestLock) { if (requestsInFlight.Contains("map")) return; requestsInFlight.Add("map"); }
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try { var bytes = GetBytes("/api/game-map", MaxResponseBytes); lock (requestLock) pendingMapJson = bytes; }
                catch (Exception ex) { lock (requestLock) pendingMapError = "Tracker not connected · " + ex.GetType().Name; }
                finally { lock (requestLock) requestsInFlight.Remove("map"); }
            });
        }

        private void RequestLivePosition()
        {
            if (trackerRoot == null) return;
            lock (requestLock) { if (requestsInFlight.Contains("live")) return; requestsInFlight.Add("live"); }
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try { var bytes = GetBytes("/api/live-position", 32 * 1024); lock (requestLock) pendingImages["live-json"] = bytes; }
                catch { lock (requestLock) pendingLiveFailed = true; }
                finally { lock (requestLock) requestsInFlight.Remove("live"); }
            });
        }

        private void RequestImage(string key, string path, int maxBytes)
        {
            if (trackerRoot == null) return;
            lock (requestLock)
            {
                if (requestsInFlight.Contains(key) || textures.ContainsKey(key)) return;
                DateTime next;
                if (retryAfter.TryGetValue(key, out next) && next > DateTime.UtcNow) return;
                requestsInFlight.Add(key);
            }
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    var bytes = GetBytes(path, maxBytes);
                    lock (requestLock) pendingImages[key] = bytes;
                }
                catch
                {
                    lock (requestLock) retryAfter[key] = DateTime.UtcNow.AddSeconds(6);
                }
                finally { lock (requestLock) requestsInFlight.Remove(key); }
            });
        }

        private byte[] GetBytes(string relativePath, int limit)
        {
            var request = (HttpWebRequest)WebRequest.Create(new Uri(trackerRoot, relativePath));
            request.Method = "GET";
            request.Timeout = (int)(RequestTimeout * 1000f);
            request.ReadWriteTimeout = (int)(RequestTimeout * 1000f);
            request.Proxy = null;
            using (var response = (HttpWebResponse)request.GetResponse())
            using (var stream = response.GetResponseStream())
            using (var memory = new MemoryStream())
            {
                if (response.StatusCode != HttpStatusCode.OK) throw new IOException("tracker returned " + response.StatusCode);
                var buffer = new byte[8192];
                int total = 0, read;
                while ((read = stream.Read(buffer, 0, buffer.Length)) > 0)
                {
                    total += read;
                    if (total > limit) throw new IOException("tracker response exceeded limit");
                    memory.Write(buffer, 0, read);
                }
                return memory.ToArray();
            }
        }

        private void DrainAsyncResults()
        {
            byte[] json = null;
            string error = null;
            Dictionary<string, byte[]> images = null;
            bool liveFailed = false;
            lock (requestLock)
            {
                if (pendingMapJson != null) { json = pendingMapJson; pendingMapJson = null; }
                if (pendingMapError != null) { error = pendingMapError; pendingMapError = null; }
                liveFailed = pendingLiveFailed; pendingLiveFailed = false;
                if (pendingImages.Count > 0) { images = new Dictionary<string, byte[]>(pendingImages); pendingImages.Clear(); }
            }
            if (liveFailed) { hasLive = false; statusMessage = "Live position unavailable"; }
            if (error != null) statusMessage = error;
            if (json != null)
            {
                try
                {
                    var firstLoad = data == null;
                    data = JsonConvert.DeserializeObject<MapData>(Encoding.UTF8.GetString(json));
                    if (data == null) throw new InvalidDataException("response was not a JSON object");
                    var missing = new List<string>();
                    if (data.groups == null) missing.Add("groups");
                    if (data.categories == null) missing.Add("categories");
                    if (data.markers == null) missing.Add("markers");
                    if (data.screenshots == null) missing.Add("screenshots");
                    if (data.sketch == null) missing.Add("sketch");
                    if (missing.Count > 0) throw new InvalidDataException("missing " + string.Join(", ", missing.ToArray()));
                    data.screenshots.valid = new HashSet<string>(data.screenshots.validTiles ?? new string[0], StringComparer.Ordinal);
                    data.sketch.valid = new HashSet<string>(data.sketch.validTiles ?? new string[0], StringComparer.Ordinal);
                    if (firstLoad) InitializeLayers();
                    else if (FindMarker(selectedId) == null) selectedId = "";
                    statusMessage = "Map ready · " + data.markers.Length + " locations";
                    if (firstLoad)
                    {
                        FitMap();
                        if (logger != null) logger.LogInfo("Loaded local tracker map for in-game overlay (" + data.markers.Length + " pins).");
                    }
                    nextMapRefresh = Time.unscaledTime + 5f;
                }
                catch (Exception ex)
                {
                    data = null;
                    statusMessage = "Map read error · " + ex.GetType().Name + ": " + ex.Message;
                    if (logger != null) logger.LogError("Could not read tracker map response: " + ex);
                }
            }
            if (images == null) return;
            foreach (var pair in images)
            {
                if (pair.Key == "live-json")
                {
                    try
                    {
                        var live = JsonConvert.DeserializeObject<LiveMessage>(Encoding.UTF8.GetString(pair.Value));
                        hasLive = live != null && live.connected && live.position != null && live.position.map != null && live.position.map.Length == 2;
                        if (hasLive) { liveScene = live.position.scene; liveMap = new Vector2(live.position.map[0], live.position.map[1]); statusMessage = "Live · " + liveScene; }
                        else if (statusMessage.StartsWith("Live ·", StringComparison.Ordinal)) statusMessage = "Map ready · " + data.markers.Length + " locations";
                    }
                    catch { hasLive = false; }
                    continue;
                }
                try
                {
                    var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                    var hornet = pair.Key == "hornet-head";
                    if (!ImageConversion.LoadImage(texture, pair.Value, !hornet)) { Destroy(texture); continue; }
                    if (hornet) MakeWhiteTransparent(texture);
                    texture.name = pair.Key;
                    texture.filterMode = pair.Key.StartsWith("tile:", StringComparison.Ordinal) ? FilterMode.Bilinear : FilterMode.Bilinear;
                    texture.wrapMode = TextureWrapMode.Clamp;
                    Texture2D previous;
                    if (textures.TryGetValue(pair.Key, out previous)) Destroy(previous);
                    textures[pair.Key] = texture;
                    if (pair.Key.StartsWith("tile:", StringComparison.Ordinal)) tileTextureOrder.Enqueue(pair.Key);
                    else if (pair.Key.StartsWith("icon:", StringComparison.Ordinal) || hornet) iconTextureOrder.Enqueue(pair.Key);
                    TrimTextures(tileTextureOrder, 26);
                    TrimTextures(iconTextureOrder, 128);
                }
                catch { lock (requestLock) retryAfter[pair.Key] = DateTime.UtcNow.AddSeconds(10); }
            }
        }

        private void TrimTextures(Queue<string> order, int max)
        {
            while (order.Count > max)
            {
                var key = order.Dequeue();
                Texture2D texture;
                if (textures.TryGetValue(key, out texture)) { textures.Remove(key); Destroy(texture); }
            }
        }

        private void MakeWhiteTransparent(Texture2D texture)
        {
            var pixels = texture.GetPixels32();
            for (int i = 0; i < pixels.Length; i++)
            {
                var pixel = pixels[i];
                var luminance = (pixel.r * 299 + pixel.g * 587 + pixel.b * 114) / 1000;
                pixel.a = (byte)(pixel.a * (255 - luminance) / 255);
                pixel.r = 255; pixel.g = 255; pixel.b = 255;
                pixels[i] = pixel;
            }
            texture.SetPixels32(pixels);
            texture.Apply(false, true);
        }

        private void InitializeLayers()
        {
            visibleCategories.Clear(); visibleShortcutFilters.Clear(); shortcutFilterNames.Clear();
            if (data == null) return;
            foreach (var group in data.groups)
                foreach (var category in data.categories)
                    if (category.group == group.id && group.visible && !DefaultHidden.Contains(category.id)) visibleCategories.Add(category.id);
            foreach (var marker in data.markers)
            {
                if (marker.cat != "shortcut") continue;
                var label = ShortcutFilterLabel(marker.name);
                shortcutFilterNames[FilterId(label)] = label;
            }
        }

        private void ResetLayers()
        {
            InitializeLayers();
        }

        private string ShortcutFilterLabel(string name)
        {
            if (name.StartsWith("Requires ", StringComparison.Ordinal)) return name;
            if (name.StartsWith("One-Way Shortcut - ", StringComparison.Ordinal)) return "One-way arrows · " + name.Substring("One-Way Shortcut - ".Length);
            if (name.StartsWith("Intersection - ", StringComparison.Ordinal)) return "Intersections";
            if (name.StartsWith("Requirement Unknown", StringComparison.Ordinal)) return "Unknown requirements";
            if (name.StartsWith("Unlocked ", StringComparison.Ordinal)) return "Unlocked route notes";
            return "Other route notes";
        }

        private string FilterId(string label) { return "shortcut-filter:" + Regex.Replace(label.ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-'); }

        private List<KeyValuePair<string, string>> OrderedShortcutFilters()
        {
            var result = new List<KeyValuePair<string, string>>(shortcutFilterNames);
            result.Sort((a, b) =>
            {
                int Family(string v) => v.StartsWith("Requires ", StringComparison.Ordinal) ? 0 : v.StartsWith("One-way arrows", StringComparison.Ordinal) ? 1 : 2;
                var compare = Family(a.Value).CompareTo(Family(b.Value));
                return compare != 0 ? compare : StringComparer.OrdinalIgnoreCase.Compare(a.Value, b.Value);
            });
            return result;
        }

        private bool MarkerVisible(MapMarker marker)
        {
            if (marker.id == selectedId) return true;
            if (!string.IsNullOrWhiteSpace(search) && (marker.name.IndexOf(search, StringComparison.OrdinalIgnoreCase) >= 0 || CategoryName(marker.cat).IndexOf(search, StringComparison.OrdinalIgnoreCase) >= 0)) { }
            else
            {
                if (marker.cat != "shortcut" && !visibleCategories.Contains(marker.cat)) return false;
                if (marker.cat == "shortcut" && !visibleShortcutFilters.Contains(FilterId(ShortcutFilterLabel(marker.name)))) return false;
            }
            return !onlyLeft || marker.status == "left";
        }

        private void DrawPanel(Rect rect, Color color)
        {
            EnsurePixel();
            var old = GUI.color;
            GUI.color = color;
            GUI.DrawTexture(rect, pixel, ScaleMode.StretchToFill, true);
            GUI.color = old;
        }

        private void DrawOutline(Rect rect, Color color, float width)
        {
            var old = GUI.color; GUI.color = color;
            GUI.DrawTexture(new Rect(rect.xMin, rect.yMin, rect.width, width), pixel);
            GUI.DrawTexture(new Rect(rect.xMin, rect.yMax - width, rect.width, width), pixel);
            GUI.DrawTexture(new Rect(rect.xMin, rect.yMin, width, rect.height), pixel);
            GUI.DrawTexture(new Rect(rect.xMax - width, rect.yMin, width, rect.height), pixel);
            GUI.color = old;
        }

        private void EnsurePixel()
        {
            if (pixel != null) return;
            pixel = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            pixel.SetPixel(0, 0, Color.white); pixel.Apply(false, true);
        }

        private GUIStyle HeaderStyle()
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = 17, fontStyle = FontStyle.Bold, wordWrap = true, alignment = TextAnchor.MiddleLeft };
            style.normal.textColor = new Color(0.91f, 0.94f, 0.92f); return style;
        }

        private GUIStyle MutedStyle()
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = 11, wordWrap = true, alignment = TextAnchor.MiddleLeft };
            style.normal.textColor = new Color(0.63f, 0.69f, 0.69f); return style;
        }

        private GUIStyle FocusStyle()
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = 12, fontStyle = FontStyle.Bold, wordWrap = true };
            style.normal.textColor = new Color(0.59f, 0.93f, 0.78f); return style;
        }

        private GUIStyle GroupStyle()
        {
            var style = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleLeft, fontStyle = FontStyle.Bold, fontSize = 12 };
            style.normal.textColor = new Color(0.9f, 0.92f, 0.91f); return style;
        }

        private GUIStyle LayerStyle()
        {
            var style = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleLeft, fontSize = 11, clipping = TextClipping.Clip };
            style.normal.textColor = new Color(0.79f, 0.86f, 0.83f); return style;
        }

        private GUIStyle MutedButtonStyle()
        {
            var style = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleLeft, fontSize = 11, clipping = TextClipping.Clip };
            style.normal.textColor = new Color(0.55f, 0.60f, 0.61f); return style;
        }

        private int CurrentZoom()
        {
            var max = CurrentStyle() == null ? 0 : CurrentStyle().maxZoom;
            return Mathf.Clamp(currentZoom, 0, max);
        }

        private int currentZoom;

        private float CurrentScale()
        {
            var spec = CurrentStyle();
            return spec == null ? 1f : Mathf.Min((Screen.width * 0.62f) / Mathf.Max(1f, spec.maxLng - spec.minLng),
                (Screen.height * 0.8f) / Mathf.Max(1f, spec.maxLat - spec.minLat)) * Mathf.Pow(2f, CurrentZoom());
        }

        private MapStyle CurrentStyle() { return data == null ? null : (useSketch ? data.sketch : data.screenshots); }

        private float[] Position(MapMarker marker)
        {
            var pos = useSketch ? marker.pos2 : marker.pos;
            return pos != null && pos.Length == 2 && !float.IsNaN(pos[0]) && !float.IsNaN(pos[1]) &&
                   !float.IsInfinity(pos[0]) && !float.IsInfinity(pos[1]) ? pos : null;
        }

        private void ToggleStyle()
        {
            useSketch = !useSketch;
            currentZoom = Mathf.Min(currentZoom, CurrentStyle() == null ? 0 : CurrentStyle().maxZoom);
            var selected = FindMarker(selectedId);
            var position = selected == null ? null : Position(selected);
            if (position != null) { centreLat = position[0]; centreLng = position[1]; }
            else if (useSketch && hasLive) { centreLat = liveMap.x; centreLng = liveMap.y; }
            else FitMap();
            PlayCursorSound();
        }

        private void Zoom(int amount)
        {
            var spec = CurrentStyle(); if (spec == null) return;
            currentZoom = Mathf.Clamp(currentZoom + amount, 0, spec.maxZoom);
            PlayCursorSound();
        }

        private void FitMap()
        {
            var spec = CurrentStyle(); if (spec == null) { centreLat = 0; centreLng = 0; return; }
            currentZoom = 0;
            centreLat = (spec.minLat + spec.maxLat) * 0.5f;
            centreLng = (spec.minLng + spec.maxLng) * 0.5f;
        }

        private void CenterOnHornet()
        {
            if (hasLive && useSketch)
            {
                centreLat = liveMap.x; centreLng = liveMap.y;
                currentZoom = Mathf.Min(Mathf.Max(currentZoom, 1), CurrentStyle().maxZoom);
            }
            else statusMessage = "Hornet position is available on Sketch when the optional bridge is connected.";
        }

        private void Pan(float x, float y, float amount)
        {
            var spec = CurrentStyle(); if (spec == null) return;
            centreLng += x * amount;
            centreLat += y * amount;
        }

        private void HandleMapMouseUnused() { }

        private void SelectHoveredMarker()
        {
            if (data == null) return;
            if (controllerHoverId.Length == 0)
            {
                statusMessage = "Move the right stick over a pin, then press Submit to inspect it.";
                return;
            }
            selectedId = controllerHoverId;
            PlayCursorSound();
        }

        private void DrawControllerCursor(Rect mapRect)
        {
            if (!controllerCursorInitialized || !mapRect.Contains(controllerCursor)) return;
            var x = controllerCursor.x;
            var y = controllerCursor.y;
            var shadow = new Color(0.015f, 0.025f, 0.03f, 0.95f);
            var accent = new Color(0.54f, 1f, 0.88f, 1f);
            DrawOutline(new Rect(x - 10, y - 10, 20, 20), shadow, 4f);
            DrawPanel(new Rect(x - 1, y - 13, 2, 26), shadow);
            DrawPanel(new Rect(x - 13, y - 1, 26, 2), shadow);
            DrawOutline(new Rect(x - 8, y - 8, 16, 16), accent, 2f);
            DrawPanel(new Rect(x - 1, y - 11, 2, 22), accent);
            DrawPanel(new Rect(x - 11, y - 1, 22, 2), accent);
            DrawPanel(new Rect(x - 2, y - 2, 4, 4), Color.white);
        }

        private void FocusFirstSearchResult()
        {
            if (data == null || string.IsNullOrWhiteSpace(search)) return;
            foreach (var marker in data.markers)
            {
                if (marker.name.IndexOf(search, StringComparison.OrdinalIgnoreCase) >= 0 || CategoryName(marker.cat).IndexOf(search, StringComparison.OrdinalIgnoreCase) >= 0)
                { selectedId = marker.id; CenterOn(marker); currentZoom = Mathf.Max(1, currentZoom); return; }
            }
            statusMessage = "No location matches “" + search + "”.";
        }

        private void CenterOn(MapMarker marker)
        {
            var pos = Position(marker);
            if (pos == null) { if (useSketch) statusMessage = "This location has no Sketch coordinate; switch to Screenshots."; return; }
            centreLat = pos[0]; centreLng = pos[1]; currentZoom = Mathf.Max(currentZoom, 1);
        }

        private void MoveControl(int delta)
        {
            var keys = ControlKeys();
            if (keys.Count == 0) return;
            controlIndex = (controlIndex + delta + keys.Count) % keys.Count;
            KeepLayerSelectionVisible();
            PlayCursorSound();
        }

        private void CycleFocus()
        {
            if (mapFocus)
            {
                mapFocus = false;
                toolbarFocus = false;
                KeepLayerSelectionVisible();
            }
            else if (!toolbarFocus) toolbarFocus = true;
            else { mapFocus = true; toolbarFocus = false; }
            PlayCursorSound();
        }

        private string ToolbarLabel(int index, string text)
        {
            return toolbarFocus && toolbarIndex == index ? "> " + text : text;
        }

        private void MoveToolbarControl(int delta)
        {
            toolbarIndex = (toolbarIndex + delta + 6) % 6;
            PlayCursorSound();
        }

        private void ActivateToolbarControl()
        {
            switch (toolbarIndex)
            {
                case 0: ToggleStyle(); break;
                case 1: Zoom(-1); break;
                case 2: Zoom(1); break;
                case 3: FitMap(); break;
                case 4: CenterOnHornet(); break;
                case 5: onlyLeft = !onlyLeft; break;
            }
            PlayCursorSound();
        }

        private void ToggleControl()
        {
            if (data == null) return;
            var keys = ControlKeys();
            if (keys.Count == 0) return;
            var key = keys[controlIndex % keys.Count];
            if (key == "layer:all")
            {
                foreach (var category in data.categories) visibleCategories.Add(category.id);
                foreach (var id in shortcutFilterNames.Keys) visibleShortcutFilters.Add(id);
            }
            else if (key == "layer:none") { visibleCategories.Clear(); visibleShortcutFilters.Clear(); }
            else if (key == "layer:reset") ResetLayers();
            else if (key.StartsWith("filter:", StringComparison.Ordinal))
            {
                var id = key.Substring("filter:".Length);
                if (!visibleShortcutFilters.Remove(id)) visibleShortcutFilters.Add(id);
            }
            else if (key.StartsWith("group:", StringComparison.Ordinal))
            {
                var groupId = key.Substring("group:".Length);
                var members = Array.FindAll(data.categories, c => c.group == groupId);
                var allEnabled = true;
                foreach (var c in members)
                    if (c.id == "shortcut" ? visibleShortcutFilters.Count < shortcutFilterNames.Count : !visibleCategories.Contains(c.id)) allEnabled = false;
                foreach (var c in members)
                {
                    if (c.id == "shortcut")
                        foreach (var id in shortcutFilterNames.Keys) if (allEnabled) visibleShortcutFilters.Remove(id); else visibleShortcutFilters.Add(id);
                    else if (allEnabled) visibleCategories.Remove(c.id); else visibleCategories.Add(c.id);
                }
            }
            else
            {
                var id = key.Substring("category:".Length);
                if (id == "shortcut")
                {
                    var show = visibleShortcutFilters.Count != shortcutFilterNames.Count;
                    foreach (var filter in shortcutFilterNames.Keys) if (show) visibleShortcutFilters.Add(filter); else visibleShortcutFilters.Remove(filter);
                }
                else if (!visibleCategories.Remove(id)) visibleCategories.Add(id);
            }
            PlayCursorSound();
        }

        private List<string> ControlKeys()
        {
            var keys = new List<string>();
            if (data == null) return keys;
            keys.Add("layer:all");
            keys.Add("layer:none");
            keys.Add("layer:reset");
            foreach (var group in data.groups)
            {
                keys.Add("group:" + group.id);
                foreach (var category in data.categories)
                {
                    if (category.group != group.id) continue;
                    keys.Add("category:" + category.id);
                    if (category.id == "shortcut")
                        foreach (var filter in OrderedShortcutFilters()) keys.Add("filter:" + filter.Key);
                }
            }
            return keys;
        }

        private void KeepLayerSelectionVisible()
        {
            if (data == null || controlIndex < 3) return;
            var index = 3;
            var y = 4f;
            foreach (var group in data.groups)
            {
                if (index++ == controlIndex) { ScrollLayerRow(y, 31f); return; }
                y += 30f;
                foreach (var category in data.categories)
                {
                    if (category.group != group.id) continue;
                    if (index++ == controlIndex) { ScrollLayerRow(y, 25f); return; }
                    y += 24f;
                    if (category.id == "shortcut")
                    {
                        foreach (var filter in OrderedShortcutFilters())
                        {
                            if (index++ == controlIndex) { ScrollLayerRow(y, 21f); return; }
                            y += 21f;
                        }
                    }
                }
            }
        }

        private void ScrollLayerRow(float rowY, float rowHeight)
        {
            var panelHeight = Mathf.Max(180f, Screen.height - 87f);
            var viewportHeight = panelHeight - 76f;
            if (rowY < layerScroll.y) layerScroll.y = Mathf.Max(0f, rowY - 4f);
            else if (rowY + rowHeight > layerScroll.y + viewportHeight)
                layerScroll.y = rowY + rowHeight - viewportHeight;
        }

        private bool WasPressed(string name)
        {
            try
            {
                var handler = GetInputHandler();
                if (handler == null) return false;
                var actions = GetMember(handler, "inputActions");
                if (actions == null) return false;
                var action = GetMember(actions, name);
                var value = GetMember(action, "WasPressed");
                return value is bool && (bool)value;
            }
            catch { return false; }
        }

        private Vector2 GetActionVector(string actionName)
        {
            try
            {
                var handler = GetInputHandler();
                if (handler == null) return Vector2.zero;
                var actions = GetMember(handler, "inputActions");
                var action = GetMember(actions, actionName);
                var value = GetMember(action, "Value");
                return value is Vector2 ? (Vector2)value : Vector2.zero;
            }
            catch { return Vector2.zero; }
        }

        private InputHandler GetInputHandler()
        {
            if (inputHandler != null && Time.unscaledTime < nextInputLookup) return inputHandler;
            nextInputLookup = Time.unscaledTime + 1f;
            inputHandler = FindAnyObjectByType<InputHandler>();
            return inputHandler;
        }

        private object GetMember(object target, string name)
        {
            if (target == null) return null;
            var type = target.GetType();
            var field = type.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (field != null) return field.GetValue(target);
            var property = type.GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            return property == null ? null : property.GetValue(target, null);
        }

        private int CountCategory(string id)
        {
            var count = 0;
            if (data != null) foreach (var marker in data.markers) if (marker.cat == id) count++;
            return count;
        }

        private MapMarker FindMarker(string id)
        {
            if (data != null) foreach (var marker in data.markers) if (marker.id == id) return marker;
            return null;
        }

        private MapCategory FindCategory(string id)
        {
            if (data != null) foreach (var category in data.categories) if (category.id == id) return category;
            return null;
        }

        private string CategoryName(string id)
        {
            var category = FindCategory(id); return category == null ? id : category.name;
        }

        private void OnDestroy()
        {
            foreach (var texture in textures.Values) if (texture != null) Destroy(texture);
            textures.Clear();
            if (pixel != null) Destroy(pixel);
            if (instance == this) instance = null;
        }

#pragma warning disable 0649 // Json.NET populates these DTO fields through reflection.
        [Serializable] private sealed class MapData
        {
            public string title; public bool hasSave; public int slot; public string saveError;
            public MapGroup[] groups; public MapCategory[] categories; public MapMarker[] markers; public MapLabel[] labels;
            public MapStyle screenshots; public MapStyle sketch;
        }
        [Serializable] private sealed class MapGroup { public string id; public string name; public string icon; public bool visible; }
        [Serializable] private sealed class MapCategory { public string id; public string name; public string group; public string icon; }
        [Serializable] private sealed class MapMarker
        {
            public string id; public string cat; public string name; public string icon; public float[] pos; public float[] pos2;
            public string status; public string tracking; public string trackingNote;
        }
        [Serializable] private sealed class MapLabel { public string name; public float[] pos; }
        [Serializable] private sealed class MapStyle
        {
            public int tileSize; public int maxZoom; public float minLat; public float maxLat; public float minLng; public float maxLng;
            public string[] validTiles;
            [NonSerialized] public HashSet<string> valid;
        }
        [Serializable] private sealed class LiveMessage { public bool connected; public LivePosition position; }
        [Serializable] private sealed class LivePosition { public string scene; public float[] map; }
#pragma warning restore 0649
    }

    [HarmonyPatch]
    internal static class TrackerMapPaneInputPatch
    {
        private static MethodBase TargetMethod() { return AccessTools.Method(typeof(InventoryPaneInput), "Update"); }
        private static bool Prefix() { return TrackerMapOverlay.PaneUpdatePrefix(); }
    }

    [HarmonyPatch]
    internal static class TrackerGameMapInputPatch
    {
        private static MethodBase TargetMethod() { return AccessTools.Method(typeof(GameMap), "Update"); }
        private static bool Prefix() { return TrackerMapOverlay.GameMapUpdatePrefix(); }
    }

    [HarmonyPatch]
    internal static class TrackerMapMarkerMenuInputPatch
    {
        private static MethodBase TargetMethod() { return AccessTools.Method(typeof(MapMarkerMenu), "Update"); }
        private static bool Prefix() { return TrackerMapOverlay.MapMarkerMenuUpdatePrefix(); }
    }

    [HarmonyPatch]
    internal static class TrackerGlobalInputPatch
    {
        private static MethodBase TargetMethod() { return AccessTools.Method(typeof(InputHandler), "Update"); }
        private static bool Prefix() { return TrackerMapOverlay.InputHandlerUpdatePrefix(); }
    }
}
