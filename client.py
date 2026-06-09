"""
Terminal direct-message client
Usage: python client.py [username] [recipient]
"""

import asyncio
import json
import sys
from datetime import datetime
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlparse

import websockets

from config import settings


SERVER_URL = settings.SERVER_URL


def http_base_url(ws_url: str) -> str:
    parsed = urlparse(ws_url)
    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"


def fetch_online_users() -> list[str]:
    url = f"{http_base_url(SERVER_URL)}/users"
    try:
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        users = payload.get("users", [])
        return users if isinstance(users, list) else []
    except Exception as error:
        print(f"\n[could not fetch online users: {error}]")
        return []


async def choose_recipient(username:str) -> str:
    while True:
        users = [user for user in fetch_online_users() if user != username]

        if not users:
            print("\nNo online users right now. Waiting for someone to join...")
            await asyncio.sleep(3)
            continue

        print("\nOnline users:")
        for index, user in enumerate(users, start=1):
            print(f"  {index}. {user}")

        while True:
            selection = input("Select user by number or name: ").strip()
            if not selection:
                continue
            if selection.isdigit():
                index = int(selection) - 1
                if 0 <= index < len(users):
                    return users[index]
            if selection in users:
                return selection
            print("Invalid selection, try again.")


async def receive_messages(ws):
    """Continuously listen for incoming messages and print them."""
    try:
        async for message in ws:
            print(f"\r\033[K{message}")
            print("you → ", end="", flush=True)
    except websockets.exceptions.ConnectionClosedOK:
        print("\n[disconnected from server]")
    except Exception as e:
        print(f"\n[receive error: {e}]")


async def receive_lobby_messages(ws, show_roster: asyncio.Event):
    """Keep the lobby socket alive and show roster updates only while selecting."""
    try:
        async for message in ws:
            if show_roster.is_set() and message.startswith("online users:"):
                print(f"\n[{message}]")
                print("choose user → ", end="", flush=True)
    except Exception:
        pass


async def send_messages(ws, terminate: asyncio.Event):
    """Read stdin and send messages."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            text = await loop.run_in_executor(None, sys.stdin.readline)
            text = text.strip()
            if not text:
                continue
            if text.lower() in ("/leave", "/back"):
                print("[leaving chat...]")
                await ws.close()
                break
            if text.lower() in ("/quit", "/exit", "/q"):
                print("[quitting application...]")
                terminate.set()
                try:
                    await ws.close()
                except Exception:
                    pass
                break
            await ws.send(text)
            print("you → ", end="", flush=True)
    except (websockets.exceptions.ConnectionClosed, EOFError):
        pass


async def main():
    if len(sys.argv) > 1:
        username = sys.argv[1].strip()
    else:
        username = input("Enter your username: ").strip()
        if not username:
            username = f"user_{datetime.now().strftime('%H%M%S')}"

    lobby_url = f"{SERVER_URL}/{username}"

    try:
        async with websockets.connect(lobby_url) as lobby_ws:
            show_roster = asyncio.Event()
            show_roster.set()
            lobby_task = asyncio.create_task(receive_lobby_messages(lobby_ws, show_roster))

            while True:
                show_roster.set()
                print("\nPick a user to open a private room with.")
                if len(sys.argv) > 2:
                    recipient = sys.argv[2].strip()
                    sys.argv = sys.argv[:2]
                else:
                    recipient = await choose_recipient(username)

                if not recipient:
                    print("recipient is required")
                    continue

                show_roster.clear()
                url = f"{SERVER_URL}/{username}/{recipient}"
                print(f"\nConnecting as '{username}'  →  {url}")
                print("Type /back or /leave to exit the room and choose another user\n")
                print("Type /quit to exit the application\n")

                try:
                    async with websockets.connect(url) as ws:
                        terminate = asyncio.Event()
                        receive_task = asyncio.create_task(receive_messages(ws))
                        send_task = asyncio.create_task(send_messages(ws, terminate))

                        print("you → ", end="", flush=True)

                        done, pending = await asyncio.wait(
                            [receive_task, send_task],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in pending:
                            task.cancel()
                except ConnectionRefusedError:
                    print("Could not connect. Is the server running?  (uvicorn main:app)")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"Error: {e}")
                    await asyncio.sleep(1)

                # if user requested full quit, break outer loop and close lobby
                if 'terminate' in locals() and terminate.is_set():
                    lobby_task.cancel()
                    return

            lobby_task.cancel()

    except ConnectionRefusedError:
        print("Could not connect. Is the server running?  (uvicorn main:app)")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
