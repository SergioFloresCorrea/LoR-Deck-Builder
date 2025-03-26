import json
import re
from collections import Counter
from combat_page_styler import load_json
from typing import List, Union, Dict, Optional, Tuple, Any, Callable

def update_counter(counter: Counter, obj: Any, value: int = 1) -> Counter:
    """
    Updates a counter with a given object
    """
    if obj in counter:
        counter[obj] += value
    else:
        counter[obj] = value

def remove_passive_cards(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]]) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Removes cards that can only be obtained via passive abilities.
    Also removed "Brawl" as its effects are real-time dependent.
    """
    filtered_combat_pages = []
    for combat_page in combat_pages:
        rank = combat_page['Rank']
        name = combat_page['Name']
        if rank != "Passive Ability" and name != "Brawl":
            filtered_combat_pages.append(combat_page)

    return filtered_combat_pages

def apply_filter(keywords: List[str], exclusive: bool = True, complement: bool = False) -> Callable[[Dict[str, Union[str, Dict[str, str]]]], bool]:
    """
    Determines whether any of the keywords are in the combat page's description or within its dices.
    Args: keywords: A list of keywords.
          combat_page: A single dictionary describing a combat page.
          exclusive: Whether the combat page must contain all the keywords or at least one of them
          complement: Whether to get the complement of the filter.
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
            if not complement:
                return len(matched) == len(keywords)
            else:
                return len(matched) != len(keywords)
        else:
            if not complement:
                return bool(matched)
            else:
                return not bool(matched)

    return apply_keywords_filter

