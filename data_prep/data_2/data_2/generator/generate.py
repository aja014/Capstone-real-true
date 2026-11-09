"""
FIREMAP synthetic learning data generator (Maagap Insurance, Bulacan).

Implements the approved "FIREMAP Synthetic Data Rules" document.
Reproducible: fixed SEED -> identical output every run.

Outputs (in ./output):
  1_customer_information.xlsx
  2_fire_surveys.xlsx
  3_motor_quotations.xlsx
  4_fire_quotations.xlsx
  5_fire_policies.xlsx
  6_motor_policies.xlsx
  7_motor_claims.xlsx
  8_fire_property_claims.xlsx
plus truth_*.csv (internal ground truth used only by validate.py, NOT uploaded).
"""
import csv, math, random, datetime as dt
from collections import defaultdict
from pathlib import Path

SEED = 20260926
TODAY = dt.date(2026, 9, 26)
START = dt.date(2023, 1, 1)
HERE = Path(__file__).parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

rng = random.Random(SEED)

def d(s): return dt.date.fromisoformat(s)
def iso(x): return x.isoformat() if x else None
def add_years(x, n=1):
    try: return x.replace(year=x.year + n)
    except ValueError: return x.replace(year=x.year + n, day=28)
def rand_date(a, b):
    if b < a: b = a
    return a + dt.timedelta(days=rng.randint(0, (b - a).days))
def wchoice(pairs):
    items, weights = zip(*pairs)
    return rng.choices(items, weights=weights, k=1)[0]
def r2(x): return round(float(x), 2)
def round_to(x, step): return int(round(x / step) * step)
def lognorm(median, sigma): return median * math.exp(rng.gauss(0, sigma))

