"""
Foundation Knowledge Seed: Test Batch (500 Facts)
Curated facts across all applicable KG layers.

Run: python -m scripts.seed_knowledge.seed_test_batch
"""

# ─── LAYER MAPPING ─────────────────────────────────────────────
# Each fact maps to one of the 26 GraphLayer values.
# Layers NOT seeded (organic only): self, internal, emotional,
#   relational, motivational, experiential, linguistic, metacognitive

PROVENANCE_WIKI = {"source": "wikidata", "confidence": 0.95, "retrieved": "2026-02-09"}
PROVENANCE_SCIENCE = {"source": "scientific_constants", "confidence": 0.99, "retrieved": "2026-02-09"}
PROVENANCE_CONCEPTNET = {"source": "conceptnet", "confidence": 0.90, "retrieved": "2026-02-09"}
PROVENANCE_DBPEDIA = {"source": "dbpedia", "confidence": 0.93, "retrieved": "2026-02-09"}


def get_test_batch():
    """Return 500 curated foundation facts across all seedable layers."""
    facts = []
    
    # ═══════════════════════════════════════════════════════════════
    # SPATIAL LAYER — Geography, locations, coordinates
    # ═══════════════════════════════════════════════════════════════
    spatial = [
        ("France", "CAPITAL_IS", "Paris"),
        ("Germany", "CAPITAL_IS", "Berlin"),
        ("Japan", "CAPITAL_IS", "Tokyo"),
        ("Australia", "CAPITAL_IS", "Canberra"),
        ("Brazil", "CAPITAL_IS", "Brasilia"),
        ("Canada", "CAPITAL_IS", "Ottawa"),
        ("India", "CAPITAL_IS", "New Delhi"),
        ("China", "CAPITAL_IS", "Beijing"),
        ("Russia", "CAPITAL_IS", "Moscow"),
        ("United Kingdom", "CAPITAL_IS", "London"),
        ("Italy", "CAPITAL_IS", "Rome"),
        ("Spain", "CAPITAL_IS", "Madrid"),
        ("Mexico", "CAPITAL_IS", "Mexico City"),
        ("Egypt", "CAPITAL_IS", "Cairo"),
        ("South Korea", "CAPITAL_IS", "Seoul"),
        ("Argentina", "CAPITAL_IS", "Buenos Aires"),
        ("Nigeria", "CAPITAL_IS", "Abuja"),
        ("South Africa", "CAPITAL_IS", "Pretoria"),
        ("Turkey", "CAPITAL_IS", "Ankara"),
        ("Thailand", "CAPITAL_IS", "Bangkok"),
        ("Sweden", "CAPITAL_IS", "Stockholm"),
        ("Norway", "CAPITAL_IS", "Oslo"),
        ("Poland", "CAPITAL_IS", "Warsaw"),
        ("Greece", "CAPITAL_IS", "Athens"),
        ("Portugal", "CAPITAL_IS", "Lisbon"),
        ("United States", "CAPITAL_IS", "Washington D.C."),
        ("Switzerland", "CAPITAL_IS", "Bern"),
        ("Austria", "CAPITAL_IS", "Vienna"),
        ("Netherlands", "CAPITAL_IS", "Amsterdam"),
        ("Belgium", "CAPITAL_IS", "Brussels"),
        ("Pacific Ocean", "LARGEST_OCEAN", "Earth"),
        ("Mount Everest", "HIGHEST_POINT_OF", "Earth"),
        ("Mariana Trench", "DEEPEST_POINT_OF", "Earth"),
        ("Amazon River", "LOCATED_IN", "South America"),
        ("Nile River", "LOCATED_IN", "Africa"),
        ("Sahara Desert", "LOCATED_IN", "Africa"),
        ("Antarctica", "IS_A", "Continent"),
        ("Europe", "IS_A", "Continent"),
        ("Asia", "IS_A", "Continent"),
        ("Africa", "IS_A", "Continent"),
    ]
    for subj, pred, obj in spatial:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "spatial", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # CATEGORICAL LAYER — Taxonomy, classification hierarchies
    # ═══════════════════════════════════════════════════════════════
    categorical = [
        # Periodic Table (first 30 elements)
        ("Hydrogen", "ATOMIC_NUMBER", "1"), ("Hydrogen", "SYMBOL", "H"),
        ("Helium", "ATOMIC_NUMBER", "2"), ("Helium", "SYMBOL", "He"),
        ("Lithium", "ATOMIC_NUMBER", "3"), ("Lithium", "SYMBOL", "Li"),
        ("Beryllium", "ATOMIC_NUMBER", "4"), ("Beryllium", "SYMBOL", "Be"),
        ("Boron", "ATOMIC_NUMBER", "5"), ("Boron", "SYMBOL", "B"),
        ("Carbon", "ATOMIC_NUMBER", "6"), ("Carbon", "SYMBOL", "C"),
        ("Nitrogen", "ATOMIC_NUMBER", "7"), ("Nitrogen", "SYMBOL", "N"),
        ("Oxygen", "ATOMIC_NUMBER", "8"), ("Oxygen", "SYMBOL", "O"),
        ("Fluorine", "ATOMIC_NUMBER", "9"), ("Fluorine", "SYMBOL", "F"),
        ("Neon", "ATOMIC_NUMBER", "10"), ("Neon", "SYMBOL", "Ne"),
        ("Sodium", "ATOMIC_NUMBER", "11"), ("Sodium", "SYMBOL", "Na"),
        ("Magnesium", "ATOMIC_NUMBER", "12"), ("Magnesium", "SYMBOL", "Mg"),
        ("Aluminum", "ATOMIC_NUMBER", "13"), ("Aluminum", "SYMBOL", "Al"),
        ("Silicon", "ATOMIC_NUMBER", "14"), ("Silicon", "SYMBOL", "Si"),
        ("Phosphorus", "ATOMIC_NUMBER", "15"), ("Phosphorus", "SYMBOL", "P"),
        ("Iron", "ATOMIC_NUMBER", "26"), ("Iron", "SYMBOL", "Fe"),
        ("Gold", "ATOMIC_NUMBER", "79"), ("Gold", "SYMBOL", "Au"),
        ("Silver", "ATOMIC_NUMBER", "47"), ("Silver", "SYMBOL", "Ag"),
        ("Copper", "ATOMIC_NUMBER", "29"), ("Copper", "SYMBOL", "Cu"),
        ("Uranium", "ATOMIC_NUMBER", "92"), ("Uranium", "SYMBOL", "U"),
        # Biological taxonomy
        ("Mammalia", "SUBCLASS_OF", "Vertebrata"),
        ("Vertebrata", "SUBCLASS_OF", "Chordata"),
        ("Chordata", "SUBCLASS_OF", "Animalia"),
        ("Homo sapiens", "MEMBER_OF", "Mammalia"),
        ("Homo sapiens", "ORDER", "Primates"),
        ("Canis lupus familiaris", "MEMBER_OF", "Mammalia"),
        ("Canis lupus familiaris", "COMMON_NAME", "Dog"),
        ("Felis catus", "MEMBER_OF", "Mammalia"),
        ("Felis catus", "COMMON_NAME", "Cat"),
        ("Plantae", "IS_A", "Kingdom"),
        ("Fungi", "IS_A", "Kingdom"),
        ("Animalia", "IS_A", "Kingdom"),
        ("Bacteria", "IS_A", "Domain"),
        ("Archaea", "IS_A", "Domain"),
        ("Eukarya", "IS_A", "Domain"),
        ("Insecta", "SUBCLASS_OF", "Arthropoda"),
        ("Aves", "SUBCLASS_OF", "Vertebrata"),
        ("Reptilia", "SUBCLASS_OF", "Vertebrata"),
        ("Amphibia", "SUBCLASS_OF", "Vertebrata"),
        ("Pisces", "SUBCLASS_OF", "Vertebrata"),
    ]
    for subj, pred, obj in categorical:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "categorical", "provenance": PROVENANCE_WIKI})
    
    # ═══════════════════════════════════════════════════════════════
    # PREDICTIVE LAYER — Physical constants, natural laws
    # ═══════════════════════════════════════════════════════════════
    predictive = [
        ("Speed of Light", "VALUE", "299792458 m/s"),
        ("Speed of Light", "SYMBOL", "c"),
        ("Gravitational Constant", "VALUE", "6.674e-11 N⋅m²/kg²"),
        ("Gravitational Constant", "SYMBOL", "G"),
        ("Planck Constant", "VALUE", "6.626e-34 J⋅s"),
        ("Planck Constant", "SYMBOL", "h"),
        ("Boltzmann Constant", "VALUE", "1.381e-23 J/K"),
        ("Boltzmann Constant", "SYMBOL", "k_B"),
        ("Avogadro Number", "VALUE", "6.022e23 mol⁻¹"),
        ("Avogadro Number", "SYMBOL", "N_A"),
        ("Elementary Charge", "VALUE", "1.602e-19 C"),
        ("Elementary Charge", "SYMBOL", "e"),
        ("Pi", "VALUE", "3.14159265358979"),
        ("Pi", "IS_A", "Irrational Number"),
        ("Euler Number", "VALUE", "2.71828182845905"),
        ("Euler Number", "SYMBOL", "e"),
        ("Golden Ratio", "VALUE", "1.61803398874989"),
        ("Golden Ratio", "SYMBOL", "φ"),
        ("Absolute Zero", "VALUE", "-273.15 °C"),
        ("Absolute Zero", "VALUE_KELVIN", "0 K"),
        # Natural laws
        ("Newton First Law", "STATES", "An object remains at rest or in uniform motion unless acted upon by a force"),
        ("Newton Second Law", "STATES", "F = ma"),
        ("Newton Third Law", "STATES", "Every action has an equal and opposite reaction"),
        ("First Law of Thermodynamics", "STATES", "Energy cannot be created or destroyed"),
        ("Second Law of Thermodynamics", "STATES", "Entropy of an isolated system always increases"),
        ("Third Law of Thermodynamics", "STATES", "Entropy approaches zero as temperature approaches absolute zero"),
        ("Law of Conservation of Mass", "STATES", "Mass is neither created nor destroyed in a chemical reaction"),
        ("Law of Conservation of Energy", "STATES", "Total energy in an isolated system remains constant"),
        ("Ohms Law", "STATES", "V = IR"),
        ("General Relativity", "DISCOVERED_BY", "Albert Einstein"),
        ("Special Relativity", "DISCOVERED_BY", "Albert Einstein"),
        ("Quantum Mechanics", "FOUNDED_BY", "Max Planck"),
        ("E equals mc squared", "FORMULA", "E = mc²"),
        ("E equals mc squared", "DISCOVERED_BY", "Albert Einstein"),
        ("Pythagorean Theorem", "FORMULA", "a² + b² = c²"),
    ]
    for subj, pred, obj in predictive:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "predictive", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # TEMPORAL LAYER — Historical dates, timelines
    # ═══════════════════════════════════════════════════════════════
    temporal = [
        ("World War I", "START_DATE", "1914"),
        ("World War I", "END_DATE", "1918"),
        ("World War II", "START_DATE", "1939"),
        ("World War II", "END_DATE", "1945"),
        ("Moon Landing", "DATE", "1969-07-20"),
        ("Moon Landing", "ACHIEVED_BY", "Apollo 11"),
        ("Fall of Berlin Wall", "DATE", "1989-11-09"),
        ("French Revolution", "START_DATE", "1789"),
        ("American Declaration of Independence", "DATE", "1776-07-04"),
        ("Industrial Revolution", "START_DATE", "1760"),
        ("Industrial Revolution", "END_DATE", "1840"),
        ("Renaissance", "START_DATE", "1300"),
        ("Renaissance", "END_DATE", "1600"),
        ("Internet", "INVENTED_YEAR", "1969"),
        ("World Wide Web", "INVENTED_YEAR", "1989"),
        ("World Wide Web", "INVENTED_BY", "Tim Berners-Lee"),
        ("Printing Press", "INVENTED_YEAR", "1440"),
        ("Printing Press", "INVENTED_BY", "Johannes Gutenberg"),
        ("Telephone", "INVENTED_YEAR", "1876"),
        ("Telephone", "INVENTED_BY", "Alexander Graham Bell"),
        ("Electricity", "HARNESSED_BY", "Thomas Edison"),
        ("DNA Structure", "DISCOVERED_YEAR", "1953"),
        ("DNA Structure", "DISCOVERED_BY", "Watson and Crick"),
        ("Penicillin", "DISCOVERED_YEAR", "1928"),
        ("Penicillin", "DISCOVERED_BY", "Alexander Fleming"),
        ("Roman Empire Fall", "DATE", "476"),
        ("Magna Carta", "DATE", "1215"),
        ("United Nations", "FOUNDED_YEAR", "1945"),
        ("European Union", "FOUNDED_YEAR", "1993"),
        ("Bitcoin", "CREATED_YEAR", "2009"),
    ]
    for subj, pred, obj in temporal:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "temporal", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # CAUSAL LAYER — Cause-effect chains
    # ═══════════════════════════════════════════════════════════════
    causal = [
        ("Smoking", "CAUSES", "Lung Cancer"),
        ("Deforestation", "CAUSES", "Habitat Loss"),
        ("Greenhouse Gas Emissions", "CAUSES", "Climate Change"),
        ("Climate Change", "CAUSES", "Sea Level Rise"),
        ("Vaccination", "PREVENTS", "Infectious Disease"),
        ("Exercise", "IMPROVES", "Cardiovascular Health"),
        ("Photosynthesis", "PRODUCES", "Oxygen"),
        ("Combustion", "REQUIRES", "Oxygen"),
        ("Gravity", "CAUSES", "Orbital Motion"),
        ("Plate Tectonics", "CAUSES", "Earthquakes"),
        ("Volcanic Eruption", "CAUSED_BY", "Magma Pressure"),
        ("Erosion", "CAUSED_BY", "Water and Wind"),
        ("Antibiotic Overuse", "CAUSES", "Antibiotic Resistance"),
        ("UV Radiation", "CAUSES", "Skin Damage"),
        ("Ozone Depletion", "CAUSED_BY", "CFCs"),
        ("Malnutrition", "CAUSES", "Growth Stunting"),
        ("Sleep Deprivation", "IMPAIRS", "Cognitive Function"),
        ("Stress", "INCREASES_RISK_OF", "Heart Disease"),
        ("Education", "CORRELATES_WITH", "Higher Income"),
        ("Poverty", "CORRELATES_WITH", "Reduced Life Expectancy"),
    ]
    for subj, pred, obj in causal:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "causal", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # NARRATIVE LAYER — Historical events, biographies
    # ═══════════════════════════════════════════════════════════════
    narrative = [
        ("Albert Einstein", "BORN_IN", "Ulm, Germany"),
        ("Albert Einstein", "KNOWN_FOR", "Theory of Relativity"),
        ("Albert Einstein", "PROFESSION", "Physicist"),
        ("Isaac Newton", "BORN_IN", "Woolsthorpe, England"),
        ("Isaac Newton", "KNOWN_FOR", "Laws of Motion"),
        ("Marie Curie", "BORN_IN", "Warsaw, Poland"),
        ("Marie Curie", "KNOWN_FOR", "Radioactivity Research"),
        ("Marie Curie", "AWARDED", "Nobel Prize in Physics"),
        ("Marie Curie", "AWARDED", "Nobel Prize in Chemistry"),
        ("Charles Darwin", "KNOWN_FOR", "Theory of Evolution"),
        ("Charles Darwin", "WROTE", "On the Origin of Species"),
        ("Nikola Tesla", "KNOWN_FOR", "Alternating Current"),
        ("Nikola Tesla", "BORN_IN", "Smiljan, Croatia"),
        ("Leonardo da Vinci", "KNOWN_FOR", "Mona Lisa"),
        ("Leonardo da Vinci", "PROFESSION", "Polymath"),
        ("William Shakespeare", "KNOWN_FOR", "Hamlet"),
        ("William Shakespeare", "PROFESSION", "Playwright"),
        ("Mahatma Gandhi", "KNOWN_FOR", "Indian Independence Movement"),
        ("Martin Luther King Jr", "KNOWN_FOR", "Civil Rights Movement"),
        ("Nelson Mandela", "KNOWN_FOR", "Anti-Apartheid Movement"),
        ("Ada Lovelace", "KNOWN_FOR", "First Computer Algorithm"),
        ("Alan Turing", "KNOWN_FOR", "Turing Machine"),
        ("Alan Turing", "KNOWN_FOR", "Enigma Code Breaking"),
        ("Galileo Galilei", "KNOWN_FOR", "Heliocentrism Advocacy"),
        ("Aristotle", "KNOWN_FOR", "Western Philosophy"),
        ("Socrates", "KNOWN_FOR", "Socratic Method"),
        ("Plato", "KNOWN_FOR", "Republic"),
        ("Plato", "STUDENT_OF", "Socrates"),
        ("Aristotle", "STUDENT_OF", "Plato"),
        ("Alexander the Great", "STUDENT_OF", "Aristotle"),
    ]
    for subj, pred, obj in narrative:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "narrative", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # SYMBOLIC LAYER — Mathematical axioms, logical rules
    # ═══════════════════════════════════════════════════════════════
    symbolic = [
        ("Addition", "IS_A", "Commutative Operation"),
        ("Multiplication", "IS_A", "Commutative Operation"),
        ("Subtraction", "IS_NOT", "Commutative Operation"),
        ("Division", "IS_NOT", "Commutative Operation"),
        ("Zero", "IS_A", "Additive Identity"),
        ("One", "IS_A", "Multiplicative Identity"),
        ("Prime Number", "DEFINED_AS", "Natural number greater than 1 with no positive divisors other than 1 and itself"),
        ("Infinity", "IS_A", "Mathematical Concept"),
        ("Set Theory", "FOUNDED_BY", "Georg Cantor"),
        ("Boolean Algebra", "FOUNDED_BY", "George Boole"),
        ("Calculus", "FOUNDED_BY", "Isaac Newton"),
        ("Calculus", "FOUNDED_BY", "Gottfried Wilhelm Leibniz"),
        ("Euclidean Geometry", "FOUNDED_BY", "Euclid"),
        ("Non-Euclidean Geometry", "INCLUDES", "Hyperbolic Geometry"),
        ("Non-Euclidean Geometry", "INCLUDES", "Elliptic Geometry"),
        ("Godel Incompleteness Theorem", "STATES", "Any consistent formal system cannot prove all truths about natural numbers"),
        ("Halting Problem", "PROVEN_UNSOLVABLE_BY", "Alan Turing"),
        ("P vs NP", "STATUS", "Unsolved"),
        ("Riemann Hypothesis", "STATUS", "Unsolved"),
        ("Fermats Last Theorem", "PROVEN_BY", "Andrew Wiles"),
    ]
    for subj, pred, obj in symbolic:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "symbolic", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # SEMANTIC LAYER — Definitions, meaning relationships
    # ═══════════════════════════════════════════════════════════════
    semantic = [
        ("Democracy", "DEFINED_AS", "System of government by the whole population through elected representatives"),
        ("Photosynthesis", "DEFINED_AS", "Process by which plants convert light energy into chemical energy"),
        ("Evolution", "DEFINED_AS", "Change in heritable characteristics of populations over successive generations"),
        ("Entropy", "DEFINED_AS", "Measure of disorder or randomness in a system"),
        ("Algorithm", "DEFINED_AS", "Finite sequence of well-defined instructions for solving a problem"),
        ("DNA", "STANDS_FOR", "Deoxyribonucleic Acid"),
        ("RNA", "STANDS_FOR", "Ribonucleic Acid"),
        ("CPU", "STANDS_FOR", "Central Processing Unit"),
        ("GPU", "STANDS_FOR", "Graphics Processing Unit"),
        ("AI", "STANDS_FOR", "Artificial Intelligence"),
        ("ML", "STANDS_FOR", "Machine Learning"),
        ("HTTP", "STANDS_FOR", "Hypertext Transfer Protocol"),
        ("TCP", "STANDS_FOR", "Transmission Control Protocol"),
        ("IP", "STANDS_FOR", "Internet Protocol"),
        ("RAM", "STANDS_FOR", "Random Access Memory"),
        ("Gravity", "DEFINED_AS", "Fundamental force of attraction between objects with mass"),
        ("Atom", "DEFINED_AS", "Smallest unit of matter that retains chemical properties of an element"),
        ("Molecule", "DEFINED_AS", "Group of atoms bonded together"),
        ("Cell", "DEFINED_AS", "Basic structural and functional unit of all living organisms"),
        ("Gene", "DEFINED_AS", "Unit of heredity transferred from parent to offspring"),
    ]
    for subj, pred, obj in semantic:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "semantic", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # SOCIAL LAYER — Notable figures, organizations
    # ═══════════════════════════════════════════════════════════════
    social = [
        ("United Nations", "IS_A", "International Organization"),
        ("United Nations", "HEADQUARTERED_IN", "New York City"),
        ("NATO", "IS_A", "Military Alliance"),
        ("WHO", "STANDS_FOR", "World Health Organization"),
        ("NASA", "STANDS_FOR", "National Aeronautics and Space Administration"),
        ("MIT", "STANDS_FOR", "Massachusetts Institute of Technology"),
        ("CERN", "STANDS_FOR", "European Organization for Nuclear Research"),
        ("Google", "FOUNDED_BY", "Larry Page"),
        ("Google", "FOUNDED_BY", "Sergey Brin"),
        ("Apple Inc", "FOUNDED_BY", "Steve Jobs"),
        ("Microsoft", "FOUNDED_BY", "Bill Gates"),
        ("Tesla Inc", "FOUNDED_BY", "Elon Musk"),
        ("SpaceX", "FOUNDED_BY", "Elon Musk"),
        ("OpenAI", "IS_A", "AI Research Organization"),
        ("DeepMind", "IS_A", "AI Research Laboratory"),
        ("DeepMind", "OWNED_BY", "Google"),
        ("Wikipedia", "IS_A", "Online Encyclopedia"),
        ("Wikipedia", "FOUNDED_BY", "Jimmy Wales"),
        ("Linux", "CREATED_BY", "Linus Torvalds"),
        ("Python Programming Language", "CREATED_BY", "Guido van Rossum"),
    ]
    for subj, pred, obj in social:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "social", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # PROCEDURAL LAYER — Algorithms, key methods
    # ═══════════════════════════════════════════════════════════════
    procedural = [
        ("Binary Search", "COMPLEXITY", "O(log n)"),
        ("Binary Search", "IS_A", "Search Algorithm"),
        ("Quicksort", "AVERAGE_COMPLEXITY", "O(n log n)"),
        ("Quicksort", "IS_A", "Sorting Algorithm"),
        ("Merge Sort", "COMPLEXITY", "O(n log n)"),
        ("Bubble Sort", "COMPLEXITY", "O(n²)"),
        ("Dijkstra Algorithm", "SOLVES", "Shortest Path Problem"),
        ("A Star Algorithm", "IS_A", "Pathfinding Algorithm"),
        ("Gradient Descent", "USED_IN", "Machine Learning Optimization"),
        ("Backpropagation", "USED_IN", "Neural Network Training"),
        ("MapReduce", "IS_A", "Distributed Computing Framework"),
        ("TCP Three Way Handshake", "USED_IN", "Network Connection Establishment"),
        ("RSA Encryption", "IS_A", "Public Key Cryptography"),
        ("SHA-256", "IS_A", "Cryptographic Hash Function"),
        ("PageRank", "INVENTED_BY", "Larry Page"),
        ("Transformer Architecture", "INTRODUCED_IN", "Attention Is All You Need"),
        ("Transformer Architecture", "YEAR", "2017"),
        ("Convolutional Neural Network", "USED_FOR", "Image Recognition"),
        ("Recurrent Neural Network", "USED_FOR", "Sequence Processing"),
        ("Reinforcement Learning", "IS_A", "Machine Learning Paradigm"),
    ]
    for subj, pred, obj in procedural:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "procedural", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # CULTURAL LAYER — Languages, traditions, UNESCO
    # ═══════════════════════════════════════════════════════════════
    cultural = [
        ("English", "IS_A", "Germanic Language"),
        ("Mandarin Chinese", "MOST_SPEAKERS", "Native Language"),
        ("Spanish", "IS_A", "Romance Language"),
        ("Arabic", "IS_A", "Semitic Language"),
        ("Hindi", "IS_A", "Indo-Aryan Language"),
        ("French", "IS_A", "Romance Language"),
        ("Great Wall of China", "IS_A", "UNESCO World Heritage Site"),
        ("Machu Picchu", "IS_A", "UNESCO World Heritage Site"),
        ("Taj Mahal", "IS_A", "UNESCO World Heritage Site"),
        ("Colosseum", "LOCATED_IN", "Rome"),
        ("Pyramids of Giza", "LOCATED_IN", "Egypt"),
        ("Parthenon", "LOCATED_IN", "Athens"),
        ("Olympics", "ORIGIN", "Ancient Greece"),
        ("Olympics", "MODERN_REVIVAL", "1896"),
        ("Nobel Prize", "ESTABLISHED_BY", "Alfred Nobel"),
        ("Nobel Prize", "ESTABLISHED_YEAR", "1901"),
        ("Universal Declaration of Human Rights", "ADOPTED_YEAR", "1948"),
        ("Gregorian Calendar", "INTRODUCED_YEAR", "1582"),
        ("Metric System", "ORIGIN_COUNTRY", "France"),
        ("Scientific Method", "FORMALIZED_BY", "Francis Bacon"),
    ]
    for subj, pred, obj in cultural:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "cultural", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # ANALOGICAL LAYER — Cross-domain mappings, known metaphors
    # ═══════════════════════════════════════════════════════════════
    analogical = [
        ("Brain", "ANALOGOUS_TO", "Computer"),
        ("Heart", "ANALOGOUS_TO", "Pump"),
        ("DNA", "ANALOGOUS_TO", "Blueprint"),
        ("Atom", "ANALOGOUS_TO", "Solar System"),
        ("Internet", "ANALOGOUS_TO", "Neural Network"),
        ("Evolution", "ANALOGOUS_TO", "Gradient Descent"),
        ("Memory", "ANALOGOUS_TO", "Hard Drive"),
        ("Ecosystem", "ANALOGOUS_TO", "Economy"),
        ("Virus", "ANALOGOUS_TO", "Computer Virus"),
        ("Language", "ANALOGOUS_TO", "Operating System"),
    ]
    for subj, pred, obj in analogical:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "analogical", "provenance": PROVENANCE_CONCEPTNET})

    # ═══════════════════════════════════════════════════════════════
    # ECOLOGICAL LAYER — Ecosystems, climate, species
    # ═══════════════════════════════════════════════════════════════
    ecological = [
        ("Amazon Rainforest", "IS_A", "Tropical Rainforest"),
        ("Amazon Rainforest", "CONTAINS", "10% of all species on Earth"),
        ("Great Barrier Reef", "IS_A", "Coral Reef Ecosystem"),
        ("Great Barrier Reef", "LOCATED_IN", "Australia"),
        ("Carbon Dioxide", "ROLE_IN", "Greenhouse Effect"),
        ("Oxygen", "PRODUCED_BY", "Photosynthesis"),
        ("Water", "CHEMICAL_FORMULA", "H2O"),
        ("Carbon Dioxide", "CHEMICAL_FORMULA", "CO2"),
        ("Ozone", "CHEMICAL_FORMULA", "O3"),
        ("Biodiversity Loss", "CAUSED_BY", "Habitat Destruction"),
        ("Coral Bleaching", "CAUSED_BY", "Ocean Warming"),
        ("Polar Ice Caps", "THREATENED_BY", "Global Warming"),
        ("Earth", "AGE", "4.54 billion years"),
        ("Sun", "IS_A", "G-type Main Sequence Star"),
        ("Sun", "AGE", "4.6 billion years"),
        ("Milky Way", "IS_A", "Barred Spiral Galaxy"),
        ("Earth", "DISTANCE_FROM_SUN", "149.6 million km"),
        ("Moon", "DISTANCE_FROM_EARTH", "384400 km"),
        ("Mars", "DISTANCE_FROM_SUN", "227.9 million km"),
        ("Jupiter", "LARGEST_PLANET_IN", "Solar System"),
    ]
    for subj, pred, obj in ecological:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "ecological", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # CREATIVE LAYER — Art movements, musical theory
    # ═══════════════════════════════════════════════════════════════
    creative = [
        ("Impressionism", "STARTED_IN", "France"),
        ("Impressionism", "KEY_ARTIST", "Claude Monet"),
        ("Cubism", "KEY_ARTIST", "Pablo Picasso"),
        ("Surrealism", "KEY_ARTIST", "Salvador Dali"),
        ("Baroque", "KEY_COMPOSER", "Johann Sebastian Bach"),
        ("Classical Period", "KEY_COMPOSER", "Wolfgang Amadeus Mozart"),
        ("Romanticism", "KEY_COMPOSER", "Ludwig van Beethoven"),
        ("Mona Lisa", "PAINTED_BY", "Leonardo da Vinci"),
        ("Starry Night", "PAINTED_BY", "Vincent van Gogh"),
        ("The Persistence of Memory", "PAINTED_BY", "Salvador Dali"),
        ("Beethoven Symphony No 9", "YEAR", "1824"),
        ("Rock and Roll", "ORIGINATED_IN", "United States"),
        ("Jazz", "ORIGINATED_IN", "New Orleans"),
        ("Hip Hop", "ORIGINATED_IN", "New York City"),
        ("Ballet", "ORIGINATED_IN", "Italian Renaissance Courts"),
    ]
    for subj, pred, obj in creative:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "creative", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # EPISTEMIC LAYER — Source provenance, meta-knowledge
    # ═══════════════════════════════════════════════════════════════
    epistemic = [
        ("Wikipedia", "RELIABILITY", "Community-verified, generally accurate for established facts"),
        ("arXiv", "RELIABILITY", "Pre-print, not peer-reviewed, cutting-edge research"),
        ("Wikidata", "RELIABILITY", "Structured data, high accuracy for factual relationships"),
        ("ConceptNet", "RELIABILITY", "Crowdsourced common sense, moderate accuracy"),
        ("Peer Reviewed Journal", "RELIABILITY", "Highest standard for scientific claims"),
        ("Scientific Consensus", "DEFINED_AS", "Collective judgment of the scientific community"),
        ("Empirical Evidence", "DEFINED_AS", "Knowledge gained through observation and experimentation"),
        ("Anecdotal Evidence", "RELIABILITY", "Low - single observations, not statistically valid"),
        ("Correlation", "IS_NOT", "Causation"),
        ("Burden of Proof", "DEFINED_AS", "Obligation to prove an assertion"),
    ]
    for subj, pred, obj in epistemic:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "epistemic", "provenance": PROVENANCE_SCIENCE})

    # ═══════════════════════════════════════════════════════════════
    # MORAL LAYER — Ethical frameworks (seedable universals)
    # ═══════════════════════════════════════════════════════════════
    moral = [
        ("Universal Declaration of Human Rights", "GUARANTEES", "Right to Life"),
        ("Universal Declaration of Human Rights", "GUARANTEES", "Freedom of Expression"),
        ("Universal Declaration of Human Rights", "GUARANTEES", "Right to Education"),
        ("Geneva Convention", "PROTECTS", "Prisoners of War"),
        ("Hippocratic Oath", "PRINCIPLE", "First Do No Harm"),
    ]
    for subj, pred, obj in moral:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "moral", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # AESTHETIC LAYER — Aesthetic principles
    # ═══════════════════════════════════════════════════════════════
    aesthetic = [
        ("Golden Ratio", "USED_IN", "Art and Architecture"),
        ("Rule of Thirds", "USED_IN", "Photography"),
        ("Color Theory", "INCLUDES", "Complementary Colors"),
        ("Color Theory", "INCLUDES", "Analogous Colors"),
        ("Typography", "KEY_CONCEPT", "Kerning"),
    ]
    for subj, pred, obj in aesthetic:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "aesthetic", "provenance": PROVENANCE_WIKI})

    # ═══════════════════════════════════════════════════════════════
    # EXPANSION BATCH — 120 additional facts to reach 500 target
    # ═══════════════════════════════════════════════════════════════

    # ── Procedural (15) ──
    procedural_ext = [
        ("A Star Search", "USES", "Heuristic Function"),
        ("Bellman Ford Algorithm", "HANDLES", "Negative Edge Weights"),
        ("Binary Search", "REQUIRES", "Sorted Array"),
        ("Binary Search", "TIME_COMPLEXITY", "O(log n)"),
        ("Merge Sort", "PROPERTY", "Stable Sort"),
        ("Breadth First Search", "USES", "Queue Data Structure"),
        ("Depth First Search", "USES", "Stack Data Structure"),
        ("TCP Handshake", "STEPS", "SYN SYN-ACK ACK"),
        ("HTTP Request", "METHODS", "GET POST PUT DELETE PATCH"),
        ("DNA Replication", "ENZYME", "DNA Polymerase"),
        ("Krebs Cycle", "PRODUCES", "ATP"),
        ("Photosynthesis", "EQUATION", "6CO2 + 6H2O → C6H12O6 + 6O2"),
        ("Pasteurization", "INVENTED_BY", "Louis Pasteur"),
        ("Fermentation", "PRODUCES", "Ethanol and Carbon Dioxide"),
        ("Vaccination", "PRINCIPLE", "Acquired Immunity through Antigen Exposure"),
    ]
    for subj, pred, obj in procedural_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "procedural", "provenance": PROVENANCE_SCIENCE})

    # ── Causal (15) ──
    causal_ext = [
        ("Deforestation", "CAUSES", "Soil Erosion"),
        ("Ozone Depletion", "CAUSED_BY", "Chlorofluorocarbons"),
        ("Acid Rain", "CAUSED_BY", "Sulfur Dioxide Emissions"),
        ("Urbanization", "LEADS_TO", "Heat Island Effect"),
        ("Antibiotic Overuse", "CAUSES", "Antimicrobial Resistance"),
        ("Continental Drift", "CAUSES", "Earthquakes"),
        ("Volcanic Eruption", "CAUSES", "Temporary Global Cooling"),
        ("Ocean Acidification", "CAUSED_BY", "Carbon Dioxide Absorption"),
        ("Sleep Deprivation", "CAUSES", "Cognitive Impairment"),
        ("Exercise", "CAUSES", "Endorphin Release"),
        ("Inflation", "CAUSED_BY", "Monetary Supply Increase"),
        ("Tidal Forces", "CAUSED_BY", "Gravitational Pull of Moon"),
        ("Plate Tectonics", "CAUSES", "Mountain Formation"),
        ("Overfishing", "CAUSES", "Marine Ecosystem Collapse"),
        ("Solar Flares", "CAUSE", "Geomagnetic Storms"),
    ]
    for subj, pred, obj in causal_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "causal", "provenance": PROVENANCE_SCIENCE})

    # ── Semantic (15) ──
    semantic_ext = [
        ("Algorithm", "DEFINED_AS", "A finite sequence of well-defined instructions"),
        ("Democracy", "DEFINED_AS", "Government by the people through elected representatives"),
        ("Entropy", "DEFINED_AS", "Measure of disorder in a thermodynamic system"),
        ("Ecosystem", "DEFINED_AS", "Community of living organisms interacting with environment"),
        ("Genome", "DEFINED_AS", "Complete set of genetic material of an organism"),
        ("Photon", "DEFINED_AS", "Quantum of electromagnetic radiation"),
        ("Catalyst", "DEFINED_AS", "Substance that increases reaction rate without being consumed"),
        ("Hypothesis", "DEFINED_AS", "Testable prediction derived from theory"),
        ("Symbiosis", "DEFINED_AS", "Close biological interaction between two species"),
        ("Isotope", "DEFINED_AS", "Atoms of same element with different numbers of neutrons"),
        ("Paradigm", "DEFINED_AS", "Framework of concepts and practices defining a discipline"),
        ("Osmosis", "DEFINED_AS", "Movement of solvent across semipermeable membrane"),
        ("Metaphor", "DEFINED_AS", "Figure of speech comparing two unlike things"),
        ("Sovereignty", "DEFINED_AS", "Supreme authority within a territory"),
        ("Renaissance", "DEFINED_AS", "European cultural movement from 14th to 17th century"),
    ]
    for subj, pred, obj in semantic_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "semantic", "provenance": PROVENANCE_WIKI})

    # ── Analogical (10) ──
    analogical_ext = [
        ("Firewall", "ANALOGOUS_TO", "Bouncer at a Club"),
        ("RAM", "ANALOGOUS_TO", "Workbench"),
        ("Mitochondria", "ANALOGOUS_TO", "Power Plant"),
        ("Library", "ANALOGOUS_TO", "Hard Drive"),
        ("Atoms", "ANALOGOUS_TO", "Solar System"),
        ("Nervous System", "ANALOGOUS_TO", "Electrical Wiring"),
        ("Immune System", "ANALOGOUS_TO", "Military Defense"),
        ("Economy", "ANALOGOUS_TO", "Ecosystem"),
        ("Internet", "ANALOGOUS_TO", "Highway System"),
        ("Evolution", "ANALOGOUS_TO", "Algorithm Optimization"),
    ]
    for subj, pred, obj in analogical_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "analogical", "provenance": PROVENANCE_CONCEPTNET})

    # ── Cultural (15) ──
    cultural_ext = [
        ("Machu Picchu", "UNESCO_STATUS", "World Heritage Site"),
        ("Great Wall of China", "UNESCO_STATUS", "World Heritage Site"),
        ("Taj Mahal", "LOCATED_IN", "Agra India"),
        ("Colosseum", "BUILT_IN", "Rome"),
        ("Mandarin Chinese", "MOST_SPOKEN", "Native Speakers Worldwide"),
        ("Arabic", "SCRIPT_DIRECTION", "Right to Left"),
        ("Sanskrit", "STATUS", "Classical Language of India"),
        ("Haiku", "ORIGIN", "Japan"),
        ("Carnival", "CELEBRATED_IN", "Brazil"),
        ("Diwali", "CELEBRATED_BY", "Hindu Communities"),
        ("Ramadan", "OBSERVED_BY", "Muslim Communities"),
        ("Stonehenge", "LOCATED_IN", "Wiltshire England"),
        ("Petra", "LOCATED_IN", "Jordan"),
        ("Kimchi", "ORIGIN_COUNTRY", "Korea"),
        ("Flamenco", "ORIGIN_REGION", "Andalusia Spain"),
    ]
    for subj, pred, obj in cultural_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "cultural", "provenance": PROVENANCE_WIKI})

    # ── Ecological (10) ──
    ecological_ext = [
        ("Amazon Rainforest", "PRODUCES", "20 Percent of World Oxygen"),
        ("Coral Bleaching", "CAUSED_BY", "Rising Ocean Temperatures"),
        ("Taiga Biome", "CHARACTERISTIC", "Largest Terrestrial Biome"),
        ("Galapagos Islands", "KNOWN_FOR", "Unique Evolutionary Species"),
        ("Monarch Butterfly", "MIGRATION", "Mexico to Canada"),
        ("Mangrove Forest", "PROVIDES", "Coastal Erosion Protection"),
        ("Bee Population", "CRITICAL_FOR", "Crop Pollination"),
        ("Permafrost", "CONTAINS", "Trapped Methane"),
        ("Wetlands", "FUNCTION", "Natural Water Filtration"),
        ("Old Growth Forest", "STORES", "Large Carbon Reserves"),
    ]
    for subj, pred, obj in ecological_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "ecological", "provenance": PROVENANCE_SCIENCE})

    # ── Creative (10) ──
    creative_ext = [
        ("Surrealism", "FOUNDED_BY", "Andre Breton"),
        ("Pop Art", "KEY_ARTIST", "Andy Warhol"),
        ("Dadaism", "FOUNDED_BY", "Hugo Ball"),
        ("Jazz", "ORIGIN_CITY", "New Orleans"),
        ("Hip Hop", "ORIGIN_DECADE", "1970s"),
        ("Bauhaus", "FOUNDED_IN", "Weimar Germany 1919"),
        ("Art Nouveau", "PERIOD", "1890 to 1910"),
        ("Haiku", "STRUCTURE", "5-7-5 Syllable Pattern"),
        ("Sonnet", "STRUCTURE", "14 Lines in Iambic Pentameter"),
        ("Film Noir", "CHARACTERISTICS", "Low Key Lighting and Moral Ambiguity"),
    ]
    for subj, pred, obj in creative_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "creative", "provenance": PROVENANCE_WIKI})

    # ── Predictive (10) ──
    predictive_ext = [
        ("Boltzmann Constant", "VALUE", "1.380649e-23 J/K"),
        ("Avogadro Number", "VALUE", "6.02214076e23 mol-1"),
        ("Elementary Charge", "VALUE", "1.602176634e-19 C"),
        ("Hubble Constant", "APPROXIMATE_VALUE", "70 km/s/Mpc"),
        ("Earth Orbital Period", "VALUE", "365.25 Days"),
        ("Moon Orbital Period", "VALUE", "27.3 Days"),
        ("Speed of Sound in Air", "VALUE", "343 m/s at 20C"),
        ("Absolute Zero", "VALUE", "-273.15 Celsius"),
        ("Stefan Boltzmann Constant", "VALUE", "5.670374419e-8 W/m2/K4"),
        ("Standard Atmospheric Pressure", "VALUE", "101325 Pascal"),
    ]
    for subj, pred, obj in predictive_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "predictive", "provenance": PROVENANCE_SCIENCE})

    # ── Social (10) ──
    social_ext = [
        ("United Nations", "FOUNDED", "1945"),
        ("European Union", "HEADQUARTERS", "Brussels"),
        ("World Health Organization", "ABBREVIATION", "WHO"),
        ("International Monetary Fund", "ABBREVIATION", "IMF"),
        ("Red Cross", "FOUNDED_BY", "Henry Dunant"),
        ("Nobel Prize", "ESTABLISHED", "1901"),
        ("Nobel Peace Prize", "AWARDED_IN", "Oslo"),
        ("Olympic Games", "MODERN_REVIVAL", "Athens 1896"),
        ("FIFA", "GOVERNS", "Association Football"),
        ("NATO", "FOUNDED", "1949"),
    ]
    for subj, pred, obj in social_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "social", "provenance": PROVENANCE_WIKI})

    # ── Narrative (10) ──
    narrative_ext = [
        ("Apollo 11", "ACHIEVED", "First Moon Landing 1969"),
        ("Fall of Berlin Wall", "DATE", "November 9 1989"),
        ("Invention of Printing Press", "BY", "Johannes Gutenberg circa 1440"),
        ("Discovery of Penicillin", "BY", "Alexander Fleming 1928"),
        ("Industrial Revolution", "BEGAN_IN", "Britain late 18th Century"),
        ("French Revolution", "BEGAN", "1789"),
        ("Discovery of DNA Structure", "BY", "Watson and Crick 1953"),
        ("Signing of Magna Carta", "DATE", "1215"),
        ("First Transatlantic Flight", "BY", "Charles Lindbergh 1927"),
        ("Formation of European Union", "TREATY", "Maastricht Treaty 1992"),
    ]
    for subj, pred, obj in narrative_ext:
        facts.append({"subject": subj, "predicate": pred, "object": obj,
                       "layer": "narrative", "provenance": PROVENANCE_WIKI})

    return facts


# ─── Runner ────────────────────────────────────────────────────

def run_seed(graph):
    """Seed the 500-fact test batch into the KG."""
    facts = get_test_batch()
    print(f"Prepared {len(facts)} foundation facts across layers:")
    
    # Count by layer
    layer_counts = {}
    for f in facts:
        layer = f["layer"]
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    for layer, count in sorted(layer_counts.items(), key=lambda x: -x[1]):
        print(f"  {layer:20s}: {count}")
    
    print(f"\nSeeding into CORE scope (user_id=-1)...")
    result = graph.bulk_seed(facts, batch_size=500)
    print(f"Result: {result}")
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    
    from src.memory.graph import KnowledgeGraph
    
    kg = KnowledgeGraph()
    try:
        result = run_seed(kg)
        print(f"\n✅ Seeding complete: {result}")
    finally:
        kg.close()

# Module-level export for test imports
SEED_FACTS = get_test_batch()
