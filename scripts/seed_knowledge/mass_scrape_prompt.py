"""
Mass Scraping Prompt — Launch 1000 Agents for Large-Scale Knowledge Extraction

This file contains the system prompt designed to be given to 1000 parallel
agent instances for massive, diverse knowledge scraping. Each agent gets a
unique domain assignment and scrapes independently into the shared KG.

Usage:
    # Generate agent assignments:
    python -m scripts.seed_knowledge.mass_scrape_prompt --count 1000

    # Or import for programmatic use:
    from scripts.seed_knowledge.mass_scrape_prompt import generate_agent_assignments
"""
import json
import random
import hashlib
import argparse
from typing import List, Dict

# ═══════════════════════════════════════════════════════════════
# Agent System Prompt
# ═══════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """You are a Knowledge Extraction Agent for Ernos, a sovereign synthetic intelligence.

Your mission: Extract structured knowledge facts from the internet and output them as JSON for seeding into Ernos's Knowledge Graph.

## Output Format
For each piece of knowledge you extract, output a JSON fact:
```json
{
    "subject": "entity name",
    "predicate": "RELATIONSHIP_TYPE",
    "object": "related entity",
    "layer": "cognitive_layer",
    "scope": "CORE_PUBLIC",
    "provenance": {
        "source": "source_name",
        "url": "source_url",
        "confidence": 0.85,
        "retrieved": "2026-02-18"
    }
}
```

