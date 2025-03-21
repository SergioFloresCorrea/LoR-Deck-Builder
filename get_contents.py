from bs4 import BeautifulSoup
from typing import List, Union, Dict

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

def get_effects(table_data: None) -> None:
    """
    Gets the effects of the page (On use, On play) and the dice-effects, as well as 
    the dice values.
    Args: The fourth <td> tag of each <tr>.
    Returns: No idea.
    """
    
    pass

def organize_pages(html_pages: List[BeautifulSoup]) -> Dict[str, Union[str, Dict[str, str]]]:
    """
    Organizes the html pages in a dictionary having the following keys:
    {'Name', 'Rank', 'Cost', 'Range', 'Effect', 'Dices'}
    Args: html_pages: A list containing the combat pages in html format.
    Returns: a dictionary with the above key-value pairs.
    """
    ranks = ["Canard", "Urban Myth", "Urban Legend", "Urban Plague", "Urban Nightmare", 
             "Stars of the City", "Impuritas Civitatis"]
    count = -1 # We are on the first rank
    for html_page in html_pages:
        if not html_page.img: # every combat page has an img attached 
            continue 

        if check_new_rank(ranks, html_page):
            count += 1
            card_rank = ranks[count]

        for index, table_data in enumerate(html_page.find_all('td')):
            if index == 0: # first element always contains the name
                name = table_data.span.contents[0]
            elif index == 1: # second element always contains the cost
                cost = table_data.contents[0]
            elif index == 2: # third element always contains the range
                attack_range = get_attack_range(table_data)
            else:
                print(f"index: {index}, table_data: {table_data}")
        

if __name__ == '__main__':
    soup = get_contents()
    pages = get_html_pages(soup)
    result = organize_pages(pages[:3])