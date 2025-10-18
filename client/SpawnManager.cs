using UnityEngine;

public class SpawnManager : MonoBehaviour
{
    public static Vector3[] SpawnPositions;

    void Awake()
    {
        var spawnPoints = GameObject.FindGameObjectsWithTag("SpawnPoint");
        SpawnPositions = new Vector3[spawnPoints.Length];

        for (int i = 0; i < spawnPoints.Length; i++)
        {
            SpawnPositions[i] = spawnPoints[i].transform.position;
        }
    }
}
