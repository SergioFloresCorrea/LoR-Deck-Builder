import json
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

def count_deck_attribute_statistics(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]]) -> Dict[str, int]:
    """
    Gets statistics such as: 
    - average cost
    - number of slash, blunt, pierce, block, evade dice. As well as attack + defence dice.
    - total light regen for all 9 cards.
    - total draw of all 9 cards.
    - average dice value. Does not consider buffs or card effects. 
    - weighted average dice value (the weight is the cost)
    - average dices per card. 
    - Attack to Defense ratio. 
    Args: combat_pages: A list of combat pages, should consist of 9 combat pages, but it is not enforced. 
    Returns: A dictionary containing all of the above. 
    """
    pass

if __name__ == '__main__':
    keywords = ['Discard', 'Urban Legend']
    combat_pages = load_json('combat_pages/combat_pages.json') 
    filtered_combat_pages = apply_filters(keywords, combat_pages)
    num_dices = get_number_of_dice(filtered_combat_pages[-1])
    print(filtered_combat_pages[-1], num_dices)