# MTG Arena Pack Recommendation Tool

This Python script helps Magic: The Gathering Arena players figure out the best booster packs to open to complete a specific deck, focusing on rare and mythic cards you still need.

---

## Overview

Given a decklist and a list of cards you already own, the script:

- Queries the Scryfall API to get card details and their printings.
- Filters to only include cards from MTG Arena legal sets.
- Calculates how many rare or mythic cards you are missing from each set.
- Calculates the value of opening standard-legal packs, factoring in golden pack contribution (including wildcards from golden packs) and giving extra weight to the most recent set for having guaranteed cards.
- Suggests which MTG Arena sets you should open packs from to maximize missing cards gained.
- Shows the missing cards per set along with the quantities needed.

---

## How It Works

1. **Input data**:  
   You provide an Excel file `mtg_decklist.xlsx` with two sheets:  
   - **Decklist**: Your desired deck with card names and quantities.
   - **Sideboard**: Your sideboard list with card names and quantities.
   - **Have**: Cards you already own with names and quantities.

2. **Scryfall API**:  
   The script fetches card details and printings from Scryfall.

3. **Set filtering**:  
   A manual list of MTG Arena sets is used to filter relevant printings.

4. **Counting missing cards**:  
   For each rare/mythic card in your deck, it calculates how many you are missing and attributes those missing copies to one printing set.

5. **Output**:  
   Calculates a weighted score for each set based on missing rares/mythics, golden pack contributions (including wildcards), and standard legality, showing recommended sets sorted by total value.

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
📦 Recommended Arena sets to open packs from (after applying wildcards):
===============================================================
Outlaws of Thunder Junction (OTJ): 6.6 card(s) weighted (rarities: 4 rare)
   - Spirebluff Canal (rare) (x4)
Bloomburrow (BLB): 6.6 card(s) weighted (rarities: 4 rare)
   - Artist's Talent (rare) (x4)
Tarkir Dragonstorm (TDM): 5.0 card(s) weighted (rarities: 3 rare)
   - Cori-Steel Cutter (rare) (x3)
...

## Notes

- Only rare and mythic cards are considered for pack recommendations.
- Missing card quantities are assigned to the first relevant printing set.
- The manual list of Arena sets can be updated as new sets are released.
- Golden pack contributions include both card drops and wildcards (1 rare every 6 packs, 1 uncommon every 6 packs; every 5th rare wildcard is mythic).
- Standard-legal sets get a bonus weight due to their contribution toward golden packs; the most recent set receives an even higher weight due to guaranteed golden pack drops.

