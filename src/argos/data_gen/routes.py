"""
60 ICN-based routes for the ARGOS synthetic dataset.
All distances are great-circle in nautical miles.
Block times are per aircraft type in minutes (representative mid-CI values).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RouteDefinition:
    route_id: str          # e.g. "ICN-NRT"
    origin_iata: str       # always "ICN"
    origin_icao: str       # always "RKSI"
    dest_iata: str
    dest_icao: str
    dest_name: str
    region: str
    distance_nm: int
    # aircraft_type -> block_time_minutes
    block_times: dict[str, int] = field(default_factory=dict)
    # flights per day (float allowed; <1 means less than daily)
    frequency_per_day: float = 1.0
    # aircraft types operated on this route (priority order)
    aircraft_types: list[str] = field(default_factory=list)


ROUTES: list[RouteDefinition] = [
    # ── Japan (10) ──────────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-NRT", "ICN", "RKSI", "NRT", "RJAA", "Tokyo Narita", "Japan", 696,
        {"B737-800": 145, "B777-300ER": 140, "B787-9": 138, "A321neo": 143},
        frequency_per_day=4.0, aircraft_types=["B737-800", "B777-300ER", "B787-9", "A321neo"],
    ),
    RouteDefinition(
        "ICN-HND", "ICN", "RKSI", "HND", "RJTT", "Tokyo Haneda", "Japan", 701,
        {"B737-800": 148, "B777-300ER": 143, "A321neo": 146},
        frequency_per_day=3.0, aircraft_types=["B737-800", "B777-300ER", "A321neo"],
    ),
    RouteDefinition(
        "ICN-KIX", "ICN", "RKSI", "KIX", "RJBB", "Osaka Kansai", "Japan", 493,
        {"B737-800": 110, "A321neo": 108},
        frequency_per_day=3.0, aircraft_types=["B737-800", "A321neo"],
    ),
    RouteDefinition(
        "ICN-NGO", "ICN", "RKSI", "NGO", "RJGG", "Nagoya Chubu", "Japan", 576,
        {"B737-800": 125, "A321neo": 123},
        frequency_per_day=2.0, aircraft_types=["B737-800", "A321neo"],
    ),
    RouteDefinition(
        "ICN-FUK", "ICN", "RKSI", "FUK", "RJFF", "Fukuoka", "Japan", 333,
        {"B737-800": 85, "A321neo": 83},
        frequency_per_day=3.0, aircraft_types=["B737-800", "A321neo"],
    ),
    RouteDefinition(
        "ICN-OKA", "ICN", "RKSI", "OKA", "ROAH", "Okinawa Naha", "Japan", 861,
        {"B737-800": 175, "B787-9": 170},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-CTS", "ICN", "RKSI", "CTS", "RJCC", "Sapporo New Chitose", "Japan", 756,
        {"B737-800": 155, "B787-9": 150},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-SDJ", "ICN", "RKSI", "SDJ", "RJSS", "Sendai", "Japan", 697,
        {"B737-800": 148},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),
    RouteDefinition(
        "ICN-KOJ", "ICN", "RKSI", "KOJ", "RJFK", "Kagoshima", "Japan", 470,
        {"B737-800": 108},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),
    RouteDefinition(
        "ICN-HIJ", "ICN", "RKSI", "HIJ", "RJOA", "Hiroshima", "Japan", 482,
        {"B737-800": 110},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),

    # ── China (10) ───────────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-PEK", "ICN", "RKSI", "PEK", "ZBAA", "Beijing Capital", "China", 578,
        {"B737-800": 130, "B777-300ER": 125, "B787-9": 123, "A321neo": 128},
        frequency_per_day=4.0, aircraft_types=["B737-800", "B777-300ER", "B787-9", "A321neo"],
    ),
    RouteDefinition(
        "ICN-PVG", "ICN", "RKSI", "PVG", "ZSPD", "Shanghai Pudong", "China", 512,
        {"B737-800": 118, "B777-300ER": 113, "A321neo": 116},
        frequency_per_day=4.0, aircraft_types=["B737-800", "B777-300ER", "A321neo"],
    ),
    RouteDefinition(
        "ICN-CAN", "ICN", "RKSI", "CAN", "ZGGG", "Guangzhou Baiyun", "China", 1095,
        {"B737-800": 215, "B787-9": 208},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-CTU", "ICN", "RKSI", "CTU", "ZUUU", "Chengdu Tianfu", "China", 1183,
        {"B737-800": 228, "B787-9": 220},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-XIY", "ICN", "RKSI", "XIY", "ZLXY", "Xi'an Xianyang", "China", 915,
        {"B737-800": 183, "B787-9": 178},
        frequency_per_day=1.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-SHA", "ICN", "RKSI", "SHA", "ZSSS", "Shanghai Hongqiao", "China", 512,
        {"B737-800": 118, "A321neo": 116},
        frequency_per_day=2.0, aircraft_types=["B737-800", "A321neo"],
    ),
    RouteDefinition(
        "ICN-SZX", "ICN", "RKSI", "SZX", "ZGSZ", "Shenzhen Bao'an", "China", 1099,
        {"B737-800": 216, "B787-9": 209},
        frequency_per_day=1.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-CSX", "ICN", "RKSI", "CSX", "ZGHA", "Changsha Huanghua", "China", 877,
        {"B737-800": 178},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),
    RouteDefinition(
        "ICN-DLC", "ICN", "RKSI", "DLC", "ZYTL", "Dalian Zhoushuizi", "China", 294,
        {"B737-800": 78, "A321neo": 76},
        frequency_per_day=1.0, aircraft_types=["B737-800", "A321neo"],
    ),
    RouteDefinition(
        "ICN-HGH", "ICN", "RKSI", "HGH", "ZSHC", "Hangzhou Xiaoshan", "China", 580,
        {"B737-800": 130, "A321neo": 128},
        frequency_per_day=1.0, aircraft_types=["B737-800", "A321neo"],
    ),

    # ── Southeast Asia (8) ───────────────────────────────────────────────────
    RouteDefinition(
        "ICN-BKK", "ICN", "RKSI", "BKK", "VTBS", "Bangkok Suvarnabhumi", "SE Asia", 2265,
        {"B737-800": 390, "B777-300ER": 375, "B787-9": 370},
        frequency_per_day=3.0, aircraft_types=["B777-300ER", "B787-9", "B737-800"],
    ),
    RouteDefinition(
        "ICN-SIN", "ICN", "RKSI", "SIN", "WSSS", "Singapore Changi", "SE Asia", 2803,
        {"B777-300ER": 450, "B787-9": 445},
        frequency_per_day=2.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-MNL", "ICN", "RKSI", "MNL", "RPLL", "Manila Ninoy Aquino", "SE Asia", 1618,
        {"B737-800": 295, "B777-300ER": 285},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B777-300ER"],
    ),
    RouteDefinition(
        "ICN-KUL", "ICN", "RKSI", "KUL", "WMKK", "Kuala Lumpur KLIA", "SE Asia", 2735,
        {"B777-300ER": 440, "B787-9": 435},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-CGK", "ICN", "RKSI", "CGK", "WIII", "Jakarta Soekarno-Hatta", "SE Asia", 3066,
        {"B777-300ER": 480, "B787-9": 475},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-DPS", "ICN", "RKSI", "DPS", "WADD", "Bali Ngurah Rai", "SE Asia", 3208,
        {"B787-9": 500},
        frequency_per_day=1.0, aircraft_types=["B787-9"],
    ),
    RouteDefinition(
        "ICN-SGN", "ICN", "RKSI", "SGN", "VVTS", "Ho Chi Minh City Tan Son Nhat", "SE Asia", 2347,
        {"B737-800": 400, "B787-9": 388},
        frequency_per_day=2.0, aircraft_types=["B737-800", "B787-9"],
    ),
    RouteDefinition(
        "ICN-RGN", "ICN", "RKSI", "RGN", "VYYY", "Yangon", "SE Asia", 2399,
        {"B737-800": 408},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),

    # ── North America (8) ────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-LAX", "ICN", "RKSI", "LAX", "KLAX", "Los Angeles", "North America", 5399,
        {"B777-300ER": 615, "B787-9": 620},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-JFK", "ICN", "RKSI", "JFK", "KJFK", "New York JFK", "North America", 6066,
        {"B747-8i": 730, "B777-300ER": 745},
        frequency_per_day=1.0, aircraft_types=["B747-8i", "B777-300ER"],
    ),
    RouteDefinition(
        "ICN-SFO", "ICN", "RKSI", "SFO", "KSFO", "San Francisco", "North America", 5338,
        {"B777-300ER": 610},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-ORD", "ICN", "RKSI", "ORD", "KORD", "Chicago O'Hare", "North America", 5818,
        {"B777-300ER": 665, "B747-8i": 660},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B747-8i"],
    ),
    RouteDefinition(
        "ICN-SEA", "ICN", "RKSI", "SEA", "KSEA", "Seattle-Tacoma", "North America", 5155,
        {"B787-9": 595},
        frequency_per_day=1.0, aircraft_types=["B787-9"],
    ),
    RouteDefinition(
        "ICN-YVR", "ICN", "RKSI", "YVR", "CYVR", "Vancouver", "North America", 5266,
        {"B787-9": 605},
        frequency_per_day=1.0, aircraft_types=["B787-9"],
    ),
    RouteDefinition(
        "ICN-ATL", "ICN", "RKSI", "ATL", "KATL", "Atlanta Hartsfield-Jackson", "North America", 6480,
        {"B777-300ER": 740},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-HNL", "ICN", "RKSI", "HNL", "PHNL", "Honolulu", "North America", 4262,
        {"B777-300ER": 500},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),

    # ── Europe (8) ───────────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-CDG", "ICN", "RKSI", "CDG", "LFPG", "Paris Charles de Gaulle", "Europe", 5280,
        {"B777-300ER": 690, "B747-8i": 685},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B747-8i"],
    ),
    RouteDefinition(
        "ICN-LHR", "ICN", "RKSI", "LHR", "EGLL", "London Heathrow", "Europe", 5374,
        {"B777-300ER": 700, "B747-8i": 695},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B747-8i"],
    ),
    RouteDefinition(
        "ICN-AMS", "ICN", "RKSI", "AMS", "EHAM", "Amsterdam Schiphol", "Europe", 5147,
        {"B777-300ER": 675},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-FRA", "ICN", "RKSI", "FRA", "EDDF", "Frankfurt", "Europe", 5235,
        {"B777-300ER": 685, "B747-8i": 680},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B747-8i"],
    ),
    RouteDefinition(
        "ICN-FCO", "ICN", "RKSI", "FCO", "LIRF", "Rome Fiumicino", "Europe", 5452,
        {"B777-300ER": 705},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-MAD", "ICN", "RKSI", "MAD", "LEMD", "Madrid Barajas", "Europe", 5858,
        {"B777-300ER": 750},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-ZRH", "ICN", "RKSI", "ZRH", "LSZH", "Zurich", "Europe", 5221,
        {"B777-300ER": 680},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-VIE", "ICN", "RKSI", "VIE", "LOWW", "Vienna", "Europe", 5247,
        {"B777-300ER": 682},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),

    # ── Middle East (4) ──────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-DXB", "ICN", "RKSI", "DXB", "OMDB", "Dubai", "Middle East", 3840,
        {"B777-300ER": 530, "B787-9": 525},
        frequency_per_day=2.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-AUH", "ICN", "RKSI", "AUH", "OMAA", "Abu Dhabi", "Middle East", 3856,
        {"B777-300ER": 532},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-DOH", "ICN", "RKSI", "DOH", "OTHH", "Doha Hamad", "Middle East", 3883,
        {"B777-300ER": 535},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-RUH", "ICN", "RKSI", "RUH", "OERK", "Riyadh King Khalid", "Middle East", 4032,
        {"B777-300ER": 548},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),

    # ── Oceania (3) ──────────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-SYD", "ICN", "RKSI", "SYD", "YSSY", "Sydney Kingsford Smith", "Oceania", 5100,
        {"B777-300ER": 660, "B787-9": 655},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-MEL", "ICN", "RKSI", "MEL", "YMML", "Melbourne Tullamarine", "Oceania", 5395,
        {"B777-300ER": 695},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-AKL", "ICN", "RKSI", "AKL", "NZAA", "Auckland", "Oceania", 5997,
        {"B777-300ER": 770},
        frequency_per_day=4 / 7, aircraft_types=["B777-300ER"],
    ),

    # ── Russia / CIS (3) ─────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-SVO", "ICN", "RKSI", "SVO", "UUEE", "Moscow Sheremetyevo", "Russia", 3910,
        {"B777-300ER": 545},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-VVO", "ICN", "RKSI", "VVO", "UHWW", "Vladivostok", "Russia", 465,
        {"B737-800": 107},
        frequency_per_day=2.0, aircraft_types=["B737-800"],
    ),
    RouteDefinition(
        "ICN-ALA", "ICN", "RKSI", "ALA", "UAAA", "Almaty", "CIS", 2174,
        {"B737-800": 375, "B787-9": 368},
        frequency_per_day=1.0, aircraft_types=["B737-800", "B787-9"],
    ),

    # ── South Asia (3) ───────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-DEL", "ICN", "RKSI", "DEL", "VIDP", "Delhi Indira Gandhi", "South Asia", 3270,
        {"B777-300ER": 475, "B787-9": 470},
        frequency_per_day=1.0, aircraft_types=["B777-300ER", "B787-9"],
    ),
    RouteDefinition(
        "ICN-BOM", "ICN", "RKSI", "BOM", "VABB", "Mumbai Chhatrapati Shivaji", "South Asia", 3735,
        {"B777-300ER": 520},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-CMB", "ICN", "RKSI", "CMB", "VCBI", "Colombo Bandaranaike", "South Asia", 3517,
        {"B787-9": 500},
        frequency_per_day=4 / 7, aircraft_types=["B787-9"],
    ),

    # ── Other (3) ────────────────────────────────────────────────────────────
    RouteDefinition(
        "ICN-JNB", "ICN", "RKSI", "JNB", "FAOR", "Johannesburg O.R. Tambo", "Africa", 7008,
        {"B777-300ER": 920},
        frequency_per_day=4 / 7, aircraft_types=["B777-300ER"],
    ),
    RouteDefinition(
        "ICN-ULN", "ICN", "RKSI", "ULN", "ZMUB", "Ulaanbaatar Chinggis Khaan", "Mongolia", 1018,
        {"B737-800": 200},
        frequency_per_day=1.0, aircraft_types=["B737-800"],
    ),
    RouteDefinition(
        "ICN-YYZ", "ICN", "RKSI", "YYZ", "CYYZ", "Toronto Pearson", "North America", 6218,
        {"B777-300ER": 755},
        frequency_per_day=1.0, aircraft_types=["B777-300ER"],
    ),
]

ROUTE_MAP: dict[str, RouteDefinition] = {r.route_id: r for r in ROUTES}

assert len(ROUTES) == 60, f"Expected 60 routes, got {len(ROUTES)}"
