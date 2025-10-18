class PacketType:
    PING = 1
    PONG = 2
    MOVE = 3  
    CHAT = 4
    WORLD_UPDATE = 5
    PLAYER_JOIN = 6
    PLAYER_ID_ASSIGNED = 7
    PLAYER_MOVE = 8
    PLAYER_CORRECTION = 9
    NPC_SPAWN = 10
    NPC_UPDATE = 11
    NPC_DESPAWN = 12
    # Handshake packet (server -> client) containing a nonce to prevent unauthenticated clients
    HANDSHAKE_CHALLENGE = 100