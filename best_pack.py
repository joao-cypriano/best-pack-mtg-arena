import pandas as pd
import requests
import time
from collections import defaultdict

# =======================
# Config
# =======================
EXCEL_PATH = "mtg_decklist.xlsx"
SEARCH_SIDEBOARD = False

# Your current wildcards
MYTHIC_WILDCARDS = 7
RARE_WILDCARDS   = 15

# Consider only rares/mythics for pack EV
ALLOWED_RARITIES = {"rare", "mythic"}

# Normal Arena pack mythic replacement rate
P_RARE   = 7/8
P_MYTHIC = 1/8

# Golden Pack parameters
GOLDEN_PACK_SLOTS_TOTAL = 6
GOLDEN_PACK_SLOTS_LATEST_SET = 2      # fixed to latest Standard set
GOLDEN_PACK_SLOTS_ANY_STANDARD = 4    # uniformly distributed across all Standard sets (incl. latest)
GOLDEN_PACKS_PER_STD_PACK = 0.1       # 1 GP per 10 Standard packs
# Expected rarity mix in a Golden Pack: 1 guaranteed mythic + 5 slots with 1/8 upgrade
GOLDEN_EXPECTED_MYTHICS = 1 + 5*(1/8)
GOLDEN_EXPECTED_RARES   = GOLDEN_PACK_SLOTS_TOTAL - GOLDEN_EXPECTED_MYTHICS
GOLDEN_MYTHIC_RATE_PER_SLOT = GOLDEN_EXPECTED_MYTHICS / GOLDEN_PACK_SLOTS_TOTAL

# Wildcard track EV (very small, but certain) — tweak to taste
# Rough heuristic: every 6 packs ~1 rare WC; every 30 rares ~1 mythic WC (via 5th). Convert to "card-equivalent" EV.
def wildcard_value_from_n_packs(n_packs):
    total_rare_wc = n_packs / 6.0                   # one rare WC per 6 packs
    total_mythic_wc = int(total_rare_wc // 5)       # every 5 rares → 1 mythic
    total_rare_wc -= total_mythic_wc
    return total_rare_wc + total_mythic_wc

INCLUDE_WILDCARD_EV = True
# Whether a Golden Pack also contributes to the WC track (toggle if you prefer otherwise)
WILDCARDS_FROM_GOLDEN_PACK = True

# Your Standard/Alchemy sets universe & latest set
STANDARD_OR_ALCHEMY_LEGAL_SETS = [
    "eoe", "fin", "tdm", "dft", "dsk", "blb", "otj", "mkm",
    "lci", "woe", "mat", "mom", "one", "bro", "dmu", "fdn"
]
LATEST_STANDARD_SET = "eoe"

# Prefer the oldest Standard-legal set in ties (0 = newest, larger = older)
STD_ROTATION_PRIORITY = {code: i for i, code in enumerate(STANDARD_OR_ALCHEMY_LEGAL_SETS)}

# Basic Scryfall rate-limit
SCRYFALL_SLEEP = 0.12


# =======================
# Arena packs available (manual list)
# Only sets that actually have Arena boosters should be here
# =======================
def get_arena_sets():
    print("Using manual list of MTG Arena packs available...")
    return {
        "eoe": "Edge of Eternities",
        "fin": "Final Fantasy",
        "tdm": "Tarkir Dragonstorm",
        "dft": "Aetherdrift",
        "pio": "Pioneer Masters",
        "fdn": "Foundations",
        "dsk": "Duskmourn: House of Horror",
        "blb": "Bloomburrow",
        "mh3": "Modern Horizons 3",
        "otj": "Outlaws of Thunder Junction",
        "mkm": "Murders at Karlov Manor",
        "lci": "The Lost Caverns of Ixalan",
        "woe": "Wilds of Eldraine",
        "ltr": "The Lord of the Rings: Tales of Middle-earth",
        "mat": "March of the Machine: Aftermath",
        "mom": "March of the Machine",
        "one": "Phyrexia: All Will Be One",
        "bro": "The Brothers’ War",
        "dmu": "Dominaria United",
        "hbg": "Alchemy Horizons: Baldur’s Gate",
        "snc": "Streets of New Capenna",
        "neo": "Kamigawa: Neon Dynasty",
        "vow": "Innistrad: Crimson Vow",
        "mid": "Innistrad: Midnight Hunt",
        "afr": "Adventures in the Forgotten Realms",
        "stx": "Strixhaven: School of Mages",
        "khm": "Kaldheim",
        "znr": "Zendikar Rising",
        "m21": "Core Set 2021",
        "iko": "Ikoria: Lair of Behemoths",
        "thb": "Theros Beyond Death",
        "eld": "Throne of Eldraine",
        "m20": "Core Set 2020",
        "war": "War of the Spark",
        "rna": "Ravnica Allegiance",
        "grn": "Guilds of Ravnica",
        "m19": "Core Set 2019",
        "xln": "Ixalan",
        "dom": "Dominaria",
        # Remastered lines with boosters on Arena:
        "sir": "Shadows over Innistrad Remastered",
        "akr": "Amonkhet Remastered",
        "klr": "Kaladesh Remastered",
        "rvr": "Ravnica Remastered",
    }


# =======================
# Scryfall helpers
# =======================
def scryfall_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=20)
        time.sleep(SCRYFALL_SLEEP)
        if r.status_code == 200:
            return r.json()
        print(f"❌ Scryfall error {r.status_code} at {url}")
        return None
    except Exception as e:
        print(f"❌ Request exception at {url}: {e}")
        return None


