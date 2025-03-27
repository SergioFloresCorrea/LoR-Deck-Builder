# LoR-Deck-Builder
Designs different decks for the game Library of Ruina. 

It uses beam search along with a experience-driven scorer (aka, my experience) to select 9 cards among all combat pages in the game, scrapped from [the wiki](https://libraryofruina.wiki.gg/wiki/List_of_Combat_Pages#tabber-tabpanel-Guests-0). This deck builder doesn't take into account combat pages with real-time effects such as Burning Flash, Clone or Brawl. 

# Installation
After cloining/downloading the repo, install the necessary dependencies with the command:
```
pip install -r requirements.txt
```

Once ready, you can directly construct your deck using
```
python main.py --effect bleed --beam 6 --temperature 0.6 --exclude_low_rank
```

# Arguments
- **effect**: Which effect the deck should focus on. Please refer to [the wiki](https://library-of-ruina.fandom.com/wiki/Status_Effects).
- **may_include**: A exhaustive list of words that the combat pages must contain in order to be included in the deck. At least one word per combat page is guaranteed to appear. To use it, the values must be separated by spaces, like `--may_include "Canard" "Urban Plague"`.
- **temperature**: A parameter that randomizes the beam search. A value of 0 is almost fully deterministic while 1 is fully random.
- **beam**: The parameter in the beam search.

 ## Special Flags
 - **--exclude_low_rank**: Excludes all combat pages belonging to: Canard, Urban Myth, Urban Plague and Urban Legend
 - **--exclude_high_rank**: Excludes all combat pages belonging to: Star of the City, Impuritas Civitatis.

# Known Limitations
- The Deck Builder doesn't consider exclusive combat pages. 
- A parameter `--temp 0` is not purely deterministic as it resulted in `NaN`, it was soft-capped to `--temp 0.01`
- The scoring function is based on my experience, so it can be improved.

You may use this code as you see fit. 
