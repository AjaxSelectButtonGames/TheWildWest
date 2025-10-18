using UnityEngine;

[System.Serializable]
public class Packet<T>
{
    public int id;
    public T data;
}

public static class PacketFactory
{
    public static string Build<T>(int id, T data)
    {
        Packet<T> packet = new Packet<T> { id = id, data = data };
        return JsonUtility.ToJson(packet) + "\n"; // newline for TCP delimiting
    }

    public static Packet<T> Parse<T>(string json)
    {
        return JsonUtility.FromJson<Packet<T>>(json);
    }
}
