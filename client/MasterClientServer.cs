using System;
using System.Collections.Generic;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using static SimpleChatConsole;

public class MasterServerClient : MonoBehaviour
{
    private TcpClient client;
    private NetworkStream stream;
    private CancellationTokenSource cts;

    // IMPORTANT: Ensure these are set in the Inspector before building!
    public string serverIP = "172.86.89.112";
    public int serverPort = 5000;
    public GameObject playerPrefab;
    public Transform[] spawnPoints;

    // Unique player ID for this client
    private string playerId = System.Guid.NewGuid().ToString();
    private bool playerIdConfirmed = false;

    // Public properties for external access
    public string PlayerId => playerId;
    public bool PlayerIdConfirmed => playerIdConfirmed;

    // Dictionary for tracking other players in the scene
    private Dictionary<string, GameObject> otherPlayers = new Dictionary<string, GameObject>();

    // Queue for main thread operations
    private readonly Queue<System.Action> mainThreadQueue = new Queue<System.Action>();
    private readonly object queueLock = new object();

    private async void Start()
    {
        await ConnectToServer();
    }

    private void Update()
    {
        // Process queued main thread operations
        lock (queueLock)
        {
            while (mainThreadQueue.Count > 0)
            {
                Application.runInBackground = true;
                var action = mainThreadQueue.Dequeue();
                action?.Invoke();
            }
        }
    }
    private TaskCompletionSource<string> handshakeTcs;
    private string serverSecret = "dev-secret-change-me";


    private async Task ConnectToServer()
    {
        if (playerPrefab == null)
        {
            Debug.LogError("[CLIENT] FATAL: playerPrefab is not assigned in the Inspector. Local player cannot spawn.");
            // Prevent connection if critical asset is missing
            return;
        }

        cts = new CancellationTokenSource();
        handshakeTcs = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        // Establish TCP connection first
        try
        {
            client = new TcpClient();
            await client.ConnectAsync(serverIP, serverPort);
            stream = client.GetStream();
        }
        catch (Exception e)
        {
            Debug.LogError($"[CLIENT] Failed to connect to server {serverIP}:{serverPort} - {e.Message}");
            client?.Close();
            return;
        }

        // Start reader loop after stream is available
        _ = Task.Run(() => ListenForMessages(cts.Token));

        // Wait for the server handshake (nonce) with a timeout
        string nonce = null;
        var completed = await Task.WhenAny(handshakeTcs.Task, Task.Delay(5000));
        if (completed == handshakeTcs.Task && handshakeTcs.Task.IsCompleted)
        {
            nonce = handshakeTcs.Task.Result;
        }
        else
        {
            Debug.LogError("[CLIENT] Handshake timeout - closing connection.");
            try { client.Close(); } catch { }
            return;
        }

        if (string.IsNullOrEmpty(nonce))
        {
            Debug.LogError("[CLIENT] No handshake nonce received; aborting.");
            try { client.Close(); } catch { }
            return;
        }

        // Now create PLAYER_JOIN with ts & hmac
        int ts = (int)DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        string msg = nonce + playerId + ts.ToString(); // preferredId is playerId
        string hmac = CryptoUtils.ComputeHmacHex(serverSecret, msg);

        var joinData = new PlayerJoinData { preferredId = playerId, nickname = "", ts = ts, hmac = hmac };
        var joinPacket = PacketFactory.Build(Protocol.PLAYER_JOIN, joinData);
        await SendPacket(joinPacket);
    }
    private async Task SendPing()
    {
        var pingData = new PingData { msg = "ping" };
        var pingPacket = PacketFactory.Build(Protocol.PING, pingData);
        await SendPacket(pingPacket);
    }