def get_card_data(card_name):
    url = "https://api.scryfall.com/cards/named"
    data = scryfall_get(url, params={"exact": card_name})
    if data:
        print(f"🔍 Processing: {card_name}")
    else:
        print(f"❌ Card not found: {card_name}")
    return data


def get_all_arena_printings(card_data, arena_sets, allowed_rarities):
    """
    Returns list of (set_code, rarity_on_arena) for this card,
    counting ONLY Arena-openable booster printings.
    Fixes issues where paper has different rarity (e.g., Arclight Phoenix).
    """
    out = []
    uri = card_data.get("prints_search_uri")
    if not uri:
        return out

    while uri:
        page = scryfall_get(uri)
        if not page:
            break
        for p in page.get("data", []):
            if "arena" not in p.get("games", []):
                continue
            if not p.get("booster", False):
                continue  # ignore promos/theme decks/etc.
            set_code = p.get("set")
            rarity   = p.get("rarity")
            if set_code in arena_sets and rarity in allowed_rarities:
                out.append((set_code, rarity))
        uri = page.get("next_page")
    # Deduplicate while preserving order
    out = list(dict.fromkeys(out))
    return out


# Cache pool sizes to avoid repeated queries
_POOL_CACHE = {}

def get_pool_size_for_set(set_code, rarity):
    """
    Count Arena-openable booster cards of given rarity in the set.
    """
    key = (set_code, rarity)
    if key in _POOL_CACHE:
        return _POOL_CACHE[key]

    total = 0
    url = "https://api.scryfall.com/cards/search"
    params = {"q": f"e:{set_code} game:arena r:{rarity}", "unique": "prints"}
    while True:
        page = scryfall_get(url, params=params) if params else scryfall_get(url)
        if not page:
            break
        for c in page.get("data", []):
            if "arena" in c.get("games", []) and c.get("booster", False):
                total += 1
        next_page = page.get("next_page")
        if not next_page:
            break
        url, params = next_page, None

    _POOL_CACHE[key] = total
    return total


# =======================
# Data loading
# =======================
def load_data():
    deck_df  = pd.read_excel(EXCEL_PATH, sheet_name="Decklist")
    owned_df = pd.read_excel(EXCEL_PATH, sheet_name="Have")

    if SEARCH_SIDEBOARD:
        try:
            sideboard_df = pd.read_excel(EXCEL_PATH, sheet_name="Sideboard")
            deck_df = pd.concat([deck_df, sideboard_df], ignore_index=True)
        except Exception:
            print("⚠️ Sideboard tab not found or error reading it. Skipping sideboard.")

    deck_df["Name"]  = deck_df["Name"].str.strip()
    owned_df["Name"] = owned_df["Name"].str.strip()
    owned_dict = dict(zip(owned_df["Name"], owned_df["Qty"]))

    return deck_df, owned_dict


