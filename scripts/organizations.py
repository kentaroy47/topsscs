"""Japanese companies and research institutes: slug, Japanese name, English name, affiliation regex.

Group companies are merged under the parent (e.g. all Sony entities -> Sony).
Foreign companies count only for affiliations located in Japan and are shown
with "(日本拠点)".
"""
import re

from universities import FORMER, FOREIGN

# slug, ja, en, pattern, foreign-company flag
ORGANIZATIONS = [
    # --- companies -----------------------------------------------------------
    ("sony", "ソニー", "Sony", r"\bSony\b", False),
    ("kioxia", "キオクシア", "Kioxia", r"Kioxia|KIOXIA|Toshiba Memory", False),
    ("renesas", "ルネサス エレクトロニクス", "Renesas Electronics", r"Renesas", False),
    ("toshiba", "東芝", "Toshiba", r"Toshiba(?! Memory)", False),
    ("ntt", "NTT", "NTT", r"\bNTT\b|Nippon Telegraph", False),
    ("hitachi", "日立製作所", "Hitachi", r"Hitachi", False),
    ("fujitsu", "富士通", "Fujitsu", r"Fujitsu", False),
    ("nec", "NEC", "NEC", r"\bNEC\b", False),
    ("mitsubishi-electric", "三菱電機", "Mitsubishi Electric", r"Mitsubishi Electric", False),
    ("panasonic", "パナソニック", "Panasonic", r"Panasonic|Nuvoton Technology Corporation Japan", False),
    ("canon", "キヤノン", "Canon", r"\bCanon\b", False),
    ("sel", "半導体エネルギー研究所", "Semiconductor Energy Laboratory", r"Semiconductor Energy Lab", False),
    ("socionext", "ソシオネクスト", "Socionext", r"Socionext", False),
    ("denso", "デンソー", "DENSO", r"\bDENSO\b|\bDenso\b|NSITEXE", False),
    ("mirise", "ミライズテクノロジーズ", "MIRISE Technologies", r"MIRISE", False),
    ("toyota", "トヨタ自動車", "Toyota Motor", r"Toyota Motor|Toyota Central R", False),
    ("murata", "村田製作所", "Murata Manufacturing", r"\bMurata\b", False),
    ("akm", "旭化成エレクトロニクス", "Asahi Kasei Microdevices", r"Asahi Kasei", False),
    ("tel", "東京エレクトロン", "Tokyo Electron", r"Tokyo Electron", False),
    ("advantest", "アドバンテスト", "Advantest", r"Advantest", False),
    ("thine", "ザインエレクトロニクス", "THine Electronics", r"THine", False),
    ("rohm", "ローム", "ROHM", r"\bROHM\b|\bRohm\b|LAPIS", False),
    ("sharp", "シャープ", "Sharp", r"\bSharp Corp", False),
    ("nikon", "ニコン", "Nikon", r"\bNikon\b", False),
    ("olympus", "オリンパス", "Olympus", r"Olympus", False),
    ("epson", "セイコーエプソン", "Seiko Epson", r"Epson", False),
    ("kyocera", "京セラ", "Kyocera", r"Kyocera", False),
    ("oki", "沖電気工業", "Oki Electric", r"\bOki Electric|\bOKI\b", False),
    ("ricoh", "リコー", "Ricoh", r"Ricoh", False),
    ("toppan", "TOPPAN", "TOPPAN", r"Toppan|TOPPAN", False),
    ("fujikura", "フジクラ", "Fujikura", r"Fujikura", False),
    ("hamamatsu-photonics", "浜松ホトニクス", "Hamamatsu Photonics", r"Hamamatsu Photonics", False),
    ("brookman", "ブルックマンテクノロジ", "Brookman Technology", r"Brookman", False),
    ("preferred-networks", "Preferred Networks", "Preferred Networks", r"Preferred Networks", False),
    ("axelspace", "アクセルスペース", "Axelspace", r"Axelspace", False),
    ("rapidus", "Rapidus", "Rapidus", r"Rapidus", False),
    ("aichi-steel", "愛知製鋼", "Aichi Steel", r"Aichi Steel", False),
    ("megachips", "メガチップス", "MegaChips", r"MegaChips", False),
    ("pi-crystal", "パイクリスタル", "PI-CRYSTAL", r"PI-CRYSTAL", False),
    ("interstellar", "インターステラテクノロジズ", "Interstellar Technologies", r"Interstellar Technologies", False),
    ("brillnics", "ブリルニクス", "Brillnics", r"Brillnics", False),
    # --- research institutes -------------------------------------------------
    ("aist", "産業技術総合研究所", "AIST", r"\bAIST\b|Advanced Industrial Science|National Institute of Advanced Science and Technology", False),
    ("nict", "情報通信研究機構", "NICT", r"\bNICT\b|National Institute of Information and Communications Tech", False),
    ("riken", "理化学研究所", "RIKEN", r"RIKEN|\bRiken\b", False),
    ("nims", "物質・材料研究機構", "NIMS", r"National Institute for Materials Science|\bNIMS\b", False),
    ("jaxa", "宇宙航空研究開発機構", "JAXA", r"\bJAXA\b|Japan Aerospace Exploration", False),
    ("kek", "高エネルギー加速器研究機構", "KEK", r"\bKEK\b|High Energy Accelerator Research", False),
    ("qst", "量子科学技術研究開発機構", "QST", r"National Institutes for Quantum|\bQST\b", False),
    ("jst", "科学技術振興機構", "JST", r"\bJST\b|Japan Science and Technology Agency", False),
    ("nii", "国立情報学研究所", "NII", r"National Institute of Informatics", False),
    # --- foreign companies' Japan sites ---------------------------------------
    ("tsmc-japan", "TSMC（日本拠点）", "TSMC Japan", r"\bTSMC\b|Taiwan Semiconductor", True),
    ("micron-japan", "Micron（日本拠点）", "Micron Japan", r"Micron", True),
    ("wdc-japan", "Western Digital / Sandisk（日本拠点）", "Western Digital / Sandisk Japan", r"Western Digital|SanDisk|Sandisk", True),
    ("ibm-japan", "IBM（日本拠点）", "IBM Japan", r"\bIBM\b", True),
    ("sss-japan", "Samsung（日本拠点）", "Samsung Japan", r"Samsung", True),
    ("ams-japan", "Analog Devices（日本拠点）", "Analog Devices Japan", r"Analog Devices", True),
    ("omnivision-japan", "OmniVision（日本拠点）", "OmniVision Japan", r"OmniVision", True),
    ("huawei-japan", "Huawei（日本拠点）", "Huawei Japan", r"Huawei", True),
    ("usj", "ユナイテッド・セミコンダクター・ジャパン", "United Semiconductor Japan", r"United Semiconductor Japan", True),
    ("intel-japan", "Intel（日本拠点）", "Intel Japan", r"\bIntel\b", True),
    ("mediatek-japan-site", "MediaTek（日本拠点）", "MediaTek Japan", r"MediaTek", True),
    ("qualcomm-japan", "Qualcomm（日本拠点）", "Qualcomm Japan", r"Qualcomm", True),
]

