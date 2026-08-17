"""Controlled dictionaries and lookup tables for field extraction and fuzzy matching."""

import re

COUNTRIES = {
    "england": "England",
    "eng1and": "England",
    "uk": "UK",
    "uks": "UK",
    "u.k.": "UK",
    "u.k": "UK",
    "unitedkingdom": "United Kingdom",
    "greatbritain": "Great Britain",
    "ireland": "Ireland",
    "lreland": "Ireland",
    "1reland": "Ireland",
    "scotland": "Scotland",
    "wales": "Wales",
}

PROVIDERS_MAP = [
    ("hutchisonwhampoa", "Hutchison Whampoa"),
    ("hutchison", "Hutchison Whampoa"),
    ("huitchisonwhampoa", "Hutchison Whampoa"),
    ("huitchison", "Hutchison Whampoa"),
    ("t-mobile", "T-Mobile"),
    ("tmobile", "T-Mobile"),
    ("vodafone", "Vodafone"),
    ("vodaf0ne", "Vodafone"),
    ("orange", "Orange"),
    ("virgin", "Virgin"),
    ("o2", "O2"),
    ("02", "O2"),
]

PROFESSIONS_MAP = {
    "self employed": "Self Employed",
    "selfemployed": "Self Employed",
    "self-employed": "Self Employed",
    "professional": "Professional",
    "professional.": "Professional",
    "services": "Services",
    "service": "Service",
    "business": "Business",
    "student": "Student",
    "others": "Others",
    "other": "Others",
    "fixed income": "Fixed Income",
    "fixedincome": "Fixed Income",
    "fixed incame": "Fixed Income",
    "unemployed": "Unemployed",
    "un employed": "Unemployed",
}

PLAN_STARTS = {
    "turbo", "turbocall",
    "classic", "classicsms", "clasic", "clasicsms", "clasicplus", "classicsms+",
    "smspro", "sms", "sms+",
    "premium", "premiumplus",
    "ultra", "ultraplus", "ulira", "uliraplus",
    "economy", "economyplus",
    "alacarte", "alacartepack", "ala",
    "ultimate", "ultimateplus", "ultimata",
    "callplus", "call",
}

CARD_STARTS = {
    "master", "mastercard", "mastertitanium", "visa", "visatitanium", "visagold"
}

NETWORKS = {
    "gsm": "GSM",
    "cdma": "CDMA",
    "cdma+gsm": "CDMA+GSM",
    "cdma*gsm": "CDMA+GSM",
    "cdma+cdma": "CDMA+CDMA",
    "cdmagsm": "CDMA+GSM",
    "cdmacdma": "CDMA+CDMA",
}

MODEL_BRANDS = {
    "nokia", "siemens", "samsung", "apple", "motorola", "sony", "lg", "htc",
    "huawei", "blackberry", "ericsson", "alcatel", "google", "xiaomi", "oneplus"
}

STREET_SUFFIX_PATTERN = re.compile(
    r"\b(Road|Street|Lane|Avenue|Drive|Way|Square|Building|House|Gardens|Crescent|Court|Walk|Close|Hill|Place|Park|Terrace|Grove|Rise|Row|Mews|Parade|Yard)\b",
    re.IGNORECASE,
)
