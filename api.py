import requests

def fetch_season7_entry(name: str, platform: str = "crossplay", timeout: float = 5.0):
    """
    Return the first Season 7 leaderboard entry for this Embark name,
    or None if not found. Raises on non‑200 or timeout.
    """
    url  = f"https://api.the-finals-leaderboard.com/v1/leaderboard/s7/{platform}"
    resp = requests.get(url, params={"name": name}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None
