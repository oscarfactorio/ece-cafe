"""Ece Cafe — boutique cafe ordering app for Streamlit Community Cloud.

Menu content lives in menu.json (+ images/). Edit those on GitHub; no code changes needed.
"""

import base64
import html
import json
import mimetypes
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
    st.session_state.setdefault("cart", {})          # {item_id: qty}
    st.session_state.setdefault("paid", False)
    st.session_state.setdefault("celebrate", False)  # fire confetti once
    st.session_state.setdefault("receipt", None)
    st.session_state.setdefault("sel_cats", [])
    st.session_state.setdefault("sel_tags", [])


def toggle(key: str, value: str):
    sel = st.session_state[key]
    if value in sel:
        sel.remove(value)
    else:
        sel.append(value)


def clear_filters():
    st.session_state.sel_cats = []
    st.session_state.sel_tags = []


def add_item(item_id: str):
    cart = st.session_state.cart
    cart[item_id] = cart.get(item_id, 0) + 1


def change_qty(item_id: str, delta: int):
    cart = st.session_state.cart
    qty = cart.get(item_id, 0) + delta
    if qty <= 0:
        cart.pop(item_id, None)
    else:
        cart[item_id] = qty


def remove_item(item_id: str):
    st.session_state.cart.pop(item_id, None)


def pay(lines: list, total: float):
    st.session_state.receipt = {"lines": lines, "total": total}
    st.session_state.paid = True
    st.session_state.celebrate = True
    st.session_state.cart = {}


def new_order():
    st.session_state.cart = {}
    st.session_state.paid = False
    st.session_state.celebrate = False
    st.session_state.receipt = None


# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
def inject_css():
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    /* --- strip Streamlit chrome --- */
    #MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="stHeader"] {{ display: none !important; }}
    .stApp {{ background: {BLUSH}; }}
    .block-container {{ padding: 2.2rem 2.6rem 4rem; max-width: 1280px; }}
    html, body, .stApp, p, span, label, div, button, input {{
        font-family: 'Plus Jakarta Sans', sans-serif; color: {ESPRESSO};
    }}
    h1, h2, h3, h4 {{ font-family: 'Fraunces', serif !important; color: {ESPRESSO}; letter-spacing: -0.01em; }}

    /* --- masthead --- */
    .masthead {{ padding: .4rem 0 1.4rem; border-bottom: 1.5px solid {PASTEL}; margin-bottom: 1.4rem; }}
    .masthead .brand {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: 3.1rem;
        line-height: 1; color: {WATERMELON}; letter-spacing: -0.02em; }}
    .masthead .brand em {{ font-style: italic; font-weight: 500; color: {ESPRESSO}; }}
    .masthead .tagline {{ margin-top: .55rem; font-size: .95rem; opacity: .75; letter-spacing: .02em; }}
    .filter-label {{ font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
        margin: .5rem 0 .35rem; opacity: .7; }}
    .cat-heading {{ font-family: 'Fraunces', serif; font-size: 1.7rem; font-weight: 600; color: {WATERMELON};
        margin: 1.6rem 0 .2rem; padding-bottom: .35rem; border-bottom: 1.5px solid {PASTEL}; }}

    /* --- buttons (base = secondary) --- */
    .stButton > button {{
        border-radius: 12px; border: 1.5px solid transparent; font-weight: 600; font-size: .92rem;
        padding: .5rem 1rem; transition: transform .12s ease, background-color .2s ease,
        border-color .2s ease, box-shadow .2s ease; box-shadow: none;
    }}
    .stButton > button p {{ color: inherit; font-weight: inherit; margin: 0; }}
    .stButton > button:active {{ transform: scale(.95); }}
    [data-testid="stBaseButton-secondary"] {{ background: {LIGHT}; color: {ESPRESSO}; }}
    [data-testid="stBaseButton-secondary"]:hover {{ background: {WATERMELON}; border-color: {ESPRESSO}22; color: {ESPRESSO}; }}
    [data-testid="stBaseButton-primary"] {{ background: {WATERMELON}; color: {ESPRESSO}; }}
    [data-testid="stBaseButton-primary"]:hover {{ background: {LIGHT}; border-color: {ESPRESSO}33; color: {ESPRESSO}; }}
    .stButton > button:disabled {{ opacity: .45; }}

    /* --- filter pills --- */
    [class*="st-key-pills_"] {{ display: flex !important; flex-direction: row !important; flex-wrap: wrap;
        gap: .5rem !important; }}
    [class*="st-key-pills_"] > div {{ width: auto !important; flex: 0 0 auto; }}
    [class*="st-key-pill_"] button {{ border-radius: 999px; padding: .38rem 1.05rem; font-size: .86rem; }}
    [class*="st-key-pill_"] [data-testid="stBaseButton-secondary"] {{ background: {PASTEL}; }}
    [class*="st-key-pill_"] [data-testid="stBaseButton-secondary"]:hover {{ background: {LIGHT}; }}
    [class*="st-key-pill_"] [data-testid="stBaseButton-primary"] {{ background: {WATERMELON}; }}

    /* --- menu cards --- */
    [class*="st-key-card_"] {{
        background: {CHAMPAGNE}; border: 1.5px solid {PASTEL}; border-radius: 20px; padding: .8rem .8rem 1rem;
        transition: transform .28s cubic-bezier(.2,.7,.3,1), border-color .28s ease;
        gap: .6rem !important;
    }}
    [class*="st-key-card_"]:hover {{ transform: translateY(-5px); border-color: {WATERMELON}; }}
    .card-img {{ width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 14px; display: block; }}
    .card-top {{ display: flex; justify-content: space-between; align-items: baseline; gap: .6rem; margin-top: .55rem; }}
    .card-title {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.28rem; line-height: 1.2; }}
    .price-tag {{ background: {LIGHT}; color: {ESPRESSO}; font-weight: 700; font-size: .9rem;
        padding: .15rem .6rem; border-radius: 999px; white-space: nowrap; }}
    .card-desc {{ font-size: .88rem; line-height: 1.5; opacity: .85; margin: .35rem 0 .1rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }}
    .chip {{ font-size: .68rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
        border: 1.3px solid {ESPRESSO}55; border-radius: 999px; padding: .08rem .5rem; }}

    /* --- cart --- */
    [data-testid="stColumn"]:has([class*="st-key-cart_panel"]) {{ position: sticky; top: 1.2rem; align-self: flex-start; }}
    [class*="st-key-cart_panel"] {{ background: {CHAMPAGNE}; border: 1.5px solid {PASTEL}; border-radius: 22px;
        padding: 1.3rem 1.2rem 1.4rem; gap: .5rem !important; }}
    .cart-title {{ font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 600; color: {WATERMELON}; margin-bottom: .2rem; }}
    .cart-empty {{ font-size: .9rem; opacity: .75; padding: .6rem 0 .2rem; }}
    .cart-name {{ font-weight: 600; font-size: .92rem; line-height: 1.25; }}
    .cart-sub {{ font-size: .8rem; opacity: .75; }}
    .cart-line-total {{ font-weight: 700; font-size: .92rem; text-align: right; }}
    .cart-divider {{ border: 0; border-top: 1.5px dashed {PASTEL}; margin: .5rem 0; }}
    .cart-total {{ display: flex; justify-content: space-between; font-family: 'Fraunces', serif; font-size: 1.45rem; font-weight: 600; }}
    [class*="st-key-cart_"] [data-testid="stBaseButton-secondary"] {{ padding: .15rem .3rem; min-height: 0; font-size: .9rem; }}
    [class*="st-key-pay"] button {{ width: 100%; padding: .8rem 1rem; font-size: 1.05rem; border-radius: 14px; }}
    [class*="st-key-neworder"] button {{ width: 100%; padding: .8rem 1rem; font-size: 1rem; border-radius: 14px; }}
    [data-testid="stHorizontalBlock"] {{ align-items: center; }}

    /* --- payment success --- */
    .frame {{ position: fixed; inset: 0; pointer-events: none; z-index: 9998; border: 10px solid {PASTEL};
        transition: border-color .9s ease, box-shadow .9s ease; }}
    .frame.paid {{ border-color: {EMERALD}; box-shadow: inset 0 0 50px {EMERALD}88, inset 0 0 0 2px {EMERALD};
        animation: frameIn 1s ease both; }}
    @keyframes frameIn {{ from {{ border-color: {PASTEL}; box-shadow: inset 0 0 0 transparent; }}
        to {{ border-color: {EMERALD}; box-shadow: inset 0 0 50px {EMERALD}88, inset 0 0 0 2px {EMERALD}; }} }}
    .success-banner {{ background: {EMERALD}; color: {ESPRESSO}; font-weight: 700; text-align: center;
        padding: 1rem 1.4rem; border-radius: 16px; margin-bottom: 1.2rem; font-size: 1.1rem;
        box-shadow: 0 0 0 4px {EMERALD}44, 0 0 28px {EMERALD}99; animation: glow 2.2s ease-in-out infinite alternate; }}
    @keyframes glow {{ from {{ box-shadow: 0 0 0 3px {EMERALD}33, 0 0 16px {EMERALD}77; }}
        to {{ box-shadow: 0 0 0 6px {EMERALD}55, 0 0 36px {EMERALD}bb; }} }}
    .receipt-line {{ display: flex; justify-content: space-between; font-size: .9rem; padding: .15rem 0; }}

    @media (max-width: 900px) {{
        .block-container {{ padding: 1.4rem 1rem 3rem; }}
        .masthead .brand {{ font-size: 2.4rem; }}
        [data-testid="stColumn"]:has([class*="st-key-cart_panel"]) {{ position: static; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


CONFETTI_JS = f"""
<script>
(function () {{
  try {{
    const win = window.parent, doc = win.document;
    const old = doc.getElementById('ece-confetti'); if (old) old.remove();
    const c = doc.createElement('canvas'); c.id = 'ece-confetti';
    c.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:10000;';
    c.width = win.innerWidth; c.height = win.innerHeight; doc.body.appendChild(c);
    const ctx = c.getContext('2d');
    const colors = ['{WATERMELON}', '{LIGHT}', '{EMERALD}', '{ESPRESSO}', '#ffffff'];
    const parts = [];
    const spawn = () => parts.push({{
      x: Math.random() * c.width, y: -30, size: 18 + Math.random() * 20,
      vy: 2 + Math.random() * 3.2, sway: Math.random() * 2 * Math.PI, swaySpeed: .02 + Math.random() * .04,
      rot: Math.random() * 6.28, vr: (Math.random() - .5) * .08, color: colors[(Math.random() * colors.length) | 0]
    }});
    const start = performance.now();
    function frame(t) {{
      const elapsed = t - start;
      ctx.clearRect(0, 0, c.width, c.height);
      if (elapsed < 3500) for (let i = 0; i < 3; i++) spawn();
      for (const p of parts) {{
        p.y += p.vy; p.sway += p.swaySpeed; p.rot += p.vr;
        ctx.save(); ctx.translate(p.x + Math.sin(p.sway) * 30, p.y); ctx.rotate(p.rot);
        ctx.font = '700 ' + p.size + 'px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = p.color; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('$', 0, 0); ctx.restore();
      }}
      if (elapsed < 10000 && parts.some(p => p.y < c.height + 40)) win.requestAnimationFrame(frame);
      else c.remove();
    }}
    win.requestAnimationFrame(frame);
  }} catch (e) {{ /* sandboxed: skip confetti silently */ }}
}})();
</script>
"""


# ----------------------------------------------------------------------------
# UI pieces
# ----------------------------------------------------------------------------
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


def render_card(item: dict, disabled: bool):
    chips = "".join(f'<span class="chip">{html.escape(t)}</span>' for t in item["special_tags"])
    card = (
        f'<img class="card-img" src="{image_src(item["image"])}" alt="{html.escape(item["name"])}">'
        f'<div class="card-top"><span class="card-title">{html.escape(item["name"])}</span>'
        f'<span class="price-tag">{money(item["price"])}</span></div>'
        f'<div class="card-desc">{html.escape(item["description"])}</div>'
        f'<div class="chips">{chips}</div>'
    )
    with st.container(key=f"card_{item['id']}"):
        st.markdown(card, unsafe_allow_html=True)
        st.button("Add to Cart", key=f"add_{item['id']}", type="primary", disabled=disabled,
                  use_container_width=True, on_click=add_item, args=(item["id"],))


def render_menu(menu: list[dict], categories: list[str]):
    sel_cats, sel_tags = st.session_state.sel_cats, st.session_state.sel_tags
    shown = False
    for cat in categories:
        if sel_cats and cat not in sel_cats:
            continue
        items = [
            i for i in menu
            if i["category"] == cat and all(t in i["special_tags"] for t in sel_tags)
        ]
        if not items:
            continue
        shown = True
        st.markdown(f'<div class="cat-heading">{html.escape(cat)}</div>', unsafe_allow_html=True)
        for start in range(0, len(items), 2):
            cols = st.columns(2, gap="medium")
            for col, item in zip(cols, items[start:start + 2]):
                with col:
                    render_card(item, disabled=st.session_state.paid)
    if not shown:
        st.info("Nothing on the menu matches those filters — try removing one.")


def render_cart(menu: list[dict]):
    by_id = {i["id"]: i for i in menu}
    lines = [(by_id[i], q) for i, q in st.session_state.cart.items() if i in by_id]
    total = sum(item["price"] * qty for item, qty in lines)

    with st.container(key="cart_panel"):
        st.markdown('<div class="cart-title">Your Order</div>', unsafe_allow_html=True)

        if st.session_state.paid and st.session_state.receipt:
            r = st.session_state.receipt
            for name, qty, sub in r["lines"]:
                st.markdown(
                    f'<div class="receipt-line"><span>{qty} × {html.escape(name)}</span><span>{money(sub)}</span></div>',
                    unsafe_allow_html=True)
            st.markdown('<hr class="cart-divider">', unsafe_allow_html=True)
            st.markdown(f'<div class="cart-total"><span>Paid</span><span>{money(r["total"])}</span></div>',
                        unsafe_allow_html=True)
            st.write("")
            with st.container(key="neworder"):
                st.button("Start New Order", type="primary", on_click=new_order, use_container_width=True)
            return

        if not lines:
            st.markdown('<div class="cart-empty">Your cart is empty. Pick something lovely from the menu.</div>',
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
            c4.button("✕", key=f"cart_rm_{iid}", on_click=remove_item, args=(iid,), use_container_width=True,
                      help="Remove")
            c5.markdown(f'<div class="cart-line-total">{money(item["price"] * qty)}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="cart-divider">', unsafe_allow_html=True)

        st.markdown(f'<div class="cart-total"><span>Total</span><span>{money(total)}</span></div>',
                    unsafe_allow_html=True)
        st.write("")
        receipt_lines = [(item["name"], qty, item["price"] * qty) for item, qty in lines]
        with st.container(key="pay"):
            st.button(f"Pay {money(total)}", type="primary", on_click=pay,
                      args=(receipt_lines, total), use_container_width=True)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    init_state()
    inject_css()
    paid = st.session_state.paid

    st.markdown(f'<div class="frame{" paid" if paid else ""}"></div>', unsafe_allow_html=True)

    menu = load_menu()

    st.markdown(
        '<div class="masthead"><div class="brand">Ece <em>Cafe</em></div>'
        '<div class="tagline">Small-batch coffee, ceremonial matcha &amp; pastries baked each morning.</div></div>',
        unsafe_allow_html=True,
    )

    if paid:
        st.markdown(
            '<div class="success-banner">Payment Successful! Thank you for ordering at Ece Cafe.</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.celebrate:
            components.html(CONFETTI_JS, height=0)
            st.session_state.celebrate = False

    if not menu:
        st.warning("The menu is being refreshed. Please check back in a moment.")
        return

    main_col, cart_col = st.columns([2.3, 1], gap="large")
    with main_col:
        categories = render_filters(menu)
        render_menu(menu, categories)
    with cart_col:
        render_cart(menu)


main()
