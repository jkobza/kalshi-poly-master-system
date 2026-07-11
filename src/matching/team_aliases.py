"""
Extensible team alias maps: names and codes → canonical codes per league.

Unknown leagues fall back to normalized full names (no code map).
"""

from __future__ import annotations

import re
import unicodedata


def _norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Canonical code -> aliases (names, nicknames, abbreviations)
MLB: dict[str, list[str]] = {
    "ARI": ["arizona diamondbacks", "diamondbacks", "arizona", "ari"],
    "ATL": ["atlanta braves", "braves", "atlanta", "atl"],
    "BAL": ["baltimore orioles", "orioles", "baltimore", "bal"],
    "BOS": ["boston red sox", "red sox", "boston", "bos"],
    "CHC": ["chicago cubs", "cubs", "chc"],
    "CWS": ["chicago white sox", "white sox", "cws", "chw"],
    "CIN": ["cincinnati reds", "reds", "cincinnati", "cin"],
    "CLE": ["cleveland guardians", "guardians", "cleveland", "cle"],
    "COL": ["colorado rockies", "rockies", "colorado", "col"],
    "DET": ["detroit tigers", "tigers", "detroit", "det"],
    "HOU": ["houston astros", "astros", "houston", "hou"],
    "KC": ["kansas city royals", "royals", "kansas city", "kc", "kcr"],
    "LAA": ["los angeles angels", "la angels", "angels", "laa", "ana"],
    "LAD": ["los angeles dodgers", "la dodgers", "dodgers", "lad"],
    "MIA": ["miami marlins", "marlins", "miami", "mia"],
    "MIL": ["milwaukee brewers", "brewers", "milwaukee", "mil"],
    "MIN": ["minnesota twins", "twins", "minnesota", "min"],
    "NYM": ["new york mets", "mets", "nym"],
    "NYY": ["new york yankees", "yankees", "nyy"],
    "OAK": ["oakland athletics", "athletics", "a's", "as", "oak", "ath"],
    "PHI": ["philadelphia phillies", "phillies", "philadelphia", "phi"],
    "PIT": ["pittsburgh pirates", "pirates", "pittsburgh", "pit"],
    "SD": ["san diego padres", "padres", "san diego", "sd", "sdp"],
    "SF": ["san francisco giants", "giants", "san francisco", "sf", "sfg"],
    "SEA": ["seattle mariners", "mariners", "seattle", "sea"],
    "STL": ["st louis cardinals", "saint louis cardinals", "cardinals", "st louis", "stl"],
    "TB": ["tampa bay rays", "rays", "tampa bay", "tb", "tbr"],
    "TEX": ["texas rangers", "rangers", "texas", "tex"],
    "TOR": ["toronto blue jays", "blue jays", "toronto", "tor"],
    "WSH": ["washington nationals", "nationals", "washington", "wsh", "was"],
}

NBA: dict[str, list[str]] = {
    "ATL": ["atlanta hawks", "hawks", "atlanta", "atl"],
    "BOS": ["boston celtics", "celtics", "boston", "bos"],
    "BKN": ["brooklyn nets", "nets", "brooklyn", "bkn", "brl"],
    "CHA": ["charlotte hornets", "hornets", "charlotte", "cha"],
    "CHI": ["chicago bulls", "bulls", "chicago", "chi"],
    "CLE": ["cleveland cavaliers", "cavaliers", "cavs", "cleveland", "cle"],
    "DAL": ["dallas mavericks", "mavericks", "mavs", "dallas", "dal"],
    "DEN": ["denver nuggets", "nuggets", "denver", "den"],
    "DET": ["detroit pistons", "pistons", "detroit", "det"],
    "GSW": ["golden state warriors", "warriors", "golden state", "gsw", "gs"],
    "HOU": ["houston rockets", "rockets", "houston", "hou"],
    "IND": ["indiana pacers", "pacers", "indiana", "ind"],
    "LAC": ["la clippers", "los angeles clippers", "clippers", "lac"],
    "LAL": ["los angeles lakers", "la lakers", "lakers", "lal"],
    "MEM": ["memphis grizzlies", "grizzlies", "memphis", "mem"],
    "MIA": ["miami heat", "heat", "miami", "mia"],
    "MIL": ["milwaukee bucks", "bucks", "milwaukee", "mil"],
    "MIN": ["minnesota timberwolves", "timberwolves", "wolves", "minnesota", "min"],
    "NOP": ["new orleans pelicans", "pelicans", "new orleans", "nop", "no"],
    "NYK": ["new york knicks", "knicks", "nyk", "ny"],
    "OKC": ["oklahoma city thunder", "thunder", "oklahoma city", "okc"],
    "ORL": ["orlando magic", "magic", "orlando", "orl"],
    "PHI": ["philadelphia 76ers", "76ers", "sixers", "philadelphia", "phi"],
    "PHX": ["phoenix suns", "suns", "phoenix", "phx", "pho"],
    "POR": ["portland trail blazers", "trail blazers", "blazers", "portland", "por"],
    "SAC": ["sacramento kings", "kings", "sacramento", "sac"],
    "SAS": ["san antonio spurs", "spurs", "san antonio", "sas", "sa"],
    "TOR": ["toronto raptors", "raptors", "toronto", "tor"],
    "UTA": ["utah jazz", "jazz", "utah", "uta"],
    "WAS": ["washington wizards", "wizards", "washington", "was", "wsh"],
}

