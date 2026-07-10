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

# ─── Direct API endpoint ───────────────────────────────────────────────────────
CHECKER_API_BASE = 'https://stripe-auto-dsam.onrender.com/gateway=autostripe/key=xebec'

# ─── Channel join requirement (ONLY CHANNEL) ────────────────────────────────
CHANNEL_LINK = 'https://t.me/+uJ4vAXPkw11mOWQ1'
CHANNEL_ID = -1003729202954

# ─── Bot owner ────────────────────────────────────────────────────────────────
OWNER_ID = 8836533598
OWNER_USERNAME = '@zayn_carder_001'  # Owner username show karega

# ─── Bot Configuration ────────────────────────────────────────────────────────
API_ID    = 39649019
API_HASH  = '0331b07302fd29c67933d43fc57c929f'
BOT_TOKEN = '8766840155:AAFJU4GU_ez5uVZTXoMO0bb7wcnYeQSpmFc'

# ─── File paths ───────────────────────────────────────────────────────────────
PREMIUM_FILE = 'premium.txt'
ADMINS_FILE  = 'admins.txt'
BANNED_FILE  = 'banned.txt'
KEYS_FILE    = 'keys.txt'
SITES_FILE   = 'sites.txt'
PROXY_FILE   = 'proxy.txt'

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

CE_CHECK    = '<tg-emoji emoji-id="5895671830210940904">✅</tg-emoji>'
CE_CHAT     = '<tg-emoji emoji-id="5303138782004924588">💬</tg-emoji>'
CE_GHOST    = '<tg-emoji emoji-id="5855207143724027916">👾</tg-emoji>'
CE_MONEYBAG = '<tg-emoji emoji-id="5348503265967355284">💰</tg-
