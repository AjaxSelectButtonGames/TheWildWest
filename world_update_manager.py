# world_update_manager.py

class WorldState:
    def __init__(self):
        # {player_id: {"x": float, "y": float, "z": float}}
        self.players = {}

    def update_player(self, player_id, x, y, z):
        self.players[player_id] = {"x": x, "y": y, "z": z}

    # NEW: remove player when a client disconnects
    def remove_player(self, player_id):
        if player_id in self.players:
            del self.players[player_id]

    # You chose the wrapped shape {"players":[...]} (matches your broadcast code)
    def get_state(self):
        return {"players": [
            {"id": pid, "x": p["x"], "y": p["y"], "z": p["z"]}
            for pid, p in self.players.items()
        ]}
