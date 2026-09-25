"""Japanese universities: slug, Japanese name, English name, affiliation regex.

Order matters: more specific patterns come first (e.g. Tokyo University of
Science before University of Tokyo). Tokyo Tech and Tokyo Medical and Dental
University are merged into Institute of Science Tokyo (2024 merger), as on
topcsuniv.org.
"""
import re

UNIVERSITIES = [
    # slug, ja, en, pattern
    ("institute-of-science-tokyo", "東京科学大学", "Institute of Science Tokyo",
     r"^Institute of Science$|Institute of Science,? Tokyo|Science Tokyo|Tokyo Institute of Technology|Tokyo Tech\b|Tokyo Medical and Dental"),
    ("tokyo-university-of-science", "東京理科大学", "Tokyo University of Science", r"Tokyo Univ(ersity|\.) of Sci"),
    ("tokyo-city-university", "東京都市大学", "Tokyo City University", r"Tokyo City Univ"),
    ("tokyo-metropolitan-university", "東京都立大学", "Tokyo Metropolitan University", r"Tokyo Metropolitan Univ"),
    ("tokyo-university-of-agriculture-and-technology", "東京農工大学", "Tokyo University of Agriculture and Technology",
     r"Tokyo Univ(ersity|\.) of Agriculture and Tech"),
    ("tokyo-denki-university", "東京電機大学", "Tokyo Denki University", r"Tokyo Denki Univ"),
    ("tokyo-university-of-technology", "東京工科大学", "Tokyo University of Technology", r"Tokyo Univ(ersity|\.) of Technology"),
    ("osaka-electro-communication-university", "大阪電気通信大学", "Osaka Electro-Communication University",
     r"Osaka Electro-?\s?Communication"),
    ("university-of-electro-communications", "電気通信大学", "The University of Electro-Communications",
     r"Electro-?\s?Communications"),
    ("university-of-tokyo", "東京大学", "The University of Tokyo",
     r"Univ(ersity|\.) of Tokyo|\bUTokyo\b|Tokyo Univ(ersity|\.)(?! of)"),
    ("kyoto-institute-of-technology", "京都工芸繊維大学", "Kyoto Institute of Technology", r"Kyoto Institute of Tech"),
    ("kyoto-sangyo-university", "京都産業大学", "Kyoto Sangyo University", r"Kyoto Sangyo"),
    ("kyoto-university", "京都大学", "Kyoto University", r"Kyoto Univ(ersity|\.)"),
    ("osaka-metropolitan-university", "大阪公立大学", "Osaka Metropolitan University",
     r"Osaka Metropolitan|Osaka Prefecture Univ|Osaka City Univ"),
    ("osaka-institute-of-technology", "大阪工業大学", "Osaka Institute of Technology", r"Osaka Institute of Tech"),
    ("osaka-university", "大阪大学", "The University of Osaka", r"Osaka Univ(ersity|\.)|University of Osaka"),
    ("tohoku-university", "東北大学", "Tohoku University", r"Tohoku Univ"),
    ("nagoya-institute-of-technology", "名古屋工業大学", "Nagoya Institute of Technology", r"Nagoya Institute of Tech"),
    ("nagoya-university", "名古屋大学", "Nagoya University", r"Nagoya Univ"),
    ("kyushu-institute-of-technology", "九州工業大学", "Kyushu Institute of Technology", r"Kyushu Institute of Tech"),
    ("kyushu-university", "九州大学", "Kyushu University", r"Kyushu Univ"),
    ("hokkaido-university", "北海道大学", "Hokkaido University", r"Hokkaido Univ"),
    ("keio-university", "慶應義塾大学", "Keio University", r"Keio Univ"),
    ("waseda-university", "早稲田大学", "Waseda University", r"Waseda Univ"),
    ("hiroshima-city-university", "広島市立大学", "Hiroshima City University", r"Hiroshima City Univ"),
    ("hiroshima-university", "広島大学", "Hiroshima University", r"Hiroshima Univ"),
    ("kobe-university", "神戸大学", "Kobe University", r"Kobe Univ"),
    ("yokohama-national-university", "横浜国立大学", "Yokohama National University", r"Yokohama National Univ"),
    ("nara-institute-of-science-and-technology", "奈良先端科学技術大学院大学", "Nara Institute of Science and Technology",
     r"Nara Institute of Science|\bNAIST\b"),
    ("jaist", "北陸先端科学技術大学院大学", "Japan Advanced Institute of Science and Technology",
     r"Japan Advanced Institute of Science|\bJAIST\b"),
    ("oist", "沖縄科学技術大学院大学", "Okinawa Institute of Science and Technology", r"Okinawa Institute of Science|\bOIST\b"),
    ("sokendai", "総合研究大学院大学", "SOKENDAI", r"SOKENDAI|Graduate University for Advanced Studies"),
    ("university-of-tsukuba", "筑波大学", "University of Tsukuba", r"Univ(ersity|\.) of Tsukuba"),
    ("shizuoka-university", "静岡大学", "Shizuoka University", r"Shizuoka Univ"),
    ("shinshu-university", "信州大学", "Shinshu University", r"Shinshu Univ"),
    ("kanazawa-institute-of-technology", "金沢工業大学", "Kanazawa Institute of Technology", r"Kanazawa Institute of Tech"),
    ("kanazawa-university", "金沢大学", "Kanazawa University", r"Kanazawa Univ"),
    ("toyohashi-university-of-technology", "豊橋技術科学大学", "Toyohashi University of Technology", r"Toyohashi Univ"),
    ("nagaoka-university-of-technology", "長岡技術科学大学", "Nagaoka University of Technology", r"Nagaoka Univ"),
    ("toyota-technological-institute", "豊田工業大学", "Toyota Technological Institute", r"Toyota Technological Inst"),
    ("ritsumeikan-university", "立命館大学", "Ritsumeikan University", r"Ritsumeikan"),
    ("doshisha-university", "同志社大学", "Doshisha University", r"Doshisha"),
    ("ryukoku-university", "龍谷大学", "Ryukoku University", r"Ryukoku"),
    ("kansai-university", "関西大学", "Kansai University", r"Kansai Univ"),
    ("kindai-university", "近畿大学", "Kindai University", r"Kindai Univ|Kinki Univ"),
    ("university-of-hyogo", "兵庫県立大学", "University of Hyogo", r"Univ(ersity|\.) of Hyogo"),
    ("university-of-aizu", "会津大学", "The University of Aizu", r"Univ(ersity|\.) of Aizu"),
    ("kochi-university-of-technology", "高知工科大学", "Kochi University of Technology", r"Kochi Univ(ersity|\.) of Tech"),
    ("chiba-institute-of-technology", "千葉工業大学", "Chiba Institute of Technology", r"Chiba Institute of Tech"),
    ("chiba-university", "千葉大学", "Chiba University", r"Chiba Univ"),
    ("saitama-university", "埼玉大学", "Saitama University", r"Saitama Univ"),
    ("gunma-university", "群馬大学", "Gunma University", r"Gunma Univ"),
    ("ibaraki-university", "茨城大学", "Ibaraki University", r"Ibaraki Univ"),
    ("iwate-university", "岩手大学", "Iwate University", r"Iwate Univ"),
    ("yamagata-university", "山形大学", "Yamagata University", r"Yamagata Univ"),
    ("niigata-university", "新潟大学", "Niigata University", r"Niigata Univ"),
    ("university-of-toyama", "富山大学", "University of Toyama", r"Univ(ersity|\.) of Toyama|Toyama Univ"),
    ("university-of-fukui", "福井大学", "University of Fukui", r"Univ(ersity|\.) of Fukui"),
    ("gifu-university", "岐阜大学", "Gifu University", r"Gifu Univ"),
    ("mie-university", "三重大学", "Mie University", r"Mie Univ"),
    ("okayama-prefectural-university", "岡山県立大学", "Okayama Prefectural University", r"Okayama Prefectural"),
    ("okayama-university", "岡山大学", "Okayama University", r"Okayama Univ"),
    ("yamaguchi-university", "山口大学", "Yamaguchi University", r"Yamaguchi Univ"),
    ("tokushima-university", "徳島大学", "Tokushima University", r"Tokushima Univ"),
    ("kagawa-university", "香川大学", "Kagawa University", r"Kagawa Univ"),
    ("ehime-university", "愛媛大学", "Ehime University", r"Ehime Univ"),
    ("kumamoto-university", "熊本大学", "Kumamoto University", r"Kumamoto Univ"),
    ("nagasaki-university", "長崎大学", "Nagasaki University", r"Nagasaki Univ"),
    ("saga-university", "佐賀大学", "Saga University", r"Saga Univ"),
    ("university-of-miyazaki", "宮崎大学", "University of Miyazaki", r"Univ(ersity|\.) of Miyazaki"),
    ("kagoshima-university", "鹿児島大学", "Kagoshima University", r"Kagoshima Univ"),
    ("university-of-the-ryukyus", "琉球大学", "University of the Ryukyus", r"Ryukyus"),
    ("fukuoka-university", "福岡大学", "Fukuoka University", r"Fukuoka Univ"),
    ("muroran-institute-of-technology", "室蘭工業大学", "Muroran Institute of Technology", r"Muroran"),
    ("future-university-hakodate", "公立はこだて未来大学", "Future University Hakodate", r"Future Univ(ersity|\.)? Hakodate"),
    ("shibaura-institute-of-technology", "芝浦工業大学", "Shibaura Institute of Technology", r"Shibaura"),
    ("meiji-university", "明治大学", "Meiji University", r"Meiji Univ"),
    ("chuo-university", "中央大学", "Chuo University", r"Chuo Univ"),
    ("hosei-university", "法政大学", "Hosei University", r"Hosei Univ"),
    ("sophia-university", "上智大学", "Sophia University", r"Sophia Univ"),
    ("nihon-university", "日本大学", "Nihon University", r"Nihon Univ"),
    ("tokai-university", "東海大学", "Tokai University", r"Tokai Univ"),
    ("kogakuin-university", "工学院大学", "Kogakuin University", r"Kogakuin"),
    ("aoyama-gakuin-university", "青山学院大学", "Aoyama Gakuin University", r"Aoyama Gakuin"),
    ("meijo-university", "名城大学", "Meijo University", r"Meijo Univ"),
    ("chubu-university", "中部大学", "Chubu University", r"Chubu Univ"),
    ("aichi-institute-of-technology", "愛知工業大学", "Aichi Institute of Technology", r"Aichi Institute of Tech"),
    ("fukuyama-university", "福山大学", "Fukuyama University", r"Fukuyama Univ"),
    ("tottori-university", "鳥取大学", "Tottori University", r"Tottori Univ"),
    ("shimane-university", "島根大学", "Shimane University", r"Shimane Univ"),
    ("university-of-yamanashi", "山梨大学", "University of Yamanashi", r"Univ(ersity|\.) of Yamanashi"),
    ("utsunomiya-university", "宇都宮大学", "Utsunomiya University", r"Utsunomiya"),
    ("hirosaki-university", "弘前大学", "Hirosaki University", r"Hirosaki"),
    ("akita-university", "秋田大学", "Akita University", r"Akita Univ"),
    ("oita-university", "大分大学", "Oita University", r"Oita Univ"),
    ("setsunan-university", "摂南大学", "Setsunan University", r"Setsunan"),
]

COMPILED = [(slug, ja, en, re.compile(pat, re.I)) for slug, ja, en, pat in UNIVERSITIES]
BY_SLUG = {slug: (ja, en) for slug, ja, en, _ in UNIVERSITIES}

FOREIGN = re.compile(
    r"\b(USA|U\.S\.A|United States|China|Korea|Taiwan|Singapore|Germany|France|Netherlands|Belgium|"
    r"Switzerland|Italy|UK|United Kingdom|Canada|India|Macau|Hong Kong)\b")
FORMER = re.compile(r"formerly|emerit|previously|now (with|at)|was with", re.I)


def match(aff: str):
    """Return the university slug for an affiliation string, or None."""
    if FORMER.search(aff):
        return None
    for slug, _ja, _en, rx in COMPILED:
        if rx.search(aff):
            # guard against e.g. "Tsukuba University,Albany,NY,USA"
            if FOREIGN.search(aff) and "Japan" not in aff:
                return None
            return slug
    return None
