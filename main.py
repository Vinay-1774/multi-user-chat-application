from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


def pair_room(username: str, recipient: str) -> str:
    first, second = sorted([username, recipient])
    return f"room:{first}:{second}"


class ConnectionManager:
    def __init__(self):
        self.user_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.lobby_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.room_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, username: str, recipient: str, websocket: WebSocket):
        await websocket.accept()
        room = pair_room(username, recipient)
        self.user_connections[username].add(websocket)
        self.room_connections[room].add(websocket)
        return room

    async def connect_lobby(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.user_connections[username].add(websocket)
        self.lobby_connections[username].add(websocket)

    def disconnect(self, username: str, room: str, websocket: WebSocket):
        user_room = self.user_connections.get(username)
        if user_room:
            user_room.discard(websocket)
            if not user_room:
                self.user_connections.pop(username, None)

        lobby_room = self.lobby_connections.get(username)
        if lobby_room:
            lobby_room.discard(websocket)
            if not lobby_room:
                self.lobby_connections.pop(username, None)

        room_connections = self.room_connections.get(room)
        if room_connections:
            room_connections.discard(websocket)
            if not room_connections:
                self.room_connections.pop(room, None)

    async def online_users(self) -> list[str]:
        return sorted(self.user_connections.keys())

    async def notify_online_users(self):
        users = await self.online_users()
        message = f"online users: {', '.join(users) if users else 'none'}"

        for username, connections in list(self.lobby_connections.items()):
            dead_connections = []
            for websocket in list(connections):
                try:
                    await websocket.send_text(message)
                except Exception:
                    dead_connections.append(websocket)

            for websocket in dead_connections:
                room = next((room_name for room_name, room_connections in self.room_connections.items() if websocket in room_connections), None)
                if room:
                    self.disconnect(username, room, websocket)

    async def send_to_room(self, room: str, message: str) -> bool:
        connections = self.room_connections.get(room)
        if not connections:
            return False

        dead_connections = []
        for websocket in list(connections):
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.append(websocket)

        for websocket in dead_connections:
            username = next((user for user, user_connections in self.user_connections.items() if websocket in user_connections), None)
            if username is not None:
                self.disconnect(username, room, websocket)

        return True


manager = ConnectionManager()


@app.get("/users")
async def list_online_users():
    return {"users": await manager.online_users()}


@app.websocket("/ws/{username}")
async def lobby_endpoint(websocket: WebSocket, username: str):
    await manager.connect_lobby(username, websocket)
    await manager.notify_online_users()

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(username, room="lobby", websocket=websocket)
        await manager.notify_online_users()


@app.websocket("/ws/{username}/{recipient}")
async def websocket_endpoint(websocket: WebSocket, username: str, recipient: str):
    room = await manager.connect(username, recipient, websocket)
    await manager.send_to_room(room, f"private room started: {username} and {recipient}")
    await manager.notify_online_users()

    try:
        await manager.send_to_room(room, f"online users: {', '.join(await manager.online_users())}")

        while True:
            text = await websocket.receive_text()
            await manager.send_to_room(room, f"{username}: {text}")

    except WebSocketDisconnect:
        manager.disconnect(username, room, websocket)
        await manager.send_to_room(room, f"{username} left the private chat")
        await manager.notify_online_users()
