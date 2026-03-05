import os, json, secrets
import requests
from flask import Flask, request, jsonify, render_template, abort
from telegram_auth import verify_init_data, TelegramAuthError
import db

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME","").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD","").strip()
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY","").strip()
REF_PERCENT = float(os.environ.get("REF_PERCENT","0.2"))

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

app = Flask(__name__, template_folder="templates")
db.init_db()

STAR_PACKS = {"10": 10, "50": 50, "100": 100}

def _need_token():
    if not BOT_TOKEN:
        abort(500, "BOT_TOKEN is not set")

def _need_admin_key():
    if not ADMIN_API_KEY:
        abort(500, "ADMIN_API_KEY is not set")

def _user(data:dict)->dict:
    raw = data.get("user")
    if not raw:
        raise TelegramAuthError("Missing user")
    return json.loads(raw)

def _ref(start_param:str):
    if start_param.startswith("ref_") and start_param[4:].isdigit():
        return int(start_param[4:])
    return None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/me")
def me():
    _need_token()
    body = request.get_json(force=True, silent=True) or {}
    initData = body.get("initData","")
    try:
        data = verify_init_data(initData, BOT_TOKEN)
        u = _user(data)
    except TelegramAuthError as e:
        return jsonify({"ok": False, "error": str(e)}), 401

    uid = int(u["id"])
    db.upsert_user(uid, u.get("first_name",""), u.get("username",""), u.get("photo_url",""))

    sp = data.get("start_param") or ""
    r = _ref(sp) if sp else None
    if r:
        db.set_referrer_if_empty(uid, r)

    row = db.get_user(uid)
    refs, earned = db.get_stats(uid)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}" if BOT_USERNAME else ""

    return {"ok": True, "user": {"id": uid, "first_name": u.get("first_name",""), "username": u.get("username",""), "photo_url": u.get("photo_url","")},
            "balance": int(row["balance"]), "refs": refs, "earned": earned, "ref_percent": REF_PERCENT, "ref_link": ref_link}

@app.post("/api/invoice")
def invoice():
    _need_token()
    body = request.get_json(force=True, silent=True) or {}
    initData = body.get("initData","")
    pack = str(body.get("pack","10"))
    if pack not in STAR_PACKS:
        return {"ok": False, "error": "Unknown pack"}, 400

    try:
        data = verify_init_data(initData, BOT_TOKEN)
        u = _user(data)
    except TelegramAuthError as e:
        return {"ok": False, "error": str(e)}, 401

    uid = int(u["id"])
    db.upsert_user(uid, u.get("first_name",""), u.get("username",""), u.get("photo_url",""))

    amount = STAR_PACKS[pack]
    nonce = secrets.token_hex(8)
    payload = f"stars|uid:{uid}|pack:{pack}|nonce:{nonce}"

    inv = {
        "title": f"AI Undress — {amount}⭐",
        "description": f"Пополнение баланса на {amount} Stars",
        "payload": payload,
        "currency": "XTR",
        "prices": [{"label": f"{amount} Stars", "amount": amount}],
        "provider_token": "",
        "start_parameter": f"stars_{uid}_{nonce}"
    }

    resp = requests.post(TG_API + "/createInvoiceLink", json=inv, timeout=20)
    j = resp.json()
    if not j.get("ok"):
        return {"ok": False, "error": j.get("description","Telegram API error"), "details": j}, 400

    return {"ok": True, "url": j["result"], "amount": amount}

@app.post("/api/payment/confirm")
def payment_confirm():
    _need_admin_key()
    if request.headers.get("X-Admin-Key","") != ADMIN_API_KEY:
        return {"ok": False, "error": "Unauthorized"}, 401

    body = request.get_json(force=True, silent=True) or {}
    user_id = int(body.get("user_id", 0))
    amount = int(body.get("amount", 0))
    currency = str(body.get("currency",""))
    charge_id = str(body.get("telegram_payment_charge_id","")).strip()
    invoice_payload = str(body.get("invoice_payload",""))

    if user_id <= 0 or amount <= 0 or currency != "XTR" or not charge_id:
        return {"ok": False, "error": "Bad params"}, 400

    if not db.get_user(user_id):
        db.upsert_user(user_id, "", "", "")

    inserted = db.record_payment_if_new(charge_id, user_id, amount, currency)
    if not inserted:
        return {"ok": True, "already": True}

    db.add_balance(user_id, amount, "stars_deposit", meta=invoice_payload)

    row = db.get_user(user_id)
    referrer = row["referrer_id"]
    if referrer:
        bonus = int(amount * REF_PERCENT)
        if bonus > 0:
            db.add_balance(int(referrer), bonus, "ref_bonus", meta=f"from:{user_id}|charge:{charge_id}")

    return {"ok": True, "credited": True}

@app.get("/admin")
def admin():
    key = request.args.get("key","")
    if not ADMIN_PASSWORD or key != ADMIN_PASSWORD:
        abort(401, "Use /admin?key=YOUR_ADMIN_PASSWORD")
    return render_template("admin.html", users=db.list_users(), txs=db.list_tx())

if __name__ == "__main__":
    port = int(os.environ.get("PORT","5000"))
    app.run(host="0.0.0.0", port=port)
