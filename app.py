"""Ece Cafe — boutique cafe ordering app for Streamlit Community Cloud.

Menu content lives in menu.json (+ images/). Edit those on GitHub; no code changes needed.

Flow: browse menu -> checkout page -> animated "processing" -> success screen with confetti.
Payment is a mock: no card data is collected or sent anywhere.
"""

import base64
import html
import json
import mimetypes
import random
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).parent.resolve()
MENU_FILE = BASE_DIR / "menu.json"

st.set_page_config(page_title="Ece Cafe", page_icon="☕", layout="wide")

# ----------------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------------
BLUSH = "#FFE5EC"       # page background
CHAMPAGNE = "#FFC2D1"   # cards, cart, containers
PASTEL = "#FFB3C6"      # borders, dividers, inactive pills
LIGHT = "#FF8FAB"       # secondary buttons, hover, price tags
WATERMELON = "#FB6F92"  # primary CTAs, active pills, headings
ESPRESSO = "#3D1E26"    # primary text
EMERALD = "#2ECC71"     # payment success
GOLD = "#F4C95D"        # confetti coins only

TOKENS = {
    "BLUSH": BLUSH, "CHAMP": CHAMPAGNE, "PASTEL": PASTEL, "LIGHT": LIGHT,
    "WM": WATERMELON, "ESP": ESPRESSO, "EMER": EMERALD, "GOLD": GOLD,
}


def themed(text: str) -> str:
    """Swap @@TOKEN@@ placeholders for palette colors (keeps CSS/JS free of brace-escaping)."""
    for key, value in TOKENS.items():
        text = text.replace(f"@@{key}@@", value)
    return text


