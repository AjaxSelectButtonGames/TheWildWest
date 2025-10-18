using UnityEngine;
using UnityEngine.UI;
using System.Text;
using System.IO;
using System;
using System.Collections;

/// <summary>
/// Unified in-game console for Debug logs + Chat, separated by tabs.
/// </summary>
public class SimpleChatConsole : MonoBehaviour
{
    // --- Chat UI Components ---
    private Text chatText;
    private ScrollRect chatScrollRect;
    private InputField chatInput;
    private GameObject chatPanel;
    private StringBuilder chatLogBuilder = new StringBuilder();

    // --- Debug UI Components ---
    private Text debugText;
    private ScrollRect debugScrollRect;
    private GameObject debugPanel;
    private StringBuilder debugLogBuilder = new StringBuilder();

    // --- Configuration ---
    private int maxLines = 200;
    private string logFilePath;

    // --- Tab Management ---
    private Button chatTabButton;
    private Button debugTabButton;

    void Awake()
    {
        SetupFileLogging();
        GameObject canvasGO = SetupCanvas();
        SetupTabButtons(canvasGO.transform);
        SetupChatPanel(canvasGO.transform);
        SetupDebugPanel(canvasGO.transform);
        SetupChatInput(canvasGO.transform);
        ShowPanel("Chat");
        DontDestroyOnLoad(canvasGO);
    }

    void OnEnable() => Application.logMessageReceived += HandleLog;
    void OnDisable() => Application.logMessageReceived -= HandleLog;

    // ------------------------------------------------------------------------------------------------
    //                                         SETUP METHODS
    // ------------------------------------------------------------------------------------------------

    private void SetupFileLogging()
    {
        logFilePath = Path.Combine(Application.persistentDataPath, "debug_log.txt");
        try
        {
            File.WriteAllText(logFilePath, "=== Debug Log Started ===\n");
            UnityEngine.Debug.Log($"Log file initialized at: {logFilePath}");
        }
        catch (Exception e)
        {
            UnityEngine.Debug.LogError($"[ConsoleInit] Failed to initialize log file: {e.Message}");
        }
    }

    private GameObject SetupCanvas()
    {
        GameObject canvasGO = new GameObject("ChatConsoleCanvas");
        Canvas canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 9999;

        CanvasScaler scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);
        scaler.matchWidthOrHeight = 0.5f;

