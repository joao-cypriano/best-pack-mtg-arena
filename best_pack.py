import pandas as pd
import requests
from collections import defaultdict
import time

EXCEL_PATH = "mtg_decklist.xlsx"
search_sideboard = False

mythic_wildcards = 5
rare_wildcards = 10

STANDARD_OR_ALCHEMY_LEGAL_SETS = [
    "eoe", "fin", "tdm", "dft", "dsk", "blb", "otj", "mkm",
    "lci", "woe", "mat", "mom", "one", "bro", "dmu", "fdn"
]
LATEST_STANDARD_SET = "eoe"

std_rotation_priority = {code: i for i, code in enumerate(STANDARD_OR_ALCHEMY_LEGAL_SETS)}

deck_df = pd.read_excel(EXCEL_PATH, sheet_name="Decklist")
owned_df = pd.read_excel(EXCEL_PATH, sheet_name="Have")

if search_sideboard:
    try:
        sideboard_df = pd.read_excel(EXCEL_PATH, sheet_name="Sideboard")
        deck_df = pd.concat([deck_df, sideboard_df], ignore_index=True)
    except Exception:
        print("⚠️ Sideboard tab not found or error reading it. Skipping sideboard.")

deck_df["Name"] = deck_df["Name"].str.strip()
owned_df["Name"] = owned_df["Name"].str.strip()
owned_dict = dict(zip(owned_df["Name"], owned_df["Qty"]))

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

def wildcard_value_from_n_packs(n_packs, rare_card_value=1.0, mythic_card_value=1.5):
    total_rare_wildcards = n_packs / 6
    total_mythic_wildcards = total_rare_wildcards // 5
    total_rare_wildcards -= total_mythic_wildcards
    return (total_rare_wildcards * rare_card_value) + (total_mythic_wildcards * mythic_card_value)

def get_card_data(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"❌ Card not found: {card_name}")
        return None
    return r.json()

def get_arena_printings(card_data, arena_sets, allowed_rarities, set_priority):
    r = requests.get(card_data["prints_search_uri"])
    if r.status_code != 200:
        return []

    printings = r.json()["data"]
    rarity_rank = {"mythic": 2, "rare": 1}

    filtered = [
        p for p in printings
        if p["set"] in arena_sets and p["rarity"] in allowed_rarities and "arena" in p.get("games", [])
    ]

    if not filtered:
        return []

    filtered.sort(key=lambda x: (-rarity_rank.get(x["rarity"], 0), set_priority.get(x["set"], 999)))
    best = filtered[0]
    return [(best["set"], best["rarity"])]

def best_sets_to_open(deck_df, owned_dict, allowed_rarities):
    preferred_order = [
        "eoe", "fdn", "dsk", "blb", "otj", "mkm", "lci", "woe", "mom", "one",
        "bro", "dmu", "snc", "neo", "vow", "mid", "afr", "stx", "khm", "znr",
        "pio", "sir", "akr", "klr", "mh3", "tdm", "eld", "thb", "m20", "war",
        "rna", "grn", "m19", "xln", "dom", "ktk", "rix"
    ]
    set_priority = {code: i for i, code in enumerate(preferred_order)}

    arena_sets = get_arena_sets()
    value_per_set = defaultdict(float)
    cards_by_set = defaultdict(lambda: defaultdict(int))
    rarity_counter_by_set = defaultdict(lambda: defaultdict(int))

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

        arena_printings = get_arena_printings(card_data, arena_sets, allowed_rarities, set_priority)
        if not arena_printings:
            continue

        chosen_set, rarity = arena_printings[0]
        cards_by_set[chosen_set][(name, rarity)] += qty_missing
        rarity_counter_by_set[chosen_set][rarity] += qty_missing

        effective_value = qty_missing

        if chosen_set in STANDARD_OR_ALCHEMY_LEGAL_SETS:
            is_latest = chosen_set == LATEST_STANDARD_SET
            golden_multiplier = 0.9 if is_latest else 0.6

            owned_qty = owned_dict.get(name, 0)
            protected_copies = min(qty_missing, 4 - owned_qty)
            golden_pack_bonus = protected_copies * golden_multiplier
            bonus_wildcard_value = wildcard_value_from_n_packs(1.1)

            effective_value += golden_pack_bonus + bonus_wildcard_value

        value_per_set[chosen_set] += effective_value
        time.sleep(0.1)

    rounded_value_per_set = {k: round(v, 3) for k, v in value_per_set.items()}

    # Debugging for checking if ties are being detected correctly
    # sorted_vals = sorted(rounded_value_per_set.items(), key=lambda x: -x[1])
    # for i in range(len(sorted_vals) - 1):
    #     if abs(sorted_vals[i][1] - sorted_vals[i + 1][1]) <= 1e-3:
    #         print(f"⚖️ Tie detected: {sorted_vals[i][0]} and {sorted_vals[i + 1][0]} with ~{sorted_vals[i][1]:.3f}")

    return rounded_value_per_set, arena_sets, cards_by_set, rarity_counter_by_set