NHL: dict[str, list[str]] = {
    "ANA": ["anaheim ducks", "ducks", "anaheim", "ana"],
    "ARI": ["arizona coyotes", "coyotes", "arizona", "ari", "utah hockey club", "utah"],
    "BOS": ["boston bruins", "bruins", "boston", "bos"],
    "BUF": ["buffalo sabres", "sabres", "buffalo", "buf"],
    "CGY": ["calgary flames", "flames", "calgary", "cgy"],
    "CAR": ["carolina hurricanes", "hurricanes", "carolina", "car"],
    "CHI": ["chicago blackhawks", "blackhawks", "chicago", "chi"],
    "COL": ["colorado avalanche", "avalanche", "colorado", "col"],
    "CBJ": ["columbus blue jackets", "blue jackets", "columbus", "cbj"],
    "DAL": ["dallas stars", "stars", "dallas", "dal"],
    "DET": ["detroit red wings", "red wings", "detroit", "det"],
    "EDM": ["edmonton oilers", "oilers", "edmonton", "edm"],
    "FLA": ["florida panthers", "panthers", "florida", "fla"],
    "LAK": ["los angeles kings", "la kings", "kings", "lak", "la"],
    "MIN": ["minnesota wild", "wild", "minnesota", "min"],
    "MTL": ["montreal canadiens", "canadiens", "montreal", "mtl", "mon"],
    "NSH": ["nashville predators", "predators", "nashville", "nsh"],
    "NJD": ["new jersey devils", "devils", "new jersey", "njd", "nj"],
    "NYI": ["new york islanders", "islanders", "nyi"],
    "NYR": ["new york rangers", "rangers", "nyr"],
    "OTT": ["ottawa senators", "senators", "ottawa", "ott"],
    "PHI": ["philadelphia flyers", "flyers", "philadelphia", "phi"],
    "PIT": ["pittsburgh penguins", "penguins", "pittsburgh", "pit"],
    "SEA": ["seattle kraken", "kraken", "seattle", "sea"],
    "SJS": ["san jose sharks", "sharks", "san jose", "sjs", "sj"],
    "STL": ["st louis blues", "saint louis blues", "blues", "stl"],
    "TBL": ["tampa bay lightning", "lightning", "tampa bay", "tbl", "tb"],
    "TOR": ["toronto maple leafs", "maple leafs", "leafs", "toronto", "tor"],
    "VAN": ["vancouver canucks", "canucks", "vancouver", "van"],
    "VGK": ["vegas golden knights", "golden knights", "vegas", "vgk"],
    "WPG": ["winnipeg jets", "jets", "winnipeg", "wpg"],
    "WSH": ["washington capitals", "capitals", "washington", "wsh", "was"],
}

