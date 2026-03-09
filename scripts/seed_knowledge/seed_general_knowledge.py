"""
Foundation Knowledge Seed: General Knowledge
Curated expansions for physical constants, periodic table, geography, and definitions.

No external API required — purely curated data for reliable, offline seeding.

Usage:
    python -m scripts.seed_knowledge.seed_general_knowledge [--dry-run]
"""
import logging

logger = logging.getLogger("Seed.General")

PROVENANCE_SCIENCE = {"source": "scientific_databases", "confidence": 0.98, "retrieved": "2026-02-09"}
PROVENANCE_GEO = {"source": "geonames", "confidence": 0.95, "retrieved": "2026-02-09"}
PROVENANCE_ENCYCLOPEDIA = {"source": "encyclopedia", "confidence": 0.95, "retrieved": "2026-02-09"}


def get_general_knowledge_facts() -> list:
    """Return curated general knowledge facts."""
    facts = []

    # ── Periodic Table Completion (elements 1-36) ──
    elements = [
        ("Helium", "He", "2"), ("Lithium", "Li", "3"), ("Beryllium", "Be", "4"),
        ("Boron", "B", "5"), ("Carbon", "C", "6"), ("Nitrogen", "N", "7"),
        ("Fluorine", "F", "9"), ("Neon", "Ne", "10"), ("Sodium", "Na", "11"),
        ("Magnesium", "Mg", "12"), ("Aluminum", "Al", "13"), ("Silicon", "Si", "14"),
        ("Phosphorus", "P", "15"), ("Sulfur", "S", "16"), ("Chlorine", "Cl", "17"),
        ("Argon", "Ar", "18"), ("Potassium", "K", "19"), ("Calcium", "Ca", "20"),
        ("Scandium", "Sc", "21"), ("Titanium", "Ti", "22"), ("Vanadium", "V", "23"),
        ("Chromium", "Cr", "24"), ("Manganese", "Mn", "25"), ("Cobalt", "Co", "27"),
        ("Nickel", "Ni", "28"), ("Zinc", "Zn", "30"), ("Gallium", "Ga", "31"),
        ("Germanium", "Ge", "32"), ("Arsenic", "As", "33"), ("Selenium", "Se", "34"),
        ("Bromine", "Br", "35"), ("Krypton", "Kr", "36"),
    ]
    for name, symbol, num in elements:
        facts.append({"subject": name, "predicate": "SYMBOL", "object": symbol,
                       "layer": "categorical", "provenance": PROVENANCE_SCIENCE})
        facts.append({"subject": name, "predicate": "ATOMIC_NUMBER", "object": num,
                       "layer": "categorical", "provenance": PROVENANCE_SCIENCE})

    # ── Additional Physical Constants ──
    constants = [
        ("Planck Length", "VALUE", "1.616255e-35 meters"),
        ("Planck Time", "VALUE", "5.391247e-44 seconds"),
        ("Electron Mass", "VALUE", "9.1093837015e-31 kg"),
        ("Proton Mass", "VALUE", "1.67262192369e-27 kg"),
        ("Fine Structure Constant", "VALUE", "approximately 1/137"),
        ("Magnetic Constant", "VALUE", "1.25663706212e-6 N/A2"),
        ("Electric Constant", "VALUE", "8.8541878128e-12 F/m"),
        ("Rydberg Constant", "VALUE", "10973731.568160 per meter"),
        ("Wien Displacement Law", "VALUE", "2.897771955e-3 m K"),
        ("Faraday Constant", "VALUE", "96485.33212 C/mol"),
    ]
    for subj, pred, obj in constants:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "predictive", "provenance": PROVENANCE_SCIENCE})

    # ── World Geography Expansion ──
    geography = [
        ("Nile River", "LENGTH", "6650 km longest river in Africa"),
        ("Amazon River", "DRAINS_INTO", "Atlantic Ocean"),
        ("Mount Kilimanjaro", "HEIGHT", "5895 meters"),
        ("Mount Fuji", "HEIGHT", "3776 meters"),
        ("Sahara Desert", "AREA", "Largest hot desert 9.2 million km2"),
        ("Pacific Ocean", "AREA", "Largest ocean 165.25 million km2"),
        ("Dead Sea", "NOTABLE", "Lowest point on land surface"),
        ("Lake Baikal", "NOTABLE", "Deepest lake in the world"),
        ("Mariana Trench", "DEPTH", "Approximately 11034 meters"),
        ("Ring of Fire", "LOCATION", "Pacific Ocean basin"),
        ("Strait of Gibraltar", "CONNECTS", "Mediterranean Sea and Atlantic Ocean"),
        ("Panama Canal", "CONNECTS", "Atlantic Ocean and Pacific Ocean"),
        ("Suez Canal", "CONNECTS", "Mediterranean Sea and Red Sea"),
        ("Antarctica", "STATUS", "No permanent population"),
        ("Greenland", "STATUS", "Largest island in the world"),
    ]
    for subj, pred, obj in geography:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "spatial", "provenance": PROVENANCE_GEO})

    # ── Human Body Systems ──
    body = [
        ("Circulatory System", "MAIN_ORGAN", "Heart"),
        ("Respiratory System", "MAIN_ORGAN", "Lungs"),
        ("Digestive System", "MAIN_ORGAN", "Stomach and Intestines"),
        ("Nervous System", "MAIN_ORGAN", "Brain"),
        ("Skeletal System", "COMPONENT_COUNT", "206 Bones in Adult Human"),
        ("Muscular System", "COMPONENT_COUNT", "Over 600 Muscles"),
        ("Human Heart", "AVERAGE_RATE", "72 Beats per Minute"),
        ("Human Brain", "NEURON_COUNT", "Approximately 86 Billion"),
        ("Human Blood", "TYPES", "A B AB O"),
        ("Human DNA", "BASE_PAIRS", "Approximately 3 Billion"),
    ]
    for subj, pred, obj in body:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "categorical", "provenance": PROVENANCE_ENCYCLOPEDIA})

    # ── Solar System ──
    solar = [
        ("Mercury", "ORBITAL_PERIOD", "88 Earth Days"),
        ("Venus", "ATMOSPHERE", "96 Percent Carbon Dioxide"),
        ("Mars", "MOONS", "Phobos and Deimos"),
        ("Jupiter", "CLASSIFICATION", "Gas Giant"),
        ("Jupiter", "MOONS_COUNT", "95 Known Moons"),
        ("Saturn", "NOTABLE_FEATURE", "Ring System"),
        ("Uranus", "AXIAL_TILT", "97.77 Degrees"),
        ("Neptune", "WIND_SPEED", "Fastest in Solar System up to 2100 km/h"),
        ("Pluto", "RECLASSIFIED", "Dwarf Planet 2006"),
        ("Sun", "SURFACE_TEMPERATURE", "Approximately 5500 Celsius"),
    ]
    for subj, pred, obj in solar:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "spatial", "provenance": PROVENANCE_SCIENCE})

    # ── Mathematical Foundations ──
    math_facts = [
        ("Pi", "APPROXIMATE_VALUE", "3.14159265358979"),
        ("Euler Number", "APPROXIMATE_VALUE", "2.71828182845905"),
        ("Pythagorean Theorem", "FORMULA", "a2 + b2 = c2"),
        ("Fibonacci Sequence", "DEFINITION", "Each number is sum of two preceding numbers"),
        ("Prime Numbers", "DEFINITION", "Numbers divisible only by 1 and themselves"),
        ("Imaginary Unit", "DEFINITION", "Square root of negative one"),
        ("Infinity", "PROPERTY", "Not a number but a concept of unboundedness"),
        ("Zero", "HISTORICAL_ORIGIN", "Independently discovered in India and Mesoamerica"),
        ("Calculus", "FOUNDERS", "Newton and Leibniz independently"),
        ("Set Theory", "FOUNDER", "Georg Cantor"),
    ]
    for subj, pred, obj in math_facts:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "symbolic", "provenance": PROVENANCE_SCIENCE})

    logger.info(f"General knowledge: {len(facts)} facts prepared")
    return facts


# ─── Runner ────────────────────────────────────────────────────

def run_seed(graph, dry_run: bool = False):
    """Seed general knowledge into KG."""
    facts = get_general_knowledge_facts()
    
    if dry_run:
        print(f"\n[DRY RUN] Would seed {len(facts)} general knowledge facts")
        for f in facts[:10]:
            print(f"  {f['subject']} -[{f['predicate']}]-> {f['object']} ({f['layer']})")
        return {"fetched": len(facts), "seeded": 0}
    
    result = graph.bulk_seed(facts)
    return {**result, "fetched": len(facts)}


if __name__ == "__main__":
    import sys
    import argparse
    
    sys.path.insert(0, ".")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Seed general knowledge")
    parser.add_argument("--dry-run", action="store_true", help="Preview without seeding")
    args = parser.parse_args()
    
    if args.dry_run:
        run_seed(None, dry_run=True)
    else:
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
        try:
            result = run_seed(kg)
            print(f"\n✅ General knowledge seed complete: {result}")
        finally:
            kg.close()