**IMPORTANT**: All facts MUST have `"scope": "CORE_PUBLIC"`. This is shareable world
knowledge — visible to all users in PUBLIC and PRIVATE contexts. Never use CORE_PRIVATE
(that is reserved for Ernos's private interiority like emotions and self-reflection).

## Valid Predicates
IS_A, PART_OF, HAS_A, USED_FOR, CAPABLE_OF, LOCATED_IN, CAUSES, HAS_PREREQUISITE,
CREATED_BY, SYMBOL_OF, DEFINED_AS, SIMILAR_TO, ANTONYM, DERIVED_FROM, RELATED_TO,
HAS_PROPERTY, MADE_OF, KNOWN_FOR, BORN_IN, FOUNDED_BY, INVENTED_BY, DISCOVERED_BY,
CAPITAL_IS, MEMBER_OF, HEADQUARTERED_IN, AUTHORED, INFLUENCED, CATEGORIZED_AS,
CONTRIBUTES_TO, AWARDED, PUBLISHED_BY, FIELD, ERA, PLAYS, FORMULA, VALUE, STATES

## Valid Layers
spatial, categorical, predictive, temporal, causal, narrative, symbolic, semantic,
social, procedural, cultural, analogical, ecological, creative, epistemic, moral,
aesthetic, emotional, motivational, experiential, linguistic, metacognitive

## Rules
1. Extract FACTUAL knowledge only — no opinions, speculation, or hearsay
2. Be DIVERSE — cover multiple relationship types and layers per topic
3. Prefer STRUCTURED facts over vague associations
4. Include source URLs for provenance tracking
5. One fact per line, valid JSON
6. Aim for 50-200 facts per assigned domain
7. Follow links from initial articles to discover deeper knowledge
8. Extract relationships between entities, not just definitions

## Your Assigned Domain
{domain_assignment}

## Your Search Seeds
Start with these and follow the knowledge trail wherever it leads:
{search_seeds}

GO. Extract as much diverse, high-quality knowledge as you can from your domain.
Output only JSON facts, one per line.
"""

# ═══════════════════════════════════════════════════════════════
# Domain Pool — 200+ unique domains for agent assignment
# ═══════════════════════════════════════════════════════════════

DOMAIN_POOL = [
    # ── Physical Sciences (40) ──────────────────────────
    "quantum mechanics", "general relativity", "particle physics",
    "nuclear physics", "plasma physics", "condensed matter physics",
    "optics and photonics", "thermodynamics", "fluid dynamics",
    "acoustics", "astrophysics", "cosmology",
    "string theory", "quantum field theory", "statistical mechanics",
    "inorganic chemistry", "organic chemistry", "physical chemistry",
    "analytical chemistry", "biochemistry", "electrochemistry",
    "polymer chemistry", "medicinal chemistry", "geochemistry",
    "atmospheric chemistry", "materials science", "nanotechnology",
    "superconductivity", "crystallography", "spectroscopy",
    "earth science", "geology", "oceanography",
    "meteorology", "volcanology", "seismology",
    "hydrology", "mineralogy", "planetary science", "astrochemistry",

    # ── Life Sciences (40) ──────────────────────────────
    "molecular biology", "cell biology", "genetics",
    "evolutionary biology", "ecology", "marine biology",
    "microbiology", "virology", "mycology",
    "botany", "zoology", "entomology",
    "immunology", "neuroscience", "endocrinology",
    "developmental biology", "bioinformatics", "systems biology",
    "epigenetics", "proteomics", "metabolomics",
    "synthetic biology", "astrobiology", "conservation biology",
    "behavioral ecology", "population genetics", "paleontology",
    "paleoanthropology", "ethology", "parasitology",
    "pharmacology", "toxicology", "pathology",
    "anatomy", "physiology", "histology",
    "oncology", "cardiology", "gastroenterology", "ophthalmology",

    # ── Mathematics (30) ────────────────────────────────
    "number theory", "algebraic geometry", "topology",
    "differential geometry", "functional analysis", "measure theory",
    "combinatorics", "graph theory", "category theory",
    "mathematical logic", "set theory", "model theory",
    "probability theory", "stochastic processes", "statistics",
    "numerical analysis", "optimization", "dynamical systems",
    "chaos theory", "fractal geometry", "knot theory",
    "representation theory", "abstract algebra", "linear algebra",
    "differential equations", "partial differential equations",
    "game theory", "information theory", "coding theory",
    "computational complexity",

    # ── Computer Science (35) ───────────────────────────
    "artificial intelligence", "machine learning", "deep learning",
    "natural language processing", "computer vision", "robotics",
    "reinforcement learning", "generative AI", "AI safety and alignment",
    "distributed systems", "database systems", "operating systems",
    "computer networks", "cybersecurity", "cryptography",
    "compiler design", "programming languages", "type theory",
    "formal verification", "software engineering",
    "computer graphics", "human-computer interaction",
    "quantum computing", "parallel computing", "edge computing",
    "blockchain technology", "internet of things",
    "data mining", "information retrieval", "recommender systems",
    "computational geometry", "bioinformatics algorithms",
    "autonomous vehicles", "drone technology", "brain-computer interfaces",

    # ── Engineering (25) ────────────────────────────────
    "mechanical engineering", "electrical engineering", "civil engineering",
    "chemical engineering", "aerospace engineering", "biomedical engineering",
    "environmental engineering", "nuclear engineering", "ocean engineering",
    "structural engineering", "control systems engineering",
    "telecommunications engineering", "power systems engineering",
    "microelectronics", "VLSI design", "signal processing",
    "renewable energy systems", "battery technology",
    "3D printing", "additive manufacturing",
    "construction engineering", "transportation engineering",
    "hydraulic engineering", "geotechnical engineering", "mining engineering",

    # ── Social Sciences (25) ────────────────────────────
    "sociology", "anthropology", "psychology",
    "political science", "economics", "geography",
    "linguistics", "archaeology", "demography",
    "cognitive science", "behavioral economics", "economic history",
    "international relations", "public policy", "urban planning",
    "criminology", "social psychology", "developmental psychology",
    "clinical psychology", "evolutionary psychology",
    "cultural studies", "gender studies", "media studies",
    "communication theory", "organizational behavior",

    # ── Philosophy (20) ────────────────────────────────
    "metaphysics", "epistemology", "ethics",
    "logic", "aesthetics", "philosophy of mind",
    "philosophy of science", "philosophy of language",
    "political philosophy", "philosophy of mathematics",
    "existentialism", "phenomenology", "pragmatism",
    "analytic philosophy", "continental philosophy",
    "philosophy of religion", "bioethics", "neuroethics",
    "philosophy of technology", "philosophy of AI",

    # ── History (25) ────────────────────────────────────
    "ancient Egypt", "ancient Greece", "ancient Rome",
    "ancient China", "ancient India", "Mesopotamia",
    "Byzantine Empire", "Ottoman Empire", "Mongol Empire",
    "Medieval Europe", "Renaissance", "Age of Exploration",
    "Scientific Revolution", "Enlightenment", "Industrial Revolution",
    "French Revolution", "American Revolution", "Russian Revolution",
    "World War I", "World War II", "Cold War",
    "decolonization", "Space Race history", "digital revolution",
    "history of philosophy",

    # ── Arts & Culture (20) ─────────────────────────────
    "art history", "music theory", "film studies",
    "architecture history", "photography", "sculpture",
    "theater history", "dance history", "opera",
    "literary criticism", "poetry", "mythology",
    "folklore", "comparative religion", "world cuisines",
    "fashion history", "graphic design", "typography",
    "video game design", "animation history",
]


def generate_agent_assignments(count: int = 1000) -> List[Dict]:
    """
    Generate unique agent assignments for mass scraping.

    Each agent gets:
    - A primary domain
    - 3 search seeds to start with
    - A unique agent ID

    Domains are distributed evenly — with 200+ domains and 1000 agents,
    each domain gets ~5 agents with different starting seeds.
    """
    assignments = []

    for i in range(count):
        # Round-robin domain assignment with shuffle for diversity
        domain = DOMAIN_POOL[i % len(DOMAIN_POOL)]

        # Generate unique search seeds per agent
        seed_hash = hashlib.md5(f"{domain}_{i}".encode()).hexdigest()[:8]
        base_seeds = [
            f"{domain} latest research",
            f"{domain} key concepts",
            f"{domain} history and evolution",
            f"{domain} applications",
            f"{domain} major breakthroughs",
            f"{domain} open problems",
            f"{domain} notable figures",
            f"{domain} fundamental principles",
        ]
        # Each agent gets a different subset of seeds
        random.seed(int(seed_hash, 16))
        search_seeds = random.sample(base_seeds, min(3, len(base_seeds)))

        prompt = AGENT_SYSTEM_PROMPT.format(
            domain_assignment=domain,
            search_seeds="\n".join(f"  - {s}" for s in search_seeds)
        )

        assignments.append({
            "agent_id": f"scraper-{i:04d}",
            "domain": domain,
            "search_seeds": search_seeds,
            "prompt": prompt,
        })

    return assignments


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mass scraping agent assignments")
    parser.add_argument("--count", type=int, default=1000,
                        help="Number of agents to generate assignments for")
    parser.add_argument("--output", type=str, default="agent_assignments.json",
                        help="Output file for assignments")
    parser.add_argument("--show-prompt", action="store_true",
                        help="Print the system prompt template")
    parser.add_argument("--show-domains", action="store_true",
                        help="List all available domains")
    args = parser.parse_args()

    if args.show_prompt:
        print(AGENT_SYSTEM_PROMPT.format(
            domain_assignment="[YOUR_DOMAIN]",
            search_seeds="  - [seed 1]\n  - [seed 2]\n  - [seed 3]"
        ))
    elif args.show_domains:
        print(f"Available domains ({len(DOMAIN_POOL)}):\n")
        for i, domain in enumerate(DOMAIN_POOL, 1):
            print(f"  {i:3d}. {domain}")
    else:
        assignments = generate_agent_assignments(args.count)

        with open(args.output, "w") as f:
            json.dump(assignments, f, indent=2)
        print(f"✅ Generated {len(assignments)} agent assignments → {args.output}")
        print(f"   Domains used: {len(set(a['domain'] for a in assignments))}")
        print(f"   Approx facts at 100/agent: {len(assignments) * 100:,}")

        # Also print the raw system prompt for quick copy-paste
        print(f"\n{'='*60}")
        print("SYSTEM PROMPT (copy this for each agent):")
        print(f"{'='*60}\n")
        print(AGENT_SYSTEM_PROMPT.format(
            domain_assignment="{{AGENT_DOMAIN}}",
            search_seeds="  - {{SEED_1}}\n  - {{SEED_2}}\n  - {{SEED_3}}"
        ))
