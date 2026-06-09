from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


def pair_room(username: str, recipient: str) -> str:
    first, second = sorted([username, recipient])
    return f"room:{first}:{second}"


class ConnectionManager:
    def __init__(self):
        self.user_connections: dict[str, set[WebSocket]]  = defaultdict(set)
        self.lobby_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.room_connections: dict[str, set[WebSocket]]  = defaultdict(set)

    async def connect_lobby(self, username: str, websocket: WebSocket):
        if username in self.user_connections and self.user_connections[username]:
            await websocket.accept()
            await websocket.send_text("error: username already taken")
            await websocket.close()
            return False

        await websocket.accept()
        self.user_connections[username].add(websocket)
        self.lobby_connections[username].add(websocket)
        return True

    async def connect(self, username: str, recipient: str, websocket: WebSocket):
        await websocket.accept()
        room = pair_room(username, recipient)
        self.user_connections[username].add(websocket)
        self.room_connections[room].add(websocket)
        
        self.lobby_connections[username].discard(websocket)

        return room

    def disconnect(self, username: str, websocket: WebSocket, room: str = ""):
        # remove from user_connections
        self.user_connections[username].discard(websocket)
        if not self.user_connections[username]:
            self.user_connections.pop(username, None)

        self.lobby_connections[username].discard(websocket)
        if not self.lobby_connections[username]:
            self.lobby_connections.pop(username, None)

        # clean room_connections only when a real room is passed
        if room:
            self.room_connections[room].discard(websocket)
            if not self.room_connections[room]:
                self.room_connections.pop(room, None)

    async def online_users(self) -> list[str]:
        return sorted(self.user_connections.keys())

    async def notify_online_users(self):
        users = await self.online_users()
        message = f"online users: {', '.join(users) if users else 'none'}"

        for username, connections in list(self.lobby_connections.items()):
            dead: list[WebSocket] = []
            for ws in list(connections):
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self.disconnect(username, ws)

    async def send_to_room(self, room: str, message: str) -> bool:
        connections = self.room_connections.get(room)
        if not connections:
            return False

        dead: list[WebSocket] = []
        delivered = 0
        for ws in list(connections):
            try:
                await ws.send_text(message)
                delivered += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            username = next(
                (u for u, sockets in self.user_connections.items() if ws in sockets),
                None,
            )
            if username:
                self.disconnect(username, ws, room)

        return delivered > 0


manager = ConnectionManager()


@app.get("/users")
async def list_online_users():
    return {"users": await manager.online_users()}


@app.websocket("/ws/{username}")
async def lobby_endpoint(websocket: WebSocket, username: str):
    accepted = await manager.connect_lobby(username, websocket)
    if not accepted:
        return  # duplicate username — connection already closed inside connect_lobby

    await manager.notify_online_users()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # FIX BUG 1: no hardcoded room="lobby" — disconnect handles lobby cleanup
        manager.disconnect(username, websocket)
        await manager.notify_online_users()


@app.websocket("/ws/{username}/{recipient}")
async def websocket_endpoint(websocket: WebSocket, username: str, recipient: str):
    room = await manager.connect(username, recipient, websocket)
    await manager.send_to_room(room, f"private room started: {username} ↔ {recipient}")
    await manager.notify_online_users()

    try:
        await manager.send_to_room(
            room, f"online users: {', '.join(await manager.online_users())}"
        )
        while True:
            text = await websocket.receive_text()
            await manager.send_to_room(room, f"{username}: {text}")

    except WebSocketDisconnect:
        manager.disconnect(username, websocket, room)
        await manager.send_to_room(room, f"{username} left the private chat")
        await manager.notify_online_users()
