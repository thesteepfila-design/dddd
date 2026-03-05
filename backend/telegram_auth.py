import hmac, hashlib, time
from urllib.parse import parse_qsl

class TelegramAuthError(Exception):
    pass

def _dcs(init_data: str) -> str:
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = {k: v for k, v in pairs}
    data.pop("hash", None)
    return "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))

def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    if not init_data:
        raise TelegramAuthError("Missing initData")
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = {k: v for k, v in pairs}
    received_hash = data.get("hash")
    auth_date = data.get("auth_date")
    if not received_hash or not auth_date:
        raise TelegramAuthError("initData missing hash/auth_date")
    if int(time.time()) - int(auth_date) > max_age_seconds:
        raise TelegramAuthError("initData expired")
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, _dcs(init_data).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise TelegramAuthError("Bad initData hash")
    return data