# =======================
# Need building (distinct names, by set/rarity)
# =======================
def build_needs(deck_df, owned_dict, arena_sets):
    """
    Build:
      - missing_by_card[name] = remaining qty needed for the deck
      - printings_by_card[name] = list of (set_code, arena_rarity)
      - need_names_by_set[set_code][rarity] = set of distinct needed names for that set/rarity
      - craft_rarity_by_card[name] = cheapest rarity available on Arena for crafting that name
    Only cards with qty_missing > 0 and rarity in ALLOWED_RARITIES will be tracked.
    """
    rarity_rank = {"rare": 1, "mythic": 2}
    need_names_by_set = defaultdict(lambda: {"rare": set(), "mythic": set()})
    printings_by_card = {}
    craft_rarity_by_card = {}
    missing_by_card = {}

    for _, row in deck_df.iterrows():
        name = str(row["Name"]).strip()
        qty_deck = int(row["Qty"])
        qty_owned = int(owned_dict.get(name, 0))
        qty_missing = max(qty_deck - qty_owned, 0)
        if qty_missing <= 0:
            continue

        card_data = get_card_data(name)
        if not card_data:
            continue

        arena_prints = get_all_arena_printings(card_data, arena_sets, ALLOWED_RARITIES)
        if not arena_prints:
            continue

        craft_rar = min((r for (_, r) in arena_prints), key=lambda r: rarity_rank[r])
        craft_rarity_by_card[name] = craft_rar
        printings_by_card[name] = arena_prints
        missing_by_card[name] = qty_missing

        for set_code, rar in arena_prints:
            need_names_by_set[set_code][rar].add(name)

    return missing_by_card, printings_by_card, craft_rarity_by_card, need_names_by_set


def compute_pool_sizes(need_names_by_set):
    pool_sizes = defaultdict(lambda: {"rare": 0, "mythic": 0})
    for set_code, by_rarity in need_names_by_set.items():
        for rar in ("rare", "mythic"):
            pool_sizes[set_code][rar] = get_pool_size_for_set(set_code, rar)
    return pool_sizes


# =======================
# Direct pack EV (per pack)
# =======================
def direct_pack_hit_prob_for_set(set_code, need_names_by_set, pool_sizes):
    Rn = len(need_names_by_set[set_code]["rare"])
    Mn = len(need_names_by_set[set_code]["mythic"])
    Rt = pool_sizes[set_code]["rare"] or 0
    Mt = pool_sizes[set_code]["mythic"] or 0
    rare_term   = P_RARE   * (Rn / Rt) if Rt > 0 else 0.0
    mythic_term = P_MYTHIC * (Mn / Mt) if Mt > 0 else 0.0
    return rare_term + mythic_term


# =======================
# Golden Pack EV (expected hit probability per Golden Pack)
# =======================
def golden_pack_expected_hit(need_names_by_set, pool_sizes, standard_sets, latest_set):
    """
    Expected # of hits (distinct-need successes) from ONE Golden Pack.
    """
    n_std = len(standard_sets)
    if n_std == 0:
        return 0.0

    # Expected slots per set
    slots_per_set = {}
    for s in standard_sets:
        base = GOLDEN_PACK_SLOTS_ANY_STANDARD / n_std  # share of the 4 "any Standard" slots
        if s == latest_set:
            base += GOLDEN_PACK_SLOTS_LATEST_SET       # +2 dedicated to latest set
        slots_per_set[s] = base

    # Expected mythic/rare slots per set
    gp_ev = 0.0
    for s, slots in slots_per_set.items():
        mythic_slots = slots * GOLDEN_MYTHIC_RATE_PER_SLOT
        rare_slots   = slots - mythic_slots
        Rn = len(need_names_by_set.get(s, {}).get("rare", set()))
        Mn = len(need_names_by_set.get(s, {}).get("mythic", set()))
        Rt = pool_sizes.get(s, {}).get("rare", 0) or 0
        Mt = pool_sizes.get(s, {}).get("mythic", 0) or 0

        if Mt > 0 and Mn > 0 and mythic_slots > 0:
            gp_ev += mythic_slots * (Mn / Mt)
        if Rt > 0 and Rn > 0 and rare_slots > 0:
            gp_ev += rare_slots * (Rn / Rt)

    return gp_ev