# ---------------------------------------------------------------------------
# Address pool (verified through the real GIS by Claude Code, step 3)
# ---------------------------------------------------------------------------
POOL = []
with open(HERE / "address_pool_verified.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["status"] != "kept":
            continue
        cat = row["flood_risk_category"] or "none"
        POOL.append({
            "address": row["address"], "town": row["town"], "barangay": row["barangay"],
            "cat": cat, "river": row["river_flood_category"] or "none",
            "surge": row["storm_surge_category"] or "none",
        })
TOWN_WEIGHT = {  # rough population weight -> where clients live
    "Malolos City": 9, "San Jose del Monte City": 10, "Meycauayan City": 7, "Santa Maria": 7,
    "Baliwag City": 5, "Marilao": 5, "Bocaue": 4, "San Miguel": 4, "Norzagaray": 3,
    "Pandi": 3, "Plaridel": 4, "Guiguinto": 4, "Calumpit": 3, "Hagonoy": 3, "Pulilan": 3,
    "Bulakan": 2, "Balagtas": 2, "Obando": 2, "Paombong": 1.5, "San Rafael": 2,
    "San Ildefonso": 2, "Bustos": 1.5, "Angat": 1.5, "Doña Remedios Trinidad": 0.5,
}
by_town = defaultdict(list)
for a in POOL:
    by_town[a["town"]].append(a)
ADDR_WEIGHTS = [TOWN_WEIGHT.get(a["town"], 1) / len(by_town[a["town"]]) for a in POOL]
def pick_address(exclude_towns=()):
    while True:
        a = rng.choices(POOL, weights=ADDR_WEIGHTS, k=1)[0]
        if a["town"] not in exclude_towns:
            return a
ZIP = {"Malolos City": "3000", "Paombong": "3001", "Hagonoy": "3002", "Calumpit": "3003",
       "Plaridel": "3004", "Pulilan": "3005", "Baliwag City": "3006", "Bustos": "3007",
       "San Rafael": "3008", "Doña Remedios Trinidad": "3009", "San Ildefonso": "3010",
       "San Miguel": "3011", "Angat": "3012", "Norzagaray": "3013", "Pandi": "3014",
       "Guiguinto": "3015", "Balagtas": "3016", "Bulakan": "3017", "Bocaue": "3018",
       "Marilao": "3019", "Meycauayan City": "3020", "Obando": "3021", "Santa Maria": "3022",
       "San Jose del Monte City": "3023"}

# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------
MALE = ("Juan Jose Antonio Jose Miguel Carlo Mark Paolo Rafael Gabriel Daniel Joshua Christian "
        "Jerome Ramon Rodrigo Ernesto Eduardo Fernando Ricardo Roberto Rolando Romeo Renato "
        "Reynaldo Rogelio Danilo Dennis Edgar Edwin Arnel Allan Alvin Arvin Bryan Ronald "
        "Noel Nestor Jaime Jericho Kenneth Kevin Lorenzo Marlon Michael Nathaniel Oscar "
        "Patrick Randy Raymond Rommel Ruel Samuel Teodoro Vicente Wilfredo Angelo Benedict "
        "Cesar Dominic Emmanuel Felix Gerardo Hernani Ismael Julius Leonardo Manuel Marvin "
        "Orlando Pedro Rey Rodel Sherwin Victor Warren Zaldy Efren Bayani Crisanto Dante "
        "Elmer Florante Gilbert Isagani Joel Lito Mario Nilo Pablo Rustico Tomas").split()
FEMALE = ("Maria Ana Rosa Teresa Elena Carmen Luz Josefina Corazon Gloria Marites Maricel "
          "Rowena Jocelyn Liza Lorna Imelda Evelyn Erlinda Leticia Lourdes Mercedes Nenita "
          "Norma Perla Remedios Rosario Susana Virginia Aileen Angelica Beatriz Camille Cristina "
          "Daisy Divina Editha Felicidad Grace Hazel Irene Jennifer Joy Karen Kristine Lalaine "
          "Maribel Marilou Melanie Michelle Nerissa Ofelia Patricia Pilar Precious Rachelle "
          "Regina Ruby Sheila Sonia Trinidad Vilma Wilma Yolanda Zenaida Analyn Bernadette "
          "Charito Dolores Estrella Fe Gemma Herminia Jovelyn Katherine Lanie Mylene Rhodora "
          "Sarah Teodora Venus").split()
SURNAMES = ("Santos Reyes Cruz Bautista Ocampo Garcia Mendoza Torres Tomas Andrada Castillo "
            "Flores Villanueva Ramos Castro Rivera Aquino Navarro Salazar Mercado Aguilar "
            "Domingo Gonzales Soriano Lopez Hernandez Perez Pascual Santiago Robles Enriquez "
            "Gatchalian Valenzuela Manalastas Dizon Mallari Lacson Pangilinan Sarmiento "
            "Carlos Buenaventura Ignacio Marcelo Evangelista Vergara Galang Serrano Vasquez "
            "Lim Tan Co Sy Chua Ong Yap Ang Uy Dela Cruz De Guzman De Leon Del Rosario Dela Rosa "
            "Dela Paz San Pedro Samonte Tolentino Magbanua Panganiban Salonga Macaraeg Bernardo "
            "Esguerra Fajardo Francisco Gregorio Hilario Jimenez Lacap Lagman Lumanlan Mangahas "
            "Manalo Nicolas Ordoñez Padilla Quiambao Rodriguez Sacdalan Sison Sta. Maria Tiongson "
            "Umali Valdez Yambao Zamora Alcantara Agustin Arceo Bacani Baluyot Bondoc Calma "
            "Canlas David Dimalanta Eusebio Feliciano Gomez Guevarra Isidro Jacinto Katigbak "
            "Laxamana Lorenzo Macapagal Medina Morales Nepomuceno Ocampo Pineda Quizon Rivera "
            "Roque Salvador Tanedo Tuazon Vitug Yumul Mariano Villareal Cabrera Concepcion "
            "Espiritu Estrada Gutierrez Legaspi Manansala Mesina Paras Pelayo Regalado "
            "Sangalang Sumulong Timbol Velasco").split()
# multi-word surnames were split above; rebuild them properly
_fixed, i = [], 0
_multi = {("Dela", "Cruz"), ("De", "Guzman"), ("De", "Leon"), ("Del", "Rosario"), ("Dela", "Rosa"),
          ("Dela", "Paz"), ("San", "Pedro"), ("Sta.", "Maria")}
while i < len(SURNAMES):
    if i + 1 < len(SURNAMES) and (SURNAMES[i], SURNAMES[i + 1]) in _multi:
        _fixed.append(SURNAMES[i] + " " + SURNAMES[i + 1]); i += 2
    else:
        _fixed.append(SURNAMES[i]); i += 1
SURNAMES = sorted(set(s.replace("Sta. Maria", "Santa Maria") for s in _fixed))
OCC_GENERAL = [("Business Owner", 14), ("Government Employee", 10), ("Teacher", 8), ("Nurse", 5),
               ("Engineer", 6), ("Accountant", 4), ("OFW", 8), ("Sales Agent", 5), ("Driver", 5),
               ("Sari-sari Store Owner", 5), ("Retired", 5), ("Police Officer", 2), ("Seaman", 4),
               ("IT Professional", 4), ("Contractor", 3), ("Farmer", 3), ("Call Center Agent", 3),
               ("Doctor", 2), ("Architect", 1), ("Lawyer", 1), ("Fisherman", 1)]
MOBILE_PREFIX = ["0917", "0918", "0919", "0920", "0921", "0927", "0928", "0929", "0935", "0936",
                 "0945", "0947", "0949", "0956", "0961", "0966", "0977", "0995", "0998", "0999"]

from rapidfuzz import fuzz
PEOPLE = []
_used_names, _used_mobiles = set(), set()
def norm_name(s): return " ".join(s.replace(".", "").lower().split())

def new_person(address=None, occupation=None, coastal=False):
    for _ in range(500):
        gender = rng.choice(["Male", "Female"])
        first = rng.choice(MALE if gender == "Male" else FEMALE)
        if rng.random() < 0.18:  # two-word first names are common
            first += " " + rng.choice(MALE if gender == "Male" else FEMALE)
        last = rng.choice(SURNAMES)
        middle = rng.choice([s for s in SURNAMES if s != last])
        full = f"{first} {middle} {last}"
        n = norm_name(full)
        if n in _used_names:
            continue
        # keep every pair of clients clearly different for the importers' fuzzy matching
        if any(fuzz.token_sort_ratio(n, o) >= 70 for o in _used_names):
            continue
        break
    _used_names.add(n)
    while True:
        mob = rng.choice(MOBILE_PREFIX) + f"{rng.randint(0, 9999999):07d}"
        if mob not in _used_mobiles:
            _used_mobiles.add(mob); break
    addr = address or pick_address()
    if occupation is None:
        occupation = wchoice(OCC_GENERAL)
        if addr["surge"] != "none" and rng.random() < 0.25:
            occupation = "Fisherman"
    p = {"id": len(PEOPLE) + 1, "first": first, "middle": middle, "last": last,
         "full": full, "gender": gender, "addr": addr, "mobile": mob, "occupation": occupation,
         "marital": wchoice([("Married", 60), ("Single", 30), ("Widowed", 7), ("Separated", 3)]),
         "agent": None}
    PEOPLE.append(p)
    return p

AGENTS = [("MS0009-01", 20), ("MS0003-01", 17), ("MS0014-01", 13), ("MS0006-01", 9),
          ("MS0011-01", 8), ("MS0017-01", 7), ("MS0019-01", 6), ("MS0023-01", 6),
          ("MS0026-01", 5), ("MS0028-01", 4), ("MS0031-01", 3), ("MS0034-01", 2)]
def agent_of(p):
    if p["agent"] is None:
        p["agent"] = wchoice(AGENTS)
    return p["agent"]

# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------
MAKES = [("Toyota", 40), ("Mitsubishi", 15), ("Honda", 9), ("Nissan", 9), ("Ford", 7),
         ("Suzuki", 8), ("Hyundai", 6), ("Isuzu", 6)]
BODY_BY_MAKE = {
    "Toyota": [("Sedan", 25), ("Hatchback", 12), ("SUV", 22), ("AUV", 20), ("Pick-up", 10), ("Van", 11)],
    "Mitsubishi": [("Sedan", 12), ("SUV", 28), ("AUV", 25), ("Pick-up", 25), ("Van", 10)],
    "Honda": [("Sedan", 45), ("Hatchback", 20), ("SUV", 35)],
    "Nissan": [("Sedan", 25), ("SUV", 25), ("Pick-up", 30), ("Van", 20)],
    "Ford": [("SUV", 45), ("Pick-up", 45), ("Van", 10)],
    "Suzuki": [("Hatchback", 45), ("Sedan", 20), ("AUV", 25), ("Van", 10)],
    "Hyundai": [("Sedan", 25), ("Hatchback", 15), ("SUV", 25), ("Van", 35)],
    "Isuzu": [("Pick-up", 40), ("SUV", 25), ("Truck", 35)],
}
NEW_PRICE = {  # (low, high) new price in PHP by body type
    "Hatchback": (650_000, 950_000), "Sedan": (800_000, 1_450_000), "SUV": (1_450_000, 2_600_000),
    "AUV": (1_050_000, 1_700_000), "Pick-up": (1_150_000, 1_900_000), "Van": (1_500_000, 2_400_000),
    "Truck": (1_600_000, 3_000_000),
}
CAPACITY = {"Hatchback": "5", "Sedan": "5", "SUV": "7", "AUV": "8", "Pick-up": "5", "Van": "15", "Truck": "3"}
COLORS = [("White", 28), ("Silver", 20), ("Gray", 16), ("Black", 16), ("Red", 8), ("Blue", 6),
          ("Brown", 3), ("Orange", 2), ("Green", 1)]
ENGINE_PREFIX = {"Toyota": ["2NR", "1TR", "2GD", "1GD", "2TR"], "Mitsubishi": ["4A91", "4N15", "4D56", "4G64"],
                 "Honda": ["L15B", "L15Z", "R18Z"], "Nissan": ["HR15", "YD25", "QR25"], "Ford": ["P5AT", "YN2S", "DURA"],
                 "Suzuki": ["K12M", "K15B", "G13B"], "Hyundai": ["G4FL", "D4CB", "G4LC"], "Isuzu": ["4JJ1", "4JK1", "4HK1"]}
VIN_PREFIX = {"Toyota": "MHF", "Mitsubishi": "PAD", "Honda": "MRH", "Nissan": "MNT", "Ford": "MNB",
              "Suzuki": "MA3", "Hyundai": "KMH", "Isuzu": "MPA"}
VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
_used_plates, _used_eng, _used_vin = set(), set(), set()
VEHICLES = []

def new_plate(year_model):
    while True:
        L = "".join(rng.choice("ABCDEFGHIJKLMNPQRSTUVWXYZ") for _ in range(3))
        if year_model >= 2015:
            p = L + f"{rng.randint(1000, 9999)}"
        else:
            p = L + f"{rng.randint(100, 999)}"
        if p not in _used_plates:
            _used_plates.add(p); return p

def new_vehicle(owner, first_policy_date, commercial_owner=False):
    make = wchoice(MAKES)
    body = wchoice(BODY_BY_MAKE[make])
    commercial = body in ("Truck",) or (body in ("Van", "Pick-up") and rng.random() < 0.45) or \
                 (commercial_owner and rng.random() < 0.5)
    age_new = wchoice([(0, 40), (1, 15), (2, 10), (3, 8), (4, 6), (5, 5), (6, 4), (7, 3), (8, 3), (10, 3), (12, 3)])
    year_model = min(first_policy_date.year + (1 if rng.random() < 0.1 and age_new == 0 else 0),
                     first_policy_date.year - age_new)
    year_model = max(2010, year_model)
    lo, hi = NEW_PRICE[body]
    new_price = round_to(rng.uniform(lo, hi), 10_000)
    while True:
        eng = rng.choice(ENGINE_PREFIX[make]) + "-" + "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(1)) + f"{rng.randint(100000, 999999)}"
        if eng not in _used_eng:
            _used_eng.add(eng); break
    while True:
        vin = VIN_PREFIX[make] + "".join(rng.choice(VIN_CHARS) for _ in range(14))
        if vin not in _used_vin and not vin[3:].isdigit():
            _used_vin.add(vin); break
    v = {"id": len(VEHICLES) + 1, "owner": owner, "make": make, "body": body, "year_model": year_model,
         "new_price": new_price, "commercial": commercial, "color": wchoice(COLORS),
         "plate": new_plate(year_model), "engine": eng, "chassis": vin}
    VEHICLES.append(v)
    return v

def vehicle_si(v, on_date):
    age = max(0, on_date.year - v["year_model"])
    return max(150_000, round_to(v["new_price"] * (0.9 ** age), 10_000))

def motor_premium(si, commercial):
    rate = rng.uniform(0.025, 0.035) + (0.004 if commercial else 0)
    return r2(si * rate + rng.uniform(0, 99))

def motor_deductible(si):
    return float(max(2000, round_to(si * 0.005, 500)))

# ---------------------------------------------------------------------------
# Fire properties
# ---------------------------------------------------------------------------
OCCUPANCIES = [
    # name, weight, commercial?, risky?(restaurant/warehouse/factory), business description, property insured
    ("Dwelling", 60, False, False, "Residential use only", "Two-storey residential building"),
    ("Store with Dwelling", 14, True, False, "Sari-sari store with residence", "Two-storey store and residential building"),
    ("Warehouse", 7, True, True, "Storage of rice, feeds and general merchandise", "One-storey warehouse building and stocks"),
    ("Restaurant", 6, True, True, "Carinderia and food service", "Restaurant building, kitchen equipment and stocks"),
    ("Office", 6, True, False, "Professional and business office", "Office building, furniture and equipment"),
    ("Small Factory", 7, True, True, "Small-scale garment and food manufacturing", "Factory building, machinery and stocks"),
]
PROTECTION = ["Fire Extinguisher", "Smoke Detector", "Fire Alarm System", "Automatic Sprinklers",
              "External Hydrants", "Internal Hydrants", "Security Guards", "CCTV/Monitor/Recording",
              "Perimeter Fence", "Water Supply", "Power Supply", "Generator Set", "Flood Control",
              "Fire Breaks/Doors", "Heat Detector", "Fire Hose Reel"]
PROTECTION = [p for p in PROTECTION if p != "Fire Hose Reel"]  # not on Maagap's form
FIRE_PROT = {"Fire Extinguisher", "Smoke Detector", "Fire Alarm System", "Automatic Sprinklers",
             "External Hydrants", "Internal Hydrants", "Heat Detector", "Fire Breaks/Doors"}
PROPERTIES = []

def new_property(owner, addr, first_date):
    occ = wchoice([(o, o[1]) for o in OCCUPANCIES])
    name, _, commercial, risky, bdesc, pins = occ
    risk_class = "b" if rng.random() < (0.30 if not commercial else 0.42) else "a"
    if commercial:
        tsi = min(30_000_000, max(2_000_000, round_to(lognorm(6_000_000, 0.6), 50_000)))
    else:
        tsi = min(5_000_000, max(500_000, round_to(lognorm(1_800_000, 0.45), 50_000)))
    # protection facilities: commercial risks tend to have more
    n = rng.choice([0, 1, 1, 2, 2, 3, 4]) + (rng.randint(0, 2) if commercial else 0)
    facs = set(rng.sample(PROTECTION, min(n, len(PROTECTION))))
    if addr["cat"] in ("High", "Medium") and rng.random() < (0.30 if commercial else 0.12):
        facs.add("Flood Control")
    fire_prot_count = len(facs & FIRE_PROT)
    prior_loss = rng.random() < 0.12
    loss_record = "No known loss history"
    if prior_loss:
        peril = wchoice([("Fire", 30), ("Flood", 45), ("Typhoon", 25)])
        if peril == "Flood" and addr["cat"] in ("none", "Low"):
            peril = "Typhoon"
        loss_record = f"With loss history: {peril}, {rng.randint(2014, first_date.year - 1)}"
    pr = {"id": len(PROPERTIES) + 1, "owner": owner, "addr": addr, "occupancy": name,
          "commercial": commercial, "risky": risky, "bdesc": bdesc, "pins": pins,
          "risk_class": risk_class, "tsi": float(tsi), "facilities": sorted(facs),
          "protected": fire_prot_count >= 2, "prior_loss": prior_loss, "loss_record": loss_record}
    # surveyor's view, consistent with the facts
    bad = sum([addr["cat"] == "High", risk_class == "b", risky, not pr["protected"], prior_loss])
    pr["overall"] = "Good" if bad <= 1 else ("Fair" if bad == 2 else "Poor")
    if pr["overall"] == "Good":
        pr["acceptability"] = "Accept"
    elif pr["overall"] == "Fair":
        pr["acceptability"] = wchoice([("Accept", 70), ("Key Consideration", 30)])
    else:
        pr["acceptability"] = wchoice([("Key Consideration", 75), ("Decline", 25)])
    PROPERTIES.append(pr)
    return pr

def fire_premium(pr):
    rate = rng.uniform(0.0025, 0.0045) + (0.0008 if pr["risk_class"] == "b" else 0) + (0.0007 if pr["commercial"] else 0)
    return r2(pr["tsi"] * rate + rng.uniform(0, 99))

# ---------------------------------------------------------------------------
# Business simulation: subjects (vehicles / properties) and their yearly terms
# ---------------------------------------------------------------------------
SUBJECTS = []  # {"line": "motor"/"fire", "obj": vehicle/property, "person", "first_from", "book": bool}
motor_owners, fire_owners = [], []

def anniversaries_ok(person, new_from, line):
    for s in SUBJECTS:
        if s["person"] is person and s["line"] == line:
            gap = abs((s["first_from"].replace(year=2000) - new_from.replace(year=2000)).days)
            gap = min(gap, 366 - gap)
            if gap < 100:   # the importer tells policies apart partly by date
                return False
    return True

def add_motor_subject(first_from, book):
    owner = None
    if motor_owners and rng.random() < 0.16:
        cand = rng.choice(motor_owners)
        if sum(1 for s in SUBJECTS if s["person"] is cand and s["line"] == "motor") < 3 \
                and anniversaries_ok(cand, first_from, "motor"):
            owner = cand
    if owner is None:
        owner = new_person()
        motor_owners.append(owner)
    v = new_vehicle(owner, first_from, commercial_owner=owner["occupation"] in ("Business Owner", "Contractor", "Driver"))
    SUBJECTS.append({"line": "motor", "obj": v, "person": owner, "first_from": first_from, "book": book})

def add_fire_subject(first_from, book):
    owner = None
    if fire_owners and rng.random() < 0.14:
        cand = rng.choice(fire_owners)
        if sum(1 for s in SUBJECTS if s["person"] is cand and s["line"] == "fire") < 2 \
                and anniversaries_ok(cand, first_from, "fire"):
            owner = cand
    if owner is None and motor_owners and rng.random() < 0.12:
        cand = rng.choice(motor_owners)
        if not any(s["person"] is cand and s["line"] == "fire" for s in SUBJECTS):
            owner = cand
    if owner is None:
        owner = new_person(occupation=wchoice(OCC_GENERAL + [("Business Owner", 10)]))
    if owner not in fire_owners:
        fire_owners.append(owner)
    existing = [s["obj"]["addr"] for s in SUBJECTS if s["person"] is owner and s["line"] == "fire"]
    if not existing:
        addr = owner["addr"]
    else:  # a second property: a different town so the importer can tell them apart
        addr = pick_address(exclude_towns={a["town"] for a in existing})
    pr = new_property(owner, addr, first_from)
    if existing and pr["occupancy"] == "Dwelling":
        pr["occupancy"], pr["commercial"], pr["risky"], pr["bdesc"], pr["pins"] = \
            "Store with Dwelling", True, False, "Sari-sari store with residence", "Two-storey store and residential building"
    if pr["acceptability"] == "Decline":
        pr["acceptability"] = "Key Consideration"   # insured risks were not declined
    SUBJECTS.append({"line": "fire", "obj": pr, "person": owner, "first_from": first_from, "book": book})

# existing book (policies that started before 2023 and renew during 2023) + new business
for _ in range(200):
    add_motor_subject(rand_date(dt.date(2023, 1, 1), dt.date(2023, 12, 31)), True)
for _ in range(140):
    add_fire_subject(rand_date(dt.date(2023, 1, 1), dt.date(2023, 12, 31)), True)
new_motor = int(100 * ((TODAY - START).days / 365.25))
new_fire = int(70 * ((TODAY - START).days / 365.25))
for _ in range(new_motor):
    add_motor_subject(rand_date(START + dt.timedelta(days=10), TODAY), False)
for _ in range(new_fire):
    add_fire_subject(rand_date(START + dt.timedelta(days=10), TODAY), False)

# ---------------------------------------------------------------------------
# Claim-chance model (the planted patterns)
# ---------------------------------------------------------------------------
import os
BASE_MOTOR = float(os.environ.get('G_BM', 0.12)); BASE_FIRE = float(os.environ.get('G_BF', 0.05))
def motor_multiplier(v, term):
    m = 1.0
    if v["commercial"]: m *= 1.8
    if v["body"] in ("Truck", "Van"): m *= 1.4
    elif v["body"] in ("SUV", "Pick-up"): m *= 1.1
    age = term["pfrom"].year - v["year_model"]
    if age <= 3: m *= 1.3
    elif age >= 10: m *= 0.8
    cat = v["owner"]["addr"]["cat"]
    if cat == "High": m *= 1.6
    elif cat == "Medium": m *= 1.25
    if term["deductible"] > 5000: m *= 0.8
    if term["prior_loss"]: m *= 1.7
    if term["si"] > 1_500_000: m *= 1.15
    return m   # color: deliberately no effect

def fire_multiplier(pr, term):
    m = 1.0
    cat = pr["addr"]["cat"]
    if cat == "High": m *= 2.2
    elif cat == "Medium": m *= 1.4
    if pr["risk_class"] == "b": m *= 1.8
    if pr["risky"]: m *= 1.6
    if pr["protected"]: m *= 0.5
    if pr["prior_loss"] or term["prior_loss"]: m *= 1.6
    if term["si"] > 10_000_000: m *= 1.2
    return m

MONTH_W_WET = {1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 6, 7: 12, 8: 14, 9: 13, 10: 9, 11: 5, 12: 2}
def loss_date(a, b, wet):
    if b < a: b = a
    for _ in range(200):
        x = rand_date(a, b)
        if not wet or rng.random() < MONTH_W_WET[x.month] / 14:
            return x
    return rand_date(a, b)

def motor_nature(v, opp):
    cat = v["owner"]["addr"]["cat"]
    w = {"Collision": 68 * (1.5 if v["commercial"] else 1), "Flood": 8 * (4 if cat == "High" else 2 if cat == "Medium" else 0.4),
         "Theft/Carnapping": 4 * (2.5 if opp else 1), "Fire": 2 * (3 if opp else 1), "Vandalism": 10, "Other": 8}
    return wchoice(list(w.items()))

def fire_nature(pr, opp):
    cat = pr["addr"]["cat"]
    fw = 30 * (2 if pr["risk_class"] == "b" else 1) * (1.5 if pr["risky"] else 1) * (0.6 if pr["protected"] else 1) * (1.8 if opp else 1)
    flw = 25 * (3 if cat == "High" else 1.8 if cat == "Medium" else 0.15) * (0.5 if "Flood Control" in pr["facilities"] else 1)
    tw = 30 * (1.5 if pr["addr"]["surge"] != "none" else 1)
    return wchoice([("Fire", fw), ("Flood", flw), ("Typhoon", tw), ("Earthquake", 4), ("Lightning", 5), ("Other", 6)])

# ---------------------------------------------------------------------------
# Walk every subject through its yearly terms
# ---------------------------------------------------------------------------
TERMS, QUOTES, EVENTS = [], [], []
_fake_2022 = set()

def fake_prev_no(line):
    while True:
        n = f"MS-{'01' if line == 'motor' else '02'}-22-MS-{rng.randint(1, 420 if line == 'motor' else 190):06d}"
        if n not in _fake_2022:
            _fake_2022.add(n); return n

for s in SUBJECTS:
    obj, person, line = s["obj"], s["person"], s["line"]
    pfrom = s["first_from"]
    prev_term = None
    prior_loss = False
    first = True
    while True:
        issue = pfrom - dt.timedelta(days=rng.randint(0, 7))
        qdate = issue - dt.timedelta(days=rng.randint(1, 7))
        if qdate > TODAY:
            break
        if line == "motor":
            si = float(vehicle_si(obj, pfrom))
            amount = motor_premium(si, obj["commercial"])
            ded = motor_deductible(si)
        else:
            if prev_term:
                obj["tsi"] = float(round_to(obj["tsi"] * rng.uniform(1.0, 1.05), 10_000))
            si = obj["tsi"]
            amount = fire_premium(obj)
            ded = None
        quote = {"line": line, "subject": s, "person": person, "date": qdate, "amount": amount,
                 "si": si, "deductible": ded, "policy": None}
        QUOTES.append(quote)
        # a renewal can be quoted and then lost
        if prev_term is not None and not prev_term["renews"]:
            break
        if issue > TODAY:
            break   # quoted, policy not issued yet (pending)
        term = {"line": line, "subject": s, "person": person, "quote": quote, "issue": issue,
                "pfrom": pfrom, "pto": add_years(pfrom), "si": si, "amount": amount, "deductible": ded,
                "agent": agent_of(person), "prior_loss": prior_loss, "prev": prev_term,
                "renewing_no": (fake_prev_no(line) if (first and s["book"]) else None),
                "events": [], "renews": None}
        quote["policy"] = term
        TERMS.append(term)
        # ---- claim events during this term (exposure up to today)
        exp_end = min(term["pto"], TODAY)
        frac = max(0.0, (exp_end - pfrom).days / 365.0)
        if line == "motor":
            p = min(0.85, BASE_MOTOR * motor_multiplier(obj, term)) * frac
        else:
            p = min(0.85, BASE_FIRE * fire_multiplier(obj, term)) * frac
        n_events = 0
        if rng.random() < p:
            n_events = 2 if rng.random() < 0.10 else 1
        for _ in range(n_events):
            opp = rng.random() < 0.13
            if opp and rng.random() < 0.55:
                ld = rand_date(pfrom, min(exp_end, pfrom + dt.timedelta(days=30)))
                nature = motor_nature(obj, True) if line == "motor" else fire_nature(obj, True)
            elif opp and rng.random() < 0.4:
                ld = rand_date(max(pfrom, term["pto"] - dt.timedelta(days=30)), exp_end)
                nature = motor_nature(obj, True) if line == "motor" else fire_nature(obj, True)
            else:
                nature = motor_nature(obj, opp) if line == "motor" else fire_nature(obj, opp)
                ld = loss_date(pfrom, exp_end, nature in ("Flood", "Typhoon"))
            ev = {"term": term, "line": line, "loss": ld, "nature": nature, "opp": opp, "cnc": False}
            term["events"].append(ev); EVENTS.append(ev)
        if line == "motor" and rng.random() < 0.033 * frac:   # CNC issuance (no payout)
            ev = {"term": term, "line": line, "loss": rand_date(pfrom, exp_end), "nature": "Collision",
                  "opp": False, "cnc": True}
            term["events"].append(ev); EVENTS.append(ev)
        # ---- renewal decision at expiry
        paid = [e for e in term["events"] if not e["cnc"]]
        if any(e["opp"] for e in paid):
            renew_p = 0.20
        elif paid:
            renew_p = 0.66
        else:
            renew_p = 0.73 if line == "motor" else 0.76
        term["renews"] = rng.random() < renew_p
        prior_loss = any(not e["opp"] for e in paid)
        prev_term = term
        first = False
        if not term["renews"] and rng.random() < 0.5:
            pfrom = term["pto"]; continue   # a renewal quote is sent, client does not take it
        if not term["renews"]:
            break
        pfrom = term["pto"]

# prospects: quoted, never bought (fresh people only)
for _ in range(170):
    person = new_person()
    qd = rand_date(START, TODAY - dt.timedelta(days=3))
    v = new_vehicle(person, qd)
    si = float(vehicle_si(v, qd))
    s = {"line": "motor", "obj": v, "person": person, "first_from": qd, "book": False, "prospect": True}
    SUBJECTS.append(s)
    QUOTES.append({"line": "motor", "subject": s, "person": person, "date": qd,
                   "amount": motor_premium(si, v["commercial"]), "si": si, "deductible": motor_deductible(si), "policy": None})
for _ in range(80):
    person = new_person(occupation=wchoice(OCC_GENERAL + [("Business Owner", 10)]))
    qd = rand_date(START, TODAY - dt.timedelta(days=3))
    pr = new_property(person, person["addr"], qd)
    s = {"line": "fire", "obj": pr, "person": person, "first_from": qd, "book": False, "prospect": True}
    SUBJECTS.append(s)
    pr["survey_only"] = pr["acceptability"] == "Decline"
    if not pr["survey_only"]:
        QUOTES.append({"line": "fire", "subject": s, "person": person, "date": qd,
                       "amount": fire_premium(pr), "si": pr["tsi"], "deductible": None, "policy": None})

# ---------------------------------------------------------------------------
# Phase C: every claim event -> timeline, amounts, red flags, label, status
# ---------------------------------------------------------------------------
INVENTED_SHOPS = ["MALOLOS AUTO CARE CENTER", "STA. RITA BODY & PAINT SHOP", "GUIGUINTO MOTORWORKS",
                  "MARILAO AUTO BODY REPAIR", "SJDM CAR CARE SERVICES", "BALIWAG AUTO SPECIALISTS",
                  "BOCAUE PAINT & BODY WORKS", "PLARIDEL AUTO CLINIC", "MEYCAUAYAN MOTOR SERVICES",
                  "SANTA MARIA AUTOWORKS", "CALUMPIT AUTO REPAIR SHOP", "PULILAN BODY & FENDER",
                  "NORTHBOUND AUTO BODY", "TRIPLE J MOTOR SHOP", "R&R AUTO REFINISHING"]
REAL_DEALERS = {"Toyota": ["TOYOTA MARILAO BULACAN", "TOYOTA PLARIDEL BULACAN"],
                "Honda": ["HONDA CARS BULACAN"], "Ford": ["FORD MALOLOS"]}
ADJUSTERS = ["LUZON LOSS ADJUSTERS INC.", "CENTRAL PLAINS ADJUSTING CORP.", "BULACAN CLAIMS SERVICES INC.",
             "PRIME LOSS ASSESSORS PHILS.", "MERIDIAN ADJUSTERS & SURVEYORS"]

def delay_report(opp):
    if opp and rng.random() < 0.5:
        return rng.randint(31, 75)
    return rng.randint(0, 7) if rng.random() < 0.8 else rng.randint(8, 45)

def delay_docs(opp):
    if opp and rng.random() < 0.4:
        return rng.randint(31, 70)
    return rng.randint(1, 20) if rng.random() < 0.9 else rng.randint(21, 45)

def motor_estimate(e, v, si):
    n, opp = e["nature"], e["opp"]
    if n == "Theft/Carnapping":
        return si
    if opp and rng.random() < 0.5:
        return si * rng.uniform(0.70, 0.95)
    if n == "Collision":
        x = min(300_000, max(5_000, lognorm(40_000, 0.8)))
        return min(x, si * 0.6)
    if n == "Flood": return si * rng.uniform(0.10, 0.50)
    if n == "Fire": return si * rng.uniform(0.30, 1.00)
    if n == "Vandalism": return rng.uniform(3_000, 40_000)
    return rng.uniform(5_000, 60_000)

FIRE_EST = {"Fire": (0.10, 1.00), "Flood": (0.05, 0.40), "Typhoon": (0.04, 0.25),
            "Earthquake": (0.05, 0.30), "Lightning": (0.01, 0.10), "Other": (0.03, 0.15)}
def fire_estimate(e, tsi):
    lo, hi = FIRE_EST[e["nature"]]
    if e["opp"] and rng.random() < 0.5:
        lo, hi = max(lo, 0.50), max(hi, 0.90)
    x = tsi * (lo + (hi - lo) * (rng.random() ** 1.8))   # most losses are partial
    if e["nature"] in ("Fire", "Lightning"):
        x = max(x, 20_000)
    return x

def fire_deductible(nature, tsi, loss):
    if nature in ("Fire", "Lightning"): return 0.0
    if nature in ("Earthquake", "Typhoon", "Flood"): return tsi * 0.02
    return min(500_000, max(1_000, tsi * 0.01))

POINTS_P = [(0, 0.02), (2, 0.08), (4, 0.30), (6, 0.55), (99, 0.75)]
FRAUD_SCALE = float(os.environ.get('G_FS', 0.8))

# chronological so "earlier claims by the same person" is known
paid_events = sorted([e for e in EVENTS if not e["cnc"]], key=lambda e: e["loss"])
history = defaultdict(list)   # person id -> dates reported
for e in sorted(EVENTS, key=lambda e: e["loss"]):
    t = e["term"]; s = t["subject"]; obj = s["obj"]; person = t["person"]
    e["reported"] = e["loss"] + dt.timedelta(days=delay_report(e["opp"] and not e["cnc"]))
    if e["reported"] > TODAY:
        e["drop"] = True; continue
    e["drop"] = False
    if e["cnc"]:
        continue
    e["docs"] = e["reported"] + dt.timedelta(days=delay_docs(e["opp"]))
    if e["line"] == "motor":
        est = motor_estimate(e, obj, t["si"])
        if e["nature"] in ("Collision", "Vandalism", "Other"):
            est = max(est, t["deductible"] * rng.uniform(2.5, 6))   # below-deductible damage is not claimed
    else:
        est = fire_estimate(e, t["si"])
    e["estimate"] = r2(est)
    # ---- red flags (documented fraud indicators = Naive Bayes clues)
    since = (e["loss"] - t["pfrom"]).days
    rep = (e["reported"] - e["loss"]).days
    ratio = e["estimate"] / t["si"]
    prior12 = sum(1 for x in history[person["id"]] if (e["reported"] - x).days <= 365)
    pts = 0
    pts += 3 if since <= 15 else 2 if since <= 30 else 0
    pts += 3 if rep > 30 else 1 if rep >= 8 else 0
    if (e["line"] == "motor" and e["nature"] != "Theft/Carnapping" and ratio >= 0.70) or \
       (e["line"] == "fire" and ratio >= 0.50):
        pts += 2
    pts += 2 if prior12 >= 2 else 0
    pts += 1 if (t["pto"] - e["loss"]).days <= 30 else 0
    pts += 1 if (e["line"] == "motor" and e["nature"] in ("Theft/Carnapping", "Fire")) else 0
    pts += 1 if t["prev"] is None and t["renewing_no"] is None else 0
    pts += 1 if (e["docs"] - e["reported"]).days > 30 else 0
    e["points"] = pts
    pf = next(p for lim, p in POINTS_P if pts <= lim) * FRAUD_SCALE
    e["fraud"] = rng.random() < pf
    e["confirmed"] = e["fraud"] and rng.random() < (0.25 + 0.05 * min(pts, 6))
    history[person["id"]].append(e["reported"])

def build_status(e):
    """Walk the claim pipeline up to TODAY. Sets final status, label, dates, amounts."""
    t = e["term"]
    e.update({"label": None, "loa_date": None, "loa_amt": None, "net": None, "billing": None,
              "updated": e["reported"], "withdrawn": False})
    docs, evald = e["docs"], e["docs"] + dt.timedelta(days=rng.randint(3, 20))
    abandon = (not e["fraud"]) and rng.random() < 0.03
    if abandon:
        e["docs"] = None
        e["final"] = "With Lacking Docs" if rng.random() < 0.6 else "No Docs. Submitted"
        return
    if TODAY < docs:
        e["docs"] = None; e["final"] = "No Docs. Submitted"; return
    e["updated"] = docs
    if TODAY < evald:
        e["final"] = "Waiting for Evaluation" if rng.random() < 0.75 else "With Lacking Docs"
        return
    e["updated"] = evald
    if e["fraud"]:
        denial = evald + dt.timedelta(days=rng.randint(5, 20))
        if TODAY < denial:
            e["final"] = "Waiting for Evaluation"; return
        e["label"] = "Confirmed Fraud" if e["confirmed"] else "Suspected Fraud"
        e["updated"] = denial
        if e["confirmed"]:
            e["final"] = "Denied Claim"
        else:
            e["final"] = wchoice([("Denied Claim", 50), ("Not Push Through", 35), ("Hold per Client", 15)])
        return
    e["label"] = "Legitimate"
    if rng.random() < 0.03:
        e["final"] = "Not Push Through"; e["withdrawn"] = True; return
    loa = evald + dt.timedelta(days=rng.randint(5, 30))
    if TODAY < loa:
        e["final"] = "Waiting for LOA"; return
    e["loa_date"] = loa; e["updated"] = loa
    total_loss = e["line"] == "motor" and e["nature"] == "Theft/Carnapping"
    e["loa_amt"] = r2(t["si"] * rng.uniform(0.85, 1.0)) if total_loss else r2(e["estimate"] * rng.uniform(0.60, 0.95))
    bill = loa + dt.timedelta(days=rng.randint(5, 30))
    if TODAY < bill:
        e["final"] = "Waiting for Billing"; return
    e["billing"] = bill; e["updated"] = bill
    check = bill + dt.timedelta(days=rng.randint(7, 25))
    if TODAY < check:
        e["final"] = "Waiting for Claim Check"; return
    e["updated"] = check
    e["final"] = "Closed Claim"

for e in EVENTS:
    if e.get("drop") or e["cnc"]:
        continue
    build_status(e)
    t = e["term"]
    if e["loa_amt"] is not None:
        if e["line"] == "motor":
            e["net"] = r2(max(0, e["loa_amt"] - t["deductible"]))
        else:
            e["net"] = r2(max(0, e["loa_amt"] - fire_deductible(e["nature"], t["si"], e["loa_amt"])))

COUNTED = {"Closed Claim", "Waiting for LOA", "Waiting for Billing", "Waiting for Claim Check"}
for t in TERMS:
    t["counted_loss"] = any((not e["cnc"]) and not e.get("drop") and e.get("label") == "Legitimate"
                            and e["final"] in COUNTED for e in t["events"])

# ---------------------------------------------------------------------------
# Owners with two properties: make sure the importer can tell the two locations apart
# (deterministic swap to another pool address with the SAME hazard profile; no rng used)
# ---------------------------------------------------------------------------
_props_by_owner = defaultdict(list)
for pr in PROPERTIES:
    _props_by_owner[pr["owner"]["id"]].append(pr)
for plist in _props_by_owner.values():
    if len(plist) == 2:
        a, b = plist
        if fuzz.token_sort_ratio(a["addr"]["address"].lower(), b["addr"]["address"].lower()) >= 70:
            for cand in POOL:
                if cand["cat"] == b["addr"]["cat"] and cand["surge"] == b["addr"]["surge"] and cand["town"] != a["addr"]["town"] \
                        and fuzz.token_sort_ratio(a["addr"]["address"].lower(), cand["address"].lower()) < 70:
                    b["addr"] = cand
                    break

# ---------------------------------------------------------------------------
# Phase D: numbering
# ---------------------------------------------------------------------------
seq = defaultdict(int)
for t in sorted(TERMS, key=lambda t: (t["issue"], t["subject"]["obj"]["id"])):
    ln = "01" if t["line"] == "motor" else "02"
    key = (ln, t["issue"].year)
    seq[key] += 1
    t["policy_no"] = f"MS-{ln}-{t['issue'].year % 100:02d}-MS-{seq[key]:06d}"
for t in TERMS:
    if t["prev"] is not None:
        t["renewing_no"] = t["prev"]["policy_no"]

LIVE = sorted([e for e in EVENTS if not e.get("drop")], key=lambda e: (e["reported"], e["loss"]))
aseq, lseq = defaultdict(int), defaultdict(lambda: rng.randint(80, 140))
for e in LIVE:
    ln = "01" if e["line"] == "motor" else "02"
    key = (ln, e["reported"].year)
    aseq[key] += 1
    e["accuterm"] = f"MS{e['reported'].year % 100:02d}{ln}03{aseq[key]:04d}"
for e in sorted([e for e in LIVE if e.get("loa_date")], key=lambda e: e["loa_date"]):
    y = e["loa_date"].year
    lseq[y] += 1
    e["loa_no"] = f"LOA{y % 100:02d}-{lseq[y]:05d}"

# ---------------------------------------------------------------------------
# Phase E: simulate the importer's policy -> quotation linking and fix conflicts
# ---------------------------------------------------------------------------
def amount_score(a, b):
    pct = abs(a - b) / b * 100 if b else 100
    return max(0.0, 100 - 2 * pct)
def date_score(days):
    days = abs(days)
    return 100 if days <= 7 else 85 if days <= 30 else 65 if days <= 90 else 40 if days <= 180 else 15

def simulate_linking():
    problems = []
    for line in ("motor", "fire"):
        taken = set()
        qs_by_person = defaultdict(list)
        for q in QUOTES:
            if q["line"] == line:
                qs_by_person[q["person"]["id"]].append(q)
        for t in sorted([t for t in TERMS if t["line"] == line], key=lambda t: (t["issue"], t["policy_no"])):
            cands = [q for q in qs_by_person[t["person"]["id"]] if id(q) not in taken]
            scored = sorted(((0.7 * amount_score(t["amount"], q["amount"]) + 0.3 * date_score((t["issue"] - q["date"]).days), q)
                             for q in cands), key=lambda x: -x[0])
            best = scored[0] if scored else (0, None)
            second = scored[1][0] if len(scored) > 1 else 0
            ok = best[1] is t["quote"] and best[0] >= 75 and best[0] - second >= 15
            if best[1] is not None and best[0] >= 75 and best[0] - second >= 15:
                taken.add(id(best[1]))
            if not ok:
                problems.append((t, scored[:3]))
    return problems

for attempt in range(6):
    probs = simulate_linking()
    if not probs:
        break
    for t, scored in probs:
        for sc, q in scored:
            if q is not t["quote"] and q["policy"] is None:
                q["amount"] = r2(q["amount"] * rng.choice([0.7, 1.35]))   # a clearly different offer
LINK_PROBLEMS = simulate_linking()

# ---------------------------------------------------------------------------
# Phase F: rows for the 8 upload files
# ---------------------------------------------------------------------------
import unicodedata
def ascii_(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
def upper_assured(p): return f"{p['first']} {p['middle'][0]}. {p['last']}".upper()
BANKS = ["BDO Unibank", "BPI", "Metrobank", "Security Bank", "PSBank", "China Bank", "RCBC"]
HEADERS = {}
FILES = {}

# ---------------------------------------------------------------------------
# Extra detail columns (Change 6 round). They use their OWN random sequence so that
# every value generated above (names, policies, claims, labels) stays byte-identical.
# ---------------------------------------------------------------------------
xr = random.Random(SEED + 606)
EMPLOYERS = ["Bulacan Provincial Government", "City Government of Malolos", "DepEd Schools Division of Bulacan",
             "Bulacan Medical Center", "SM Supermalls", "Puregold Price Club", "Jollibee Foods Corporation",
             "Meralco", "PLDT", "Globe Telecom", "BDO Unibank", "Metrobank", "San Miguel Corporation",
             "Petron Corporation", "Toyota Motor Philippines", "Concentrix", "Teleperformance",
             "St. Paul University Philippines", "Bulacan State University", "Philippine Coast Guard",
             "Philippine National Police", "Maynilad Water Services", "Mercury Drug Corporation",
             "Robinsons Land Corporation", "Ayala Land", "DMCI Homes", "Monde Nissin Corporation",
             "Universal Robina Corporation", "Megaworld Corporation", "Bureau of Internal Revenue"]
OFW_EMPLOYERS = ["Saudi Aramco", "Emirates Group", "Qatar Airways", "Hamad Medical Corporation",
                 "Singapore General Hospital", "Carnival Cruise Line", "Royal Caribbean", "Maersk Line"]
SEA_EMPLOYERS = ["Magsaysay Maritime Corporation", "PTC Group", "Philippine Transmarine Carriers", "Anglo-Eastern Crew Management"]
GOV_OCC = {"Government Employee", "Teacher", "Police Officer"}
SELF_OCC = {"Business Owner", "Sari-sari Store Owner", "Farmer", "Fisherman", "Contractor", "Architect", "Lawyer", "Doctor"}
used_tin, used_sss = set(), set()
def tin():
    while True:
        t = f"{xr.randint(100, 999)}-{xr.randint(100, 999)}-{xr.randint(100, 999)}-000"
        if t not in used_tin:
            used_tin.add(t); return t
def sss():
    while True:
        t = f"{xr.choice(['33', '34', '02', '03', '04'])}-{xr.randint(1000000, 9999999)}-{xr.randint(0, 9)}"
        if t not in used_sss:
            used_sss.add(t); return t
for p in PEOPLE:
    occ = p["occupation"]
    p["spouse"] = None
    if p["marital"] == "Married":
        sg = MALE if p["gender"] == "Female" else FEMALE
        sp_last = p["last"]  # married couples share the family name
        p["spouse"] = f"{xr.choice(sg)} {xr.choice([s for s in SURNAMES if s != sp_last])} {sp_last}"
    p["permanent"] = p["addr"]["address"] if xr.random() < 0.85 else xr.choices(POOL, weights=ADDR_WEIGHTS, k=1)[0]["address"]
    p["landline"] = f"(044) {xr.choice(['791', '796', '662', '760', '815', '913', '931'])}-{xr.randint(1000, 9999)}" if xr.random() < 0.33 else None
    if p.get("email_x") is None:
        base = ascii_(f"{p['first'].split()[0]}.{p['last'].replace(' ', '')}").lower()
        p["email_x"] = f"{base}{xr.randint(1, 99)}@{xr.choice(['gmail.com'] * 8 + ['yahoo.com', 'outlook.com'])}" if xr.random() < 0.85 else None
    if occ == "Retired":
        p["employer"] = None
    elif occ in SELF_OCC:
        p["employer"] = "Self-Employed"
    elif occ == "OFW":
        p["employer"] = xr.choice(OFW_EMPLOYERS)
    elif occ == "Seaman":
        p["employer"] = xr.choice(SEA_EMPLOYERS)
    elif occ == "Government Employee":
        p["employer"] = xr.choice(["Bulacan Provincial Government", "City Government of Malolos", "Bureau of Internal Revenue",
                                   f"Municipal Government of {p['addr']['town'].replace(' City', '')}"])
    elif occ == "Teacher":
        p["employer"] = xr.choice(["DepEd Schools Division of Bulacan", "Bulacan State University", "St. Paul University Philippines"])
    elif occ == "Police Officer":
        p["employer"] = "Philippine National Police"
    else:
        p["employer"] = xr.choice(EMPLOYERS)
    p["tin"] = tin() if xr.random() < 0.9 else None
    p["sss"] = None if (occ in GOV_OCC or occ == "Retired" and xr.random() < 0.4) else (sss() if xr.random() < 0.85 else None)

# survey extras
TOWN_CODE = {t: i + 1 for i, t in enumerate(sorted(TOWN_WEIGHT))}
EQ_ZONE = {t: ("Zone 1" if t in ("San Jose del Monte City", "Norzagaray", "Doña Remedios Trinidad", "Angat", "Santa Maria")
               else "Zone 2" if t in ("Marilao", "Meycauayan City", "Bocaue", "Pandi", "San Rafael", "San Ildefonso", "San Miguel", "Bustos", "Baliwag City")
               else "Zone 3") for t in TOWN_WEIGHT}
TI_CODE = {"Dwelling": "TI-101 (Dwelling)", "Store with Dwelling": "TI-112 (Store with Dwelling)",
           "Warehouse": "TI-305 (Warehouse)", "Restaurant": "TI-214 (Restaurant)", "Office": "TI-120 (Office)",
           "Small Factory": "TI-402 (Light Manufacturing)"}
BOUND = {"Dwelling": ["Residential house", "Vacant lot", "Barangay road", "Sari-sari store", "Chapel", "Rice field", "Concrete fence"],
         "commercial": ["Barangay road", "Provincial road", "Residential house", "Commercial building", "Vacant lot",
                        "Warehouse", "Gasoline station", "Drainage canal", "Market stalls"]}
for pr in PROPERTIES:
    t = pr["addr"]["town"]
    pr["district_block"] = f"D-{TOWN_CODE[t]:02d} / B-{xr.randint(10, 250):03d}"
    pr["block_acc"] = f"PHP {pr['tsi'] + xr.randint(2, 60) * 250_000:,.2f}"
    pr["zone"] = EQ_ZONE[t]
    pr["ti"] = TI_CODE[pr["occupancy"]]
    tsi = pr["tsi"]
    if pr["occupancy"] == "Dwelling":
        shares = {"building": 0.80, "main_occupancy": 0.0, "stocks": 0.0, "me": 0.0, "fff": 0.20, "bi_lop": 0.0, "others": 0.0}
    elif pr["occupancy"] == "Store with Dwelling":
        shares = {"building": 0.60, "main_occupancy": 0.0, "stocks": 0.25, "me": 0.0, "fff": 0.15, "bi_lop": 0.0, "others": 0.0}
    elif pr["occupancy"] == "Warehouse":
        shares = {"building": 0.40, "main_occupancy": 0.0, "stocks": 0.50, "me": 0.05, "fff": 0.05, "bi_lop": 0.0, "others": 0.0}
    elif pr["occupancy"] == "Restaurant":
        shares = {"building": 0.50, "main_occupancy": 0.0, "stocks": 0.10, "me": 0.25, "fff": 0.15, "bi_lop": 0.0, "others": 0.0}
    elif pr["occupancy"] == "Office":
        shares = {"building": 0.65, "main_occupancy": 0.0, "stocks": 0.0, "me": 0.15, "fff": 0.20, "bi_lop": 0.0, "others": 0.0}
    else:
        shares = {"building": 0.40, "main_occupancy": 0.0, "stocks": 0.25, "me": 0.30, "fff": 0.05, "bi_lop": 0.0, "others": 0.0}
    if pr["commercial"]:
        shares["main_occupancy"] = 0.10                     # improvements for the main occupancy
        if xr.random() < 0.5:
            shares["bi_lop"] = 0.12                         # business interruption / loss of profit
    if xr.random() < 0.4:
        shares["others"] = 0.03                             # fences, signage, outbuildings
    jitter = {k: (v * xr.uniform(0.85, 1.15) if v else 0) for k, v in shares.items()}
    tot = sum(jitter.values())
    parts = {k: float(round_to(tsi * v / tot, 1000)) for k, v in jitter.items() if v}
    main_key = max(parts, key=parts.get)
    parts[main_key] += tsi - sum(parts.values())      # parts add up exactly to the total sum insured
    pr["occ_parts"] = parts
    kind = "Dwelling" if pr["occupancy"] == "Dwelling" else "commercial"
    pr["bounds"] = {k: xr.choice(BOUND[kind]) for k in ("front", "right", "left", "rear")}
    pr["bounds"]["front"] = xr.choice(["Barangay road", "Provincial road", "Municipal road"]) if kind == "commercial" else xr.choice(["Barangay road", "Street", "Alley"])
    pr["sketch"] = "Refer to attached location sketch"

# 1 Customer Information
rows = []
for p in PEOPLE:
    if rng.random() < 0.45:   # kept only so the main random sequence stays identical to the first release
        rng.randint(1, 99)
    rows.append({"Last Name": p["last"], "First Name": p["first"], "Middle Name": p["middle"],
                 "Gender": p["gender"], "Marital Status": p["marital"], "Complete Name of Spouse": p["spouse"],
                 "Nationality": "Filipino", "Present Address": p["addr"]["address"], "Permanent Address": p["permanent"],
                 "Residence Phone Number": p["landline"], "Mobile Number": p["mobile"],
                 "Email Address": p["email_x"], "Zip Code": ZIP.get(p["addr"]["town"]), "Occupation": p["occupation"],
                 "Employer": p["employer"], "TIN": p["tin"], "SSS No.": p["sss"]})
FILES["1_customer_information"] = rows

# 2 Fire Surveys (one per property)
EQ_HIGH = {"San Jose del Monte City", "Norzagaray", "Doña Remedios Trinidad", "Angat", "Santa Maria"}
def rate3(x): return ["Low", "Moderate", "High"][x]
rows = []
for pr in PROPERTIES:
    p, a = pr["owner"], pr["addr"]
    fire_lvl = (pr["risk_class"] == "b") + pr["risky"]
    flood_lvl = {"High": 2, "Medium": 1}.get(a["cat"], 0)
    haz_bias = 1 if (pr["risk_class"] == "b" or pr["risky"]) else 0
    def haz():
        return wchoice([("Good", 55 - 25 * haz_bias), ("Fair", 35 + 10 * haz_bias), ("Poor", 10 + 15 * haz_bias)])
    rows.append({"Name of Insured": p["full"], "Contact Person": p["full"],
                 "Brief Description of Owner's Business": pr["bdesc"], "Location of Risk": a["address"],
                 "Tel/Fax No.": p["mobile"], "Risk Class": pr["risk_class"], "Description": pr["pins"],
                 "Maximum Amount Subject": pr["tsi"], "Loss Record": pr["loss_record"],
                 "Fire": rate3(fire_lvl), "Earthquake": "High" if a["town"] in EQ_HIGH else "Moderate",
                 "Typhoon": "High" if a["surge"] != "none" else "Moderate", "Flood": rate3(flood_lvl),
                 "Burglary/Robbery": rng.choice(["Low", "Low", "Moderate"]), "RSMD": "Low",
                 "Landslide/Subsidence": "Moderate" if a["town"] in EQ_HIGH else "Low",
                 "Smoke/Aircraft/Vehicle Impact/Explosion": "Moderate" if pr["risky"] else "Low",
                 "Volcanic Eruption": "Low", "Tsunami": "Moderate" if a["surge"] != "none" else "Low",
                 "Terrorist Attack": "Low", "Spontaneous Combustion": "Moderate" if pr["occupancy"] in ("Warehouse", "Small Factory") else "Low",
                 "Machinery Breakdown": "Moderate" if pr["occupancy"] in ("Small Factory", "Restaurant") else "Low",
                 "General Liability": "Moderate" if pr["commercial"] else "Low", "Money": "Moderate" if pr["commercial"] else "Low",
                 "Fidelity Guarantee": "Low", "Goods Transit": "Moderate" if pr["occupancy"] == "Warehouse" else "Low",
                 "Others": "Low",
                 "Maintenance": haz(), "Housekeeping": haz(), "Storage Arrangement": haz(),
                 "Safety/Security": haz(), "Block Condition": haz(), "Surrounding Community": haz(),
                 "Overall Risk Assessment": pr["overall"], "Surveyor Risk Acceptability": pr["acceptability"],
                 "Protection Facilities": ", ".join(pr["facilities"]) if pr["facilities"] else "None",
                 "District No./Block No.": pr["district_block"], "Current Block Accumulation": pr["block_acc"],
                 "Zone": pr["zone"], "T.I.": pr["ti"],
                 **{f"Occupancy - {lbl}": pr["occ_parts"].get(k) for k, lbl in
                    (("building", "Building"), ("main_occupancy", "Main Occupancy"), ("stocks", "Stocks"), ("me", "M/E"),
                     ("fff", "FFF"), ("bi_lop", "BI/LOP"), ("others", "Others"))},
                 "Occupancy - Total": pr["tsi"],
                 "Boundary - Front": pr["bounds"]["front"], "Boundary - Right": pr["bounds"]["right"],
                 "Boundary - Left": pr["bounds"]["left"], "Boundary - Rear": pr["bounds"]["rear"],
                 "Boundary - Sketch": pr["sketch"]})
FILES["2_fire_surveys"] = rows

# 3 Motor Quotations
rows = []
for q in sorted([q for q in QUOTES if q["line"] == "motor"], key=lambda q: (q["date"], q["subject"]["obj"]["id"])):
    v, p = q["subject"]["obj"], q["person"]
    if "bank" not in v:
        v["bank"] = rng.choice(BANKS) if (v["year_model"] >= q["date"].year - 1 and rng.random() < 0.35) else None
    rows.append({"Date": iso(q["date"]), "Insured Name": p["full"], "Address": p["addr"]["address"], "Unit": "1",
                 "Classification": "Commercial" if v["commercial"] else "Private", "Color": v["color"],
                 "Deductible": q["deductible"], "Plate No.": v["plate"], "Total Amount Due": q["amount"],
                 "Sum Insured": q["si"], "Model": str(v["year_model"]), "Make": v["make"], "Body Type": v["body"],
                 "Motor/Engine No.": v["engine"], "Serial/Chassis No.": v["chassis"],
                 "Authorized Capacity": CAPACITY[v["body"]], "Bank": v["bank"]})
FILES["3_motor_quotations"] = rows

# 4 Fire Quotations
DEDUCT_TEXT = "Fire/Lightning: NIL; Earthquake/Typhoon/Flood: 2% of ACV per claim; Extended Cover: 1% of SI (min P1,000, max P500,000)"
rows = []
for q in sorted([q for q in QUOTES if q["line"] == "fire"], key=lambda q: (q["date"], q["subject"]["obj"]["id"])):
    pr, p = q["subject"]["obj"], q["person"]
    rows.append({"Date": iso(q["date"]), "Name of Insured": p["full"], "Location of Risk": pr["addr"]["address"],
                 "Period of Cover": "One (1) Year", "Property Sums Insured": q["si"], "Total Sum Insured": q["si"],
                 "Total Premium": q["amount"], "Deductibles": DEDUCT_TEXT, "Occupancy": pr["occupancy"],
                 "Basis of Evaluation": "Replacement Cost",
                 "Perils Covered": "Fire and Lightning, Extended Coverage, Earthquake, Typhoon and Flood",
                 "Line of Insurance": "Fire"})
FILES["4_fire_quotations"] = rows

# 5 Fire Policies / 6 Motor Policies
for line, key in (("fire", "5_fire_policies"), ("motor", "6_motor_policies")):
    rows = []
    for t in sorted([t for t in TERMS if t["line"] == line], key=lambda t: (t["issue"], t["policy_no"])):
        p = t["person"]
        r = {"Issue Date": iso(t["issue"]), "Insured Name & Address": f"{p['full']}, {p['addr']['address'] if line == 'motor' else t['subject']['obj']['addr']['address']}",
             "Line of Insurance": "Fire" if line == "fire" else "Motor Car", "Policy No.": t["policy_no"],
             "Renewing Policy No.": t["renewing_no"], "Period From": iso(t["pfrom"]), "Period To": iso(t["pto"]),
             "Total Amount Due": t["amount"], "Sum Insured": t["si"], "Agency Code": t["agent"]}
        if line == "fire":
            pr = t["subject"]["obj"]
            r.update({"Property Insured": pr["pins"], "Construction": "Concrete" if pr["risk_class"] == "a" else "Concrete and Wood",
                      "Occupancy": pr["occupancy"]})
        else:
            r["Deductible"] = t["deductible"]
        rows.append(r)
    FILES[key] = rows

# 7/8 Claims
UPD = {"Closed Claim": ("SETTLED", ["SETTLED", "UNIT RELEASED"]),
       "Waiting for Claim Check": ("AWAITING FOR SETTLEMENT CHEQUE", ["WITH BILLING"]),
       "Waiting for Billing": ("AWAITING FOR BILLING", ["UNIT RELEASED", "ON REPAIR"]),
       "Waiting for LOA": ("WITH FINAL APPROVAL", ["FOR LOA ISSUANCE"]),
       "Waiting for Evaluation": ("FOR EVALUATION", ["ON PROCESS"]),
       "No Docs. Submitted": ("NO DOCUMENTS SUBMITTED", ["-"]),
       "With Lacking Docs": ("WITH LACKING DOCUMENTS", ["-"]),
       "Denied Claim": ("ALREADY SERVED THE DENIAL LETTER", ["DENIED"]),
       "Not Push Through": ("CLIENT DID NOT PURSUE THE CLAIM", ["-"]),
       "Hold per Client": ("ON HOLD PER CLIENT'S REQUEST", ["ON HOLD"]),
       "CNC Only": ("CNC ISSUED", ["OKAY"])}
FIRE_UPD = {"Closed Claim": ("SETTLED", ["SETTLED", "CHEQUE RELEASED"]),
            "Waiting for Claim Check": ("AWAITING FOR SETTLEMENT CHEQUE", ["FOR CHEQUE RELEASE"]),
            "Waiting for Billing": ("SIGNED OFFER RECEIVED", ["FOR PAYMENT PROCESSING"]),
            "Waiting for LOA": ("WITH ADJUSTER'S FINAL REPORT", ["FOR APPROVAL"]),
            "Waiting for Evaluation": ("WAITING FOR ADJUSTER REPORT", ["ON PROCESS"])}
def dash(x): return x if x not in (None, "") else "-"
def mmddyyyy(x): return x.strftime("%m.%d.%Y")
used_plates_tp = set()
def tp_plate():
    while True:
        p = "".join(rng.choice("ABCDEFGHIJKLMNPQRSTUVWXYZ") for _ in range(3)) + f"{rng.randint(1000, 9999)}"
        if p not in _used_plates and p not in used_plates_tp:
            used_plates_tp.add(p); return p
def third_party_name():
    g = rng.choice([MALE, FEMALE])
    return f"{rng.choice(g)} {rng.choice(SURNAMES)[0]}. {rng.choice(SURNAMES)}".upper()

def shop_for(e, v):
    if e["final"] in ("No Docs. Submitted",) or e.get("docs") is None and e["final"] == "With Lacking Docs":
        return None
    legit = e.get("label") == "Legitimate"
    if legit and rng.random() < 0.08:
        return rng.choice(["CASH SETTLEMENT", "REIMBURSEMENT"])
    if legit and v["make"] in REAL_DEALERS and rng.random() < 0.45:
        return rng.choice(REAL_DEALERS[v["make"]])
    return rng.choice(INVENTED_SHOPS)

motor_rows, fire_rows, TP_ROWS = [], [], 0
for e in LIVE:
    t = e["term"]; p = t["person"]; obj = t["subject"]["obj"]
    if e["cnc"]:
        final = "CNC Only"
        upd, sts = UPD[final]
        motor_rows.append({"Accuterm Claim No.": e["accuterm"], "Assured": upper_assured(p), "Claimant Name": upper_assured(p),
                           "Policy No.": t["policy_no"], "Plate No.": obj["plate"], "PLA Date (Date Reported)": iso(e["reported"]),
                           "Date of Loss": iso(e["loss"]), "Date of Docs Submission": "-", "Nature of Loss": "Collision",
                           "Coverage Type": "Own Damage", "Claim Type": "CNC Issuance", "Updates": upd,
                           "Date Updated": iso(min(TODAY, e["reported"] + dt.timedelta(days=rng.randint(1, 5)))),
                           "Agent Name": t["agent"], "Amount of Repair Estimate": "-", "Date of LOA Received": "-",
                           "LOA No.": "-", "LOA Amount": "-", "Net Liability": "-", "Shop/Casa": "-", "Status": sts[0],
                           "Billing Date and Remarks": "-", "Final Status": final, "Claim Investigation Result": None})
        continue
    table = UPD if e["line"] == "motor" else {**UPD, **FIRE_UPD}
    upd, sts = table[e["final"]]
    base = {"Accuterm Claim No.": e["accuterm"], "Assured": upper_assured(p), "Claimant Name": upper_assured(p),
            "Policy No.": t["policy_no"], "PLA Date (Date Reported)": iso(e["reported"]), "Date of Loss": iso(e["loss"]),
            "Date of Docs Submission": dash(iso(e.get("docs"))), "Nature of Loss": e["nature"], "Claim Type": "Paid Claim",
            "Updates": upd, "Date Updated": iso(e["updated"]), "Agent Name": t["agent"],
            "Amount of Repair Estimate": e["estimate"] if e.get("docs") else "-",
            "Date of LOA Received": dash(iso(e["loa_date"])), "LOA No.": dash(e.get("loa_no")),
            "LOA Amount": dash(e["loa_amt"]), "Net Liability": dash(e["net"]), "Status": rng.choice(sts),
            "Billing Date and Remarks": mmddyyyy(e["billing"]) if e["billing"] else "-",
            "Final Status": e["final"], "Claim Investigation Result": e["label"]}
    if e["line"] == "motor":
        shop = shop_for(e, obj)
        e["shop"] = shop
        motor_rows.append({**base, "Plate No.": obj["plate"], "Coverage Type": "Own Damage", "Shop/Casa": dash(shop)})
        # third party rows of the same accident (same Accuterm No., same investigation result)
        if e["nature"] == "Collision" and e.get("docs"):
            for cov, prob, lo, hi in (("Third Party Property Damage", 0.20, 10_000, 150_000),
                                      ("Third Party Bodily Injury/Death", 0.03, 20_000, 200_000)):
                if rng.random() < prob:
                    est = r2(rng.uniform(lo, hi))
                    loa = r2(est * rng.uniform(0.6, 0.95)) if e["loa_amt"] is not None else None
                    motor_rows.append({**base, "Claimant Name": third_party_name(),
                                       "Plate No.": tp_plate() if cov.endswith("Damage") else "-",
                                       "Coverage Type": cov, "Amount of Repair Estimate": est,
                                       "LOA No.": dash(e.get("loa_no")), "LOA Amount": dash(loa), "Net Liability": dash(loa),
                                       "Shop/Casa": dash(rng.choice(INVENTED_SHOPS) if cov.endswith("Damage") and loa else ("CASH SETTLEMENT" if loa else None))})
                    TP_ROWS += 1
    else:
        adj = rng.choice(ADJUSTERS) if e.get("docs") else None
        fire_rows.append({**base, "Adjuster": dash(adj)})

MOTOR_CLAIM_COLS = ["Accuterm Claim No.", "Assured", "Claimant Name", "Policy No.", "Plate No.", "PLA Date (Date Reported)",
                    "Date of Loss", "Date of Docs Submission", "Nature of Loss", "Coverage Type", "Claim Type", "Updates",
                    "Date Updated", "Agent Name", "Amount of Repair Estimate", "Date of LOA Received", "LOA No.",
                    "LOA Amount", "Net Liability", "Shop/Casa", "Status", "Billing Date and Remarks", "Final Status",
                    "Claim Investigation Result"]
FIRE_CLAIM_COLS = [c for c in MOTOR_CLAIM_COLS if c not in ("Plate No.", "Coverage Type", "Shop/Casa")]
FIRE_CLAIM_COLS.insert(FIRE_CLAIM_COLS.index("Status"), "Adjuster")
FILES["7_motor_claims"] = [{c: r.get(c) for c in MOTOR_CLAIM_COLS} for r in motor_rows]
FILES["8_fire_property_claims"] = [{c: r.get(c) for c in FIRE_CLAIM_COLS} for r in fire_rows]

# ---------------------------------------------------------------------------
# Write files
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import openpyxl
    for name, rows in FILES.items():
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sheet1"
        cols = list(rows[0].keys())
        ws.append(cols)
        for r in rows:
            ws.append([r[c] for c in cols])
        for i, c in enumerate(cols, 1):   # text cells stay text (mobile numbers keep their leading 0)
            if c in ("Mobile Number", "Tel/Fax No.", "Zip Code", "Model", "Unit", "Authorized Capacity", "TIN", "SSS No.", "Residence Phone Number"):
                for cell in ws.iter_cols(min_col=i, max_col=i, min_row=2):
                    for x in cell: x.number_format = "@"
        wb.save(OUT / f"{name}.xlsx")
    print("written:", {k: len(v) for k, v in FILES.items()})