    private async Task ListenForMessages(CancellationToken token)
    {
        byte[] buffer = new byte[1024];
        StringBuilder incoming = new StringBuilder();

        try
        {
            while (!token.IsCancellationRequested)
            {
                int bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length, token);
                if (bytesRead == 0)
                {
                    Debug.Log("[CLIENT] Disconnected from server (Read 0 bytes).");
                    break;
                }

                string chunk = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                incoming.Append(chunk);

                // Split by newline since our server sends \n per packet
                while (true)
                {
                    string current = incoming.ToString();
                    int newlineIndex = current.IndexOf('\n');
                    if (newlineIndex == -1) break;

                    string completePacket = current[..newlineIndex];
                    incoming.Remove(0, newlineIndex + 1);
                    HandlePacket(completePacket);
                }
            }
        }
        catch (OperationCanceledException)
        {
            Debug.Log("[CLIENT] Listener gracefully cancelled.");
        }
        catch (Exception e)
        {
            Debug.LogError($"[CLIENT READ ERROR] {e.Message}");
        }
    }

    private void HandlePacket(string json)
    {
        try
        {
            // Debug.Log("[CLIENT] RAW PACKET: " + json); // Too noisy, commenting out

            var basePacket = JsonUtility.FromJson<PacketWrapper>(json);
            switch (basePacket.id)
            {
                case Protocol.PONG:
                    // Handled PONG
                    break;

                case Protocol.HANDSHAKE_CHALLENGE:
                    QueueMainThreadAction(() =>
                    {
                        try
                        {
                            var hand = JsonUtility.FromJson<Packet<HandshakeData>>(json);
                            if (hand != null && hand.data != null && handshakeTcs != null)
                            {
                                handshakeTcs.TrySetResult(hand.data.nonce);
                                Debug.Log("[CLIENT] Received handshake nonce from server.");
                            }
                        }
                        catch (Exception e)
                        {
                            Debug.LogError($"[CLIENT] Failed to parse HANDSHAKE_CHALLENGE: {e.Message}");
                        }
                    });
                    break;
                case Protocol.PLAYER_ID_ASSIGNED:
                    // Queue parsing + spawn to main thread
                    QueueMainThreadAction(() =>
                    {
                        try
                        {
                            var idPacket = JsonUtility.FromJson<Packet<PlayerIdData>>(json);
                            if (idPacket != null && idPacket.data != null)
                            {
                                playerId = idPacket.data.assignedId;
                                playerIdConfirmed = true;
                                SpawnLocalPlayer(idPacket.data.spawnIndex);
                                Debug.Log($"[CLIENT] Server confirmed player ID: {playerId}, SpawnIndex: {idPacket.data.spawnIndex}");
                            }
                            else
                            {
                                Debug.LogError("[CLIENT] PLAYER_ID_ASSIGNED parsed as null!");
                            }
                        }
                        catch (Exception e)
                        {
                            Debug.LogError($"[CLIENT] Failed to parse PLAYER_ID_ASSIGNED: {e.Message}");
                        }
                    });
                    break;

                case Protocol.WORLD_UPDATE:
                    try
                    {
                        var worldPacket = JsonUtility.FromJson<Packet<WorldState>>(json);
                        if (worldPacket != null && worldPacket.data != null)
                        {
                            // Queue the update operation for the main thread
                            QueueMainThreadAction(() => UpdateOtherPlayers(worldPacket.data.players));
                        }
                        else
                        {
                            Debug.LogError("[CLIENT] WORLD_UPDATE parsed as null!");
                        }
                    }
                    catch (Exception e)
                    {
                        Debug.LogError("[CLIENT] Failed to parse WORLD_UPDATE: " + e.Message);
                    }
                    break;

                default:
                    Debug.Log($"[CLIENT] Unknown packet ID: {basePacket.id}");
                    break;
                case Protocol.CHAT:
                    QueueMainThreadAction(() =>
                    {
                        var chatPacket = JsonUtility.FromJson<Packet<ChatMessage>>(json);
                        if (chatPacket?.data != null)
                        {
                            string channel = chatPacket.data.channel;
                            string from = string.IsNullOrEmpty(chatPacket.data.nickname)
                                          ? chatPacket.data.playerId
                                          : chatPacket.data.nickname;
                            string text = chatPacket.data.text;

                            if (chatPacket.data.playerId == playerId)
                                return; // ignore our own echo

                            var console = FindObjectOfType<SimpleChatConsole>();
                            console?.AppendChat($"[{channel}] {from}: {text}");
                        }
                    });
                    break;
                case Protocol.PLAYER_CORRECTION:
                    QueueMainThreadAction(() =>
                    {
                        try
                        {
                            var correctionPacket = JsonUtility.FromJson<Packet<CorrectionData>>(json);
                            if (correctionPacket != null && correctionPacket.data != null)
                            {
                                Vector3 correctedPos = new Vector3(
                                    correctionPacket.data.x,
                                    correctionPacket.data.y,
                                    correctionPacket.data.z
                                );

                                if (localPlayer != null)
                                {
                                    localPlayer.transform.position = correctedPos;
                                    Debug.LogWarning($"[SERVER AUTH] Corrected position to {correctedPos}");
                                }
                                else
                                {
                                    Debug.LogWarning("[CLIENT] Received correction but localPlayer is null!");
                                }
                            }
                        }
                        catch (Exception e)
                        {
                            Debug.LogError($"[CLIENT] Failed to parse PLAYER_CORRECTION: {e.Message}");
                        }
                    });
                    break;
                case Protocol.NPC_SPAWN:
                    QueueMainThreadAction(() =>
                    {
                        var npcPacket = JsonUtility.FromJson<Packet<NPCState>>(json);
                        Debug.Log($"[CLIENT DEBUG] Raw NPC packet: {json}");

                        if (npcPacket != null && npcPacket.data != null)
                        {
                            string npcId = npcPacket.data.npcId;
                            if (!npcs.ContainsKey(npcId))
                            {
                                GameObject npc = Instantiate(npcPrefab,
                                    new Vector3(npcPacket.data.x, npcPacket.data.y, npcPacket.data.z),
                                    Quaternion.identity);
                                npc.name = "NPC_" + npcId;
                                npcs[npcId] = npc;
                                Debug.Log($"[CLIENT] Spawned NPC {npcId}");
                            }
                        }
                    });
                    break;

                case Protocol.NPC_UPDATE:
                    QueueMainThreadAction(() =>
                    {
                        var npcPacket = JsonUtility.FromJson<Packet<NPCState>>(json);
                        Debug.Log($"[CLIENT DEBUG] Raw NPC packet: {json}");

                        if (npcPacket != null && npcPacket.data != null)
                        {
                            string npcId = npcPacket.data.npcId;
                            if (npcs.ContainsKey(npcId))
                            {
                                npcs[npcId].transform.position =
                                    new Vector3(npcPacket.data.x, npcPacket.data.y, npcPacket.data.z);
                                Debug.Log($"[CLIENT] NPCUpdate {npcId}");
                            }
                        }
                    });
                    break;

                case Protocol.NPC_DESPAWN:
                    QueueMainThreadAction(() =>
                    {
                        var npcPacket = JsonUtility.FromJson<Packet<NPCState>>(json);
                        Debug.Log($"[CLIENT DEBUG] Raw NPC packet: {json}");

                        if (npcPacket != null && npcPacket.data != null)
                        {
                            string npcId = npcPacket.data.npcId;
                            if (npcs.ContainsKey(npcId))
                            {
                                Destroy(npcs[npcId]);
                                npcs.Remove(npcId);
                                Debug.Log($"[CLIENT] Despawned NPC {npcId}");
                            }
                        }
                    });
                    break;



            

            }
        }
        catch (Exception e)
        {
            Debug.LogError($"[CLIENT PARSE ERROR] Error processing JSON: {e.Message}. JSON: {json}");
        }
    }

    public async Task SendPacket(string packet)
    {
        if (client == null || !client.Connected)
        {
            Debug.LogWarning("[CLIENT] Not connected to server, cannot send packet.");
            return;
        }

        try
        {
            byte[] data = Encoding.UTF8.GetBytes(packet + "\n");
            await stream.WriteAsync(data, 0, data.Length);
            // Debug.Log($"[CLIENT] Sent: {packet.Trim()}"); // Too noisy, commenting out
        }
        catch (Exception e)
        {
            Debug.LogError($"[CLIENT SEND ERROR] Failed to send packet: {e.Message}");
        }
    }

    private void OnApplicationQuit()
    {
        cts?.Cancel();
        stream?.Close();
        client?.Close();
        Debug.Log("[CLIENT] Closed connection.");
    }

    // Queue an action to be executed on the main thread
    private void QueueMainThreadAction(System.Action action)
    {
        lock (queueLock)
        {
            mainThreadQueue.Enqueue(action);
        }
    }

    // --- Helpers for WORLD_UPDATE ---
    private void UpdateOtherPlayers(PlayerState[] players)
    {
        if (!playerIdConfirmed)
        {
            Debug.LogWarning("[CLIENT] Player ID not confirmed yet, skipping world update");
            return;
        }

        // Track which player IDs we received in this update
        HashSet<string> receivedPlayerIds = new HashSet<string>();

        foreach (var p in players)
        {
            receivedPlayerIds.Add(p.id);

            if (p.id == playerId)
            {
                // Self-player logic: if you have a local movement script, 
                // you might update your own position here based on server authoritative data.
                continue;
            }

            if (!otherPlayers.ContainsKey(p.id))
            {
                Debug.Log($"[CLIENT] Spawning new remote player object: {p.id}");
                GameObject capsule = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                capsule.name = "Player_" + p.id;

                var renderer = capsule.GetComponent<Renderer>();
                if (renderer != null)
                {
                    // FIX: Check for null shader returned by Shader.Find()
                    Shader desiredShader = Shader.Find("Universal Render Pipeline/Lit"); // Try URP default first

                    if (desiredShader == null)
                    {
                        desiredShader = Shader.Find("Standard"); // Fallback to Standard
                    }
                    if (desiredShader == null)
                    {
                        desiredShader = Shader.Find("Unlit/Color"); // Fallback to simple unlit
                    }

                    if (desiredShader != null)
                    {
                        // CRITICAL FIX: Explicitly create a new material instance using a found shader.
                        renderer.material = new Material(desiredShader);
                        renderer.material.color = Color.red;
                        Debug.Log($"[CLIENT] Assigned {desiredShader.name} Material to {p.id}.");
                    }
                    else
                    {
                        Debug.LogError($"[CLIENT] FATAL: Could not find any suitable shader! Remote players will be invisible for {p.id}.");
                    }
                }
                else
                {
                    Debug.LogError($"[CLIENT] Spawned Capsule for {p.id} is missing Renderer component!");
                }

                otherPlayers[p.id] = capsule;
            }

            // Update position
            otherPlayers[p.id].transform.position = new Vector3(p.x, p.y, p.z);
            // Debug.Log($"[CLIENT] Updated player {p.id} position to ({p.x}, {p.y}, {p.z})"); // Too noisy
        }

        // Removal logic for disconnected players
        List<string> playersToRemove = new List<string>();
        foreach (var existingPlayerId in otherPlayers.Keys)
        {
            if (!receivedPlayerIds.Contains(existingPlayerId))
            {
                playersToRemove.Add(existingPlayerId);
            }
        }

        foreach (var playerToRemoveId in playersToRemove)
        {
            Debug.Log($"[CLIENT] Removing disconnected player: {playerToRemoveId}");
            Destroy(otherPlayers[playerToRemoveId]);
            otherPlayers.Remove(playerToRemoveId);
        }
    }



