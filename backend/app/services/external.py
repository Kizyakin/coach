import httpx
from app.core.config import settings

async def chesscom_games(username: str, limit: int = 20):
    headers={"User-Agent":settings.chesscom_user_agent, "Accept":"application/json"}
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        r=await client.get(f"https://api.chess.com/pub/player/{username}/games/archives")
        r.raise_for_status(); archives=r.json().get("archives", [])
        games=[]
        for url in reversed(archives):
            rr=await client.get(url); rr.raise_for_status()
            games.extend(reversed(rr.json().get("games", [])))
            if len(games)>=limit: break
    result=[]
    for g in games[:limit]:
        result.append({"id":g.get("uuid") or g.get("url"),"pgn":g.get("pgn"),"url":g.get("url"),"time_class":g.get("time_class"),"white":g.get("white"),"black":g.get("black"),"eco":g.get("eco")})
    return result

async def lichess_games(username: str, limit: int = 20):
    headers={"Accept":"application/x-ndjson"}
    params={"max":limit,"pgnInJson":"true","clocks":"false","evals":"false","opening":"true"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        r=await client.get(f"https://lichess.org/api/games/user/{username}", params=params)
        r.raise_for_status()
    rows=[]
    for line in r.text.splitlines():
        if not line.strip(): continue
        import json
        g=json.loads(line)
        rows.append({"id":g.get("id"),"pgn":g.get("pgn"),"players":g.get("players"),"opening":g.get("opening"),"speed":g.get("speed"),"createdAt":g.get("createdAt")})
    return rows
