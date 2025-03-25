import re
import os
import json
from bs4 import BeautifulSoup
from typing import List, Union, Dict, Optional, Tuple, Any

def combat_page_dict_checker(data: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Recursively checks a combat page or list of pages to ensure all fields are non-empty.
    'Effect' is allowed to be None or empty.
    Returns: (True, None) if all fields are OK, (False, key) for the first bad field.
    """
    if isinstance(data, list):
        for item in data:
            ok, key = combat_page_dict_checker(item)
            if not ok:
                return False, key

    elif isinstance(data, dict):
        for key, value in data.items():
            if key in ["Effect", "Obtained"]:
                continue  # Effect is allowed to be None or empty. Some cards like Pú Láo have no origin.

            if isinstance(value, dict):
                ok, nested_key = combat_page_dict_checker(value)
                if not ok:
                    return False, nested_key

            elif isinstance(value, str) and value.strip().lower() in ["", "null"]:
                return False, key

            elif value is None:
                return False, key

    return True, None

def get_contents() -> BeautifulSoup:
    """
    Reads and saves the contents of the List of Combat Pages.html file
    saved. 
    returns: soup: BeautifulSoup object.
    """
    # read the file
    with open('List of Combat Pages.html', 'r') as html:
        index = html.read()
        soup = BeautifulSoup(index, 'html.parser')
    
    return soup

def get_html_pages(soup: BeautifulSoup) -> List[BeautifulSoup]:
    """
    Gets the html view, in a list, of the pages and the rank (e.g Canard, Urban Legend)
    in order they appear in the wiki.
    Args: soup: the html contents.
    returns: A list containing all the data, e.g, effects, light cost, dice values.
    """
    html_pages = list()
    for page in soup.find_all('tr'):
        html_pages.append(page)
    return html_pages

def check_new_rank(ranks: List[str], html_page: BeautifulSoup) -> bool:
    """
    Checks if we have reached a new rank.
    Args: ranks: A list of ranks (e.g Canard, Urban Myth).
          html_page: a beatifulsoup object of a single combat page.
    returns: True if it denotes a new rank, if not, false.
    """
    th = html_page.find('th')
    try:
        all_text = th.get_text(strip=True)
    except AttributeError: 
        return False
    return any(rank in all_text for rank in ranks)

def get_attack_range(table_data: BeautifulSoup) -> str:
    """
    Gets the attack range of a card, e.g, melee, ranged, mass.
    Args: Third <td> tag of each <tr>.
    Returns: A string containing the range of the combat page.
    """
    return table_data.get('data-sort-value')

def get_dice_type(part: str, debug=False) -> str:
    """
    Gets the dice type from the img name (Not the best way).
    Args: A beautifulsoup object. It should contain an image with the corresponding dice name
          debug: A boolean flag that helps with debugging, in other words, prints.
    Returns: the dice type.
    """
    dice_types =  ["slashcounter", "bluntcounter", "piercecounter", "evadecounter", 
                  "blockcounter", "slash", "blunt", "pierce", "evade", "block"]
    image_names = list()
    image_objects = part.find_all('img') # some lines may have more than one img
    for image in image_objects:
        image_name = image.get('alt')
        if debug:
            print(f"part: {part}")
            print(f"image name: {image_name}")
        for dice_type in dice_types:
            if dice_type in image_name.lower():
                return dice_type

    return None

def get_effects(table_data: BeautifulSoup, debug=False) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Gets the effects of the page (On use, On play) and the dice-effects, as well as 
    the dice values.
    Args: The fourth <td> tag of each <tr>.
          debug: A bool that helps with debugging (aka, prints).
    Returns: The card effect (if there is) and a dictionary containing all dices.
    """
    parts = re.split(r"(?=<br/>)", str(table_data)) # separate into linebreaks
    card_effect = "" # most cards have no card effect
    dices = dict()
    for index, part in enumerate(parts):
        part = BeautifulSoup(part, 'html.parser') # we need to return to a beautifulsoup object
        dice_type = get_dice_type(part, debug=debug)
        if dice_type is None: # it has no dice; hence, it is the card effect. The card effect may have more than one line. 
            card_effect += part.get_text(separator=" ", strip=True) + "\n "
        else:
            card_effect = card_effect.rstrip()
            label = "Dice " + str(index) 
            min_max_effect = part.get_text(strip=True)
            dices[label] = f"{dice_type}: {min_max_effect}"
    
    return card_effect, dices

def get_origin(table_data: BeautifulSoup) -> str:
    """
    Gets the origin of the combat page.
    Args: The fifth <td> tag of each <tr>
    Returns: a string containing the books that drop this combat page
    """
    return table_data.get_text(strip=True)

def export_list_to_txt(file: str, lst: List[any]) -> bool:
    """
    Exports a list to a given filename.
    Returns True on success, False on failure.
    """
    try:
        if os.path.isfile(file):
            print("A file already exists, do you wish to overwrite it? (y/n)")
            x = input()
            if x != 'y':
                return False
        
        # Create the folder containing the file to avoid issues
        dir_path = os.path.dirname(file)
        os.makedirs(dir_path, exist_ok=True)
        with open(file, 'w') as f:
            for line in lst:
                f.write(f"{line}\n\n")
        return True

    except (OSError, IOError) as e:
        print(f"[Error] Failed to write to file: {file}\n{e}")
        return False

def export_dict_to_json(file: str, dct: Dict[any, any]) -> bool:
    """
    Exports a dictionary to a JSON file.
    Returns True on success, False on failure.
    """
    try:
        if os.path.isfile(file):
            print("A file already exists, do you wish to overwrite it? (y/n)")
            x = input()
            if x != 'y':
                return False
        # Create the folder containing the file to avoid issues
        dir_path = os.path.dirname(file)
        os.makedirs(dir_path, exist_ok=True)
        with open(file, 'w') as f:
            json.dump(dct, f, indent=4)
        return True

    except (OSError, IOError, TypeError) as e:
        print(f"[Error] Failed to export JSON to file: {file}\n{e}")
        return False

def organize_pages(html_pages: List[BeautifulSoup], 
                   log = True, debug = False) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Organizes the html pages in a dictionary having the following keys:
    {'Name', 'Rank', 'Cost', 'Range', 'Effect', 'Dices', 'Obtained'}
    Args: html_pages: A list containing the combat pages in html format.
          log: Helps with logging.
          debug: Helps with debugging (printing statements).
    Returns: a dictionary with the above key-value pairs.
    """
    ranks = ["Canard", "Urban Myth", "Urban Legend", "Urban Plague", "Urban Nightmare", 
             "Star of the City", "Impuritas Civitatis", "Passive Ability"]
    combat_pages = list()
    not_dice_found_combat_pages = list()
    count = -1 # We are on the first rank
    for page_number, html_page in enumerate(html_pages):
        combat_page = dict()
        if debug:
            card_rank = "dummy" # We need to add a dummy card rank as we are testing
            print(f"htmml page = {html_page}")

        if check_new_rank(ranks, html_page):
            count += 1
            card_rank = ranks[count]
        
        if not html_page.img: # every combat page has an img attached 
            continue 
            
        if html_page.get('style') != '':
            continue

        combat_page['Rank'] = card_rank
        for index, table_data in enumerate(html_page.find_all('td')):
            if index == 0: # first element always contains the name
                name = table_data.get_text(separator=" ", strip=True)
                combat_page['Name'] = name
                if debug:
                    print(f"first td = {table_data}")
                    print(f"name = {name}")
            elif index == 1: # second element always contains the cost
                cost = table_data.get_text(strip=True)
                combat_page['Cost'] = cost
            elif index == 2: # third element always contains the range
                attack_range = get_attack_range(table_data)
                combat_page['Range'] = attack_range
            elif index == 3: # fourth element always contains the dices
                card_effect, dices = get_effects(table_data, debug=debug)
                combat_page['Effect'] = card_effect
                combat_page['Dices'] = dices
            else: # last index corresponds to the origins
                origins = get_origin(table_data)
                combat_page['Obtained'] = origins

        combat_pages.append(combat_page)

    if not debug: # no need to export on testing
        success, value = combat_page_dict_checker(combat_pages)
        if success:
            status = export_dict_to_json('combat_pages/combat_pages.json', combat_pages)
            if not status:
                print("JSON export failed.")
        else:
            raise ValueError(f"The combat pages dictionary contains errors in, at least, {value}.") 
    return combat_pages 
        

if __name__ == '__main__':
    soup = get_contents()
    pages = get_html_pages(soup)
    result = organize_pages(pages, log = False, debug = False)
    #result = organize_pages([pages[3], pages[11]], log = False, debug = True)