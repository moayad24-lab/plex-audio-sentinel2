import json, urllib.parse, urllib.request

def refresh_plex(url, token, section, timeout=15):
    if not (url and section): raise ValueError("PLEX_URL and PLEX_SECTION are required for refresh")
    endpoint=f"{url.rstrip('/')}/library/sections/{urllib.parse.quote(str(section), safe='')}/refresh"
    req=urllib.request.Request(endpoint, method="GET", headers={"X-Plex-Token":token} if token else {})
    with urllib.request.urlopen(req, timeout=timeout) as response: return response.status

def send_telegram(token, chat_id, text, timeout=15):
    if not (token and chat_id): return False
    endpoint=f"https://api.telegram.org/bot{token}/sendMessage"
    body=urllib.parse.urlencode({"chat_id":chat_id,"text":text}).encode()
    req=urllib.request.Request(endpoint, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data=json.loads(response.read().decode());
        if not data.get("ok"): raise RuntimeError("Telegram API rejected message")
    return True
