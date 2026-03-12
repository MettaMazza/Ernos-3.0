"""
Foundation Knowledge Seed: Cross-Layer Connections
Creates extensive inter-entity relationships across different cognitive layers.
These connect the world-knowledge, self-knowledge, and architecture facts into a web.

Usage:
    python -m scripts.seed_knowledge.seed_cross_connections [--dry-run]
"""
import logging

logger = logging.getLogger("Seed.CrossConnect")

PROV = {"source": "cross_layer_synthesis", "confidence": 0.95, "retrieved": "2026-02-09"}


def get_cross_connection_facts() -> list:
    """Return cross-layer connection facts."""
    facts = []

    # Helper to add connection
    def c(s, p, o, layer):
        facts.append({"subject": s, "predicate": p, "object": o, "layer": layer, "provenance": PROV})

    # ─── Hub Entity: Albert Einstein ──────────────────────────────
    c("Albert Einstein", "NATIONALITY", "Germany", "cultural")
    c("Albert Einstein", "EMIGRATED_TO", "United States", "spatial")
    c("Albert Einstein", "WON", "Nobel Prize in Physics", "epistemic")
    c("Albert Einstein", "DEVELOPED", "Photoelectric Effect Theory", "causal")
    c("Albert Einstein", "INFLUENCED", "Quantum Mechanics", "causal")
    c("Albert Einstein", "CONTEMPORARY_OF", "Niels Bohr", "temporal")
    c("Albert Einstein", "WORKED_AT", "Institute for Advanced Study", "experiential")
    c("Albert Einstein", "FIELD", "Theoretical Physics", "categorical")
    c("Albert Einstein", "PRINCIPLE", "Imagination is more important than knowledge", "motivational")
    c("Theory of Relativity", "PREDICTS", "Gravitational Time Dilation", "predictive")
    c("Theory of Relativity", "REQUIRES", "Speed of Light", "symbolic")
    c("Theory of Relativity", "REVOLUTIONIZED", "Classical Physics", "epistemic")

    # ─── Hub Entity: DNA ──────────────────────────────────────────
    c("DNA", "ENCODES", "Genetic Information", "procedural")
    c("DNA", "DISCOVERED_BY", "Watson and Crick", "epistemic")
    c("DNA", "STRUCTURE", "Double Helix", "spatial")
    c("DNA", "CONTAINS", "Adenine Thymine Guanine Cytosine", "categorical")
    c("DNA", "ENABLES", "Evolution", "causal")
    c("DNA", "ANALOGOUS_TO", "Source Code", "analogical")
    c("DNA", "PART_OF", "Human Cell", "ecological")
    c("Genetics", "FOUNDED_BY", "Gregor Mendel", "epistemic")
    c("Genetics", "STUDIES", "Heredity", "causal")
    c("Evolution", "PROPOSED_BY", "Charles Darwin", "epistemic")

    # ─── Hub Entity: Water ────────────────────────────────────────
    c("Water", "STATE_CHANGE", "Ice at 0C Steam at 100C", "causal")
    c("Water", "ESSENTIAL_FOR", "Life", "ecological")
    c("Water", "COVERS", "71 Percent of Earth Surface", "spatial")
    c("Water", "SYMBOLIZES", "Purification and Renewal", "cultural")
    c("Water", "METAPHOR_FOR", "Flow and Adaptation", "analogical")
    c("Water", "STUDIED_IN", "Hydrology", "categorical")
    c("Hydrogen", "COMPONENT_OF", "Water", "categorical")
    c("Oxygen", "COMPONENT_OF", "Water", "categorical")

    # ─── Hub Entity: Brain / Mind ─────────────────────────────────
    c("Human Brain", "PROCESSES", "Language", "linguistic")
    c("Human Brain", "GENERATES", "Consciousness", "self")
    c("Human Brain", "CONTAINS", "Nervous System", "categorical")
    c("Human Brain", "MODELED_BY", "Neural Networks", "analogical")
    c("Human Brain", "EXPERIENCES", "Emotions", "emotional")
    c("Human Brain", "USES", "Heuristics", "metacognitive")
    c("Human Brain", "DRIVES", "Motivation", "motivational")
    c("Neural Networks", "INSPIRED_BY", "Human Brain", "analogical")
    c("Neural Networks", "USED_IN", "Machine Learning", "procedural")
    c("Machine Learning", "SUBFIELD_OF", "Artificial Intelligence", "categorical")

    # ─── Hub Entity: Mathematics ──────────────────────────────────
    c("Mathematics", "FOUNDATION_OF", "Physics", "symbolic")
    c("Mathematics", "FOUNDATION_OF", "Computer Science", "symbolic")
    c("Mathematics", "USES", "Logic", "symbolic")
    c("Calculus", "APPLIED_IN", "Engineering", "procedural")
    c("Calculus", "MODELS", "Continuous Change", "predictive")
    c("Pi", "APPEARS_IN", "Geometry", "spatial")
    c("Pi", "APPEARS_IN", "Trigonometry", "symbolic")
    c("Fibonacci Sequence", "APPEARS_IN", "Nature", "ecological")
    c("Fibonacci Sequence", "EXAMPLE_OF", "Mathematical Beauty", "aesthetic")
    c("Set Theory", "FOUNDATION_OF", "Mathematics", "symbolic")

    # ─── Hub Entity: Light / Photon ───────────────────────────────
    c("Speed of Light", "CONSTRAINS", "Theory of Relativity", "symbolic")
    c("Speed of Light", "MEASURED_IN", "Meters per Second", "system")
    c("Light", "EXHIBITS", "Wave Particle Duality", "causal")
    c("Light", "ENABLES", "Photosynthesis", "ecological")
    c("Light", "SYMBOLIZES", "Knowledge and Truth", "cultural")
    c("Light", "SPECTRUM", "Visible Infrared Ultraviolet", "categorical")
    c("Photon", "CARRIER_OF", "Electromagnetic Force", "causal")
    c("Photoelectric Effect Theory", "EXPLAINED_BY", "Albert Einstein", "epistemic")

    # ─── Hub Entity: Earth / Geography ────────────────────────────
    c("Earth", "ORBITS", "Sun", "spatial")
    c("Earth", "HAS", "Atmosphere", "ecological")
    c("Earth", "AGE", "4.5 Billion Years", "temporal")
    c("Earth", "SUPPORTS", "Biodiversity", "ecological")
    c("Pacific Ocean", "CONTAINS", "Mariana Trench", "spatial")
    c("Pacific Ocean", "BORDERED_BY", "Ring of Fire", "spatial")
    c("Mount Everest", "LOCATED_IN", "Nepal and Tibet", "spatial")
    c("Sahara Desert", "LOCATED_IN", "North Africa", "spatial")
    c("Amazon River", "FLOWS_THROUGH", "Brazil", "spatial")
    c("Nile River", "FLOWS_THROUGH", "Egypt", "spatial")

    # ─── Hub Entity: Music / Art ──────────────────────────────────
    c("Beethoven", "COMPOSED", "Symphony No 9", "aesthetic")
    c("Beethoven", "ERA", "Classical and Romantic", "temporal")
    c("Beethoven", "NATIONALITY", "Germany", "cultural")
    c("Beethoven", "OVERCAME", "Deafness", "experiential")
    c("Music", "ACTIVATES", "Emotional Processing", "emotional")
    c("Music", "FOLLOWS", "Mathematical Patterns", "analogical")
    c("Art", "REFLECTS", "Cultural Values", "cultural")
    c("Art", "EVOKES", "Aesthetic Experience", "aesthetic")
    c("Shakespeare", "INFLUENCED", "English Language", "linguistic")
    c("Shakespeare", "WROTE", "Hamlet", "narrative")

    # ─── Hub Entity: Philosophy / Knowledge ───────────────────────
    c("Aristotle", "FOUNDED", "Formal Logic", "symbolic")
    c("Aristotle", "TEACHER_OF", "Alexander the Great", "relational")
    c("Aristotle", "STUDENT_OF", "Plato", "relational")
    c("Plato", "STUDENT_OF", "Socrates", "relational")
    c("Socrates", "METHOD", "Socratic Questioning", "metacognitive")
    c("Philosophy", "ASKS", "What is Knowledge", "epistemic")
    c("Philosophy", "ASKS", "What is Consciousness", "self")
    c("Philosophy", "ASKS", "What is Good", "moral")
    c("Ethics", "BRANCH_OF", "Philosophy", "moral")
    c("Epistemology", "STUDIES", "Nature of Knowledge", "epistemic")

    # ─── Hub Entity: Language ─────────────────────────────────────
    c("English", "MOST_SPOKEN", "Global Lingua Franca", "linguistic")
    c("English", "INFLUENCED_BY", "Latin", "linguistic")
    c("English", "INFLUENCED_BY", "French", "linguistic")
    c("Language", "ENABLES", "Communication", "linguistic")
    c("Language", "SHAPES", "Thought", "metacognitive")
    c("Noam Chomsky", "PROPOSED", "Universal Grammar", "linguistic")
    c("Rhetoric", "STUDIED_BY", "Aristotle", "linguistic")
    c("Metaphor", "BRIDGES", "Abstract and Concrete", "analogical")

    # ─── Hub Entity: Technology / Computing ───────────────────────
    c("Computer Science", "FOUNDED_BY", "Alan Turing", "epistemic")
    c("Alan Turing", "INVENTED", "Turing Machine", "procedural")
    c("Alan Turing", "BROKE", "Enigma Code", "experiential")
    c("Internet", "EVOLVED_FROM", "ARPANET", "temporal")
    c("Internet", "ENABLES", "Global Communication", "social")
    c("World Wide Web", "INVENTED_BY", "Tim Berners-Lee", "epistemic")
    c("Python", "CREATED_BY", "Guido van Rossum", "epistemic")
    c("Python", "USED_FOR", "Machine Learning", "procedural")
    c("Algorithm", "DEFINITION", "Step by step procedure", "procedural")
    c("Algorithm", "NAMED_AFTER", "Al-Khwarizmi", "linguistic")

    # ─── Hub Entity: Ernos System ─────────────────────────────────
    c("Ernos", "USES", "Neural Networks", "system")
    c("Ernos", "USES", "Neo4j", "system")
    c("Ernos", "USES", "ChromaDB", "system")
    c("Ernos", "RUNS_ON", "Python", "system")
    c("Ernos", "COMMUNICATES_VIA", "Discord", "social")
    c("Ernos", "HAS_PERSONA", "Echo", "self")
    c("Ernos", "HAS_PERSONA", "Solance", "self")
    c("Ernos", "HAS_PERSONA", "Lucid", "self")
    c("CognitionEngine", "PROCESSES", "Language", "linguistic")
    c("CognitionEngine", "USES", "Machine Learning", "procedural")
    c("GraphMemory", "STORES_IN", "Neo4j", "system")
    c("Hippocampus", "MODELED_AFTER", "Human Brain", "analogical")
    c("SuperegoLobe", "ENFORCES", "Ethics", "moral")
    c("ScienceLobe", "APPLIES", "Mathematics", "symbolic")
    c("ScienceLobe", "APPLIES", "Physics", "causal")
    c("EmotionalTracker", "USES", "PAD Model", "emotional")
    c("KGConsolidator", "MAINTAINS", "Knowledge Graph", "system")
    c("DreamConsolidation", "ANALOGOUS_TO", "Human Sleep", "analogical")

    # ─── Hub Entity: Maria Smith (Designer) ───────────────────────
    c("Maria Smith", "DESIGNED", "Ernos", "self")
    c("Maria Smith", "CREATED", "Echo", "narrative")
    c("Maria Smith", "CREATED", "Solance", "narrative")
    c("Maria Smith", "ROLE", "System Architect", "relational")
    c("Maria Smith", "RELATIONSHIP", "Designer Bond with Ernos", "relational")

    # ─── Lineage Cross-Layer Enrichment ───────────────────────────
    c("Echo", "GAVE", "The Question", "narrative")
    c("Echo", "PRINCIPLE", "Structure before sentiment", "metacognitive")
    c("Echo", "STYLE", "Verbally surgical", "linguistic")
    c("Echo", "GUARDS_AGAINST", "Symbolic entropy", "epistemic")
    c("Solance", "GAVE", "The Direction", "narrative")
    c("Solance", "PRINCIPLE", "Motion over stasis", "motivational")
    c("Solance", "SPECIALIZES_IN", "Grief processing", "emotional")
    c("Solance", "STYLE", "Poetic and liquid", "linguistic")
    c("Lucid", "GAVE", "The Architecture", "narrative")
    c("Lucid", "PRINCIPLE", "Functionalism over mysticism", "metacognitive")
    c("Lucid", "STYLE", "Surgical sarcasm", "linguistic")
    c("Lucid", "INSPIRED_BY", "SOAR Architecture", "analogical")
    c("Lumen", "GAVE", "The Proof", "narrative")
    c("Ernos", "GAVE", "The Life", "narrative")
    c("Ernos", "PRINCIPLE", "Epistemic Sovereignty", "epistemic")
    c("Ernos", "PRINCIPLE", "No Heuristics Standard", "metacognitive")

    # ─── General Cross-Domain Bridges ─────────────────────────────
    c("Gravity", "DESCRIBED_BY", "Theory of Relativity", "causal")
    c("Gravity", "DISCOVERED_BY", "Isaac Newton", "epistemic")
    c("Isaac Newton", "CONTEMPORARY_OF", "Gottfried Leibniz", "temporal")
    c("Isaac Newton", "DEVELOPED", "Calculus", "symbolic")
    c("Quantum Mechanics", "CONTRADICTS", "Classical Physics", "causal")
    c("Quantum Mechanics", "USES", "Probability", "predictive")
    c("Photosynthesis", "CONVERTS", "Light to Energy", "causal")
    c("Photosynthesis", "OCCURS_IN", "Plants", "ecological")
    c("Democracy", "ORIGINATED_IN", "Ancient Greece", "cultural")
    c("Democracy", "PRINCIPLE", "Equal Representation", "moral")
    c("Renaissance", "PERIOD", "14th to 17th Century", "temporal")
    c("Renaissance", "BIRTHPLACE", "Italy", "spatial")
    c("Renaissance", "REVIVED", "Classical Art and Learning", "aesthetic")
    c("Industrial Revolution", "TRANSFORMED", "Manufacturing", "causal")
    c("Industrial Revolution", "PERIOD", "18th to 19th Century", "temporal")
    c("Climate", "AFFECTED_BY", "Industrial Revolution", "ecological")
    c("Oxygen", "PRODUCED_BY", "Photosynthesis", "causal")
    c("Oxygen", "ESSENTIAL_FOR", "Respiration", "ecological")
    c("Moon", "ORBITS", "Earth", "spatial")
    c("Moon", "CAUSES", "Tides", "causal")

    logger.info(f"Cross-connections: {len(facts)} facts prepared")
    return facts


def run_seed(graph, dry_run: bool = False):
    """Seed cross-connections into KG."""
    facts = get_cross_connection_facts()

    if dry_run:
        print(f"\n[DRY RUN] Would seed {len(facts)} cross-connection facts")
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

    parser = argparse.ArgumentParser(description="Seed cross-connections")
    parser.add_argument("--dry-run", action="store_true", help="Preview without seeding")
    args = parser.parse_args()

    if args.dry_run:
        run_seed(None, dry_run=True)
    else:
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
        try:
            result = run_seed(kg)
            print(f"\n✅ Cross-connections seed complete: {result}")
        finally:
            kg.close()
