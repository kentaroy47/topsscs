"""Group OpenAlex institutions outside Japan, like organizations.py does for Japan.

OpenAlex splits companies into many records ("Samsung (South Korea)", "Samsung
Electronics (South Korea)", "Samsung Advanced Institute of Technology", ...).
Companies are merged per brand and country; research institutes are merged into
a parent only when the parent is a company in the same country, or the Chinese
Academy of Sciences. Universities are never merged.
"""
import re

# brand display name, regex on the OpenAlex display name
BRANDS = [
    ("Samsung", r"^Samsung\b(?! Medical| Hospital)"),
    ("SK hynix", r"^SK [Hh]ynix|^Hynix"),
    ("LG", r"^LG\b"),
    ("IBM", r"^IBM\b"),
    ("Intel", r"^Intel\b"),
    ("TSMC", r"^Taiwan Semiconductor Manufacturing|^TSMC\b"),
    ("MediaTek", r"^MediaTek"),
    ("Qualcomm", r"^Qualcomm"),
    ("Apple", r"^Apple\b"),
    ("Google", r"^Google\b|^Alphabet\b"),
    ("Meta", r"^Meta\b|^Facebook"),
    ("Microsoft", r"^Microsoft"),
    ("Amazon", r"^Amazon\b"),
    ("NVIDIA", r"^Nvidia|^NVIDIA"),
    ("AMD", r"^Advanced Micro Devices|^AMD\b"),
    ("Texas Instruments", r"^Texas Instruments"),
    ("Analog Devices", r"^Analog Devices"),
    ("Broadcom", r"^Broadcom"),
    ("Marvell", r"^Marvell"),
    ("Huawei", r"^Huawei|^HiSilicon"),
    ("Micron", r"^Micron\b"),
    ("NXP", r"^NXP"),
    ("Infineon", r"^Infineon"),
    ("STMicroelectronics", r"^STMicroelectronics"),
    ("Realtek", r"^Realtek"),
    ("Nokia", r"^Nokia"),
    ("Ericsson", r"^Ericsson"),
    ("Bosch", r"^Robert Bosch|^Bosch\b"),
    ("Cadence", r"^Cadence"),
    ("Synopsys", r"^Synopsys"),
    ("Rambus", r"^Rambus"),
    ("Western Digital", r"^Western Digital|^SanDisk|^Sandisk"),
    ("Sony", r"^Sony\b"),
    ("Apple", r"^Apple\b"),
]
_BRANDS = [(name, re.compile(pat)) for name, pat in BRANDS]
CAS = "Chinese Academy of Sciences"
GROUPABLE = {"company", "facility", "other", "nonprofit", "government", "archive"}


def canonical(iid, insts):
    """Map an OpenAlex institution ID to its group.

    insts: {id: {"name", "cc", "type", "lineage"}} (data/openalex_institutions.json).
    Returns (group_id, name, cc, type)."""
    inst = insts.get(iid)
    if not inst:
        return None
    name, cc, typ = inst["name"], inst["cc"], inst["type"]
    if typ == "education":
        return iid, name, cc, typ
    # parent company in the same country, or the Chinese Academy of Sciences.
    # OpenAlex lineage lists the institution and its ancestors in no particular order.
    parents = [(x, insts[x]) for x in inst["lineage"] if x != iid and insts.get(x)]
    parents = [(x, a) for x, a in parents if (a["type"] == "company" and a["cc"] == cc) or a["name"] == CAS]
    if parents:
        x, a = min(parents, key=lambda xa: len(xa[1]["lineage"]))  # the root-most ancestor
        iid, name, typ = x, a["name"], a["type"]
    if typ in GROUPABLE:
        for brand, rx in _BRANDS:
            if rx.search(name):
                return f"B-{brand.lower().replace(' ', '-')}-{cc.lower()}", brand, cc, "company"
    return iid, name, cc, typ