def per_pack_golden_bonus(need_names_by_set, pool_sizes):
    """
    EV added to ONE Standard-legal pack from the Golden Pack progress (0.1 GP per pack).
    This is identical across Standard sets (composition of GP is independent of which Standard pack you buy),
    but differs vs. non-Standard packs (which don't progress GP).
    """
    std_sets_present = [s for s in STANDARD_OR_ALCHEMY_LEGAL_SETS if s in need_names_by_set]
    if not std_sets_present:
        return 0.0
    gp_ev_one = golden_pack_expected_hit(
        need_names_by_set, pool_sizes, std_sets_present, LATEST_STANDARD_SET
    )
    return GOLDEN_PACKS_PER_STD_PACK * gp_ev_one


# =======================
# Wildcard EV per pack
# =======================
def wildcard_ev_per_pack(is_standard_pack: bool):
    if not INCLUDE_WILDCARD_EV:
        return 0.0
    ev = wildcard_value_from_n_packs(1.0)  # normal pack contributes
    if is_standard_pack and WILDCARDS_FROM_GOLDEN_PACK:
        ev += GOLDEN_PACKS_PER_STD_PACK * wildcard_value_from_n_packs(1.0)  # share of a GP "pack"
    return ev


# =======================
# Scoring and sorting
# =======================
def total_ev_for_pack(set_code, need_names_by_set, pool_sizes):
    direct = direct_pack_hit_prob_for_set(set_code, need_names_by_set, pool_sizes)

    is_standard = (set_code in STANDARD_OR_ALCHEMY_LEGAL_SETS)
    golden_bonus = per_pack_golden_bonus(need_names_by_set, pool_sizes) if is_standard else 0.0
    wc_bonus = wildcard_ev_per_pack(is_standard)

    return direct + golden_bonus + wc_bonus


def rank_sets(need_names_by_set, pool_sizes, arena_sets):
    scores = {}
    for s in need_names_by_set:
        if s not in arena_sets:
            continue
        scores[s] = total_ev_for_pack(s, need_names_by_set, pool_sizes)

    # Prefer higher score, then oldest Standard-legal in ties
    def tiebreak(item):
        s, val = item
        std_age = STD_ROTATION_PRIORITY.get(s, float("inf"))
        return (-round(val, 9), -std_age)

    return sorted(scores.items(), key=tiebreak)