def apply_wildcards_greedily(cards_by_set, rarity_counter_by_set, mythic_wildcards, rare_wildcards):
    usage_log = []

    while True:
        small_sets = [s for s in list(cards_by_set.keys()) if sum(cards_by_set[s].values()) <= 2]
        if not small_sets:
            break

        crafted_any = False
        for set_code in small_sets:
            rares = rarity_counter_by_set[set_code].get("rare", 0)
            mythics = rarity_counter_by_set[set_code].get("mythic", 0)

            mythics_to_craft = min(mythics, mythic_wildcards)
            for (card_name, card_rarity) in list(cards_by_set[set_code].keys()):
                if card_rarity == "mythic" and mythics_to_craft > 0:
                    qty = cards_by_set[set_code][(card_name, card_rarity)]
                    used = min(qty, mythics_to_craft)
                    cards_by_set[set_code][(card_name, card_rarity)] -= used
                    rarity_counter_by_set[set_code]["mythic"] -= used
                    mythic_wildcards -= used
                    mythics_to_craft -= used
                    usage_log.append(f"Crafted {used}x Mythic '{card_name}' from {set_code.upper()}")

            rares_to_craft = min(rares, rare_wildcards)
            for (card_name, card_rarity) in list(cards_by_set[set_code].keys()):
                if card_rarity == "rare" and rares_to_craft > 0:
                    qty = cards_by_set[set_code][(card_name, card_rarity)]
                    used = min(qty, rares_to_craft)
                    cards_by_set[set_code][(card_name, card_rarity)] -= used
                    rarity_counter_by_set[set_code]["rare"] -= used
                    rare_wildcards -= used
                    rares_to_craft -= used
                    usage_log.append(f"Crafted {used}x Rare '{card_name}' from {set_code.upper()}")

            cards_by_set[set_code] = {k: v for k, v in cards_by_set[set_code].items() if v > 0}
            rarity_counter_by_set[set_code] = {k: v for k, v in rarity_counter_by_set[set_code].items() if v > 0}

            if not cards_by_set[set_code]:
                del cards_by_set[set_code]
                rarity_counter_by_set.pop(set_code, None)

            crafted_any = True
        if not crafted_any:
            break

    def set_age_priority(set_code):
        return 1 if set_code in STANDARD_OR_ALCHEMY_LEGAL_SETS else 0

    remaining_sets = sorted(
        cards_by_set.keys(),
        key=lambda s: (set_age_priority(s), sum(cards_by_set[s].values())),
        reverse=False
    )

    for set_code in remaining_sets:
        if mythic_wildcards == 0 and rare_wildcards == 0:
            break

        mythics = rarity_counter_by_set[set_code].get("mythic", 0)
        rares = rarity_counter_by_set[set_code].get("rare", 0)

        mythics_to_craft = min(mythics, mythic_wildcards)
        for (card_name, card_rarity) in list(cards_by_set[set_code].keys()):
            if card_rarity == "mythic" and mythics_to_craft > 0:
                qty = cards_by_set[set_code][(card_name, card_rarity)]
                used = min(qty, mythics_to_craft)
                cards_by_set[set_code][(card_name, card_rarity)] -= used
                rarity_counter_by_set[set_code]["mythic"] -= used
                mythic_wildcards -= used
                mythics_to_craft -= used
                usage_log.append(f"Crafted {used}x Mythic '{card_name}' from {set_code.upper()}")

        rares_to_craft = min(rares, rare_wildcards)
        for (card_name, card_rarity) in list(cards_by_set[set_code].keys()):
            if card_rarity == "rare" and rares_to_craft > 0:
                qty = cards_by_set[set_code][(card_name, card_rarity)]
                used = min(qty, rares_to_craft)
                cards_by_set[set_code][(card_name, card_rarity)] -= used
                rarity_counter_by_set[set_code]["rare"] -= used
                rare_wildcards -= used
                rares_to_craft -= used
                usage_log.append(f"Crafted {used}x Rare '{card_name}' from {set_code.upper()}")

        cards_by_set[set_code] = {k: v for k, v in cards_by_set[set_code].items() if v > 0}
        rarity_counter_by_set[set_code] = {k: v for k, v in rarity_counter_by_set[set_code].items() if v > 0}

        if not cards_by_set[set_code]:
            del cards_by_set[set_code]
            rarity_counter_by_set.pop(set_code, None)

    return cards_by_set, rarity_counter_by_set, usage_log

