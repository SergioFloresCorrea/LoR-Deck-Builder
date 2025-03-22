import json
import re
import os
from typing import List, Union, Dict, Optional, Tuple, Any
from get_contents import export_dict_to_json, combat_page_dict_checker

def load_json(path: str) -> Dict[any, any]:
    """
    Loads a json file from a path.
    Args: path: Path-like string containing the path to the json file.
    Returns: A dictionary containing the json file.
    """
    if not os.path.isfile(path): # Check if the doesn't path exists
        raise ValueError("What are you trying to load?")
    
    with open(path, 'r') as file:
        data = json.load(file)
    
    return data

def normalize_spacing(text: str) -> str:
    """
    Adds spacing between digit and letter (and viceversa), and lowercase + uppercase.
    Args: text: the text to normalize the spacing.
    Returns: The string with the added spacing.
    """
    # Add space between digit and letter (1Haste → 1 Haste)
    text = re.sub(r'(?<=\d)(?=[A-Za-z])', ' ', text)
    
    # Add space between letter and digit (Gain1 → Gain 1)
    text = re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', text)

    # Add space between lowercase and uppercase (nextScene → next Scene)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)

    return text

def beautify_dice_effects(combat_pages: List[Dict[str, Union[str, Dict[str, str]]]]) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    The dice effects' text are initially a mess, this function is going to make them human-readable.
    Args: A list of combat pages.
    Returns: A list of combat pages with the dice effects nicely done.
    """

    for combat_page in combat_pages:
        dices = combat_page['Dices']
        for key, value in dices.items():
            dices[key] = normalize_spacing(value) # here the text is getting nicely done
    
    # Now that everything was rewritten, we need to know, was it correctly done?
    success, value = combat_page_dict_checker(combat_pages)
    if success:
        status = export_dict_to_json('combat_pages/combat_pages.json', combat_pages)
        if not status:
            print("JSON export failed.")
    else:
        raise ValueError(f"The combat pages dictionary contains errors in, at least, {value}.")

    return combat_pages

if __name__ == '__main__':
    combat_pages = load_json('combat_pages/combat_pages.json') 
    combat_pages = beautify_dice_effects(combat_pages)