def apply_filters(keywords: List[str], combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], 
                  exclusive: bool = True, complement: bool = False) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Filters the combat pages with respect to the selected keywords. 
    Args: keywords: A list of keywords.
          combat_pages: A list of combat pages.
          exclusive: Whether the combat page must contain all the keywords or at least one of them
          complement: Whether to get the complement of the filter.
    Returns: Filtered combat pages.
    """
    keywords_filter = apply_filter(keywords, exclusive = exclusive, complement=complement)
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

def total_status_effects(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]]) -> Counter[str]:
    """
    Generates the total amount of status effects inflicted by the combat pages. Returns a dictionary.
    """
    status_effects = ["burn", "paralysis", "bleed", "fairy", 
                      "protection", "stagger protection", "fragile", 
                      "strength", "feeble", "endurance", "disarm",
                      "haste", "bind", "nullify Power", "immobilized", 
                      "charge", "smoke", "persistence", "erosion"]
    counter = Counter(dict.fromkeys(status_effects, 0))

    pattern_a = r"inflict\s+(\d+)\s+(\w+)" # Burn, Bleed, Paralysis
    pattern_b = r"gain\s+(\d+)\s+(\w+)" # Protection, Stagger Protection, Strength, Endurance, Haste
    pattern_c = r"give\s+(\d+)\s+(\w+)"
    pattern_d = r"use\s+(\d+)\s+(\w+)" # Smoke
    pattern_e = r"spend\s+(\d+)\s+(\w+)" # Charge
    patterns = [pattern_a, pattern_b, pattern_c, pattern_d, pattern_e]

    all_text_parts = []
    for card in combat_pages:
        all_text_parts.append(card.get("Effect", ""))
        all_text_parts.extend(card.get("Dices", {}).values())

    all_text = "\n".join(all_text_parts)
    all_text = all_text.lower()

    # Run regex
    for index, pattern in enumerate(patterns):
        for value, effect in re.findall(pattern, all_text):
            if index >= 3: # These correspond to using or spending
                value = "-" + value
            if effect in status_effects:
                update_counter(counter, effect, value=int(value))
            elif effect.endswith("next"): # This is bad parsing on my end
                effect = effect[:-len("next")]
                if effect in status_effects:
                    update_counter(counter, effect, value=int(value))
            elif effect.endswith("to"): # This is also bad parsing on my end
                effect = effect[:-len("to")]
                if effect in status_effects:
                    update_counter(counter, effect, value=int(value))
            elif effect.endswith("this"): # And then is heard no more
                effect = effect[:-len("this")]
                if effect in status_effects:
                    update_counter(counter, effect, value=int(value))
    
    return counter
    
def generate_empty_statisics_dict() -> Dict[str, Union[int, Counter[str]]]:
    """
    Generates an empty dictionary for the function `count_deck_attribute_statistics`.
    """
    keys = ['average_cost', 'total_light_regen', 'total_drawn_cards', 'average_dice_value', 
            'weighted_average_dice_value', 'average_dice_per_card', 'weighted_average_dice_per_card', 
            'attack_to_defense_ratio', 'total_dice_counts', 'status_effects']
    statistics = dict.fromkeys(keys, 0)
    dice_types = ["slash", "blunt", "pierce", "evade", "block", 
                  "slashcounter", "bluntcounter", "piercecounter", "evadecounter", 
                  "blockcounter"]
    statistics['total_dice_types'] = Counter(dict.fromkeys(dice_types, 0))
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
        if "single-use" in text: # single use cards are exhausted, so we consider them as if they are discarded. 
            total_discard += 1

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

def get_mean_dice_values(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> float:
    """
    Gets the mean value of all dices, doesn't distinguish between attack or defense dice. 
    Args: combat_page: A dictionary describing a combat page.
    Returns: A integer with the mean value.
    """
    pattern = r"\b(\d+)~(\d+)\b"
    num_dices = get_number_of_dice(combat_page)
    if num_dices == 0: # If it has no dice, we skip it
        return 0 
    dices = combat_page['Dices']
    mean_values = [None] * num_dices
    for index, dice_description in enumerate(dices.values()):
        matched = re.search(pattern, dice_description)
        if matched:
            min_value = int(matched.group(1))
            max_value = int(matched.group(2))
            mean_values[index] = (min_value + max_value) / 2
        else:
            raise ValueError(f"One dice does not contain in {combat_page['Name']} does not contain a valid range (e.g., 3~6). Just what have gone wrong?")
    return sum(mean_values) / num_dices

def get_dice_types(combat_page: Dict[str, Union[str, Dict[str, str]]]) -> Counter[str]:
    """
    Counts the number of slash, blunt, pierce, block and evade dice there are, as well as their counter- counterparts. 
    Args: combat_page: A dictionary describing a combat page.
    Returns: A dictionary containing this counts.
    """
    dice_types = ["slash", "blunt", "pierce", "evade", "block", 
                  "slashcounter", "bluntcounter", "piercecounter", "evadecounter", 
                  "blockcounter"]
    attributes = dict.fromkeys(dice_types, 0)
    dices = combat_page['Dices']
    for dice_description in dices.values():
        dice_type = dice_description.split(":")[0] # We made the description so that it is of the form "dice_type: XYZ"
        if dice_type not in dice_types: # still, not bad to check
            raise ValueError(f"{dice_type} is not a valid dice type, what have we done...")
        attributes[dice_type] += 1
    
    return Counter(attributes)

def get_attack_defense_ratio(attributes: Counter[str]) -> float:
    """
    Calculates the attack to defense dices ratio.
    Args: attributes: a Counter object containing the dice types.
    Returns: a float containing the ratio
    """
    attack_types = ["slash", "blunt", "pierce", "slashcounter", "bluntcounter", "piercecounter"]
    defense_types = ["evade", "block", "evadecounter", "blockcounter"]
    attack_dices = 0
    defense_dices = 0
    for dice_type in attributes.keys():
        if dice_type in attack_types:
            attack_dices += attributes[dice_type]
        elif dice_type in defense_types:
            defense_dices += attributes[dice_type]
        else:
            raise ValueError(f"{dice_type} is not a valid dice type!")
    
    if defense_dices == 0:
        return float("inf")
    else:
        return round(attack_dices / defense_dices, 2)

def get_deck_max_cost(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]]) -> int:
    """
    Gets the max cost of all the combat pages in a deck. Avoids skewing in the weighting process.
    Args: combat_pages: A list of combat pages.
    Returns: The maximum cost.
    """
    max_cost = float("-inf")
    for combat_page in combat_pages:
        cost = int(combat_page['Cost'])
        if cost > max_cost:
            max_cost = cost
    
    return max_cost

def count_deck_attribute_statistics(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]], deploy = False) -> Dict[str, Union[float, Counter[str]]]:
    """
    Gets statistics such as: 
    - average cost
    - number of slash, blunt, pierce, block, evade dice. As well as attack + defence dice.
    - total light regen for all 9 cards. This is optimist as it assumes you always win the clash.
    - total draw of all 9 cards. This is optimist as it assumes you always win the clash.
    - average dice value. Does not consider buffs or card effects. 
    - weighted average dice value (the weight is inverse to the cost. If the card is more costly, you would use it less)
    - total number of dices.
    - average dices per card. 
    - Attack to Defense ratio. 
    Sadly, this implementation does not take into account real-time effects such as "Burning Flash" or "Clone". 
    Args: combat_pages: A list of combat pages, should consist of 9 combat pages, but it is not enforced. 
    Returns: A dictionary containing all of the above. 
    """
    number_of_cards = len(combat_pages) 
    max_cost = get_deck_max_cost(combat_pages)
    statistics = generate_empty_statisics_dict()
    single_point_stab_count = 0 # this will be added to the draw count as per its effects. May not fully represent what it does, but not too shabby.
    if deploy:
        assert number_of_cards == 9, "The deck-builder is not selecting only 9 cards, this is troubling..."
    
    for combat_page in combat_pages:
        if combat_page['Name'] == 'Single-Point Stab':
            single_point_stab_count += 1
        card_cost = int(combat_page['Cost'])
        weight = (max_cost - card_cost + 1) / (max_cost + 1) # Cards go from cost 0 to max cost, avoid skewing. 
        mean_dice_values = get_mean_dice_values(combat_page)
        num_dices = get_number_of_dice(combat_page)
        statistics['average_cost'] += card_cost / number_of_cards
        statistics['total_dice_counts'] += num_dices
        statistics['average_dice_per_card'] += num_dices / number_of_cards
        statistics['weighted_average_dice_per_card'] += weight * num_dices / number_of_cards
        statistics['total_light_regen'] += total_light_regen(combat_page) 
        statistics['total_drawn_cards'] += total_drawn_cards(combat_page)
        statistics['average_dice_value'] += mean_dice_values / number_of_cards
        statistics['weighted_average_dice_value'] += weight * mean_dice_values / number_of_cards
        statistics['total_dice_types'] += get_dice_types(combat_page)

    statistics['attack_to_defense_ratio'] += get_attack_defense_ratio(statistics['total_dice_types'])
    statistics['status_effects'] = total_status_effects(combat_pages)
    statistics['total_drawn_cards'] += single_point_stab_count
    return statistics

if __name__ == '__main__':
    keywords = ["Bleed", "Urban Nightmare"]
    combat_pages = load_json('combat_pages/combat_pages.json') 
    filtered_combat_pages = apply_filters(keywords, combat_pages)
    counter = total_status_effects(filtered_combat_pages)
    print(f"combat_pages: {filtered_combat_pages}")
    print(f"counter: {counter}")
