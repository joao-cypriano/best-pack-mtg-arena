import pandas as pd
import requests
from collections import defaultdict
import time

# === 1. Load decklist and owned cards from Excel ===
EXCEL_PATH = "mtg_decklist.xlsx"

deck_df = pd.read_excel(EXCEL_PATH, sheet_name="Decklist")
owned_df = pd.read_excel(EXCEL_PATH, sheet_name="Have")

deck_df["Name"] = deck_df["Name"].str.strip()
owned_df["Name"] = owned_df["Name"].str.strip()
owned_dict = dict(zip(owned_df["Name"], owned_df["Qty"]))


# === 2. Get Scryfall Arena sets ===
def get_arena_sets():
    print("Using manual list of MTG Arena packs available...")
    return {
        "eoe": "Edge of Eternities",
        "fin": "Final Fantasy",
        "tdm": "Tarkir Dragonstorm",
        "dft": "Aetherdrift",
        "pio": "Pioneer Masters",
        "fdn": "Foundations",
        "dsk": "Duskmourn House of Horror",
        "blb": "Bloomburrow",
        "mh3": "Modern Horizons 3",
        "otj": "Outlaws of Thunder Junction",
        "mkm": "Murders at Karlov Manor",
        "lci": "Lost Caves of Ixalan",
        "woe": "Wilds of Eldraine",
        "ltr": "LotR",
        "mat": "March of Machine Aftermath",
        "mom": "March of Machine",
        "one": "Phyrexia One",
        "bro": "Brothers War",
        "dmu": "Dominaria United",
        "hbg": "Alchemy Horizons BG",
        "snc": "Streets of New Capenna",
        "neo": "Kamigawa Neon",
        "vow": "Innistrad Crimson Vow",
        "mid": "Innistrad Midnight Hunt",
        "afr": "Adventures in the Forgotten Realms",
        "stx": "Strixhaven School of Mages",
        "khm": "Kaldheim",
        "znr": "Zendikar Rising",
        "m21": "Core 21",
        "ikd": "Ikoria Lair of Behemots",
        "thb": "Theros Beyond Death",
        "eld": "Throne of Eldraine",
        "m20": "Core 20",
        "war": "War of the Spark",
        "rna": "Ravnica Allegiance",
        "grn": "Guilds of Ravnica",
        "m19": "Core 19",
        "xln": "Ixalan",
        "dom": "Dominaria",
        "ktk": "Khans of Tarkir",
        "rix": "Rivals of Ixalan",
        "sir": "Shadows over Innistrad Remastered",
        "akr": "Amonkhet Remastered",
        "klr": "Kaladesh Remastered"
    }


# === 3. Get card info and printings from Scryfall ===
def get_card_data(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"❌ Card not found: {card_name}")
        return None
    return r.json()


def get_arena_printings(card_data, arena_sets, allowed_rarities):
    printings_url = card_data["prints_search_uri"]
    r = requests.get(printings_url)
    if r.status_code != 200:
        return []

    printings = r.json()["data"]
    arena_printings = [
        (p["set"], p["rarity"]) for p in printings
        if p["set"] in arena_sets and p["rarity"] in allowed_rarities
    ]
    return arena_printings


# === 4. Main logic: find best sets ===
def best_sets_to_open(deck_df, owned_dict, allowed_rarities):
    arena_sets = get_arena_sets()
    set_counter = defaultdict(int)
    cards_by_set = defaultdict(lambda: defaultdict(int))  # dict[set_code][card_name] = qty_missing

    for _, row in deck_df.iterrows():
        name = row["Name"]
        qty_deck = int(row["Qty"])
        qty_owned = owned_dict.get(name, 0)
        qty_missing = max(qty_deck - qty_owned, 0)

        if qty_missing == 0:
            continue

        print(f"🔍 Processing: {name} (needs {qty_missing})")
        card_data = get_card_data(name)
        if not card_data:
            continue

        arena_printings = get_arena_printings(card_data, arena_sets, allowed_rarities)

        if not arena_printings:
            continue  # no matching arena printings, skip

        # Assign the missing quantity to the first matching set printing
        chosen_set = arena_printings[0][0]
        set_counter[chosen_set] += qty_missing
        cards_by_set[chosen_set][name] += qty_missing

        time.sleep(0.1)  # be kind to the API

    sorted_sets = sorted(set_counter.items(), key=lambda x: x[1], reverse=True)
    return sorted_sets, arena_sets, cards_by_set


# === 5. Run and output result ===
# Here you define which rarities you want to consider
allowed_rarities = ["rare", "mythic"]  # ex: include mythics and rares
# allowed_rarities = ["rare"]  # ex: only rares
# allowed_rarities = ["mythic"]  # ex: only mythics

results, arena_sets, cards_by_set = best_sets_to_open(deck_df, owned_dict, allowed_rarities)

print("\n📦 Recommended Arena sets to open packs from:")
print("=============================================")
for set_code, count in results:
    print(f"{arena_sets[set_code]} ({set_code.upper()}): {count} card(s) missing (rarities: {allowed_rarities})")
    for card_name, qty_missing in sorted(cards_by_set[set_code].items()):
        print(f"   - {card_name} (x{qty_missing})")