# =======================
# Wildcard planner (avoid killing targets in top sets)
# =======================
def wildcard_plan(missing_by_card,
                  printings_by_card,
                  craft_rarity_by_card,
                  need_names_by_set,
                  pool_sizes,
                  rare_wildcards,
                  mythic_wildcards,
                  top_k_protect=3):
    """
    Greedy crafting that first preserves EV in the top-K sets,
    then continues crafting from lower-EV sets until wildcards are exhausted.
    """

    usage_log = []
    base_scores_map = {s: direct_pack_hit_prob_for_set(s, need_names_by_set, pool_sizes)
                       for s in need_names_by_set}
    protected_sets = set([s for s, _ in
                          sorted(base_scores_map.items(), key=lambda kv: kv[1], reverse=True)[:top_k_protect]])

    rarity_prob = {"rare": P_RARE, "mythic": P_MYTHIC}

    def ev_loss_if_eliminate(card_name):
        loss = 0.0
        for s, rar in printings_by_card[card_name]:
            if card_name in need_names_by_set.get(s, {}).get(rar, set()):
                denom = pool_sizes.get(s, {}).get(rar, 0)
                if denom > 0:
                    loss += rarity_prob[rar] * (1.0 / denom)
        return loss

    def protected_affinity(card_name):
        return sum(base_scores_map.get(s, 0.0) for (s, _) in printings_by_card[card_name] if s in protected_sets)

    def pick_and_craft_one(rarity, wc_left, ignore_protection=False):
        if wc_left <= 0:
            return False, wc_left

        candidates = [n for n, miss in missing_by_card.items()
                      if miss > 0 and craft_rarity_by_card.get(n) == rarity]
        if not candidates:
            return False, wc_left

        not_eliminate = [n for n in candidates if missing_by_card[n] > 1]
        eliminate     = [n for n in candidates if missing_by_card[n] == 1]

        chosen = None
        if not_eliminate:
            # Safe craft
            not_eliminate.sort(key=lambda n: (protected_affinity(n), ev_loss_if_eliminate(n)))
            chosen = not_eliminate[0]
        elif eliminate and not ignore_protection:
            # Only eliminate if unavoidable
            eliminate.sort(key=lambda n: (ev_loss_if_eliminate(n), protected_affinity(n)))
            chosen = eliminate[0]
        elif candidates:
            # Force-craft ignoring protection
            # Pick from lowest-EV sets first
            candidates.sort(key=lambda n: sum(base_scores_map.get(s, 0.0) for (s, _) in printings_by_card[n]))
            chosen = candidates[0]

        if chosen is None:
            return False, wc_left

        # Craft
        missing_by_card[chosen] -= 1
        usage_log.append(f"Crafted 1x {rarity.capitalize()} '{chosen}' (remaining need: {missing_by_card[chosen]})")

        # Remove from need sets if eliminated
        if missing_by_card[chosen] == 0:
            for s, rar in printings_by_card[chosen]:
                if chosen in need_names_by_set.get(s, {}).get(rar, set()):
                    need_names_by_set[s][rar].remove(chosen)

        return True, wc_left - 1

    # Phase 1: preserve top-K sets
    progress = True
    toggle = "mythic"
    while progress and (rare_wildcards > 0 or mythic_wildcards > 0):
        progress = False
        if toggle == "mythic" and mythic_wildcards > 0:
            did, mythic_wildcards = pick_and_craft_one("mythic", mythic_wildcards)
            progress = progress or did
        if toggle == "rare" and rare_wildcards > 0:
            did, rare_wildcards = pick_and_craft_one("rare", rare_wildcards)
            progress = progress or did
        toggle = "rare" if toggle == "mythic" else "mythic"

        # Stop if no craftable cards remain
        if not any(missing_by_card.get(n, 0) > 0 for n in missing_by_card):
            break

    # Phase 2: craft remaining wildcards ignoring top-K protection, lowest-EV sets first
    while rare_wildcards > 0 or mythic_wildcards > 0:
        progress = False
        if mythic_wildcards > 0:
            did, mythic_wildcards = pick_and_craft_one("mythic", mythic_wildcards, ignore_protection=True)
            progress = progress or did
        if rare_wildcards > 0:
            did, rare_wildcards = pick_and_craft_one("rare", rare_wildcards, ignore_protection=True)
            progress = progress or did
        if not progress:
            break  # no more candidates left

    return missing_by_card, need_names_by_set, usage_log


# =======================
# Print results
# =======================
def print_recommendations(sorted_scores, need_names_by_set, pool_sizes, arena_sets, title, missing_by_card):
    print(f"\n📦 {title}")
    print("=" * (2 + len(title)))
    # Precompute constant Golden Pack per-pack bonus for Standard sets (for display)
    gp_per_pack = per_pack_golden_bonus(need_names_by_set, pool_sizes)

    for set_code, score in sorted_scores:
        if set_code not in arena_sets:
            continue

        Rn = len(need_names_by_set[set_code]["rare"])
        Mn = len(need_names_by_set[set_code]["mythic"])
        Rt = pool_sizes[set_code]["rare"] or 0
        Mt = pool_sizes[set_code]["mythic"] or 0

        # Skip sets with no needed cards
        if Rn + Mn == 0:
            continue

        direct = direct_pack_hit_prob_for_set(set_code, need_names_by_set, pool_sizes)
        is_std = set_code in STANDARD_OR_ALCHEMY_LEGAL_SETS
        gp = gp_per_pack if is_std else 0.0
        wc = wildcard_ev_per_pack(is_std)

        pct_direct = f"{100.0 * direct:.2f}%"
        pct_total  = f"{100.0 * score:.2f}%"
        gp_str = f" + GP:{100.0*gp:.2f}%" if is_std else ""
        wc_str = f" + WC:{100.0*wc:.2f}%" if INCLUDE_WILDCARD_EV else ""

        rare_str   = f"{Rn}/{Rt} rares"
        mythic_str = f"{Mn}/{Mt} mythics"
        print(f"{arena_sets[set_code]} ({set_code.upper()}): direct≈{pct_direct}{gp_str}{wc_str} → total≈{pct_total}  |  {rare_str}, {mythic_str}")

        # Merge all cards of same rarity in one line with remaining count
        for rar in ("mythic", "rare"):
            names = sorted(need_names_by_set[set_code][rar])
            if not names:
                continue
            cards_info = ", ".join(f"{name} (remaining needed: {missing_by_card.get(name, '?')})" for name in names)
            print(f"   - {rar.capitalize()}: {cards_info}")



