"""Config for NSE paper-trading bot. Paper/research only. No broker, no real orders."""
import datetime as dt
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

IST_NAME = "Asia/Kolkata"
def IST():
    return ZoneInfo(IST_NAME) if ZoneInfo else dt.timezone(dt.timedelta(hours=5, minutes=30))
def now_ist():
    return dt.datetime.now(IST())
def today_ist():
    return now_ist().date()

CAPITAL = 5000.0
MAX_POSITIONS = 2
MAX_CAPITAL_PCT = 0.45
SL_ATR = 1.5
TP_ATR = 2.5
TRAIL_ATR = 1.0
MIS_LEVERAGE = 5
DATA_DELAY_MINUTES = 15
LOOP_SECONDS = 300
STALE_DATA_MINUTES = 30

KRONOS_THRESHOLD = 0.58
SHORTLIST_TOP_N = 20
HEADLINES_N = 50
# Kronos cost rule: run Kronos ONLY on the final candidates after cheap filters.
KRONOS_MAX_CANDIDATES = 5
# 2 consecutive losing days -> halve position size for the next day (risk.update_day_close)
CONSECUTIVE_LOSING_DAYS_THRESHOLD = 2
HALVED_SIZE_MULTIPLIER = 0.5
DEFAULT_SIZE_MULTIPLIER = 1.0
RSI_MIN, RSI_MAX = 40, 70
FINBERT_MIN = 0.0
KRONOS_LOOKBACK, KRONOS_PRED_LEN, KRONOS_SAMPLE_COUNT = 400, 12, 10
KRONOS_T, KRONOS_TOP_P = 1.0, 0.9
ENABLE_CHRONOS_ENSEMBLE = False  # research only, remove if commercial
ENABLE_TIMESFM_ENSEMBLE = False  # research only (weights non-commercial), remove if commercial
ENABLE_MOIRAI_ENSEMBLE = False   # research only (non-commercial), remove if commercial

NO_NEW_TRADES_AFTER = dt.time(14, 45)
MARKET_OPEN = dt.time(9, 15)
MARKET_CLOSE = dt.time(15, 30)
SQUARE_OFF_FROM = dt.time(15, 15)
HARD_FLAT_BY = dt.time(15, 20)
JOB_A_EXIT = dt.time(14, 50)
JOB_B_EXIT = dt.time(15, 40)
EOD_MESSAGE_TIME = dt.time(15, 35)

PRICE_MIN, PRICE_MAX = 100.0, 1500.0
MIN_AVG_VOLUME = 500_000
MIN_ATR_PCT = 0.01

SLIPPAGE_PCT = 0.001  # 0.1%
BROKERAGE_PER_ORDER = 20.0
STT_SELL_PCT = 0.00025
EXCHANGE_TXN_PCT = 0.0000325
GST_PCT = 0.18
SEBI_PER_CRORE = 10.0  # 0.0001%
STAMP_BUY_PCT = 0.00003

STATE_FILE = "state.json"
JOURNAL_DB = "journal.db"
STATE_BRANCH_MODE = False  # workflow sets env STATE_BRANCH_MODE=1
STATE_BRANCH = "bot-state"

# NIFTY50 (as of 2024-25 composition; symbols without .NS)
NIFTY50 = ["ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA","DRREDDY","EICHERMOT","GRASIM","HCLTECH","HDFCBANK","HDFCLIFE","HEROMOTOCO","HINDALCO","HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC","JIOFIN","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID","RELIANCE","SBILIFE","SHRIRAMFIN","SBIN","SUNPHARMA","TCS","TATACONSUM","TATAMOTORS","TATASTEEL","TECHM","TITAN","TRENT","ULTRACEMCO","WIPRO"]
# Liquid NIFTY500 placeholder subset (extend as needed)
NIFTY500_LIQUID = ["ABB","ACC","ALKEM","AMBUJACEM","ASHOKLEY","AUROPHARMA","BALKRISIND","BANKBARODA","BERGEPAINT","BHEL","BIOCON","BOSCHLTD","BPCL","BRITANNIA","CANBK","CHOLAFIN","COLPAL","CONCOR","CUMMINSIND","DABUR","DIVISLAB","DLF","EXIDEIND","FEDERALBNK","GAIL","GLENMARK","GODREJCP","HAVELLS","ICICIPRULI","IDEA","IDFCFIRSTB","INDHOTEL","IOC","IRCTC","JUBLFOOD","LICHSGFIN","LUPIN","MFSL","MOTHERSON","MPHASIS","MUTHOOTFIN","NAUKRI","NMDC","OFSS","PAGEIND","PERSISTENT","PETRONET","PIDILITIND","PNB","POLYCAB","RECLTD","SAIL","SIEMENS","SRF","TATAPOWER","TORNTPHARM","TVSMOTOR","UBL","UPL","VEDL","VOLTAS","YESBANK","ZYDUSLIFE"]
SYMBOLS = list(dict.fromkeys(NIFTY50 + NIFTY500_LIQUID))
# T2T / BE-series exclusion placeholder - maintain manually, Yahoo does not flag reliably
T2T_EXCLUSIONS = set()

NSE_HOLIDAYS_2026 = {
    "2026-01-15",  # Municipal Corporation Election, Maharashtra (extra)
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-09-14", "2026-10-02", "2026-10-20",
    "2026-11-10", "2026-11-24", "2026-12-25",
}

RSS_FEEDS = {
    "moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
    "economictimes": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "pulse": "https://pulse.zerodha.com/feed.xml",
}

def is_trading_day(d=None):
    d = d or today_ist()
    if isinstance(d, dt.datetime): d = d.date()
    return d.weekday() < 5 and d.isoformat() not in NSE_HOLIDAYS_2026

def is_market_open(t=None):
    t = t or now_ist()
    if not is_trading_day(t): return False
    tt = t.timetz().replace(tzinfo=None) if isinstance(t, dt.datetime) else t
    return MARKET_OPEN <= tt <= MARKET_CLOSE

def no_new_trades(now=None):
    now = now or now_ist()
    return now.time() >= NO_NEW_TRADES_AFTER
