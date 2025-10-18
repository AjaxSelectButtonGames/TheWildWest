using System;

[Serializable]
public class PlayerState
{
    public string id;
    public float x;
    public float y;
    public float z;
}

[Serializable]
public class WorldUpdateData
{
    public PlayerState[] players;
}