NFL: dict[str, list[str]] = {
    "ARI": ["arizona cardinals", "cardinals", "arizona", "ari"],
    "ATL": ["atlanta falcons", "falcons", "atlanta", "atl"],
    "BAL": ["baltimore ravens", "ravens", "baltimore", "bal"],
    "BUF": ["buffalo bills", "bills", "buffalo", "buf"],
    "CAR": ["carolina panthers", "panthers", "carolina", "car"],
    "CHI": ["chicago bears", "bears", "chicago", "chi"],
    "CIN": ["cincinnati bengals", "bengals", "cincinnati", "cin"],
    "CLE": ["cleveland browns", "browns", "cleveland", "cle"],
    "DAL": ["dallas cowboys", "cowboys", "dallas", "dal"],
    "DEN": ["denver broncos", "broncos", "denver", "den"],
    "DET": ["detroit lions", "lions", "detroit", "det"],
    "GB": ["green bay packers", "packers", "green bay", "gb", "gnb"],
    "HOU": ["houston texans", "texans", "houston", "hou"],
    "IND": ["indianapolis colts", "colts", "indianapolis", "ind"],
    "JAX": ["jacksonville jaguars", "jaguars", "jacksonville", "jax", "jac"],
    "KC": ["kansas city chiefs", "chiefs", "kansas city", "kc"],
    "LAC": ["los angeles chargers", "la chargers", "chargers", "lac"],
    "LAR": ["los angeles rams", "la rams", "rams", "lar"],
    "LV": ["las vegas raiders", "raiders", "las vegas", "lv", "oak"],
    "MIA": ["miami dolphins", "dolphins", "miami", "mia"],
    "MIN": ["minnesota vikings", "vikings", "minnesota", "min"],
    "NE": ["new england patriots", "patriots", "new england", "ne"],
    "NO": ["new orleans saints", "saints", "new orleans", "no", "nor"],
    "NYG": ["new york giants", "giants", "nyg"],
    "NYJ": ["new york jets", "jets", "nyj"],
    "PHI": ["philadelphia eagles", "eagles", "philadelphia", "phi"],
    "PIT": ["pittsburgh steelers", "steelers", "pittsburgh", "pit"],
    "SEA": ["seattle seahawks", "seahawks", "seattle", "sea"],
    "SF": ["san francisco 49ers", "49ers", "niners", "san francisco", "sf", "sfo"],
    "TB": ["tampa bay buccaneers", "buccaneers", "bucs", "tampa bay", "tb"],
    "TEN": ["tennessee titans", "titans", "tennessee", "ten"],
    "WAS": ["washington commanders", "commanders", "washington", "was", "wsh"],
}

LEAGUE_ALIASES: dict[str, dict[str, list[str]]] = {
    "mlb": MLB,
    "nba": NBA,
    "nhl": NHL,
    "nfl": NFL,
}

# Kalshi series ticker -> league slug
SERIES_TO_LEAGUE: dict[str, str] = {
    "KXMLBGAME": "mlb",
    "KXNBAGAME": "nba",
    "KXNHLGAME": "nhl",
    "KXNFLGAME": "nfl",
    "KXWNBAGAME": "wnba",
    "KXNCAAFGAME": "ncaaf",
    "KXNCAAMBGAME": "ncaab",
    "KXNCAAWBGAME": "ncaaw",
    "KXEPLGAME": "epl",
    "KXMLSGAME": "mls",
    "KXLALIGAGAME": "laliga",
    "KXUCLGAME": "ucl",
    "KXNBA": "nba",
}

# Polymarket sport slug -> league
POLY_SPORT_TO_LEAGUE: dict[str, str] = {
    "mlb": "mlb",
    "nba": "nba",
    "nhl": "nhl",
    "nfl": "nfl",
    "wnba": "wnba",
    "cfb": "ncaaf",
    "ncaaf": "ncaaf",
    "cbb": "ncaab",
    "ncaab": "ncaab",
    "epl": "epl",
    "mls": "mls",
    "laliga": "laliga",
    "ucl": "ucl",
}


def build_alias_index(league: str) -> dict[str, str]:
    """
    Map normalized alias text -> canonical code for a league.
    """
    table = LEAGUE_ALIASES.get(league.lower(), {})
    index: dict[str, str] = {}
    for code, aliases in table.items():
        index[_norm_text(code)] = code
        for alias in aliases:
            index[_norm_text(alias)] = code
    return index


_ALIAS_CACHE: dict[str, dict[str, str]] = {}


def canonicalize_team(league: str, raw: str) -> str:
    """
    Map a team name or code to a canonical code when known; otherwise normalized text.
    """
    league_key = (league or "").lower()
    if league_key not in _ALIAS_CACHE:
        _ALIAS_CACHE[league_key] = build_alias_index(league_key)
    index = _ALIAS_CACHE[league_key]
    key = _norm_text(raw)
    if not key:
        return ""
    if key in index:
        return index[key]
    # Prefer longer alias matches contained in the string
    best = ""
    best_len = 0
    for alias, code in index.items():
        if alias and alias in key and len(alias) > best_len:
            best = code
            best_len = len(alias)
    if best:
        return best
    return key


def league_from_kalshi_series(series_ticker: str) -> str:
    series = (series_ticker or "").upper()
    if series in SERIES_TO_LEAGUE:
        return SERIES_TO_LEAGUE[series]
    # Heuristic: KXMLBGAME -> mlb
    m = re.match(r"^KX([A-Z0-9]+?)GAME$", series)
    if m:
        return m.group(1).lower()
    return series.lower()


def league_from_poly_sport(sport: str) -> str:
    sport_key = (sport or "").lower()
    return POLY_SPORT_TO_LEAGUE.get(sport_key, sport_key)
