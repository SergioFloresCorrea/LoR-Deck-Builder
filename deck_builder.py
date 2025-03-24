from combat_page_getter import count_deck_attribute_statistics, apply_filters
from combat_page_styler import load_json

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

def is_self_sustaining_light_regen(deck_attributes: Dict[str, Union[float, Counter[str]]]) -> bool:
    """
    Based on decks I build in my game. The data can be found in Data/LoRDecks.csv.
    The coefficients were found using a linear fit to the points named "Blunt", "Brace Up" and "UB" as they 
    were the ones with the least light regen in their respective cost category while still being self-sustaining.
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Returns: True or False according to a pre-determined formula.
    """
    total_light_regen = deck_attributes['total_light_regen']
    avg_cost = deck_attributes['average_cost']
    return total_light_regen >= 6.38 * avg_cost - 6.88

def is_self_sustaining_draw_cards(deck_attributes: Dict[str, Union[float, Counter[str]]]) -> bool:
    """
    Based on decks I build in my game. The data can be found in Data/LoRDecks.csv.
    According to my lackluster data, the mean is 4.88, the median is 5 and the standard deviation is 1.2. 
    Args: deck_attributes: Obtained from `count_deck_attribute_statistics`
    Returns: True or False.
    """
    cards_drawn = deck_attributes['total_drawn_cards']
    return cards_drawn >= 4

def check_deck(flags: Dict[str, bool] = None, deck: List[Dict[str, Union[str, Dict[str, str]]]]) -> bool:
    """
    Checks if a deck is valid or can sustain itself with respect to some flags. 
    Keyword args: flags: A dictionary containing flags such as...
    Return: True or false depending whether the deck is valid or not.
    """
    prolonged_battle = flags.get('prolonged', False)
    short_battle = not prolonged_battle 
    deck_attributes = count_deck_attribute_statistics(deck)
    if prolonged_battle: # For long term, the most important aspects are fulfilling metrics are card regen and light drawn
        if is_self_sustaining_light_regen(deck_attributes) and is_self_sustaining_draw_cards(deck_attributes):
            return True
        else:
            return False
    else: # For short-term battles, we want high number of dices per card and high attack-to-defense ratio. 
        if has_enough_dices(deck_attributes) and is_attack_focused(deck_attributes):
            return True
        else:
            return False


def build_deck(may_keywords: List[str], must_include: List[str] = None, flags: Dict[str, bool] = None) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Builds a deck according to a set of keywords.
    Args: may_keywords: A list of keywords that the combat pages may or may not contain. For example, 
    may_include = ["Canard", "Urban Nightmare", "Urban Legend"] implies that the cards may be within any of those three ranks.
    Keyword args: must_include: A list of keywords that the combat pages must contain.
                  flags: a dictionary containing some flags... 
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

    if must_keywords: # Only apply the filters if it is not an empty list
        combat_pages = apply_filters(must_keywords, combat_pages, exclusive = False)
    
    if must_include:
        combat_pages = apply_filter(must_keywords, combat_pages)
    
    if len(combat_pages < 9): # a deck must have 9 cards
        deck_length = len(combat_pages)
        print(f"Your conditions are too restrictive, we couldn't form a deck. Current length: {deck_length}")
    
    if len(combat_pages == 9): 
        if check_deck(flags, combat_pages):
            return combat_pages
        else:
            print("No good deck could be built with the conditions imposed.")
            return None
     


if __name__ == '__main__':
    combat_pages = load_json('combat_pages/combat_pages.json') 