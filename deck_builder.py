import math
import numpy as np
import scipy
from copy import deepcopy
from typing import List, Union, Dict, Optional, Tuple, Any, Callable, Iterator
from combat_page_getter import count_deck_attribute_statistics, apply_filters, remove_passive_cards, total_status_effects
from combat_page_styler import load_json
from get_contents import export_dict_to_json
from data_checkpoint import DeckCheckpoint
from collections import Counter

def softmax(x, temp):
    """
    Compute softmax values for each sets of scores in x. 
    Courtesy of https://github.com/sascha-kirch/ML_Notebooks/blob/main/Softmax_Temperature.ipynb.
    """
    return np.exp(np.divide(x,temp)) / np.sum(np.exp(np.divide(x,temp)), axis=0)

def normalize_values(min_val: float, max_val: float) -> Callable[[float], float]:
    """
    Defines a normalizer for any value to a range between 0 to 1. 
    Args: min_val: Minimum value expected of the magnitude to normalize.
          max_val: Maximum value expected of the magnitude to normalize.
    Returns: A Callable object that will normalize the values.
    """
    def normalizer(x: float):
        k = 0.99 * ( 1 / (max_val - min_val) + 1) # assures normalizer(max_val) = 0.99
        try: 
            return k * (x - min_val) / (1 + x - min_val)
        except ZeroDivisionError:
            return 0
    return normalizer