public static class CryptoUtils
{
    public static string ComputeHmacHex(string secret, string message)
    {
        var key = Encoding.UTF8.GetBytes(secret);
        var msg = Encoding.UTF8.GetBytes(message);
        using (var h = new HMACSHA256(key))
        {
            var mac = h.ComputeHash(msg);
            // convert to lowercase hex
            var hex = BitConverter.ToString(mac).Replace("-", "").ToLowerInvariant();
            return hex;
        }
    }
}

// --- Data Structures ---
[System.Serializable]
    public class PlayerState
    {
        public string id;
        public float x;
        public float y;
        public float z;
    }

    [System.Serializable]
    public class WorldState
    {
        public PlayerState[] players;
    }

    [System.Serializable]
    public class Packet<T>
    {
        public int id;
        public T data;
    }

    [System.Serializable]
    public class PacketWrapper
    {
        public int id;
    }

    // NOTE: PingData is only used for sending, no need for [System.Serializable]
    public class PingData
    {
        public string msg;
    }

    [System.Serializable]
    public class PlayerJoinData
    {
        public string preferredId;
        public string nickname; // NEW
        public int ts;
        public string hmac; // hex string
    }

    [System.Serializable]
    public class HandshakeData
    {
        public string nonce;
    }

    [System.Serializable]
    public class PlayerIdData
    {
        public string assignedId;
        public int spawnIndex;
    }
    private Dictionary<string, GameObject> npcs = new Dictionary<string, GameObject>();
    public GameObject npcPrefab;

    [System.Serializable]
    public class ChatMessage
    {
        public string channel;
        public string playerId;
        public string nickname;   // add this
        public string text;
        public int timestamp;
    }
    [System.Serializable]
    public class CorrectionData
    {
        public float x;
        public float y;
        public float z;
    }
    private GameObject localPlayer;
    [System.Serializable]
    public class NPCState
    {
        public string npcId;
        public float x;
        public float y;
        public float z;
    }
    private void SpawnLocalPlayer(int spawnIndex)
    {
        if (playerPrefab == null)
        {
            Debug.LogError("[CLIENT] playerPrefab is null, cannot spawn local player!");
            return;
        }
        if (spawnPoints == null || spawnPoints.Length == 0)
        {
            Debug.LogError("[CLIENT] spawnPoints are missing, cannot spawn local player!");
            return;
        }

        Transform spawn = spawnPoints[spawnIndex % spawnPoints.Length];
        localPlayer = Instantiate(playerPrefab, spawn.position, spawn.rotation);

        Debug.Log($"[CLIENT] Spawned local player at {spawn.position}");
    }
}
