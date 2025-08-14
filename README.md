# MTG Arena Pack Recommendation Tool

This Python script helps Magic: The Gathering Arena players figure out the best booster packs to open to complete a specific deck, focusing on rare and mythic cards you still need.

---

## Overview

Given a decklist and a list of cards you already own, the script:

- Queries the Scryfall API to get card details and their printings.
- Filters to only include cards from MTG Arena legal sets.
- Calculates how many rare or mythic cards you are missing from each set.
- Calculates the expected value (EV) of opening each pack, factoring in:
  - Direct chance to hit missing rares/mythics from that set.
  - Golden Pack contribution (including partial contribution from wildcards in golden packs).
  - Wildcard track EV (1 rare wildcard every 6 packs; every 5th rare wildcard is a mythic).
- Gives extra weight to Standard-legal sets, especially the latest set, due to guaranteed Golden Pack drops.
- Suggests which MTG Arena sets you should open packs from to maximize missing cards gained.
- Shows the missing cards per set along with the quantities needed.
- Recommends a wildcard crafting order that aims to preserve EV in top sets.

---

## How It Works

1. **Input data**:  
   You provide an Excel file `mtg_decklist.xlsx` with these sheets:  
   - **Decklist**: Your desired deck with card names and quantities.  
   - **Have**: Cards you already own with names and quantities.  
   - **Sideboard** (optional): Your sideboard list (if `SEARCH_SIDEBOARD = True`).

2. **Scryfall API**:  
   The script fetches card details and printings from Scryfall.

3. **Set filtering**:  
   A manual list of MTG Arena sets is used to filter relevant printings.

4. **Counting missing cards**:  
   For each rare/mythic card in your deck, it calculates how many you are missing and assigns those missing copies to one printing set.

5. **Pack EV calculation**:  
   - **Direct pack EV**: Probability of pulling a needed rare or mythic from a pack.  
   - **Golden Pack EV**: Expected hits from progress toward golden packs, including slots distributed across Standard sets (latest set gets dedicated slots).  
   - **Wildcard EV**: Each pack contributes toward wildcards, which are converted into "card-equivalent" EV. Every 6 packs gives roughly 1 rare wildcard, and every 5th rare wildcard becomes a mythic.

6. **Ranking sets**:  
   Sets are ranked by total EV (direct + golden + wildcard), with ties broken in favor of older Standard sets.

7. **Wildcard crafting plan**:  
   Greedy crafting algorithm preserves high-EV sets first, then crafts remaining wildcards for lower-EV sets. Output includes a compressed log showing suggested crafting order.

---

## Requirements

- Python 3.7+
- Packages: `pandas`, `requests`, `openpyxl`

Install packages with:

```bash
pip install pandas requests openpyxl
```


## Excel File Format

Create `mtg_decklist.xlsx` with these two sheets on the same folder as the script (we have an example excel file on this repository):

### Decklist

| Name             | Qty |
|------------------|-----|
| Arclight Phoenix | 4   |
| Steam Vents      | 4   |
| ...              | ... |

### Have

| Name             | Qty |
|------------------|-----|
| Arclight Phoenix | 1   |
| Steam Vents      | 0   |
| ...              | ... |

- **Name** columns: Exact card names as recognized by Scryfall.
- **Qty** columns: Integer quantities.

## Usage

Run the script:

```bash
python best_packs.py
```

## Example Output

Using manual list of MTG Arena packs available
🔍 Processing: Arclight Phoenix
🔍 Processing: Artist's Talent

📦 Recommended sets to open (after crafting plan)
================================================
Dominaria United (DMU): direct≈1.46% + GP:0.49% + WC:18.33% → total≈20.28%  |  1/60 rares, 0/20 mythics
   - Rare: Shivan Reef (remaining needed: 1)
Outlaws of Thunder Junction (OTJ): direct≈1.46% + GP:0.49% + WC:18.33% → total≈20.28%  |  1/60 rares, 0/20 mythics
   - Rare: Spirebluff Canal (remaining needed: 1)

🎯 Suggested wildcard usage order (aiming not to eliminate targets in top sets):
  - Crafted 4x Mythic 'Arclight Phoenix' (remaining needed: 0)
  - Crafted 2x Rare 'Cori-Steel Cutter' (remaining needed: 1)
  - Crafted 3x Rare 'Artist' (remaining needed: 1)
  - Crafted 3x Rare 'Spirebluff Canal' (remaining needed: 1)
  - Crafted 3x Rare 'Steam Vents' (remaining needed: 1)
  - Crafted 4x Rare 'Riverglide Pathway' (remaining needed: 0)

🧩 Cards still missing after crafting plan (by name):
Artist's Talent, Cori-Steel Cutter, Hall of Storm Giants, Otawara, Soaring City, Shivan Reef, Spirebluff Canal, Steam Vents, Stormcarved Coast


## Notes

- Only rare and mythic cards are considered for pack recommendations.
- Missing card quantities are assigned to the first relevant printing set.
- The manual list of Arena sets can be updated as new sets are released.
- Golden pack contributions include both card drops and wildcards:
- 1 rare wildcard every 6 packs
- Every 5th rare wildcard is converted into a mythic
- Standard-legal sets get a bonus weight due to Golden Pack contributions; the latest set gets even more weight because of dedicated Golden Pack slots.
- Suggested wildcard crafting aims to preserve high-EV sets first, then fills lower-EV sets.