def recalc_set_scores_with_bonus(cards_by_set, rarity_counter_by_set, allowed_rarities):
    scores = {}
    for set_code in cards_by_set:
        rare_count = rarity_counter_by_set[set_code].get("rare", 0)
        mythic_count = rarity_counter_by_set[set_code].get("mythic", 0)
        total_missing = rare_count + mythic_count

        base_score = total_missing

        if set_code in STANDARD_OR_ALCHEMY_LEGAL_SETS:
            is_latest = set_code == LATEST_STANDARD_SET
            golden_multiplier = 0.9 if is_latest else 0.6

            protected_copies = min(total_missing, 4)
            golden_pack_bonus = protected_copies * golden_multiplier
            bonus_wildcard_value = wildcard_value_from_n_packs(1.1)

            total_score = base_score + golden_pack_bonus + bonus_wildcard_value
        else:
            total_score = base_score

        scores[set_code] = total_score

    return scores

allowed_rarities = ["rare", "mythic"]

results, arena_sets, cards_by_set, rarity_counter_by_set = best_sets_to_open(deck_df, owned_dict, allowed_rarities)

cards_by_set, rarity_counter_by_set, usage_log = apply_wildcards_greedily(
    cards_by_set, rarity_counter_by_set, mythic_wildcards, rare_wildcards
)

scores_after = recalc_set_scores_with_bonus(cards_by_set, rarity_counter_by_set, allowed_rarities)

def tiebreaker_final(item):
    set_code, value = item
    std_age = std_rotation_priority.get(set_code, float("inf"))
    return (-round(value, 3), -std_age)

sorted_after = sorted(scores_after.items(), key=tiebreaker_final)

print("\n📦 Recommended Arena sets to open packs from (after applying wildcards):")
print("===============================================================")
for set_code, score in sorted_after:
    rarity_breakdown = ", ".join(
        f"{rarity_counter_by_set[set_code].get(rarity, 0)} {rarity}"
        for rarity in allowed_rarities
        if rarity_counter_by_set[set_code].get(rarity, 0) > 0
    )
    print(f"{arena_sets[set_code]} ({set_code.upper()}): {score:.1f} card(s) weighted (rarities: {rarity_breakdown})")
    for (card_name, card_rarity), qty_missing in sorted(cards_by_set[set_code].items()):
        print(f"   - {card_name} ({card_rarity}) (x{qty_missing})")

print("\n🎯 Wildcard crafting usage (only use them when you have enough wildcards to complete the deck, this step is just to aid in calculations):")
for log_line in usage_log:
    print(" -", log_line)
