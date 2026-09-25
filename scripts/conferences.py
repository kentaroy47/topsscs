"""Venue and edition definitions shared by the build scripts."""

FETCH_YEARS = range(2021, 2027)

# Editions, like topcsuniv.org: a rolling live window and a frozen release.
EDITIONS = [
    {"id": "live", "label": "2022–2026 LIVE", "years": range(2022, 2027), "live": True, "path": ""},
    {"id": "2021-2025", "label": "2021–2025 確定版", "years": range(2021, 2026), "live": False, "path": "2021-2025/"},
]

# Championship weight per tier: F1 points are multiplied by this.
TIER_WEIGHT = {1: 1.0, 2: 0.5}

# Order = tab order. `month` is the usual month the proceedings appear, used to
# decide which conference was reflected most recently (journals have none).
# `joint_from`: from this year on the venue also has a technology/device track,
# and only circuits-track papers are counted.
CONFERENCES = [
    {"id": "isscc", "short": "ISSCC", "kind": "conference", "tier": 1, "month": 2,
     "name": "IEEE International Solid-State Circuits Conference", "url": "https://www.isscc.org/"},
    {"id": "vlsi", "short": "VLSI", "kind": "conference", "tier": 1, "month": 6, "joint_from": 2022,
     "name": "IEEE/JSAP Symposium on VLSI Technology and Circuits", "url": "https://www.vlsisymposium.org/"},
    {"id": "jssc", "short": "JSSC", "kind": "journal", "tier": 1, "month": None,
     "name": "IEEE Journal of Solid-State Circuits",
     "url": "https://sscs.ieee.org/publications/ieee-journal-of-solid-state-circuits/"},
    {"id": "cicc", "short": "CICC", "kind": "conference", "tier": 2, "month": 4,
     "name": "IEEE Custom Integrated Circuits Conference", "url": "https://www.ieee-cicc.org/"},
    {"id": "asscc", "short": "A-SSCC", "kind": "conference", "tier": 2, "month": 11,
     "name": "IEEE Asian Solid-State Circuits Conference", "url": "https://www.a-sscc.org/"},
    {"id": "esscirc", "short": "ESSERC", "kind": "conference", "tier": 2, "month": 9, "joint_from": 2024,
     "name": "IEEE European Solid-State Electronics Research Conference (ESSCIRC/ESSERC)",
     "url": "https://www.esserc.org/"},
]
BY_ID = {c["id"]: c for c in CONFERENCES}


def weight(conf_id):
    return TIER_WEIGHT[BY_ID[conf_id]["tier"]]


def needs_track(conf_id, year):
    j = BY_ID[conf_id].get("joint_from")
    return j is not None and year >= j