COMPILED = [(slug, ja, en, re.compile(pat), foreign) for slug, ja, en, pat, foreign in ORGANIZATIONS]
BY_SLUG = {slug: (ja, en) for slug, ja, en, _, _ in ORGANIZATIONS}
# Overseas sites that the shared country list misses: US state codes (",CA"), U.K., Europe.
OVERSEAS = re.compile(r",\s*[A-Z]{2}\s*(,|$)|\bU\.K\b|\bEurope\b|\bCambridge\b|\bBristol\b|\bB\.V\b|\bGmbH\b")
JAPAN = re.compile(r"Japan|Tokyo|Kanagawa|Yokohama|Kawasaki|Atsugi|Osaka|Kyoto|Nagoya|Aichi|Tsukuba|Ibaraki|"
                   r"Yokkaichi|Kumamoto|Nagasaki|Hiroshima|Sendai|Fukuoka|Sapporo|Hokkaido|Kobe|Saitama|Chiba")


def match(aff: str):
    """Return the organization slug for an affiliation string, or None."""
    if FORMER.search(aff):
        return None
    for slug, _ja, _en, rx, foreign in COMPILED:
        if rx.search(aff):
            if foreign:
                # foreign companies: only their sites in Japan
                return slug if "Japan" in aff else None
            if (FOREIGN.search(aff) or OVERSEAS.search(aff)) and not JAPAN.search(aff):
                return None
            return slug
    return None
