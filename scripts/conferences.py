"""Conference definitions shared by the build scripts."""

YEARS = range(2022, 2027)
EDITION = "2022–2026"

# Order = tab order. `month` is the usual month the proceedings appear, used to
# decide which conference was reflected most recently.
CONFERENCES = [
    {"id": "isscc", "short": "ISSCC", "name": "IEEE International Solid-State Circuits Conference",
     "url": "https://www.isscc.org/", "month": 2},
    {"id": "vlsi", "short": "VLSI", "name": "IEEE/JSAP Symposium on VLSI Technology and Circuits",
     "url": "https://www.vlsisymposium.org/", "month": 6},
    {"id": "cicc", "short": "CICC", "name": "IEEE Custom Integrated Circuits Conference",
     "url": "https://www.ieee-cicc.org/", "month": 4},
    {"id": "asscc", "short": "A-SSCC", "name": "IEEE Asian Solid-State Circuits Conference",
     "url": "https://www.a-sscc.org/", "month": 11},
    {"id": "esscirc", "short": "ESSERC", "name": "IEEE European Solid-State Electronics Research Conference (ESSCIRC/ESSERC)",
     "url": "https://www.esserc.org/", "month": 9},
]
BY_ID = {c["id"]: c for c in CONFERENCES}