        canvasGO.AddComponent<GraphicRaycaster>();
        return canvasGO;
    }

    private void SetupTabButtons(Transform parent)
    {
        GameObject tabsGO = new GameObject("TabContainer");
        tabsGO.transform.SetParent(parent, false);
        RectTransform tabsRT = tabsGO.AddComponent<RectTransform>();
        tabsRT.anchorMin = new Vector2(0f, 0.3f);
        tabsRT.anchorMax = new Vector2(0.5f, 0.35f);
        tabsRT.offsetMin = new Vector2(10, 5);
        tabsRT.offsetMax = new Vector2(-10, -5);

        HorizontalLayoutGroup layout = tabsGO.AddComponent<HorizontalLayoutGroup>();
        layout.spacing = 10;
        layout.childControlWidth = true;
        layout.childForceExpandWidth = true;

        chatTabButton = CreateTabButton(tabsGO.transform, "Chat", () => ShowPanel("Chat"));
        debugTabButton = CreateTabButton(tabsGO.transform, "Debug", () => ShowPanel("Debug"));
    }

    private Button CreateTabButton(Transform parent, string name, UnityEngine.Events.UnityAction onClick)
    {
        GameObject buttonGO = new GameObject(name + "TabButton");
        buttonGO.transform.SetParent(parent, false);

        Image img = buttonGO.AddComponent<Image>();
        img.color = new Color(0.2f, 0.2f, 0.2f, 0.8f);

        Button button = buttonGO.AddComponent<Button>();
        button.onClick.AddListener(onClick);

        GameObject textGO = new GameObject("Text");
        textGO.transform.SetParent(buttonGO.transform, false);
        Text txt = textGO.AddComponent<Text>();
        txt.text = name;
        txt.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        txt.fontSize = 18;
        txt.color = Color.white;
        txt.alignment = TextAnchor.MiddleCenter;

        RectTransform rt = textGO.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;

        return button;
    }

    private void SetupChatPanel(Transform parent)
    {
        chatPanel = SetupLogPanel(parent, "ChatPanel", ref chatScrollRect, ref chatText);
        RectTransform chatRT = chatPanel.GetComponent<RectTransform>();
        chatRT.anchorMin = new Vector2(0f, 0.15f);
        chatRT.anchorMax = new Vector2(0.5f, 0.3f);
    }

    private void SetupDebugPanel(Transform parent)
    {
        debugPanel = SetupLogPanel(parent, "DebugPanel", ref debugScrollRect, ref debugText);
        RectTransform debugRT = debugPanel.GetComponent<RectTransform>();
        debugRT.anchorMin = new Vector2(0f, 0.15f);
        debugRT.anchorMax = new Vector2(0.5f, 0.3f);
    }

    private GameObject SetupLogPanel(Transform parent, string name, ref ScrollRect scrollRectRef, ref Text textRef)
    {
        // --- Main panel ---
        GameObject panelGO = new GameObject(name);
        panelGO.transform.SetParent(parent, false);
        RectTransform panelRT = panelGO.AddComponent<RectTransform>();
        panelRT.offsetMin = new Vector2(10, 10);
        panelRT.offsetMax = new Vector2(-10, -10);

        Image bg = panelGO.AddComponent<Image>();
        bg.color = new Color(0, 0, 0, 0.7f);

        scrollRectRef = panelGO.AddComponent<ScrollRect>();
        scrollRectRef.horizontal = false;
        scrollRectRef.movementType = ScrollRect.MovementType.Clamped;

        // --- Viewport ---
        GameObject viewportGO = new GameObject("Viewport");
        viewportGO.transform.SetParent(panelGO.transform, false);
        RectTransform viewportRT = viewportGO.AddComponent<RectTransform>();
        viewportRT.anchorMin = Vector2.zero;
        viewportRT.anchorMax = Vector2.one;
        viewportRT.offsetMin = new Vector2(5, 5);
        viewportRT.offsetMax = new Vector2(-25, -5);

        // Mask + Image (must not be Color.clear or mask won't work)
        Image maskImg = viewportGO.AddComponent<Image>();
        maskImg.color = new Color(1, 1, 1, 0); // invisible but still a valid mask
        Mask mask = viewportGO.AddComponent<Mask>();
        mask.showMaskGraphic = false;

        scrollRectRef.viewport = viewportRT;

        // --- Content (fixed to viewport size, no auto-growth) ---
        GameObject contentGO = new GameObject("Content");
        contentGO.transform.SetParent(viewportGO.transform, false);
        RectTransform contentRT = contentGO.AddComponent<RectTransform>();

        contentRT.anchorMin = Vector2.zero;
        contentRT.anchorMax = Vector2.one;
        contentRT.pivot = new Vector2(0.5f, 0.5f);
        contentRT.sizeDelta = Vector2.zero; // fixed size, matches viewport

        scrollRectRef.content = contentRT;

        // --- Text component ---
        textRef = contentGO.AddComponent<Text>();
        textRef.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        textRef.fontSize = 14;
        textRef.color = Color.green;
        textRef.alignment = TextAnchor.LowerLeft;
        textRef.horizontalOverflow = HorizontalWrapMode.Wrap;
        textRef.verticalOverflow = VerticalWrapMode.Truncate; // ✅ cut off old lines
        textRef.supportRichText = true;
        if (textRef.font != null) textRef.material = textRef.font.material;

        // --- Scrollbar ---
        GameObject scrollbarGO = new GameObject("Scrollbar");
        scrollbarGO.transform.SetParent(panelGO.transform, false);
        RectTransform scrollbarRT = scrollbarGO.AddComponent<RectTransform>();
        scrollbarRT.anchorMin = new Vector2(1, 0);
        scrollbarRT.anchorMax = new Vector2(1, 1);
        scrollbarRT.pivot = new Vector2(1, 1);
        scrollbarRT.anchoredPosition = Vector2.zero;
        scrollbarRT.sizeDelta = new Vector2(20, 0);

        Image sbBg = scrollbarGO.AddComponent<Image>();
        sbBg.color = new Color(0.1f, 0.1f, 0.1f, 0.6f);

        Scrollbar scrollbar = scrollbarGO.AddComponent<Scrollbar>();
        scrollbar.direction = Scrollbar.Direction.BottomToTop;

        // Handle
        GameObject handleGO = new GameObject("Handle");
        handleGO.transform.SetParent(scrollbarGO.transform, false);
        RectTransform handleRT = handleGO.AddComponent<RectTransform>();
        handleRT.anchorMin = Vector2.zero;
        handleRT.anchorMax = Vector2.one;
        handleRT.offsetMin = Vector2.zero;
        handleRT.offsetMax = Vector2.zero;

        Image handleImg = handleGO.AddComponent<Image>();
        handleImg.color = new Color(0.3f, 0.7f, 1f, 0.9f);

        scrollbar.handleRect = handleRT;
        scrollbar.targetGraphic = handleImg;

        scrollRectRef.verticalScrollbar = scrollbar;
        scrollRectRef.verticalScrollbarVisibility = ScrollRect.ScrollbarVisibility.AutoHideAndExpandViewport;

        return panelGO;
    }

    private void SetupChatInput(Transform parent)
    {
        GameObject inputGO = new GameObject("ChatInput");
        inputGO.transform.SetParent(parent, false);
        RectTransform inputRT = inputGO.AddComponent<RectTransform>();
        inputRT.anchorMin = new Vector2(0f, 0f);
        inputRT.anchorMax = new Vector2(0.5f, 0.15f);
        inputRT.offsetMin = new Vector2(10, 10);
        inputRT.offsetMax = new Vector2(-10, -5);

        Image inputBg = inputGO.AddComponent<Image>();
        inputBg.color = new Color(0, 0, 0, 0.8f);

        chatInput = inputGO.AddComponent<InputField>();
        chatInput.textComponent = CreateInputText(inputGO.transform);
        chatInput.onEndEdit.AddListener(OnChatSubmitted);
    }

    private Text CreateInputText(Transform parent)
    {
        GameObject textGO = new GameObject("InputText");
        textGO.transform.SetParent(parent, false);
        Text txt = textGO.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        txt.fontSize = 14;
        txt.color = Color.white;
        txt.alignment = TextAnchor.MiddleLeft;

        RectTransform rt = textGO.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = new Vector2(10, 0);
        rt.offsetMax = new Vector2(-10, 0);
        return txt;
    }

    // ------------------------------------------------------------------------------------------------
    //                                         LOGIC METHODS
    // ------------------------------------------------------------------------------------------------

    private void ShowPanel(string panelName)
    {
        bool isChat = panelName.Equals("Chat", StringComparison.OrdinalIgnoreCase);

        chatPanel.SetActive(isChat);
        debugPanel.SetActive(!isChat);
        chatInput.gameObject.SetActive(isChat);

        Color activeColor = new Color(0.1f, 0.5f, 0.8f, 0.8f);
        Color inactiveColor = new Color(0.2f, 0.2f, 0.2f, 0.8f);

        chatTabButton.GetComponent<Image>().color = isChat ? activeColor : inactiveColor;
        debugTabButton.GetComponent<Image>().color = !isChat ? activeColor : inactiveColor;

        // Scroll to bottom after switching
        StartCoroutine(ScrollToBottomNextFrame(isChat ? chatScrollRect : debugScrollRect));
    }

    private void HandleLog(string logString, string stackTrace, LogType type)
    {
        string typeTag = type switch
        {
            LogType.Error or LogType.Exception => "error",
            LogType.Warning => "warn",
            _ => "log"
        };
        AppendDebugLog(logString, typeTag, stackTrace);
    }

    public void AppendDebugLog(string msg, string type = "log", string stackTrace = "")
    {
        string timestamp = DateTime.Now.ToString("HH:mm:ss");
        string formatted = type switch
        {
            "error" => $"<color=red>[ERR {timestamp}]</color> {msg}\n<color=red><size=10>StackTrace: {stackTrace}</size></color>",
            "warn" => $"<color=yellow>[WARN {timestamp}]</color> {msg}",
            _ => $"<color=lime>[{timestamp}]</color> {msg}"
        };

        UpdateLogBuilder(debugLogBuilder, debugText, debugScrollRect, formatted);

        try { File.AppendAllText(logFilePath, $"[{type.ToUpper()} {timestamp}] {msg}\n"); } catch { }
    }

    public void AppendChat(string msg)
    {
        string timestamp = DateTime.Now.ToString("HH:mm:ss");
        string formatted = $"<color=cyan>[CHAT {timestamp}]</color> {msg}";
        UpdateLogBuilder(chatLogBuilder, chatText, chatScrollRect, formatted);
    }

    private void UpdateLogBuilder(StringBuilder builder, Text textComponent, ScrollRect scrollRectComponent, string formattedMessage)
    {
        builder.AppendLine(formattedMessage);

        // Limit lines
        string[] lines = builder.ToString().Split(new char[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
        if (lines.Length > maxLines)
        {
            builder.Clear();
            for (int i = lines.Length - maxLines; i < lines.Length; i++)
                builder.AppendLine(lines[i]);
        }

        textComponent.text = builder.ToString();

        // Scroll to bottom using coroutine to ensure layout is updated
        StartCoroutine(ScrollToBottomNextFrame(scrollRectComponent));
    }

    private IEnumerator ScrollToBottomNextFrame(ScrollRect scrollRect)
    {
        // Wait for end of frame to ensure layout has been recalculated
        yield return new WaitForEndOfFrame();

        Canvas.ForceUpdateCanvases();
        scrollRect.verticalNormalizedPosition = 0f;

        // Force another update to be sure
        yield return null;
        scrollRect.verticalNormalizedPosition = 0f;
    }

    private void OnChatSubmitted(string text)
    {
        if (!string.IsNullOrWhiteSpace(text))
        {
            AppendChat($"[You]: {text}");

            MasterServerClient client = FindObjectOfType<MasterServerClient>();
            if (client != null)
            {
                var chatData = new ChatSendData
                {
                    channel = "global",
                    text = text
                };
                string chatPacket = PacketFactory.Build(Protocol.CHAT, chatData);
                _ = client.SendPacket(chatPacket);
            }
            else
            {
                UnityEngine.Debug.LogWarning("Warning: MasterServerClient not found to send chat message.");
            }

            chatInput.text = "";
            chatInput.ActivateInputField();
        }
    }

    // ------------------------------------------------------------------------------------------------
    //                                         DATA STRUCTURES
    // ------------------------------------------------------------------------------------------------

    [System.Serializable]
    public class ChatSendData
    {
        public string channel;
        public string text;
    }

    [System.Serializable]
    public class ChatRecvData
    {
        public string channel;
        public string playerId;
        public string text;
    }
}