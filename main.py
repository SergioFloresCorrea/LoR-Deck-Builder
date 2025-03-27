import argparse
from combat_page_styler import load_json
from deck_builder import build_deck, assign_score
from get_contents import export_dict_to_json
from combat_page_getter import count_deck_attribute_statistics

def main():
    parser = argparse.ArgumentParser(description="Library of Ruina Deck Builder")

    parser.add_argument('--effect', type=str, default='strength', help="Focus on this status effect (e.g., burn, bleed, smoke, or 'no_effects')")
    parser.add_argument('--temperature', type=float, default=0.8, help="Sampling randomness (0 is deterministic, 1 is random)")
    parser.add_argument('--beam', type=int, default=5, help="Beam width for beam search")
    parser.add_argument('--seed', type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument('--output', type=str, default='decks/generated_deck.json', help="Path to export the generated deck")
    parser.add_argument('--debug', action='store_true', help="Print debug statistics and scoring breakdown")
    parser.add_argument('--prolonged', action='store_true', help="Optimize for long battles (light and draw sustainability)")
    parser.add_argument('--exclude_low_rank', action='store_true', help="Exclude lower-tier cards (Canard, Urban Myth, etc.)")
    parser.add_argument('--exclude_high_rank', action='store_true', help="Exclude lower-tier cards (Star of the City, Impuritas Civitatis)")

    args = parser.parse_args()

    # Load and optionally filter combat pages
    combat_pages = load_json('combat_pages/combat_pages.json')

    exclude = None
    if args.exclude_low_rank:
        exclude = ["Canard", "Urban Myth", "Urban Legend", "Urban Plague"]
    
    if args.exclude_high_rank:
        exclude = ["Star of the City", "Impuritas Civitatis"]

    flags = {'prolonged': args.prolonged, 'short': not args.prolonged}
    deck = build_deck(not_include=exclude, B=args.beam, combat_pages=combat_pages,
                      temp=args.temperature, effect=args.effect, debug=args.debug,
                      seed=args.seed, flags=flags)

    if deck:
        print("\nDeck generated successfully!\n")
        print(f"Exporting deck to {args.output} ...")
        export_dict_to_json(args.output, deck)
        stats = count_deck_attribute_statistics(deck)
        score = assign_score(deck, effect=args.effect, debug=args.debug)
        print("\nDeck Statistics:")
        for k, v in stats.items():
            print(f"{k}: {v}")
        print(f"\nFinal Score: {score:.3f}")
    else:
        print("\nDeck generation failed. Try adjusting the constraints or temperature.\n")

if __name__ == '__main__':
    main()
