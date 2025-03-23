import json
import re
from combat_page_styler import load_json
from typing import List, Union, Dict, Optional, Tuple, Any, Callable


def apply_filter(keywords: List[str], exclusive: bool = True) -> Callable[[Dict[str, Union[str, Dict[str, str]]]], bool]:
    """
    Determines whether any of the keywords are in the combat page's description or within its dices.
    Args: keywords: A list of keywords.
          combat_page: A single dictionary describing a combat page.
          exclusive: Whether the combat page must contain all the keywords or at least one of them
    Returns: A boolean value showing if any of the keywords is within the combat page.
    """
    if isinstance(keywords, str):
        keywords = [keywords]  # If a single keyword was parsed not as a list, then this shall do the trick
    elif not isinstance(keywords, list):
        raise ValueError("keywords must be a list of strings.")

    def apply_keywords_filter(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> bool:
        def search(value: Union[str, Dict[str, str]], matched_keywords: set) -> set:
            if isinstance(value, str):
                for keyword in keywords:
                    if keyword.lower() in value.lower():
                        matched_keywords.add(keyword)
            elif isinstance(value, dict):
                for v in value.values():
                    matched_keywords = search(v, matched_keywords)
            return matched_keywords

        matched = search(combat_page, set())
        if exclusive:
            return len(matched) == len(keywords)
        else:
            return bool(matched)

    return apply_keywords_filter

def apply_filters(keywords: List[str], combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], exclusive: bool = True) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Filters the combat pages with respect to the selected keywords. 
    Args: keywords: A list of keywords.
          combat_pages: A list of combat pages.
          exclusive: Whether the combat page must contain all the keywords or at least one of them
    Returns: Filtered combat pages.
    """
    keywords_filter = apply_filter(keywords)

    filtered_combat_pages = filter(keywords_filter, combat_pages)
    return list(filtered_combat_pages)

def get_number_of_dice(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> int:
    """
    Gets the number of dices, important for the deck builder.
    Args: A dictionary containing the combat page.
    Returns: An integer containing the number of dices.
    """
    dices = combat_page['Dices']
    return len(dices)

def generate_empty_statisics_dict() -> Dict[str, Union[int, Dict[str, int]]]:
    """
    Generates an empty dictionary for the function `count_deck_attribute_statistics`.
    """
    keys = ['average_cost', 'total_light_regen', 'total_drawn_cards', 'average_dice_value', 
            'weighted_average_dice_value', 'average_dice_per_card', 'attack_to_defense_ratio', 'total_dice_counts']
    statistics = dict.fromkeys(keys, 0)
    dice_types = ["slash", "blunt", "pierce", "evade", "block", 
                  "slashcounter", "bluntcounter", "piercecounter", "evadecounter", 
                  "blockcounter"]
    statistics[keys] = dict.fromkeys(dice_types, 0)
    return statistics 

def total_light_regen(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> int:
    """
    Gets the total light regen of a combat page. If it doesn't have, then it returns 0.
    """
    total_light = 0
    pattern = r"restore\s+(\d+)\s+light"
    effect_text = combat_page["Effect"]
    
    if effect_text:
        matched = re.search(pattern, effect_text.lower())
        if matched:
            total_light += int(matched.group(1))

    for dice_description in combat_page['Dices'].values():
        matched = re.search(pattern, dice_description.lower())
        if matched:
            total_light += int(matched.group(1))

    return total_light


def total_drawn_cards(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> int:
    """
    Gets the total drawn cards of a combat page. If it doesn't have, then it returns 0.
    Takes into account discard effects the card may also have.
    Ammunition are not considered cards as, well, you wouldn't really use them, right?
    Args: combat_page: A dictionary containing the combat page. 
    Returns: an integer containing the total cards drawn.
    """
    total_draw = 0
    total_discard = 0

    draw_pattern = r"draws?\s+(a|\d+)\s+page"
    discard_pattern = r"discard\s+(a|a random|\d+)\s+page[s]?"

    effect_text = combat_page["Effect"]
    if effect_text:
        text = effect_text.lower()

        draw_match = re.search(draw_pattern, text)
        if draw_match:
            val = draw_match.group(1)
            total_draw += 1 if val == "a" else int(val)

        discard_match = re.search(discard_pattern, text)
        if discard_match:
            val = discard_match.group(1)
            total_discard += 1 if val in ("a", "a random") else int(val)

    for desc in combat_page["Dices"].values():
        text = desc.lower()

        draw_match = re.search(draw_pattern, text)
        if draw_match:
            val = draw_match.group(1)
            total_draw += 1 if val == "a" else int(val)

        discard_match = re.search(discard_pattern, text)
        if discard_match:
            val = discard_match.group(1)
            total_discard += 1 if val in ("a", "a random") else int(val)

    return total_draw - total_discard


def count_deck_attribute_statistics(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], deploy = False) -> Dict[str, Union[int, Dict[str, int]]]:
    """
    Gets statistics such as: 
    - average cost
    - number of slash, blunt, pierce, block, evade dice. As well as attack + defence dice.
    - total light regen for all 9 cards. This is optimist as it assumes you always win the clash.
    - total draw of all 9 cards. This is optimist as it assumes you always win the clash.
    - average dice value. Does not consider buffs or card effects. 
    - weighted average dice value (the weight is the cost)
    - average dices per card. 
    - Attack to Defense ratio. 
    Sadly, this implementation does not take into account real-time effects such as "Burning Flash" or "Clone". 
    Args: combat_pages: A list of combat pages, should consist of 9 combat pages, but it is not enforced. 
    Returns: A dictionary containing all of the above. 
    """
    number_of_cards = len(combat_pages) 
    statistics = generate_empty_statisics_dict()
    single_point_stab_count = 0 # this will be added to the draw count as per its effects. May not fully represent what it does, but not too shabby.
    if deploy:
        assert number_of_cards == 9, "The deck-builder is not selecting only 9 cards, this is troubling..."
    
    for combat_page in combat_pages:
        if combat_page['Name'] == 'Single-Point Stab':
            single_point_stab_count += 1
        statistics['average_cost'] += int(combat_page['Cost'])
        statistics['average_dice_per_card'] += get_number_of_dice(combat_page)
    
    statistics['total_drawn_cards'] += single_point_stab_count
    return statistics

if __name__ == '__main__':
    keywords = ['Discard', 'Urban Legend']
    combat_pages = load_json('combat_pages/combat_pages.json') 
    filtered_combat_pages = apply_filters(keywords, combat_pages)
    num_dices = get_number_of_dice(filtered_combat_pages[-1])
