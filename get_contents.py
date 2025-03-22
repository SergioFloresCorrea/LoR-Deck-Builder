import re
from bs4 import BeautifulSoup
from typing import List, Union, Dict, Optional, Tuple

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
        all_text = list(th.stripped_strings)
    except AttributeError: 
        return False
    result = [text for text in all_text if text not in ('Collapse',)]
    return any(rank in result[0] for rank in ranks)

def get_attack_range(table_data: BeautifulSoup) -> str:
    """
    Gets the attack range of a card, e.g, melee, ranged, mass.
    Args: Third <td> tag of each <tr>.
    Returns: A string containing the range of the combat page.
    """
    return table_data.get('data-sort-value')

def get_dice_type(part: str) -> str:
    """
    Gets the dice type from the img name (Not the best way).
    """
    dice_types = ["slash", "blunt", "pierce", "evade", "block", 
                  "slashcounter", "bluntcounter", "piercecounter", "evadecounter", 
                  "blockcounter"]
    image_name = part.find('img').get('alt')
    for dice_type in dice_types:
        if dice_type in image_name.lower():
            return dice_type

    raise ValueError('No dice type was found!')

def get_effects(table_data: BeautifulSoup) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Gets the effects of the page (On use, On play) and the dice-effects, as well as 
    the dice values.
    Args: The fourth <td> tag of each <tr>.
    Returns: The card effect (if there is) and a dictionary containing all dices.
    """
    parts = re.split(r"(?=<img alt=)", str(table_data))
    dices = dict()
    for index, part in enumerate(parts):
        part = BeautifulSoup(part, 'html.parser') # we need to return to a beautifulsoup object
        if index == 0: # first index always contains on-play or on-use effects
            card_effect = part.get_text(separator=" ", strip=True)
        else:
            label = "Dice " + str(index) 
            dice_type = get_dice_type(part)
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

def organize_pages(html_pages: List[BeautifulSoup]) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Organizes the html pages in a dictionary having the following keys:
    {'Name', 'Rank', 'Cost', 'Range', 'Effect', 'Dices', 'Obtained'}
    Args: html_pages: A list containing the combat pages in html format.
    Returns: a dictionary with the above key-value pairs.
    """
    ranks = ["Canard", "Urban Myth", "Urban Legend", "Urban Plague", "Urban Nightmare", 
             "Stars of the City", "Impuritas Civitatis"]
    combat_pages = list()
    count = -1 # We are on the first rank
    for html_page in html_pages:
        combat_page = dict()

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
                name = table_data.find('span').get('title')
                combat_page['Name'] = name
            elif index == 1: # second element always contains the cost
                cost = table_data.get_text(strip=True)
                combat_page['Cost'] = cost
            elif index == 2: # third element always contains the range
                attack_range = get_attack_range(table_data)
                combat_page['Range'] = attack_range
            elif index == 3: # fourth element always contains the dices
                try:
                    card_effect, dices = get_effects(table_data)
                except ValueError:
                    print(f"part: {table_data}")
                    continue
                combat_page['Effect'] = card_effect
                combat_page['Dices'] = dices
            else: # last index corresponds to the origins
                origins = get_origin(table_data)
                combat_page['Obtained'] = origins

        combat_pages.append(combat_page)
    return combat_pages 
        

if __name__ == '__main__':
    soup = get_contents()
    pages = get_html_pages(soup)
    result = organize_pages(pages)