def compress_crafting_log_global(usage_log):
    """
    Aggregate all crafts of the same card+rarity, ignoring order,
    and track the last remaining need.
    """

    counter = defaultdict(lambda: {"count": 0, "remaining": 0})

    for line in usage_log:
        # Parse line: "Crafted 1x Rare 'CardName' (remaining needed: X)"
        parts = line.split("'")
        if len(parts) < 2:
            continue
        name = parts[1]
        rar = line.split(" ")[2]  # 'Rare' or 'Mythic'
        rem = int(line.split("remaining need:")[1].strip(") "))

        counter[(rar, name)]["count"] += 1
        counter[(rar, name)]["remaining"] = rem

    # Build compressed log
    compressed = []
    for (rar, name), info in counter.items():
        compressed.append(f"- Crafted {info['count']}x {rar} '{name}' (remaining needed: {info['remaining']})")

    # Optional: sort by rarity then name
    compressed.sort(key=lambda x: (0 if "Mythic" in x else 1, x))
    return compressed



# =======================
# Main
# =======================
def main():
    arena_sets = get_arena_sets()
    deck_df, owned_dict = load_data()

    # Build needs
    missing_by_card, printings_by_card, craft_rarity_by_card, need_names_by_set = build_needs(
        deck_df, owned_dict, arena_sets
    )

    if not need_names_by_set:
        print("🎉 No missing rares/mythics detected for Arena boosters in this deck.")
        return

    # Pools
    pool_sizes = compute_pool_sizes(need_names_by_set)

    # If you want to know what is best without considering wildcard usage, uncomment these lines

    # # Rank before crafting
    # ranked_before = rank_sets(need_names_by_set, pool_sizes, arena_sets)
    # print_recommendations(ranked_before, need_names_by_set, pool_sizes, arena_sets,
    #                       "Recommended sets to open (before crafting)")

    # Wildcard plan (preserve EV in top sets)
    missing_after, need_after, usage_log = wildcard_plan(
        missing_by_card.copy(),
        printings_by_card,
        craft_rarity_by_card,
        {s: {"rare": set(need_names_by_set[s]["rare"]),
             "mythic": set(need_names_by_set[s]["mythic"])}
         for s in need_names_by_set},
        pool_sizes,
        RARE_WILDCARDS,
        MYTHIC_WILDCARDS,
        top_k_protect=3
    )

    # Rank after crafting plan
    ranked_after = rank_sets(need_after, pool_sizes, arena_sets)
    print_recommendations(ranked_after, need_after, pool_sizes, arena_sets,
                      "Recommended sets to open (after crafting plan)", missing_after)

    # Crafting log
    print("\n🎯 Suggested wildcard usage order (aiming not to eliminate targets in top sets):")
    compressed_log = compress_crafting_log_global(usage_log)
    if compressed_log:
        for line in compressed_log:
            print(" ", line)
    else:
        print(" - No wildcard crafting suggested or no candidates available with given wildcards.")



    # Any cards still missing (by name)
    still_missing = sorted([n for n, m in missing_after.items() if m > 0])
    if still_missing:
        print("\n🧩 Cards still missing after crafting plan (by name):")
        print(", ".join(still_missing))


if __name__ == "__main__":
    main()