def calculate_normalized_entropy(attributes: Counter) -> float:
    """
    Calculates the spreadness of the dices in their different attributes. Ideally, we would want them all to be of the same type.
    We are using a variant of Shannon's entropy.
    It returns 1 if the data is completely skewed (no spread) while 0 if the data is completely uniform. 
    """
    # We want to consider counterX and X as the same
    dice_types = ["slash", "blunt", "pierce", "evade", "block"]
    suffix = "counter"
    counter = dict.fromkeys(dice_types, 0)

    for i in attributes.keys():
        if i in dice_types:
            counter[i] += attributes[i]
        elif i.endswith(suffix):
            dice_type = i[:-len(suffix)]
            counter[dice_type] += attributes[i]
        else:
            raise ValueError(f"{i} is not a valid dice type.")
    
    counter = Counter(counter)
    total = sum(counter.values())
    if total == 0:
        return 0.0  # no dice at all

    probs = [count / total for count in counter.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(len(counter))  # max possible entropy

    return 1 - (entropy / max_entropy) if max_entropy > 0 else 1.0


def assign_score(combat_pages: Union[Dict[str, Union[str, Dict[str, str]]], List[Dict[str, Union[str, Dict[str, str]]]]], 
                 effect: Optional[str] = "strength", debug: bool = False) -> float:
    """
    Assigns a single number as a score to a list(or single) of combat pages with respect to its attributes.
    We want to maximize the avg dice value and minimize the dice spreadness.  
    I am not sure how to merge the weighted avg dice value and the avg dice value, so the implementation is lazy. 
    Keyword Args: effects: A string containing the status effect that wants to be included in the deck. 
                           If no effect is passed, then strength it is. If you really want none, parse "no_effects" 
    """
    if isinstance(combat_pages, dict):
        combat_pages = [combat_pages]
    elif not isinstance(combat_pages, list):
        raise ValueError("A score can only be assigned to a list of combat pages.")

    if effect == "no_effects":
        multiplier = 0 # let's see what we do with this
    else:
        multiplier = 0.20
    
    stats = count_deck_attribute_statistics(combat_pages)
    status_effects = stats['status_effects']
    num_cards = len(combat_pages)

    # Normalizers
    norm = normalize_values
    n_effects = norm(0, 5)(status_effects[effect]) # Lazy as hell
    if debug:
        print(f"number of effects: {n_effects}\n Multiplier: {multiplier}")
    n_dice_val = norm(2, 10)(stats['weighted_average_dice_value'])
    n_total_dice = norm(0, 30)(stats['average_dice_per_card'] * num_cards)
    skewness = calculate_normalized_entropy(stats['total_dice_types'])

    # New sustainability metric
    light_regen = stats['total_light_regen']
    avg_cost = stats['average_cost']
    margin = light_regen - (6.38 * avg_cost - 6.88)
    sustain_score = (margin / (1 + abs(margin)) + 1) / 2
    sustain_score = scipy.stats.norm.pdf(sustain_score, loc=0.55, scale=0.2) # We don't want to have a lot of light regen, but also not little of
    sustain_score = sustain_score / sustain_score.max()

    # Same for n_draw
    draw_center, draw_spread = 4, 1.5
    n_draw = scipy.stats.norm.pdf(stats['total_drawn_cards'], loc=draw_center, scale=draw_spread)
    n_draw /= scipy.stats.norm.pdf(draw_center, loc=draw_center, scale=draw_spread)

    # Weighted score
    score = (
        (0.18 - 1/3 * multiplier) * sustain_score +
        (0.25 - 1/3 * multiplier) * n_dice_val +
        (0.20 - 1/3 * multiplier) * n_draw +
        0.15 * n_total_dice +
        0.22 * skewness + 
        multiplier * n_effects
    )

    return score

def update_counter(counter: Counter, obj: Any, value: int = 1) -> Counter:
    """
    Updates a counter with a given object
    """
    if obj in counter:
        counter[obj] += value
    else:
        counter[obj] = value

def count_cards(selected_decks: List[List[Dict[str, Union[str, Dict[str, str]]]]]) -> List[Counter]:
    """
    Counts the number of cards in the selected decks.
    """
    n_selected_decks = len(selected_decks)
    counters = [Counter() for _ in range(n_selected_decks)]
    for index, counter in enumerate(counters):
        deck = selected_decks[index]
        if isinstance(deck, list):
            for combat_page in deck:
                name = combat_page['Name']
                update_counter(counter, name)

        elif isinstance(deck, dict):
            name = deck['Name']
            update_counter(counter, name)
    
    return counters


def sample_top_cards(cards_score: List[float], decks: List[List[Dict[str, Union[str, Dict[str, str]]]]], 
                     B: int = 4, temp: float = 1.0) -> Iterator[Tuple[float, List[Dict]]]:
    """
    Samples a list of decks using softmax probability. It also tracks how many of each card is being added.
    """
    n_decks = len(decks)
    indices = np.arange(0, n_decks)
    indices_sampled = np.random.choice(indices, p=softmax(cards_score, temp), size=B, replace=False)
    
    selected_scores = [cards_score[index] for index in indices_sampled]
    selected_decks = [deepcopy(decks[index]) for index in indices_sampled]
    counters = count_cards(selected_decks)
    return zip(selected_scores, selected_decks, counters)

def is_singleton(deck: List[Dict[str, Union[str, Dict[str, str]]]]) -> bool:
    """
    Checks if it contains a Singleton card.
    """
    all_text_parts = []
    for card in deck:
        all_text_parts.append(card.get("Effect", ""))
        all_text_parts.extend(card.get("Dices", {}).values())
    
    all_text = "\n".join(all_text_parts)
    all_text = all_text.lower()

    return "singleton" in all_text

def change_card_limit(deck: List[Dict[str, Union[str, Dict[str, str]]]]) -> bool:
    """
    Changes the card limit of all cards in the deck to 1.
    """
    new_deck = deepcopy(deck)
    for card in new_deck:
        card["Card Limit"] = 1
    
    return new_deck

def deck_beam_search(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], B: int = 4, flags: Dict[str, bool] = None,
                     max_deck_size: int = 9, temp: float = 1.0, seed: Optional[int] = None, effect: str = "Strength", 
                     debug: bool = False) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Performs beam search algorithm on a list of combat pages and returns a deck consisting of 9 cards.
    Keyword args: B: Beam search parameter.
    """
    if seed:
        np.random.seed(seed)
    checkpoint = DeckCheckpoint() 
    cards_score = [assign_score(combat_page, effect=effect) for combat_page in combat_pages]
    scored_cards = [(cards_score[index], combat_pages[index]) for index in range(len(combat_pages))]
    beam = sample_top_cards(cards_score, combat_pages, B = B, temp = temp)

    checkpoints = [6, 7, 8]

    for current_card in range(1, max_deck_size):
        print(f"We are looking for the {current_card + 1}-th card.")
        new_beam = []
        for score, deck, counter in beam:
            if isinstance(deck, dict): # This is the first pass
                deck = [deck]
                if is_singleton(deck):
                    deck = change_card_limit(deck)
            remaining = [card for _, card in scored_cards if counter[card['Name']] < card['Card Limit']] # allows repeated cards
            for card in remaining:
                new_deck = deepcopy(deck) + [deepcopy(card)]
                if is_singleton(new_deck):
                    new_deck = change_card_limit(new_deck)
                scale = len(new_deck) / 9

                is_valid, reason = check_deck(new_deck, flags=flags, scale=scale)
                if not is_valid:
                    checkpoint.update(new_deck, assign_score(new_deck, effect=effect), reason=reason)
                    continue  # prune this deck early

                new_score = assign_score(new_deck, effect=effect)
                new_beam.append((new_score, new_deck))

        if new_beam:
            new_scores, new_decks = zip(*new_beam)
        else:
            new_scores, new_decks = [], []
        # Sample the decks to avoid a deterministic output
        beam = sample_top_cards(new_scores, new_decks, B=B)

    try:
        _, best_deck, counter = next(beam)
        if debug:
            print(counter)
        return best_deck
    except StopIteration:
        print("No valid decks found. Closest attempt:\n")
        print(checkpoint)
        return None

def has_enough_dices(deck_attributes: Dict[str, Union[float, Counter[str]]]) -> bool:
    """
    Checks if a deck has enough dices per card. Only usable for short battles.
    The values here are not supported by any real data, just my own gut feeling.  
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Returns: True of False
    """
    dices_per_card = deck_attributes['average_dice_per_card']
    weighted_average_dice_per_card = deck_attributes['weighted_average_dice_per_card']
    return dices_per_card >= 2.6 and weighted_average_dice_per_card >= 2.3

def is_attack_focused(deck_attributes: Dict[str, Union[float, Counter[str]]]) -> bool:
    """
    Checks if a deck is attack focused. Only usable for short battles. 
    The values here are not supported by any real data, just my own gut feeling.  
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Returns: True of False
    """
    attack_to_defense_ratio = deck_attributes['attack_to_defense_ratio']
    return attack_to_defense_ratio >= 5

def is_self_sustaining_light_regen(deck_attributes: Dict[str, Union[float, Counter[str]]], scale: float = 1.0) -> bool:
    """
    Based on decks I build in my game. The data can be found in Data/LoRDecks.csv.
    The coefficients were found using a linear fit to the points named "Blunt", "Brace Up" and "UB" as they 
    were the ones with the least light regen in their respective cost category while still being self-sustaining.
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Keyword args: scale: equal to the `len(deck)/9`, scales the light regen as if it were from a full deck.
    Returns: True or False according to a pre-determined formula.
    """
    total_light_regen = deck_attributes['total_light_regen'] / scale 
    avg_cost = deck_attributes['average_cost']
    required = (6.38 * avg_cost - 6.88)
    return total_light_regen >= required

def is_self_sustaining_draw_cards(deck_attributes: Dict[str, Union[float, Counter[str]]], scale: float = 1.0) -> bool:
    """
    Based on decks I build in my game. The data can be found in Data/LoRDecks.csv.
    According to my lackluster data, the mean is 4.88, the median is 5 and the standard deviation is 1.2. 
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Keyword args: scale: equal to the `len(deck)/9`, scales the light regen as if it were from a full deck.
    Returns: True or False.
    """
    cards_drawn = deck_attributes['total_drawn_cards'] / scale
    return cards_drawn >= 4 

def check_deck(deck: List[Dict[str, Union[str, Dict[str, str]]]], flags: Dict[str, bool] = None, scale: float = 1.0) -> Tuple[bool, Optional[str]]:
    """
    Checks if a deck is valid or can sustain itself with respect to some flags. 
    Keyword args: flags: A dictionary containing flags such as...
    Return: True or false depending whether the deck is valid or not.
    """
    prolonged_battle = flags.get('prolonged', False)
    short_battle = not prolonged_battle 
    deck_attributes = count_deck_attribute_statistics(deck) 
    if prolonged_battle: # For long term, the most important fulfilling metrics are light regen and cards drawn
        if not is_self_sustaining_light_regen(deck_attributes, scale=scale):
            return False, f"Not enough light regen — {deck_attributes['total_light_regen']:.2f}"
        if not is_self_sustaining_draw_cards(deck_attributes, scale=scale):
            return False, f"Not enough card draw — {deck_attributes['total_drawn_cards']:.2f}"
        return True, None

    else: # For short-term battles, we want high number of dices per card and high attack-to-defense ratio. 
        if not has_enough_dices(deck_attributes):
            return False, f"Not enough dice per card - {deck_attributes['average_dice_per_card']}"
        if not is_attack_focused(deck_attributes):
            return False, f"Not attack-focused enough - {deck_attributes['attack_to_defense_ratio']}"
        return True, None


def build_deck(may_keywords: Optional[List[str]] = None, combat_pages: Optional[List[Dict[str, Union[str, Dict[str, str]]]]] = None, 
               must_include: Optional[List[str]] = None, flags: Optional[Dict[str, bool]] = None, B: int = 10, temp: float = 1.0,
               effect: str = "Strength", seed: Optional[int] = None, debug: bool = False) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Builds a deck according to a set of keywords.
    Args: may_keywords: A list of keywords that the combat pages may or may not contain. For example, 
    may_include = ["Canard", "Urban Nightmare", "Urban Legend"] implies that the cards may be within any of those three ranks.
    Keyword args: must_include: A list of keywords that the combat pages must contain.
                  flags: a dictionary containing some flags... 
                  B: The beam search parameter. Attempts to use it, if it cannot, use the maximum available according the the length of the 
                  resulting combat pages after filtering.
                  temp: A temperature parameter controlling how randomized the selecting process is.
    Returns: A list of 9 combat pages.
    """
    valid_status_effects = ["burn", "paralysis", "bleed", "fairy", 
                      "protection", "stagger protection", "fragile", 
                      "strength", "feeble", "endurance", "disarm",
                      "haste", "bind", "nullify Power", "immobilized", 
                      "charge", "smoke", "persistence", "erosion"]

    if not isinstance(effect, str):
        raise ValueError(f"{effect} must be a string!")
    effect = effect.lower()

    if effect not in valid_status_effects and effect != "no_effect":
        raise ValueError(f"{effect} is not a valid status effect in LoR. Please refer to https://library-of-ruina.fandom.com/wiki/Status_Effects")

    if not flags: # We assume it is for a prolonged battle
        flags = {'prolonged': True, 'short': False}

    # load all combat pages there exist
    if not combat_pages:
        try:
            combat_pages = load_json('combat_pages/combat_pages.json') 
        except FileNotFoundError:
            print("No json file in 'combat_pages/combat_pages.json' was found. We couldn't build a deck.")
            return None

    if may_keywords: # Only apply the filters if it is not an empty list
        combat_pages = apply_filters(may_keywords, combat_pages, exclusive = False)
    
    if must_include:
        combat_pages = apply_filter(must_keywords, combat_pages)
    
    # if we aren't building for Charge or Smoke, let's not include them in the available cards.
    if effect != "charge": 
        combat_pages = apply_filters(["Charge"], combat_pages, complement=True)
    
    if effect != "smoke":
        combat_pages = apply_filters(["Smoke"], combat_pages, complement=True)

    filtered_length = len(combat_pages)
    if filtered_length < 9: # a deck must have 9 cards
        print(f"Your conditions are too restrictive, we couldn't form a deck. Current length: {filtered_length}")
    
    if filtered_length == 9: 
        if check_deck(combat_pages, flags)[0]:
            return combat_pages
        else:
            print("No good deck could be built with the conditions imposed.")
            return None
    
    B = min(B, filtered_length - 9)
    deck = deck_beam_search(combat_pages, B = B, flags=flags, temp=temp, debug=debug, effect=effect, seed=seed)
    if deck:
        stats = count_deck_attribute_statistics(deck)
        status_effects = stats['status_effects']
        if status_effects.get(effect, 4) < 3: 
            print(f"We found a deck, but it only contains a maximum of {status_effects[effect]} stacks of {effect} per cycle.")
            print("Would you want to try a search again? (y/n)")
            answer = input()
            if answer == "y":
                build_deck(may_keywords=may_keywords, combat_pages=combat_pages, must_include=must_include,
                           flags=flags, B=B, temp=temp, effect=effect, seed=seed)
        return deck
    else:
        print("No good deck could be built with the conditions imposed.")
        return None
     
def test_card_reference_integrity(deck1, deck2):
    """
    Courtesy of GPT 4.0
    """
    for card1 in deck1:
        for card2 in deck2:
            if card1['Name'] == card2['Name']:
                if card1 is card2:
                    print(f"[Shared Reference] Card '{card1['Name']}' is the same object in memory.")
                else:
                    print(f"[Safe Copy] Card '{card1['Name']}' is a separate object.")

if __name__ == '__main__':
    combat_pages = load_json('combat_pages/combat_pages.json') 
    combat_pages = remove_passive_cards(combat_pages)

    # Initialize results
    light_regens: List[float] = []
    cards_drawn: List[float] = []

    # Generate 10 sample decks and extract stats
    for _ in range(10):
        deck = build_deck(B=5, combat_pages=combat_pages, temp=0.8, effect="no_effect", debug=False)
        stats = count_deck_attribute_statistics(deck)
        light_regens.append(stats['total_light_regen'])
        cards_drawn.append(stats['total_drawn_cards'])

    print(f"light regen: {light_regens}")
    print(f"cards drawn: {cards_drawn}")