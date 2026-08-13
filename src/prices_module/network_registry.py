"""Canonical network name registry for Ukrainian fuel station networks.

Maps all known name variants (from Minfin, VseAZS, and OSM) to a single
canonical display name per network. Used by both the fuel-price ETL
(transform step) and the station-import DAG.
"""

from src.utils.logs import Logger

# Canonical display name → set of known aliases (case-insensitive lookup).
# Each alias will be lowercased + stripped during registry build.
_REGISTRY: dict[str, set[str]] = {
    # ── Major networks (Latin branding) ─────────────────────────────
    "OKKO": {
        "OKKO", "ОККО", "Окко", "Okko",
    },
    "WOG": {
        "WOG", "ВОГ", "Вог",
    },
    "KLO": {
        "KLO", "КЛО", "Кло",
    },
    "UPG": {
        "UPG", "УПГ",
    },
    "SOCAR": {
        "SOCAR", "Socar", "СОКАР", "Сокар",
    },
    "Shell": {
        "Shell", "shell", "Шелл",
    },
    "AMIC Energy": {
        "AMIC", "AMIC Energy", "Amic", "Amic energy", "Амік",
    },
    "BVS": {
        "BVS", "БВС",
    },
    "Mango": {
        "Mango", "MANGO", "Манго",
    },
    "Marshal": {
        "Marshal", "MARSHAL", "Маршал", "Marsel",
    },
    "Motto": {
        "Motto", "МОТТО", "Мотто",
    },
    "Parallel": {
        "Parallel", "Paralell", "Паралель",
    },
    "EURO5": {
        "EURO5", "Euro 5", "Євро 5", "Евро 5",
    },
    "Grand Petrol": {
        "Grand Petrol", "GRAND-PETROL", "Гранд Петрол",
    },
    "Chipo": {
        "Chipo", "CHIPO", "Чіпо",
    },
    "SUN OIL": {
        "SUN OIL", "Sun Oil", "Sun oil", "SunOil", "Sunoil",
    },
    "Brent Oil": {
        "Brent Oil", "Brent oil",
    },

    # ── Major networks (Cyrillic branding) ──────────────────────────
    "Укрнафта": {
        "UKRNAFTA", "Ukrnafta", "Укрнафта", "укрнафта",
    },
    "БРСМ-Нафта": {
        "БРСМ-Нафта", "БРСМ-нафта", "БРСМ Нафта", "БРСМ",
        "BRSM-Nafta", "Glusco",  # Glusco rebranded to БРСМ-Нафта
    },
    "Авіас": {
        "Авіас", "АВІАС", "Авіас Плюс",
    },
    "Авантаж 7": {
        "Авантаж 7", "Авантаж", "Advantage 7", "Avantage 7",
        "Avantage-7", "Avantage7", "Avantge 7",
    },
    "Маркет": {
        "Маркет", "АЗС МАРКЕТ",
    },
    "СВОЇ": {
        "СВОЇ", "Свої",
    },
    "ДНІПРОНАФТА": {
        "ДНІПРОНАФТА", "Дніпронафта",
    },
    "Автотранс": {
        "Автотранс",
    },
    "Катрал": {
        "Катрал",
    },
    "Кворум": {
        "Кворум",
    },
    "Олас": {
        "Олас",
    },
    "Рур груп": {
        "Рур груп",
    },
    "Фактор": {
        "Фактор",
    },

    # ── Smaller / regional networks ─────────────────────────────────
    "VST": {
        "VST", "ВСТ",
    },
    "VostokGaz": {
        "VostokGaz", "VostokGas",
    },
    "ZOG": {
        "ZOG", "ЗОГ",
    },
    "RLS": {
        "RLS", "РЛС",
    },
    "Rodnik": {
        "Rodnik", "Роднік",
    },
    "Neftek": {
        "Neftek", "Нефтек",
    },
    "Ovis": {
        "Ovis", "Овіс",
    },
    "Green Wave": {
        "Green Wave", "Грін Вейв",
    },
    "U.GO": {
        "U.GO",
    },
    "Ultra": {
        "Ultra", "Ультра",
    },
}

# ── Build inverted lookup ───────────────────────────────────────────
_ALIAS_TO_CANONICAL: dict[str, str] = {}

for canonical, aliases in _REGISTRY.items():
    for alias in aliases:
        key = alias.strip().lower()
        if key in _ALIAS_TO_CANONICAL:
            existing = _ALIAS_TO_CANONICAL[key]
            if existing != canonical:
                raise ValueError(
                    f"Alias collision: '{alias}' maps to both "
                    f"'{existing}' and '{canonical}'"
                )
        _ALIAS_TO_CANONICAL[key] = canonical


def normalize_network_name(raw: str) -> str:
    """Normalize a raw network name to its canonical display form.

    Looks up the lowercased, stripped input in the alias registry.
    If found, returns the canonical display name.
    If not found, logs a warning and returns the raw name as-is,
    so it still gets inserted, just not merged with known networks.
    """
    key = raw.strip().lower()
    canonical = _ALIAS_TO_CANONICAL.get(key)
    if canonical is not None:
        return canonical
    Logger.warning(
        "Unrecognized network name — not in registry",
        raw_name=raw,
    )
    return raw


def is_known_network(raw: str) -> bool:
    return raw.strip().lower() in _ALIAS_TO_CANONICAL
