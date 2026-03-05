const API_BASE = "http://127.0.0.1:5000"; // <-- later replace with your HTTPS backend

const tg = window.Telegram?.WebApp;
tg?.ready?.();
tg?.expand?.();

const el = (id) => document.getElementById(id);
const avatar = el("avatar");
const username = el("username");
const sub = el("sub");
const balance = el("balance");
const refs = el("refs");
const earned = el("earned");
const percent = el("percent");
const reflink = el("reflink");
const statusPill = el("status");
const backendInfo = el("backendInfo");

backendInfo.textContent = `Backend: ${API_BASE}`;

function setStatus(ok, text){
  statusPill.textContent = text;
  statusPill.classList.remove("ok","bad");
  statusPill.classList.add(ok ? "ok" : "bad");
}

async function api(path, body){
  const res = await fetch(`${API_BASE}${path}`, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  const j = await res.json();
  if(!j.ok) throw new Error(j.error || "API error");
  return j;
}

async function loadMe(){
  const initData = tg?.initData || "";
  if(!initData){
    setStatus(false, "открой в Telegram");
    username.textContent = "Preview";
    sub.textContent = "@local";
    reflink.value = "Откройте в Telegram";
    return;
  }
  try{
    setStatus(true, "подключаемся…");
    const data = await api("/api/me", {initData});
    const u = data.user || {};
    username.textContent = u.first_name || "Пользователь";
    sub.textContent = u.username ? `@${u.username}` : "";
    avatar.src = u.photo_url || "assets/avatar.jpg";

    balance.textContent = String(data.balance ?? 0);
    refs.textContent = String(data.refs ?? 0);
    earned.textContent = String(data.earned ?? 0);
    percent.textContent = String(Math.round((data.ref_percent ?? 0.2)*100)) + "%";
    reflink.value = data.ref_link || "Укажите BOT_USERNAME на backend";

    setStatus(true, "онлайн");
  }catch(e){
    console.error(e);
    setStatus(false, "backend недоступен");
  }
}

async function buyStars(pack){
  const initData = tg?.initData || "";
  if(!initData) return;
  try{
    setStatus(true, "создаём инвойс…");
    const inv = await api("/api/invoice", {initData, pack});

    if(!tg?.openInvoice){
      alert("openInvoice не поддерживается в вашем Telegram клиенте");
      return;
    }

    tg.openInvoice(inv.url, (status) => {
      if(status === "paid"){
        setStatus(true, "оплачено ✅ обновляем…");
        setTimeout(loadMe, 1200);
      } else if(status === "cancelled"){
        setStatus(true, "отменено");
      } else {
        setStatus(false, "ошибка оплаты");
      }
    });
  }catch(e){
    console.error(e);
    setStatus(false, "ошибка инвойса");
    alert("Ошибка: " + e.message);
  }
}

document.querySelectorAll(".pack").forEach(btn => btn.addEventListener("click", () => buyStars(btn.dataset.pack)));
document.getElementById("fab")?.addEventListener("click", () => buyStars("50"));

document.getElementById("btnCopy")?.addEventListener("click", async () => {
  try{ await navigator.clipboard.writeText(reflink.value); } catch { reflink.select(); document.execCommand("copy"); }
});

document.getElementById("btnShare")?.addEventListener("click", () => {
  const link = reflink.value || "";
  if(tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}`);
  else window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}`, "_blank");
});

document.getElementById("btnInfo")?.addEventListener("click", () => {
  tg?.showPopup?.({ title:"AI Undress", message:"Пополнение через Telegram Stars. Рефералка 20% от пополнений.", buttons:[{id:"ok", type:"ok"}] });
});

loadMe();
