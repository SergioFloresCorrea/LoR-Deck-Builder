import math
import numpy as np
from scipy.special import softmax
from copy import deepcopy
from typing import List, Union, Dict, Optional, Tuple, Any, Callable, Iterator
from combat_page_getter import count_deck_attribute_statistics, apply_filters
from combat_page_styler import load_json
from get_contents import export_dict_to_json
from data_checkpoint import DeckCheckpoint
from collections import Counter

def normalize_values(min_val: float, max_val: float) -> Callable[[float], float]:
    """
    Defines a normalizer for any value to a range between 0 to 1. 
    Args: min_val: Minimum value expected of the magnitude to normalize.
          max_val: Maximum value expected of the magnitude to normalize.
    Returns: A Callable object that will normalize the values.
    """
    def normalizer(x: float):
        k = 0.99 * ( 1 / (max_val - min_val) + 1)
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


def assign_score(combat_pages: Union[Dict[str, Union[str, Dict[str, str]]], List[Dict[str, Union[str, Dict[str, str]]]]]) -> float:
    """
    Assigns a single number as a score to a list(or single) of combat pages with respect to its attributes.
    We want to maximize the avg dice value and minimize the dice spreadness.  
    I am not sure how to merge the weighted avg dice value and the avg dice value, so the implementation is lazy. 
    """
    if isinstance(combat_pages, dict):
        combat_pages = [combat_pages]
    elif not isinstance(combat_pages, list):
        raise ValueError("A score can only be assigned to a list of combat pages.")

    statistics = count_deck_attribute_statistics(combat_pages)
    light_regen = statistics['total_light_regen']
    light_regen_normalizer = normalize_values(0, 8)
    cards_drawn = statistics['total_drawn_cards']
    cards_drawn_normalizer = normalize_values(0, 6)
    average_cost = statistics['average_cost']
    average_cost_normalizer = normalize_values(0, 3)
    dice_skewness = calculate_normalized_entropy(statistics['total_dice_types'])
    avg_dice_value = statistics['average_dice_value']
    weighted_avg_dice_value = statistics['weighted_average_dice_value']
    dice_value_normalizer = normalize_values(2, 10)
    
    fulfilling_metrics = light_regen_normalizer(light_regen) + cards_drawn_normalizer(cards_drawn) - average_cost_normalizer(average_cost)
    optimizing_metric = dice_value_normalizer(0.4 * avg_dice_value + 0.6 * weighted_avg_dice_value)
    return dice_skewness + fulfilling_metrics 

def sample_top_cards(cards_score: List[float], combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], B: int = 4) -> Iterator[Tuple[float, List[Dict]]]:
    """
    Samples a list of combat pages using softmax probability.
    """
    n_combat_pages = len(combat_pages)
    indices = np.arange(0, n_combat_pages)
    indices_sampled = np.random.choice(indices, p=softmax(cards_score), size=B, replace=False)
    
    selected_scores = [cards_score[index] for index in indices_sampled]
    selected_combat_pages = [combat_pages[index] for index in indices_sampled]
    return zip(selected_scores, selected_combat_pages)

def deck_beam_search(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], B: int = 4, flags: Dict[str, bool] = None,
                     max_deck_size: int = 9, seed: int = 42) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Performs beam search algorithm on a list of combat pages and returns a deck consisting of 9 cards.
    Keyword args: B: Beam search parameter.
    """
    if seed:
        np.random.seed(seed)
    checkpoint = DeckCheckpoint() 
    cards_score = [assign_score(combat_page) for combat_page in combat_pages]
    scored_cards = [(cards_score[index], combat_pages[index]) for index in range(len(combat_pages))]
    beam = sample_top_cards(cards_score, combat_pages, B = B)

    checkpoints = [6, 7, 8]
    counter = Counter()
    for current_card in range(1, max_deck_size):
        print(f"We are looking for the {current_card + 1}-th card.")
        new_beam = []
        for score, deck in beam:
            if isinstance(deck, dict):
                deck = [deck]
            remaining = [card for _, card in scored_cards if card not in deck]
            for card in remaining:
                new_deck = deck + [card]
                scale = len(new_deck) / 9

                is_valid, reason = check_deck(new_deck, flags=flags, scale=scale)
                if not is_valid:
                    checkpoint.update(new_deck, assign_score(new_deck), reason=reason)
                    continue  # prune this deck early

                new_score = assign_score(new_deck)
                new_beam.append((new_score, new_deck))

        if new_beam:
            new_scores, new_decks = zip(*new_beam)
        else:
            new_scores, new_decks = [], []
        # Sample the decks to avoid a deterministic output
        beam = sample_top_cards(new_scores, new_decks, B=B)

    try:
        best_score, best_deck = next(beam)
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


def build_deck(may_keywords: List[str], must_include: List[str] = None, flags: Dict[str, bool] = None, B = 10) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Builds a deck according to a set of keywords.
    Args: may_keywords: A list of keywords that the combat pages may or may not contain. For example, 
    may_include = ["Canard", "Urban Nightmare", "Urban Legend"] implies that the cards may be within any of those three ranks.
    Keyword args: must_include: A list of keywords that the combat pages must contain.
                  flags: a dictionary containing some flags... 
                  B: The beam search parameter. Attempts to use it, if it cannot, use the maximum available according the the length of the 
                  resulting combat pages after filtering.
    Returns: A list of 9 combat pages.
    """
    if not flags: # We assume it is for a prolonged battle
        flags = {'prolonged': True, 'short': False}

    # load all combat pages there exist
    try:
        combat_pages = load_json('combat_pages/combat_pages.json') 
    except FileNotFoundError:
        print("No json file in 'combat_pages/combat_pages.json' was found. We couldn't build a deck.")
        return None

    if may_keywords: # Only apply the filters if it is not an empty list
        combat_pages = apply_filters(may_keywords, combat_pages, exclusive = False)
    
    if must_include:
        combat_pages = apply_filter(must_keywords, combat_pages)
    
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
    deck = deck_beam_search(combat_pages, B = B, flags=flags)
    if deck:
        return deck
    else:
        print("No good deck could be built with the conditions imposed.")
        return None
     


if __name__ == '__main__':
    combat_pages = load_json('combat_pages/combat_pages.json') 
    deck = build_deck(may_keywords = ["Canard", "Urban Myth", "Urban Legend", "Urban Plague", "Urban Nightmare", 
             "Stars of the City"], B = 15)
    export_dict_to_json('decks/first_built_deck.json', deck)
    print(deck)