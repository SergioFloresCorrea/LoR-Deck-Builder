from typing import List, Dict, Union

class DeckCheckpoint:
    def __init__(self):
        self.best_deck = []
        self.best_score = float('-inf')
        self.reason_failed = None

    def update(self, deck: List[Dict[str, Union[str, Dict[str, str]]]], score: float, reason: str = None):
        if score > self.best_score:
            self.best_score = score
            self.best_deck = deck
            self.reason_failed = reason

    def __str__(self):
        summary = f"Best partial deck (score: {self.best_score:.2f}):\n"
        summary += "\n".join(card['Name'] for card in self.best_deck)
        if self.reason_failed:
            summary += f"\nReason for last failure: {self.reason_failed}"
        return summary