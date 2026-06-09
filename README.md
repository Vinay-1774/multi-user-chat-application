# Private Chat App

## Setup

```bash
git clone <your-repo-url>
cd websocket

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # edit .env with your values
```

## Run

**Terminal 1 — server:**
```bash
uvicorn main:app --reload
```

**Terminal 2 — you:**
```bash
python client.py
```

**Terminal 3 — another user:**
```bash
python client.py
```

## What Happens Next

1. Enter your username
2. You'll see a list of online users
3. Type a username to open a private chat with them
4. Start messaging

## Commands

| Command | Action |
|---------|--------|
| `/leave` | Exit current chat room |
| `/quit` | Close the app |