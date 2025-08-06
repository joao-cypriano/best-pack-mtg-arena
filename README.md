# MTG Arena Pack Recommendation Tool

This Python script helps Magic: The Gathering Arena players figure out the best booster packs to open to complete a specific deck, focusing on rare and mythic cards you still need.

---

## Overview

Given a decklist and a list of cards you already own, the script:

- Queries the Scryfall API to get card details and their printings.
- Filters to only include cards from MTG Arena legal sets.
- Calculates how many rare or mythic cards you are missing from each set.
- Suggests which MTG Arena sets you should open packs from to maximize missing cards gained.
- Shows the missing cards per set along with the quantities needed.

---

## How It Works

1. **Input data**:  
   You provide an Excel file `mtg_decklist.xlsx` with two sheets:  
   - **Decklist**: Your desired deck with card names and quantities.  
   - **Have**: Cards you already own with names and quantities.

2. **Scryfall API**:  
   The script fetches card details and printings from Scryfall.

3. **Set filtering**:  
   A manual list of MTG Arena sets is used to filter relevant printings.

4. **Counting missing cards**:  
   For each rare/mythic card in your deck, it calculates how many you are missing and attributes those missing copies to one printing set.

5. **Output**:  
   Displays recommended sets to open packs from, along with a breakdown of missing cards and their quantities.

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
📦 Recommended Arena sets to open packs from:
=============================================
Guilds of Ravnica (GRN): 7 rare/mythic card(s) missing
   - Arclight Phoenix (x3)
   - Steam Vents (x4)

Outlaws of Thunder Junction (OTJ): 4 rare/mythic card(s) missing
   - Spirebluff Canal (x4)
...

## Notes

- Only rare and mythic cards are considered for pack recommendations.
- Missing card quantities are assigned to the first relevant printing set.
- The manual list of Arena sets can be updated as new sets are released.

