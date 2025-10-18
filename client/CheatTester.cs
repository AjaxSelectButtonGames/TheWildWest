using UnityEngine;

public class CheatTester : MonoBehaviour
{
    MasterServerClient client;
    public float normalStep = 0.1f;   // normal movement per tick
    public float hackStep = 1.0f;     // exaggerated speed for hack
    private Vector3 fakePos;

    void Start()
    {
        client = FindObjectOfType<MasterServerClient>();
        if (client == null) Debug.LogWarning("MasterServerClient not found.");
        else fakePos = client.transform.position; // start where player is
    }

    void Update()
    {
        if (client == null) return;

        // Hold Left Shift = continuous speed hack
        if (Input.GetKey(KeyCode.LeftShift))
        {
            // simulate running forward fast
            fakePos += Vector3.forward * hackStep;

            var data = new { x = fakePos.x, y = fakePos.y, z = fakePos.z };
            string packet = PacketFactory.Build(Protocol.PLAYER_MOVE, data);
            _ = client.SendPacket(packet);

            Debug.Log("[CHEAT TEST] Sent SpeedHack step: " + fakePos);
        }
        else
        {
            // normal slow drift to compare
            fakePos += Vector3.forward * normalStep;

            var data = new { x = fakePos.x, y = fakePos.y, z = fakePos.z };
            string packet = PacketFactory.Build(Protocol.PLAYER_MOVE, data);
            _ = client.SendPacket(packet);
        }
    }
}