TIP_OPTIONS = {"No tip": 0, "10%": 10, "15%": 15, "20%": 20}
ORDER_TYPES = ["Pickup", "Dine in"]
PAY_METHODS = ["Card", "Tap to Pay"]


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_menu() -> list[dict]:
    """Read menu.json. Short TTL so GitHub updates show up within ~a minute."""
    try:
        raw = json.loads(MENU_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = []
    for entry in raw if isinstance(raw, list) else raw.get("items", []):
        try:
            items.append(
                {
                    "id": str(entry["id"]),
                    "name": str(entry["name"]),
                    "category": str(entry.get("category", "Other")),
                    "special_tags": [str(t) for t in entry.get("special_tags", [])],
                    "price": float(entry["price"]),
                    "description": str(entry.get("description", "")),
                    "image": str(entry.get("image", "")),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed entries instead of crashing the app
    return items


PLACEHOLDER_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'>"
    f"<rect width='400' height='300' fill='{PASTEL}'/>"
    f"<g fill='none' stroke='{ESPRESSO}' stroke-width='6' stroke-linecap='round' opacity='.55'>"
    "<path d='M140 130h110v50a45 45 0 0 1-45 45h-20a45 45 0 0 1-45-45z'/>"
    "<path d='M250 145h18a22 22 0 0 1 0 44h-22'/>"
    "<path d='M175 100c-8-10 8-18 0-28M210 100c-8-10 8-18 0-28'/></g></svg>"
)
PLACEHOLDER_URI = "data:image/svg+xml;base64," + base64.b64encode(PLACEHOLDER_SVG.encode()).decode()


@st.cache_data(ttl=60)
def image_src(image: str) -> str:
    """Return a src usable in <img>: external URL, base64 local file, or placeholder."""
    image = (image or "").strip()
    if not image:
        return PLACEHOLDER_URI
    if image.startswith(("http://", "https://", "data:")):
        return image
    path = (BASE_DIR / image).resolve()
    try:
        path.relative_to(BASE_DIR)  # keep reads inside the repo
        data = path.read_bytes()
    except (ValueError, OSError):
        return PLACEHOLDER_URI
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def money(value: float) -> str:
    return f"${value:,.2f}"


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("cart", {})             # {item_id: qty}
    ss.setdefault("stage", "browse")      # browse | checkout | processing | success
    ss.setdefault("celebrate", False)     # fire confetti once
    ss.setdefault("receipt", None)
    ss.setdefault("sel_cats", [])
    ss.setdefault("sel_tags", [])
    ss.setdefault("co_type", ORDER_TYPES[0])
    ss.setdefault("co_tip", "10%")
    ss.setdefault("co_method", PAY_METHODS[0])
    ss.setdefault("cart_open", False)     # mobile cart bottom sheet


def open_cart():
    st.session_state.cart_open = True


def close_cart():
    st.session_state.cart_open = False


def go_checkout():
    st.session_state.cart_open = False
    st.session_state.stage = "checkout"


def toggle(key: str, value: str):
    sel = st.session_state[key]
    if value in sel:
        sel.remove(value)
    else:
        sel.append(value)


def clear_filters():
    st.session_state.sel_cats = []
    st.session_state.sel_tags = []


def set_value(key: str, value):
    st.session_state[key] = value


def add_item(item_id: str, name: str):
    cart = st.session_state.cart
    cart[item_id] = cart.get(item_id, 0) + 1
    st.toast(f"{name} added to your bag", icon="☕")


def change_qty(item_id: str, delta: int):
    cart = st.session_state.cart
    qty = cart.get(item_id, 0) + delta
    if qty <= 0:
        cart.pop(item_id, None)
    else:
        cart[item_id] = qty


def remove_item(item_id: str):
    st.session_state.cart.pop(item_id, None)


def start_payment(lines: list, subtotal: float, tip: float, total: float):
    st.session_state.receipt = {
        "lines": lines,
        "subtotal": subtotal,
        "tip": tip,
        "total": total,
        "order_no": f"EC-{random.randint(1000, 9999)}",
        "name": (st.session_state.get("field_name") or "").strip(),
        "type": st.session_state.co_type,
        "method": st.session_state.co_method,
    }
    st.session_state.stage = "processing"


def finish_payment():
    st.session_state.stage = "success"
    st.session_state.celebrate = True
    st.session_state.cart = {}


def new_order():
    st.session_state.cart_open = False
    st.session_state.cart = {}
    st.session_state.stage = "browse"
    st.session_state.celebrate = False
    st.session_state.receipt = None


def cart_lines(menu: list[dict]):
    by_id = {i["id"]: i for i in menu}
    lines = [(by_id[i], q) for i, q in st.session_state.cart.items() if i in by_id]
    subtotal = sum(item["price"] * qty for item, qty in lines)
    return lines, subtotal


# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* ---------- keyframes ---------- */
@keyframes fadeUp   { from { opacity: 0; translate: 0 20px; } to { opacity: 1; translate: 0 0; } }
@keyframes fadeIn   { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideIn  { from { opacity: 0; translate: 24px 0; } to { opacity: 1; translate: 0 0; } }
@keyframes popIn    { 0% { scale: .6; opacity: 0; } 60% { scale: 1.12; opacity: 1; } 100% { scale: 1; } }
@keyframes bumpA    { 0% { scale: 1; } 40% { scale: 1.35; } 100% { scale: 1; } }
@keyframes bumpB    { 0% { scale: 1; } 40% { scale: 1.35; } 100% { scale: 1; } }
@keyframes wiggle   { 0%,100% { rotate: 0deg; } 25% { rotate: -5deg; } 75% { rotate: 5deg; } }
@keyframes drawLine { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes steam    { 0% { opacity: 0; translate: 0 8px; } 40% { opacity: .85; } 100% { opacity: 0; translate: 0 -14px; } }
@keyframes bob      { 0%,100% { translate: 0 0; } 50% { translate: 0 -6px; } }
@keyframes ticker   { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes sheen    { 0% { left: -60%; } 55%,100% { left: 140%; } }
@keyframes payPulse { 0% { box-shadow: 0 0 0 0 @@WM@@88; } 70% { box-shadow: 0 0 0 16px @@WM@@00; } 100% { box-shadow: 0 0 0 0 @@WM@@00; } }
@keyframes frameBusy { 0%,100% { border-color: @@PASTEL@@; } 50% { border-color: @@WM@@; } }
@keyframes frameIn  { from { border-color: @@PASTEL@@; box-shadow: inset 0 0 0 transparent; }
                      to { border-color: @@EMER@@; box-shadow: inset 0 0 60px @@EMER@@88, inset 0 0 0 2px @@EMER@@; } }
@keyframes frameGlow { from { box-shadow: inset 0 0 40px @@EMER@@66, inset 0 0 0 2px @@EMER@@; }
                       to { box-shadow: inset 0 0 80px @@EMER@@aa, inset 0 0 0 2px @@EMER@@; } }
@keyframes glow     { from { box-shadow: 0 0 0 3px @@EMER@@33, 0 0 16px @@EMER@@77; }
                      to { box-shadow: 0 0 0 6px @@EMER@@55, 0 0 38px @@EMER@@bb; } }
@keyframes ringPulse { 0% { scale: 1; opacity: .55; } 100% { scale: 1.9; opacity: 0; } }
@keyframes tick     { to { stroke-dashoffset: 0; } }
@keyframes receiptIn { from { opacity: 0; translate: 0 -40px; rotate: -2deg; } to { opacity: 1; translate: 0 0; rotate: 0deg; } }
@keyframes barFill  { from { width: 0; } to { width: 100%; } }
@keyframes stepOn   { from { opacity: .35; translate: -6px 0; } to { opacity: 1; translate: 0 0; } }
@keyframes dotOn    { from { background: @@PASTEL@@; } to { background: @@WM@@; } }
@keyframes dotPulse { 0% { box-shadow: 0 0 0 0 @@WM@@88; } 100% { box-shadow: 0 0 0 10px @@WM@@00; } }
@keyframes lineFill { from { width: 0; } to { width: 100%; } }
@keyframes tapRing  { 0% { scale: .4; opacity: .9; } 100% { scale: 1.6; opacity: 0; } }

/* ---------- strip Streamlit chrome ---------- */
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stHeader"] { display: none !important; }
.stApp { background: @@BLUSH@@; }
.block-container { padding: 1.6rem 2.6rem 4rem; max-width: 1280px; }
html, body, .stApp, p, span, label, div, button, input {
    font-family: 'Plus Jakarta Sans', sans-serif; color: @@ESP@@;
}
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3, h4 { font-family: 'Fraunces', serif !important; color: @@ESP@@; letter-spacing: -0.01em; }

/* ---------- masthead ---------- */
.masthead { padding: .4rem 0 1rem; animation: fadeUp .7s cubic-bezier(.2,.7,.3,1) backwards; }
.masthead-row { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; }
.brand { position: relative; display: inline-block; font-family: 'Fraunces', serif; font-weight: 600; font-size: 3.1rem;
    line-height: 1; color: @@WM@@; letter-spacing: -0.02em; }
.brand em { font-style: italic; font-weight: 500; color: @@ESP@@; }
.steam { position: absolute; right: -34px; top: -22px; width: 30px; height: 34px; }
.steam path { fill: none; stroke: @@WM@@; stroke-width: 3; stroke-linecap: round; opacity: 0; animation: steam 2.8s ease-in-out infinite; }
.steam path:nth-child(2) { animation-delay: .9s; } .steam path:nth-child(3) { animation-delay: 1.8s; }
.tagline { margin-top: .55rem; font-size: .95rem; opacity: .75; letter-spacing: .02em; }
.bag { display: flex; align-items: center; gap: .55rem; background: @@CHAMP@@; border: 1.5px solid @@PASTEL@@;
    border-radius: 999px; padding: .4rem .5rem .4rem .9rem; font-weight: 700; font-size: .88rem; }
.bag svg { width: 20px; height: 20px; stroke: @@ESP@@; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.bag-count { background: @@WM@@; min-width: 1.6rem; height: 1.6rem; border-radius: 999px; display: inline-flex;
    align-items: center; justify-content: center; font-size: .8rem; }
.bag-count.a { animation: bumpA .45s; } .bag-count.b { animation: bumpB .45s; }

.ticker { overflow: hidden; border-top: 1.5px solid @@PASTEL@@; border-bottom: 1.5px solid @@PASTEL@@;
    margin: .6rem 0 1.4rem; padding: .5rem 0; animation: fadeIn 1.2s .3s backwards; }
.ticker-track { display: flex; width: max-content; animation: ticker 32s linear infinite; }
.ticker:hover .ticker-track { animation-play-state: paused; }
.ticker-track span { font-family: 'Fraunces', serif; font-style: italic; font-size: .98rem; white-space: nowrap; padding: 0 1.1rem; }
.ticker-track i { font-style: normal; color: @@WM@@; }

.filter-label, .co-label { font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
    margin: .5rem 0 .35rem; opacity: .7; }
.cat-heading { position: relative; font-family: 'Fraunces', serif; font-size: 1.7rem; font-weight: 600; color: @@WM@@;
    margin: 1.6rem 0 .6rem; padding-bottom: .35rem; border-bottom: 1.5px solid @@PASTEL@@;
    animation: fadeUp .6s cubic-bezier(.2,.7,.3,1) backwards; }
.cat-heading::after { content: ""; position: absolute; left: 0; bottom: -2px; height: 3px; width: 72px; border-radius: 2px;
    background: @@WM@@; transform-origin: left; animation: drawLine .9s .25s cubic-bezier(.2,.7,.3,1) backwards; }

/* ---------- buttons (base = secondary) ---------- */
.stButton > button {
    position: relative; overflow: hidden; border-radius: 12px; border: 1.5px solid transparent; font-weight: 600;
    font-size: .92rem; padding: .5rem 1rem; box-shadow: none;
    transition: transform .15s ease, background-color .25s ease, border-color .25s ease, box-shadow .25s ease;
}
.stButton > button p { color: inherit; font-weight: inherit; margin: 0; }
.stButton > button:hover { transform: translateY(-2px); }
.stButton > button:active { transform: scale(.94); }
.stButton > button::after { content: ""; position: absolute; top: 0; left: -120%; width: 55%; height: 100%;
    background: rgba(255,255,255,.38); transform: skewX(-20deg); transition: left .65s ease; pointer-events: none; }
.stButton > button:hover::after { left: 150%; }
[data-testid="stBaseButton-secondary"] { background: @@LIGHT@@; color: @@ESP@@; }
[data-testid="stBaseButton-secondary"]:hover { background: @@WM@@; border-color: @@ESP@@22; color: @@ESP@@; }
[data-testid="stBaseButton-primary"] { background: @@WM@@; color: @@ESP@@; }
[data-testid="stBaseButton-primary"]:hover { background: @@LIGHT@@; border-color: @@ESP@@33; color: @@ESP@@; }
.stButton > button:disabled { opacity: .45; }

/* ---------- filter / choice pills ---------- */
[class*="st-key-pills_"] { display: flex !important; flex-direction: row !important; flex-wrap: wrap; gap: .5rem !important; }
[class*="st-key-pills_"] > div { width: auto !important; flex: 0 0 auto; }
[class*="st-key-pill_"] button { border-radius: 999px; padding: .38rem 1.05rem; font-size: .86rem; }
[class*="st-key-pill_"] [data-testid="stBaseButton-secondary"] { background: @@PASTEL@@; }
[class*="st-key-pill_"] [data-testid="stBaseButton-secondary"]:hover { background: @@LIGHT@@; }
[class*="st-key-pill_"] [data-testid="stBaseButton-primary"] { background: @@WM@@; animation: popIn .35s cubic-bezier(.2,.7,.3,1); }

/* ---------- menu cards ---------- */
[class*="st-key-card_"] {
    background: @@CHAMP@@; border: 1.5px solid @@PASTEL@@; border-radius: 20px; padding: .8rem .8rem 1rem;
    transition: transform .3s cubic-bezier(.2,.7,.3,1), border-color .3s ease; gap: 1rem !important; padding-bottom: 1.3rem;
    animation: fadeUp .7s cubic-bezier(.2,.7,.3,1) backwards;
}
[data-testid="stColumn"]:nth-child(2) [class*="st-key-card_"] { animation-delay: .1s; }
[class*="st-key-card_"]:hover { transform: translateY(-6px); border-color: @@WM@@; }
.img-wrap { overflow: hidden; border-radius: 14px; }
.card-img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; transition: transform .7s cubic-bezier(.2,.7,.3,1); }
[class*="st-key-card_"]:hover .card-img { transform: scale(1.08); }
[class*="st-key-card_"]:hover .price-tag { animation: wiggle .55s; }
.card-top { display: flex; justify-content: space-between; align-items: baseline; gap: .6rem; margin-top: .55rem; }
.card-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.28rem; line-height: 1.2; }
.price-tag { background: @@LIGHT@@; font-weight: 700; font-size: .9rem; padding: .15rem .6rem; border-radius: 999px; white-space: nowrap; }
.card-desc { font-size: .88rem; line-height: 1.5; opacity: .85; margin: .35rem 0 .1rem; }
.chips { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .6rem; margin-bottom: .5rem; min-height: 1.4rem; }
.chip { font-size: .68rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
    border: 1.3px solid @@ESP@@55; border-radius: 999px; padding: .08rem .5rem; transition: background .25s, border-color .25s; }
.chip:hover { background: @@PASTEL@@; border-color: @@ESP@@; }

/* ---------- panels (cart / checkout / hero) ---------- */
[data-testid="stColumn"]:has([class*="st-key-cart_panel"]) { position: sticky; top: 1.2rem; align-self: flex-start; }
[class*="st-key-cart_panel"], [class*="st-key-panel_"] {
    background: @@CHAMP@@; border: 1.5px solid @@PASTEL@@; border-radius: 22px; padding: 1.3rem 1.2rem 1.4rem;
    gap: .55rem !important; animation: fadeUp .7s cubic-bezier(.2,.7,.3,1) backwards; position: relative;
}
/* cart rows stay on one line even on narrow phones (Streamlit would otherwise stack the columns) */
[class*="st-key-cart_panel"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: .35rem !important; }
[class*="st-key-cart_panel"] [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
[class*="st-key-cart_panel"] [data-testid="stColumn"]:nth-child(5) { flex: 2.2 1 0 !important; }
.sheet-handle, [class*="st-key-sheet_close"], [class*="st-key-fab_cart"] { display: none; }
[class*="st-key-panel_summary"] { animation-delay: .12s; }
.cart-title, .panel-title { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 600; color: @@WM@@; margin-bottom: .2rem; }
.cart-empty { text-align: center; font-size: .92rem; opacity: .8; padding: .8rem 0 .4rem; }
.cart-empty svg { width: 64px; height: 64px; display: block; margin: 0 auto .5rem; animation: bob 3.2s ease-in-out infinite;
    stroke: @@ESP@@; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; opacity: .7; }
.cart-name { font-weight: 600; font-size: .92rem; line-height: 1.25; }
.cart-sub { font-size: .8rem; opacity: .75; }
.cart-line-total { font-weight: 700; font-size: .92rem; text-align: right; }
.cart-divider { border: 0; border-top: 1.5px dashed @@PASTEL@@; margin: .5rem 0; }
.cart-total { display: flex; justify-content: space-between; font-family: 'Fraunces', serif; font-size: 1.45rem; font-weight: 600; }
.cart-total span:last-child.a { display: inline-block; animation: bumpA .45s; }
.cart-total span:last-child.b { display: inline-block; animation: bumpB .45s; }
.sum-row { display: flex; justify-content: space-between; font-size: .92rem; padding: .12rem 0; }
[class*="st-key-cart_panel"] [data-testid="stHorizontalBlock"] { align-items: center; animation: slideIn .45s cubic-bezier(.2,.7,.3,1) backwards; }
[class*="st-key-cart_"] [data-testid="stBaseButton-secondary"] { padding: .15rem .3rem; min-height: 0; font-size: .9rem; }

[class*="st-key-bigbtn_"] button { width: 100%; padding: .85rem 1rem; font-size: 1.05rem; border-radius: 14px; }
[class*="st-key-bigbtn_pay"] button, [class*="st-key-bigbtn_checkout"] button { animation: payPulse 2.2s ease-out infinite; }

/* inputs */
[data-baseweb="input"] { background: @@BLUSH@@ !important; border: 1.5px solid @@PASTEL@@ !important; border-radius: 12px !important;
    transition: border-color .25s, box-shadow .25s; }
[data-baseweb="input"]:focus-within { border-color: @@WM@@ !important; box-shadow: 0 0 0 4px @@WM@@33; }
[data-baseweb="input"] input { background: transparent !important; color: @@ESP@@ !important; }
[data-testid="stTextInput"] label p { font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; opacity: .7; }

/* toast */
[data-testid="stToast"] { background: @@CHAMP@@ !important; border: 1.5px solid @@PASTEL@@; border-radius: 14px; }
[data-testid="stToast"] * { color: @@ESP@@ !important; }

/* ---------- checkout ---------- */
.co-heading { font-family: 'Fraunces', serif; font-size: 2.1rem; font-weight: 600; color: @@WM@@; margin: .2rem 0 .1rem;
    animation: fadeUp .6s cubic-bezier(.2,.7,.3,1) backwards; }
.co-sub { opacity: .75; font-size: .95rem; margin-bottom: 1rem; animation: fadeUp .6s .08s cubic-bezier(.2,.7,.3,1) backwards; }
.vcard { position: relative; overflow: hidden; border-radius: 18px; padding: 1.1rem 1.25rem; background: @@WM@@; max-width: 350px;
    aspect-ratio: 1.586; display: flex; flex-direction: column; justify-content: space-between; margin-top: .6rem;
    animation: popIn .6s cubic-bezier(.2,.7,.3,1), bob 5s 1s ease-in-out infinite; border: 1.5px solid @@ESP@@22; }
.vcard::after { content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
    background: rgba(255,255,255,.3); transform: skewX(-20deg); animation: sheen 4.5s ease-in-out infinite; }
.vcard .v-top { display: flex; justify-content: space-between; align-items: center; font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.1rem; }
.vcard .v-chip { width: 40px; height: 29px; border-radius: 6px; background: @@PASTEL@@; border: 1.5px solid @@ESP@@55; }
.vcard .v-num { font-weight: 700; letter-spacing: .2em; font-size: 1.05rem; }
.vcard .v-bot { display: flex; justify-content: space-between; font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.tapcard { position: relative; max-width: 350px; aspect-ratio: 1.586; margin-top: .6rem; border-radius: 18px; background: @@BLUSH@@;
    border: 1.5px dashed @@WM@@; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .6rem;
    animation: popIn .6s cubic-bezier(.2,.7,.3,1); }
.tap-wrap { position: relative; width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; }
.tap-wrap b { position: absolute; inset: 0; border: 3px solid @@WM@@; border-radius: 50%; animation: tapRing 2s ease-out infinite; }
.tap-wrap b:nth-child(2) { animation-delay: .65s; } .tap-wrap b:nth-child(3) { animation-delay: 1.3s; }
.tap-wrap i { width: 16px; height: 16px; border-radius: 50%; background: @@WM@@; }
.tapcard span { font-weight: 700; font-size: .9rem; }
.demo-note { font-size: .76rem; opacity: .7; margin-top: .5rem; }
.secure-note { text-align: center; font-size: .78rem; opacity: .7; margin-top: .4rem; }

/* ---------- processing overlay ---------- */
.proc { position: fixed; inset: 0; z-index: 10001; display: flex; align-items: center; justify-content: center;
    background: @@BLUSH@@ee; backdrop-filter: blur(6px); animation: fadeIn .35s; }
.proc-box { width: min(420px, 88vw); background: @@CHAMP@@; border: 1.5px solid @@PASTEL@@; border-radius: 26px; padding: 2rem 2rem 1.8rem;
    text-align: center; animation: popIn .5s cubic-bezier(.2,.7,.3,1); }
.ring { width: 64px; height: 64px; margin: 0 auto 1.1rem; border-radius: 50%; border: 5px solid @@PASTEL@@; border-top-color: @@WM@@;
    animation: spin .9s linear infinite; }
.proc-title { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 600; margin-bottom: 1rem; }
.proc-steps { text-align: left; display: grid; gap: .5rem; margin: 0 auto 1.2rem; width: fit-content; }
.proc-steps div { font-size: .95rem; font-weight: 600; opacity: .35; animation: stepOn .4s ease forwards; }
.proc-steps div::before { content: "✓ "; color: @@EMER@@; font-weight: 700; }
.proc-steps div:nth-child(1) { animation-delay: .2s; } .proc-steps div:nth-child(2) { animation-delay: 1s; } .proc-steps div:nth-child(3) { animation-delay: 1.8s; }
.proc-bar { height: 8px; border-radius: 999px; background: @@PASTEL@@; overflow: hidden; }
.proc-bar i { display: block; height: 100%; background: @@WM@@; border-radius: 999px; animation: barFill 2.7s cubic-bezier(.45,.05,.3,1) forwards; }

/* ---------- frame ---------- */
.frame { position: fixed; inset: 0; pointer-events: none; z-index: 9998; border: 10px solid @@PASTEL@@;
    transition: border-color .9s ease, box-shadow .9s ease; }
.frame.busy { animation: frameBusy 1.2s ease-in-out infinite; }
.frame.paid { border-color: @@EMER@@; box-shadow: inset 0 0 60px @@EMER@@88, inset 0 0 0 2px @@EMER@@;
    animation: frameIn 1.1s ease both, frameGlow 2.4s 1.1s ease-in-out infinite alternate; }

/* ---------- success ---------- */
.success-banner { background: @@EMER@@; font-weight: 700; text-align: center; padding: 1rem 1.4rem; border-radius: 16px;
    margin-bottom: 1.4rem; font-size: 1.12rem; animation: popIn .6s cubic-bezier(.2,.7,.3,1), glow 2.2s .6s ease-in-out infinite alternate; }
.hero { text-align: center; padding: .6rem 0 .2rem; }
.check-wrap { position: relative; width: 120px; height: 120px; margin: .4rem auto 1rem; }
.check-wrap::before, .check-wrap::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 3px solid @@EMER@@;
    animation: ringPulse 2.4s ease-out infinite; }
.check-wrap::after { animation-delay: 1.2s; }
.check { position: relative; width: 120px; height: 120px; z-index: 1; }
.check .c-bg { fill: @@EMER@@; transform-box: fill-box; transform-origin: center; animation: popIn .6s cubic-bezier(.2,.7,.3,1) backwards; }
.check .c-tick { fill: none; stroke: #fff; stroke-width: 9; stroke-linecap: round; stroke-linejoin: round;
    stroke-dasharray: 90; stroke-dashoffset: 90; animation: tick .6s .5s ease forwards; }
.hero-title { font-family: 'Fraunces', serif; font-size: 2.2rem; font-weight: 600; animation: fadeUp .6s .5s backwards; }
.hero-sub { font-size: 1rem; margin-top: .2rem; animation: fadeUp .6s .65s backwards; }
.eta { display: inline-block; margin: .9rem 0 1.4rem; background: @@BLUSH@@; border: 1.5px solid @@PASTEL@@; border-radius: 999px;
    padding: .35rem 1rem; font-weight: 700; font-size: .88rem; animation: fadeUp .6s .8s backwards; }
.track { display: flex; align-items: flex-start; justify-content: center; margin: .2rem 0 1.4rem; animation: fadeUp .6s .95s backwards; }
.t-step { display: flex; flex-direction: column; align-items: center; gap: .4rem; width: 92px; font-size: .74rem; font-weight: 700; }
.t-step .dot { width: 20px; height: 20px; border-radius: 50%; background: @@PASTEL@@; }
.t-step.done .dot { background: @@EMER@@; animation: popIn .5s 1s backwards; }
.t-step.now .dot { animation: dotOn .4s 1.8s forwards, dotPulse 1.5s 2.2s ease-out infinite; }
.t-line { flex: 1; max-width: 70px; height: 4px; margin-top: 8px; border-radius: 2px; background: @@PASTEL@@; overflow: hidden; }
.t-line i { display: block; height: 100%; width: 0; background: @@EMER@@; animation: lineFill .7s 1.1s ease forwards; }
.receipt { background: @@CHAMP@@; border: 1.5px solid @@PASTEL@@; border-bottom: 0; border-radius: 20px 20px 0 0; padding: 1.4rem 1.3rem 1rem;
    animation: receiptIn .9s .3s cubic-bezier(.2,.7,.3,1) backwards; transform-origin: top center; }
.r-head { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 600; color: @@WM@@; text-align: center; }
.r-meta { text-align: center; font-size: .78rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; opacity: .75; margin-bottom: .3rem; }
.r-line { display: flex; justify-content: space-between; gap: .8rem; font-size: .92rem; padding: .18rem 0; animation: fadeUp .5s backwards; }
.r-total { display: flex; justify-content: space-between; font-family: 'Fraunces', serif; font-size: 1.5rem; font-weight: 600; margin-top: .2rem; }
.r-foot { text-align: center; font-size: .74rem; opacity: .7; margin-top: .7rem; }
.r-edge { height: 14px; background: @@CHAMP@@; margin-top: -1px; animation: receiptIn .9s .3s cubic-bezier(.2,.7,.3,1) backwards;
    -webkit-mask: radial-gradient(circle at 50% 0, transparent 7px, #000 7.5px) 0 0 / 18px 14px repeat-x;
    mask: radial-gradient(circle at 50% 0, transparent 7px, #000 7.5px) 0 0 / 18px 14px repeat-x; }

@media (max-width: 900px) {
    .block-container { padding: 1.2rem 1rem 7rem; }
    .brand { font-size: 2.3rem; }
    .bag-label { display: none; }
    .bag { padding: .35rem .4rem; }

    /* floating cart button */
    [class*="st-key-fab_cart"] { display: block; position: fixed; right: 14px; bottom: 16px; left: auto; width: auto !important;
        z-index: 9990; animation: popIn .45s cubic-bezier(.2,.7,.3,1); }
    [class*="st-key-fab_cart"] button { width: auto; border-radius: 999px; padding: .85rem 1.3rem; font-size: .98rem;
        box-shadow: 0 6px 18px @@WM@@66; animation: payPulse 2.4s ease-out infinite; }

    /* cart becomes a bottom sheet */
    [data-testid="stColumn"]:has([class*="st-key-cart_panel"]) {
        position: fixed !important; top: auto !important; left: 0; right: 0; bottom: 0; width: 100% !important; max-width: none;
        z-index: 9999; max-height: 82vh; overflow-y: auto; background: @@CHAMP@@; border-top: 1.5px solid @@PASTEL@@;
        border-radius: 24px 24px 0 0; padding-bottom: env(safe-area-inset-bottom);
        transform: translateY(105%); visibility: hidden;
        transition: transform .45s cubic-bezier(.2,.7,.3,1), visibility 0s .45s;
    }
    [data-testid="stColumn"]:has(.sheet-open) { transform: translateY(0); visibility: visible;
        transition: transform .45s cubic-bezier(.2,.7,.3,1), visibility 0s; }
    .stApp:has(.sheet-open)::after { content: ""; position: fixed; inset: 0; background: @@ESP@@55; z-index: 9990; animation: fadeIn .3s; }
    [class*="st-key-cart_panel"] { background: transparent; border: 0; border-radius: 0; padding: .6rem 1.1rem 1.4rem; animation: none; }
    .sheet-handle { display: block; width: 44px; height: 5px; border-radius: 3px; background: @@PASTEL@@; margin: 0 auto .5rem; }
    [class*="st-key-sheet_close"] { display: block; position: absolute; top: 1.1rem; right: 1.1rem; z-index: 2; }
    [class*="st-key-sheet_close"] [data-testid="stBaseButton-secondary"] { padding: .3rem .85rem; min-height: 0; font-size: .82rem; border-radius: 999px; }

    /* pay button stays reachable on the checkout page */
    [class*="st-key-bigbtn_pay"] { position: fixed; left: 14px; right: 14px; bottom: 14px; z-index: 9990; }
    [class*="st-key-bigbtn_pay"] button { box-shadow: 0 6px 18px @@WM@@55; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
"""

CONFETTI_JS = """
<script>
(function () {
  try {
    const win = window.parent, doc = win.document;
    if (win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const old = doc.getElementById('ece-confetti'); if (old) old.remove();
    const c = doc.createElement('canvas'); c.id = 'ece-confetti';
    c.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:10000;';
    c.width = win.innerWidth; c.height = win.innerHeight; doc.body.appendChild(c);
    const ctx = c.getContext('2d');
    const colors = ['@@WM@@', '@@LIGHT@@', '@@EMER@@', '@@ESP@@', '#ffffff', '@@PASTEL@@'];
    const parts = [];
    const rnd = (a, b) => a + Math.random() * (b - a);
    const pick = arr => arr[(Math.random() * arr.length) | 0];
    function make(x, y, vx, vy, g) {
      parts.push({ x, y, vx, vy, g, drag: .992, size: rnd(18, 38), rot: rnd(0, 6.28), vr: rnd(-.12, .12),
        spin: rnd(0, 6.28), vs: rnd(.05, .16), sway: rnd(0, 6.28), sws: rnd(.02, .05), swa: g < .1 ? rnd(.4, 1.2) : 0,
        coin: Math.random() < .35, color: pick(colors) });
    }
    function cannon(side) {
      for (let i = 0; i < 45; i++) {
        const ang = (side === 'l' ? rnd(-80, -50) : rnd(-130, -100)) * Math.PI / 180, sp = rnd(11, 19);
        make(side === 'l' ? -10 : c.width + 10, c.height * .9, Math.cos(ang) * sp, Math.sin(ang) * sp, .24);
      }
    }
    function burst() {
      for (let i = 0; i < 60; i++) {
        const ang = rnd(0, 6.28), sp = rnd(4, 11);
        make(c.width / 2, c.height * .32, Math.cos(ang) * sp, Math.sin(ang) * sp - 3, .16);
      }
    }
    cannon('l'); cannon('r');
    setTimeout(burst, 900);
    const start = performance.now();
    let last = 0;
    function frame(t) {
      const el = t - start;
      ctx.clearRect(0, 0, c.width, c.height);
      if (el < 4200 && t - last > 40) { last = t; make(rnd(0, c.width), -30, rnd(-.5, .5), rnd(2, 4.5), .03); make(rnd(0, c.width), -30, rnd(-.5, .5), rnd(2, 4.5), .03); }
      for (const p of parts) {
        p.vy += p.g; p.vx *= p.drag; p.sway += p.sws;
        p.x += p.vx + Math.sin(p.sway) * p.swa; p.y += p.vy; p.rot += p.vr; p.spin += p.vs;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        if (p.coin) {
          ctx.scale(Math.cos(p.spin), 1);
          ctx.beginPath(); ctx.arc(0, 0, p.size / 2, 0, 6.283); ctx.fillStyle = '@@GOLD@@'; ctx.fill();
          ctx.lineWidth = 2; ctx.strokeStyle = '@@ESP@@'; ctx.stroke();
          ctx.fillStyle = '@@ESP@@'; ctx.font = '800 ' + (p.size * .62) + 'px "Plus Jakarta Sans", sans-serif';
        } else {
          ctx.fillStyle = p.color; ctx.font = '800 ' + p.size + 'px "Plus Jakarta Sans", sans-serif';
        }
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('$', 0, 1); ctx.restore();
      }
      const alive = parts.some(p => p.y < c.height + 60);
      if (el < 14000 && (alive || el < 4200)) win.requestAnimationFrame(frame); else c.remove();
    }
    win.requestAnimationFrame(frame);
  } catch (e) { /* sandboxed: skip confetti silently */ }
})();
</script>
"""

TICKER_ITEMS = [
    "Small-batch coffee", "Ceremonial matcha", "Pastries baked each morning",
    "Made with care", "Honey lavender, our signature", "Sit a while",
]


def inject_css():
    st.markdown(themed(CSS), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Shared UI pieces
# ----------------------------------------------------------------------------
BAG_SVG = '<svg viewBox="0 0 24 24"><path d="M6 8h12l-1 12H7z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>'
CUP_SVG = ('<svg viewBox="0 0 64 64"><path d="M14 26h30v12a12 12 0 0 1-12 12h-6a12 12 0 0 1-12-12z"/>'
           '<path d="M44 29h5a6 6 0 0 1 0 12h-6"/><path d="M24 20c-3-3 3-5 0-9M33 20c-3-3 3-5 0-9"/></svg>')


def parity(n: int) -> str:
    """Alternating class so a CSS animation restarts each time a number changes."""
    return "a" if n % 2 == 0 else "b"


def render_masthead(bag_count: int):
    steam = '<svg class="steam" viewBox="0 0 30 34"><path d="M6 30c-5-6 5-9 0-16"/><path d="M15 30c-5-6 5-9 0-16"/><path d="M24 30c-5-6 5-9 0-16"/></svg>'
    st.markdown(
        '<div class="masthead"><div class="masthead-row"><div>'
        f'<div class="brand">Ece <em>Cafe</em>{steam}</div>'
        '<div class="tagline">Small-batch coffee, ceremonial matcha &amp; pastries baked each morning.</div></div>'
        f'<div class="bag">{BAG_SVG}<span class="bag-label">Your bag</span><span class="bag-count {parity(bag_count)}">{bag_count}</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    track = "".join(f"<span>{html.escape(t)}</span><i>✦</i>" for t in TICKER_ITEMS) * 2
    st.markdown(f'<div class="ticker"><div class="ticker-track">{track}</div></div>', unsafe_allow_html=True)


def render_filters(menu: list[dict]):
    categories = list(dict.fromkeys(i["category"] for i in menu))
    tags = sorted({t for i in menu for t in i["special_tags"]})

    st.markdown('<div class="filter-label">Menu</div>', unsafe_allow_html=True)
    with st.container(key="pills_cat"):
        all_active = not st.session_state.sel_cats and not st.session_state.sel_tags
        st.button("All", key="pill_all", type="primary" if all_active else "secondary", on_click=clear_filters)
        for cat in categories:
            active = cat in st.session_state.sel_cats
            st.button(cat, key=f"pill_cat_{cat}", type="primary" if active else "secondary",
                      on_click=toggle, args=("sel_cats", cat))
    if tags:
        st.markdown('<div class="filter-label">Specials</div>', unsafe_allow_html=True)
        with st.container(key="pills_tag"):
            for tag in tags:
                active = tag in st.session_state.sel_tags
                st.button(tag, key=f"pill_tag_{tag}", type="primary" if active else "secondary",
                          on_click=toggle, args=("sel_tags", tag))
    return categories


def render_card(item: dict):
    chips = "".join(f'<span class="chip">{html.escape(t)}</span>' for t in item["special_tags"])
    card = (
        f'<div class="img-wrap"><img class="card-img" src="{image_src(item["image"])}" alt="{html.escape(item["name"])}"></div>'
        f'<div class="card-top"><span class="card-title">{html.escape(item["name"])}</span>'
        f'<span class="price-tag">{money(item["price"])}</span></div>'
        f'<div class="card-desc">{html.escape(item["description"])}</div>'
        f'<div class="chips">{chips}</div>'
    )
    with st.container(key=f"card_{item['id']}"):
        st.markdown(card, unsafe_allow_html=True)
        st.button("Add to Cart", key=f"add_{item['id']}", type="primary", use_container_width=True,
                  on_click=add_item, args=(item["id"], item["name"]))


def render_menu(menu: list[dict], categories: list[str]):
    sel_cats, sel_tags = st.session_state.sel_cats, st.session_state.sel_tags
    shown = False
    for cat in categories:
        if sel_cats and cat not in sel_cats:
            continue
        items = [i for i in menu if i["category"] == cat and all(t in i["special_tags"] for t in sel_tags)]
        if not items:
            continue
        shown = True
        st.markdown(f'<div class="cat-heading">{html.escape(cat)}</div>', unsafe_allow_html=True)
        for start in range(0, len(items), 2):
            cols = st.columns(2, gap="medium")
            for col, item in zip(cols, items[start:start + 2]):
                with col:
                    render_card(item)
    if not shown:
        st.info("Nothing on the menu matches those filters — try removing one.")


def render_cart(menu: list[dict]):
    lines, subtotal = cart_lines(menu)
    qty_total = sum(q for _, q in lines)

    with st.container(key="cart_panel"):
        state = " sheet-open" if st.session_state.cart_open else ""
        st.markdown(f'<span class="sheet-state{state}"></span><div class="sheet-handle"></div>', unsafe_allow_html=True)
        with st.container(key="sheet_close"):  # only visible on mobile (bottom sheet)
            st.button("Close", key="sheet_close_btn", on_click=close_cart)
        st.markdown('<div class="cart-title">Your Order</div>', unsafe_allow_html=True)

        if not lines:
            st.markdown(f'<div class="cart-empty">{CUP_SVG}Your cart is empty.<br>Pick something lovely from the menu.</div>',
                        unsafe_allow_html=True)
            return

        for item, qty in lines:
            iid = item["id"]
            st.markdown(
                f'<div class="cart-name">{html.escape(item["name"])}</div>'
                f'<div class="cart-sub">{money(item["price"])} each</div>', unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2.2], gap="small")
            c1.button("−", key=f"cart_dec_{iid}", on_click=change_qty, args=(iid, -1), use_container_width=True)
            c2.markdown(f'<div style="text-align:center;font-weight:700">{qty}</div>', unsafe_allow_html=True)
            c3.button("+", key=f"cart_inc_{iid}", on_click=change_qty, args=(iid, 1), use_container_width=True)
            c4.button("✕", key=f"cart_rm_{iid}", on_click=remove_item, args=(iid,), use_container_width=True, help="Remove")
            c5.markdown(f'<div class="cart-line-total">{money(item["price"] * qty)}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="cart-divider">', unsafe_allow_html=True)

        st.markdown(f'<div class="cart-total"><span>Subtotal</span><span class="{parity(qty_total)}">{money(subtotal)}</span></div>',
                    unsafe_allow_html=True)
        st.write("")
        with st.container(key="bigbtn_checkout"):
            st.button(f"Checkout · {money(subtotal)}", type="primary", on_click=go_checkout,
                      use_container_width=True)


# ----------------------------------------------------------------------------
# Checkout
# ----------------------------------------------------------------------------
def choice_pills(label: str, container_key: str, state_key: str, options: list[str]):
    st.markdown(f'<div class="co-label">{label}</div>', unsafe_allow_html=True)
    with st.container(key=container_key):
        for opt in options:
            active = st.session_state[state_key] == opt
            st.button(opt, key=f"pill_{state_key}_{opt}", type="primary" if active else "secondary",
                      on_click=set_value, args=(state_key, opt))


def payment_visual(method: str, name: str):
    if method == "Tap to Pay":
        st.markdown(
            '<div class="tapcard"><div class="tap-wrap"><b></b><b></b><b></b><i></i></div>'
            '<span>Hold your phone near the reader</span></div>'
            '<div class="demo-note">Demo only — nothing is charged.</div>', unsafe_allow_html=True)
    else:
        holder = html.escape((name or "Ece Cafe Guest").upper()[:24])
        st.markdown(
            '<div class="vcard"><div class="v-top"><span>Ece Cafe</span><span class="v-chip"></span></div>'
            '<div class="v-num">••••&nbsp;&nbsp;••••&nbsp;&nbsp;••••&nbsp;&nbsp;4242</div>'
            f'<div class="v-bot"><span>{holder}</span><span>Demo card</span></div></div>'
            '<div class="demo-note">Demo only — no real card details are collected.</div>', unsafe_allow_html=True)


def render_checkout(menu: list[dict]):
    lines, subtotal = cart_lines(menu)
    if not lines:
        st.session_state.stage = "browse"
        st.rerun()

    st.button("← Back to menu", key="back_menu", on_click=set_value, args=("stage", "browse"))
    st.markdown('<div class="co-heading">Checkout</div>'
                '<div class="co-sub">Review your order and choose how you’d like to pay.</div>', unsafe_allow_html=True)

    tip_pct = TIP_OPTIONS.get(st.session_state.co_tip, 0)
    tip = round(subtotal * tip_pct / 100, 2)
    total = subtotal + tip

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        with st.container(key="panel_details"):
            st.text_input("Name for the order", key="field_name", placeholder="e.g. Ece", max_chars=24)
            choice_pills("Order type", "pills_type", "co_type", ORDER_TYPES)
            choice_pills("Add a tip", "pills_tip", "co_tip", list(TIP_OPTIONS))
            choice_pills("Pay with", "pills_method", "co_method", PAY_METHODS)
            payment_visual(st.session_state.co_method, (st.session_state.get("field_name") or "").strip())
    with right:
        with st.container(key="panel_summary"):
            st.markdown('<div class="panel-title">Order summary</div>', unsafe_allow_html=True)
            rows = "".join(
                f'<div class="sum-row"><span>{qty} × {html.escape(item["name"])}</span><span>{money(item["price"] * qty)}</span></div>'
                for item, qty in lines)
            st.markdown(rows, unsafe_allow_html=True)
            st.markdown('<hr class="cart-divider">', unsafe_allow_html=True)
            st.markdown(f'<div class="sum-row"><span>Subtotal</span><span>{money(subtotal)}</span></div>'
                        f'<div class="sum-row"><span>Tip ({html.escape(st.session_state.co_tip)})</span><span>{money(tip)}</span></div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div class="cart-total"><span>Total</span><span class="{parity(int(total * 100))}">{money(total)}</span></div>',
                        unsafe_allow_html=True)
            st.write("")
            receipt_lines = [(item["name"], qty, item["price"] * qty) for item, qty in lines]
            with st.container(key="bigbtn_pay"):
                st.button(f"Pay {money(total)}", type="primary", on_click=start_payment,
                          args=(receipt_lines, subtotal, tip, total), use_container_width=True)
            st.markdown('<div class="secure-note">Secure demo checkout</div>', unsafe_allow_html=True)


def render_processing():
    st.markdown(
        '<div class="proc"><div class="proc-box"><div class="ring"></div>'
        '<div class="proc-title">Processing payment</div>'
        '<div class="proc-steps"><div>Securing connection</div><div>Authorizing payment</div><div>Confirming your order</div></div>'
        '<div class="proc-bar"><i></i></div></div></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Success
# ----------------------------------------------------------------------------
def render_success():
    r = st.session_state.receipt
    if st.session_state.celebrate:
        components.html(themed(CONFETTI_JS), height=0)
        st.session_state.celebrate = False

    st.markdown('<div class="success-banner">Payment Successful! Thank you for ordering at Ece Cafe.</div>',
                unsafe_allow_html=True)

    name = html.escape(r["name"]) if r["name"] else ""
    thanks = f"Thank you, {name}!" if name else "Thank you!"
    check = ('<div class="check-wrap"><svg class="check" viewBox="0 0 120 120"><circle class="c-bg" cx="60" cy="60" r="52"/>'
             '<path class="c-tick" d="M36 62l17 17 32-36"/></svg></div>')
    hero = (f'<div class="hero">{check}<div class="hero-title">Order {r["order_no"]}</div>'
            f'<div class="hero-sub">{thanks} We’re on it.</div>'
            '<div class="eta">Being prepared · Show your order code to Ece</div></div>')

    rows = "".join(
        f'<div class="r-line" style="animation-delay:{0.7 + i * 0.12:.2f}s"><span>{qty} × {html.escape(n)}</span><span>{money(sub)}</span></div>'
        for i, (n, qty, sub) in enumerate(r["lines"]))
    tip_row = (f'<div class="r-line" style="animation-delay:{0.7 + len(r["lines"]) * 0.12:.2f}s"><span>Tip</span><span>{money(r["tip"])}</span></div>'
               if r["tip"] > 0 else "")
    receipt = (
        '<div class="receipt"><div class="r-head">Ece Cafe</div>'
        f'<div class="r-meta">{r["order_no"]} · {html.escape(r["type"])}</div><hr class="cart-divider">'
        f'{rows}{tip_row}<hr class="cart-divider">'
        f'<div class="r-total"><span>Total paid</span><span>{money(r["total"])}</span></div>'
        f'<div class="r-foot">Paid with {html.escape(r["method"])}</div></div><div class="r-edge"></div>')

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        with st.container(key="panel_hero"):
            st.markdown(hero, unsafe_allow_html=True)
            with st.container(key="bigbtn_neworder"):
                st.button("Start New Order", type="primary", on_click=new_order, use_container_width=True)
    with right:
        st.markdown(receipt, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    init_state()
    inject_css()
    stage = st.session_state.stage

    frame_cls = {"success": " paid", "processing": " busy"}.get(stage, "")
    st.markdown(f'<div class="frame{frame_cls}"></div>', unsafe_allow_html=True)

    menu = load_menu()
    bag_count = sum(q for _, q in cart_lines(menu)[0]) if stage in ("browse", "checkout") else 0
    render_masthead(bag_count)

    if not menu:
        st.warning("The menu is being refreshed. Please check back in a moment.")
        return

    if stage == "processing":
        render_processing()
        time.sleep(2.9)  # lets the CSS progress animation play; payment itself is mocked
        finish_payment()
        st.rerun()
    elif stage == "success" and st.session_state.receipt:
        render_success()
    elif stage == "checkout":
        render_checkout(menu)
    else:
        # Mobile: floating cart button (hidden on desktop by CSS) opens the cart as a bottom sheet.
        lines, subtotal = cart_lines(menu)
        if lines and not st.session_state.cart_open:
            with st.container(key="fab_cart"):
                st.button(f"View cart · {bag_count} · {money(subtotal)}", key="fab_btn", type="primary",
                          on_click=open_cart)
        main_col, cart_col = st.columns([2.3, 1], gap="large")
        with main_col:
            categories = render_filters(menu)
            render_menu(menu, categories)
        with cart_col:
            render_cart(menu)


main()
