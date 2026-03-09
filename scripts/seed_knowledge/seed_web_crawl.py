"""
Full-Scale Internet Scraping & Crawling Seed
Pulls structured knowledge from multiple internet sources:

  1. DBpedia SPARQL   — Structured knowledge (people, places, orgs, inventions)
  2. ConceptNet API   — Commonsense reasoning edges
  3. RSS News Feeds   — Current events → temporal/social layers
  4. DuckDuckGo       — Topic discovery → browse → extract
  5. Trafilatura      — Clean article text → entity extraction

Usage:
    python -m scripts.seed_knowledge.seed_web_crawl [--source=all|dbpedia|conceptnet|rss|ddg|articles] [--limit 500] [--dry-run]
"""
import logging
import time
import json
import re
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Seed.WebCrawl")

RATE_LIMIT = 1.5  # seconds between requests (be polite)

PROVENANCE_DBPEDIA = {"source": "dbpedia", "confidence": 0.93, "retrieved": "2026-02-09"}
PROVENANCE_CONCEPTNET = {"source": "conceptnet", "confidence": 0.88, "retrieved": "2026-02-09"}
PROVENANCE_RSS = {"source": "rss_feeds", "confidence": 0.85, "retrieved": "2026-02-09"}
PROVENANCE_DDG = {"source": "duckduckgo", "confidence": 0.82, "retrieved": "2026-02-09"}
PROVENANCE_ARTICLE = {"source": "web_article", "confidence": 0.80, "retrieved": "2026-02-09"}


# ═══════════════════════════════════════════════════════════════
# 1. DBpedia SPARQL — Structured Knowledge
# ═══════════════════════════════════════════════════════════════

DBPEDIA_ENDPOINT = "https://dbpedia.org/sparql"

def _sparql_dbpedia(query: str) -> list:
    """Execute a SPARQL query against DBpedia."""
    params = urllib.parse.urlencode({
        "query": query,
        "format": "application/json"
    })
    url = f"{DBPEDIA_ENDPOINT}?{params}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ErnOS-KG-Seed/1.0",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", {}).get("bindings", [])
    except Exception as e:
        logger.error(f"DBpedia SPARQL error: {e}")
        return []


def fetch_dbpedia_people(limit: int = 500) -> list:
    """Fetch notable people with birth/death places, occupations."""
    query = f"""
    SELECT DISTINCT ?name ?birthPlace ?occupation ?abstract WHERE {{
        ?person a dbo:Person ;
                rdfs:label ?name ;
                dbo:birthPlace ?bp .
        ?bp rdfs:label ?birthPlace .
        OPTIONAL {{ ?person dbo:occupation ?occ . ?occ rdfs:label ?occupation . FILTER(lang(?occupation) = 'en') }}
        OPTIONAL {{ ?person dbo:abstract ?abstract . FILTER(lang(?abstract) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(lang(?birthPlace) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        birth = r.get("birthPlace", {}).get("value", "")
        occ = r.get("occupation", {}).get("value", "")
        if name and birth:
            facts.append({"subject": name, "predicate": "BORN_IN", "object": birth,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
        if name and occ:
            facts.append({"subject": name, "predicate": "OCCUPATION", "object": occ,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia people: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_places(limit: int = 500) -> list:
    """Fetch cities, countries, and geographic relationships."""
    query = f"""
    SELECT DISTINCT ?name ?country ?population ?abstract WHERE {{
        ?place a dbo:City ;
               rdfs:label ?name ;
               dbo:country ?c .
        ?c rdfs:label ?country .
        OPTIONAL {{ ?place dbo:populationTotal ?population }}
        OPTIONAL {{ ?place dbo:abstract ?abstract . FILTER(lang(?abstract) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(lang(?country) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        country = r.get("country", {}).get("value", "")
        pop = r.get("population", {}).get("value", "")
        if name and country:
            facts.append({"subject": name, "predicate": "LOCATED_IN", "object": country,
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
        if name and pop:
            facts.append({"subject": name, "predicate": "POPULATION", "object": str(pop),
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia places: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_achievements(limit: int = 300) -> list:
    """Fetch notable people and what they're known for."""
    query = f"""
    SELECT DISTINCT ?personName ?achievementName WHERE {{
        ?person a dbo:Person ;
                rdfs:label ?personName ;
                dbo:knownFor ?achievement .
        ?achievement rdfs:label ?achievementName .
        FILTER(lang(?personName) = 'en')
        FILTER(lang(?achievementName) = 'en')
        FILTER(STRLEN(?personName) > 3)
        FILTER(STRLEN(?achievementName) > 3)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        person = r.get("personName", {}).get("value", "")
        achievement = r.get("achievementName", {}).get("value", "")
        if person and achievement:
            facts.append({"subject": person, "predicate": "KNOWN_FOR", "object": achievement,
                          "layer": "causal", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia achievements: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_species(limit: int = 400) -> list:
    """Fetch biological species with kingdom and class (guaranteed fields)."""
    query = f"""
    SELECT DISTINCT ?name ?kingdom ?cls WHERE {{
        ?species a dbo:Species ;
                 rdfs:label ?name ;
                 dbo:kingdom ?k .
        ?k rdfs:label ?kingdom .
        OPTIONAL {{ ?species dbo:class ?c . ?c rdfs:label ?cls . FILTER(lang(?cls) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(lang(?kingdom) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        kingdom = r.get("kingdom", {}).get("value", "")
        cls = r.get("cls", {}).get("value", "")
        if name and kingdom:
            facts.append({"subject": name, "predicate": "KINGDOM", "object": kingdom,
                          "layer": "ecological", "provenance": PROVENANCE_DBPEDIA})
        if name and cls:
            facts.append({"subject": name, "predicate": "CLASS", "object": cls,
                          "layer": "categorical", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            # At minimum, record the species exists
            facts.append({"subject": name, "predicate": "IS_A", "object": "Species",
                          "layer": "ecological", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia species: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_organizations(limit: int = 400) -> list:
    """Fetch organizations with locations and types."""
    query = f"""
    SELECT DISTINCT ?name ?location ?type WHERE {{
        ?org a dbo:Organisation ;
             rdfs:label ?name .
        OPTIONAL {{ ?org dbo:locationCity ?loc . ?loc rdfs:label ?location . FILTER(lang(?location) = 'en') }}
        OPTIONAL {{ ?org rdf:type ?type }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 3)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        loc = r.get("location", {}).get("value", "")
        if name and loc:
            facts.append({"subject": name, "predicate": "HEADQUARTERED_IN", "object": loc,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia organizations: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_countries(limit: int = 500) -> list:
    """Fetch countries with capitals and populations."""
    query = f"""
    SELECT DISTINCT ?name ?capital ?population WHERE {{
        ?country a dbo:Country ;
                 rdfs:label ?name ;
                 dbo:capital ?cap .
        ?cap rdfs:label ?capital .
        OPTIONAL {{ ?country dbo:populationTotal ?population }}
        FILTER(lang(?name) = 'en')
        FILTER(lang(?capital) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        capital = r.get("capital", {}).get("value", "")
        pop = r.get("population", {}).get("value", "")
        if name and capital:
            facts.append({"subject": name, "predicate": "CAPITAL_IS", "object": capital,
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
        if name and pop:
            facts.append({"subject": name, "predicate": "POPULATION", "object": str(pop),
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia countries: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_universities(limit: int = 500) -> list:
    """Fetch universities with locations and founding dates."""
    query = f"""
    SELECT DISTINCT ?name ?city ?established WHERE {{
        ?uni a dbo:University ;
             rdfs:label ?name .
        OPTIONAL {{ ?uni dbo:city ?c . ?c rdfs:label ?city . FILTER(lang(?city) = 'en') }}
        OPTIONAL {{ ?uni dbo:established ?established }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 4)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        city = r.get("city", {}).get("value", "")
        est = r.get("established", {}).get("value", "")
        if name and city:
            facts.append({"subject": name, "predicate": "LOCATED_IN", "object": city,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
        if name and est:
            facts.append({"subject": name, "predicate": "FOUNDED", "object": est[:10],
                          "layer": "temporal", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "University",
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia universities: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_films(limit: int = 500) -> list:
    """Fetch films with directors and years."""
    query = f"""
    SELECT DISTINCT ?name ?director ?year WHERE {{
        ?film a dbo:Film ;
              rdfs:label ?name .
        OPTIONAL {{ ?film dbo:director ?d . ?d rdfs:label ?director . FILTER(lang(?director) = 'en') }}
        OPTIONAL {{ ?film dbo:releaseDate ?year }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 2)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        director = r.get("director", {}).get("value", "")
        year = r.get("year", {}).get("value", "")
        if name and director:
            facts.append({"subject": name, "predicate": "DIRECTED_BY", "object": director,
                          "layer": "cultural", "provenance": PROVENANCE_DBPEDIA})
        if name and year:
            facts.append({"subject": name, "predicate": "RELEASED", "object": year[:10],
                          "layer": "temporal", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Film",
                          "layer": "cultural", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia films: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_books(limit: int = 500) -> list:
    """Fetch literary works with authors."""
    query = f"""
    SELECT DISTINCT ?name ?author WHERE {{
        ?book a dbo:Book ;
              rdfs:label ?name ;
              dbo:author ?a .
        ?a rdfs:label ?author .
        FILTER(lang(?name) = 'en')
        FILTER(lang(?author) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        author = r.get("author", {}).get("value", "")
        if name and author:
            facts.append({"subject": name, "predicate": "WRITTEN_BY", "object": author,
                          "layer": "cultural", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia books: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_albums(limit: int = 500) -> list:
    """Fetch music albums with artists."""
    query = f"""
    SELECT DISTINCT ?name ?artist WHERE {{
        ?album a dbo:Album ;
               rdfs:label ?name ;
               dbo:artist ?a .
        ?a rdfs:label ?artist .
        FILTER(lang(?name) = 'en')
        FILTER(lang(?artist) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        artist = r.get("artist", {}).get("value", "")
        if name and artist:
            facts.append({"subject": name, "predicate": "BY_ARTIST", "object": artist,
                          "layer": "cultural", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia albums: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_software(limit: int = 500) -> list:
    """Fetch software with developers and programming languages."""
    query = f"""
    SELECT DISTINCT ?name ?developer ?lang WHERE {{
        ?sw a dbo:Software ;
            rdfs:label ?name .
        OPTIONAL {{ ?sw dbo:developer ?d . ?d rdfs:label ?developer . FILTER(lang(?developer) = 'en') }}
        OPTIONAL {{ ?sw dbo:programmingLanguage ?pl . ?pl rdfs:label ?lang . FILTER(lang(?lang) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 2)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        dev = r.get("developer", {}).get("value", "")
        lang = r.get("lang", {}).get("value", "")
        if name and dev:
            facts.append({"subject": name, "predicate": "DEVELOPED_BY", "object": dev,
                          "layer": "procedural", "provenance": PROVENANCE_DBPEDIA})
        if name and lang:
            facts.append({"subject": name, "predicate": "WRITTEN_IN", "object": lang,
                          "layer": "procedural", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia software: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_events(limit: int = 500) -> list:
    """Fetch historical events with dates and locations."""
    query = f"""
    SELECT DISTINCT ?name ?date ?place WHERE {{
        ?event a dbo:Event ;
               rdfs:label ?name .
        OPTIONAL {{ ?event dbo:date ?date }}
        OPTIONAL {{ ?event dbo:place ?p . ?p rdfs:label ?place . FILTER(lang(?place) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 4)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        date = r.get("date", {}).get("value", "")
        place = r.get("place", {}).get("value", "")
        if name and date:
            facts.append({"subject": name, "predicate": "OCCURRED_ON", "object": date[:10],
                          "layer": "temporal", "provenance": PROVENANCE_DBPEDIA})
        if name and place:
            facts.append({"subject": name, "predicate": "OCCURRED_IN", "object": place,
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Historical Event",
                          "layer": "temporal", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia events: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_diseases(limit: int = 500) -> list:
    """Fetch diseases with symptoms and affected systems."""
    query = f"""
    SELECT DISTINCT ?name ?field WHERE {{
        ?disease a dbo:Disease ;
                 rdfs:label ?name .
        OPTIONAL {{ ?disease dbo:medicalSpecialty ?f . ?f rdfs:label ?field . FILTER(lang(?field) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 3)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        field = r.get("field", {}).get("value", "")
        if name and field:
            facts.append({"subject": name, "predicate": "SPECIALTY", "object": field,
                          "layer": "ecological", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Disease",
                          "layer": "ecological", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia diseases: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_compounds(limit: int = 500) -> list:
    """Fetch chemical compounds with formulas."""
    query = f"""
    SELECT DISTINCT ?name ?formula WHERE {{
        ?compound a dbo:ChemicalCompound ;
                  rdfs:label ?name .
        OPTIONAL {{ ?compound dbo:chemicalFormula ?formula }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 3)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        formula = r.get("formula", {}).get("value", "")
        if name and formula:
            facts.append({"subject": name, "predicate": "CHEMICAL_FORMULA", "object": formula,
                          "layer": "categorical", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Chemical Compound",
                          "layer": "categorical", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia compounds: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_celestial(limit: int = 500) -> list:
    """Fetch celestial bodies (planets, stars, galaxies)."""
    query = f"""
    SELECT DISTINCT ?name ?type WHERE {{
        ?body a dbo:CelestialBody ;
              rdfs:label ?name .
        OPTIONAL {{ ?body rdf:type ?type }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 2)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        if name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Celestial Body",
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia celestial: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_languages(limit: int = 500) -> list:
    """Fetch languages with language families."""
    query = f"""
    SELECT DISTINCT ?name ?family WHERE {{
        ?lang a dbo:Language ;
              rdfs:label ?name .
        OPTIONAL {{ ?lang dbo:languageFamily ?f . ?f rdfs:label ?family . FILTER(lang(?family) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 2)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        family = r.get("family", {}).get("value", "")
        if name and family:
            facts.append({"subject": name, "predicate": "LANGUAGE_FAMILY", "object": family,
                          "layer": "linguistic", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Language",
                          "layer": "linguistic", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia languages: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_scientists(limit: int = 500) -> list:
    """Fetch scientists with fields and awards."""
    query = f"""
    SELECT DISTINCT ?name ?field ?award WHERE {{
        ?person a dbo:Scientist ;
                rdfs:label ?name .
        OPTIONAL {{ ?person dbo:field ?f . ?f rdfs:label ?field . FILTER(lang(?field) = 'en') }}
        OPTIONAL {{ ?person dbo:award ?a . ?a rdfs:label ?award . FILTER(lang(?award) = 'en') }}
        FILTER(lang(?name) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        field = r.get("field", {}).get("value", "")
        award = r.get("award", {}).get("value", "")
        if name and field:
            facts.append({"subject": name, "predicate": "FIELD", "object": field,
                          "layer": "epistemic", "provenance": PROVENANCE_DBPEDIA})
        if name and award:
            facts.append({"subject": name, "predicate": "AWARDED", "object": award,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Scientist",
                          "layer": "epistemic", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia scientists: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_philosophers(limit: int = 500) -> list:
    """Fetch philosophers with eras and influences."""
    query = f"""
    SELECT DISTINCT ?name ?era ?influenced WHERE {{
        ?person a dbo:Philosopher ;
                rdfs:label ?name .
        OPTIONAL {{ ?person dbo:era ?e . ?e rdfs:label ?era . FILTER(lang(?era) = 'en') }}
        OPTIONAL {{ ?person dbo:influenced ?i . ?i rdfs:label ?influenced . FILTER(lang(?influenced) = 'en') }}
        FILTER(lang(?name) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        era = r.get("era", {}).get("value", "")
        influenced = r.get("influenced", {}).get("value", "")
        if name and era:
            facts.append({"subject": name, "predicate": "ERA", "object": era,
                          "layer": "temporal", "provenance": PROVENANCE_DBPEDIA})
        if name and influenced:
            facts.append({"subject": name, "predicate": "INFLUENCED", "object": influenced,
                          "layer": "epistemic", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Philosopher",
                          "layer": "epistemic", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia philosophers: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_athletes(limit: int = 500) -> list:
    """Fetch athletes with sports and teams."""
    query = f"""
    SELECT DISTINCT ?name ?sport WHERE {{
        ?person a dbo:Athlete ;
                rdfs:label ?name .
        OPTIONAL {{ ?person dbo:sport ?s . ?s rdfs:label ?sport . FILTER(lang(?sport) = 'en') }}
        FILTER(lang(?name) = 'en')
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        sport = r.get("sport", {}).get("value", "")
        if name and sport:
            facts.append({"subject": name, "predicate": "PLAYS", "object": sport,
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Athlete",
                          "layer": "social", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia athletes: {len(facts)} facts from {len(results)} results")
    return facts


def fetch_dbpedia_structures(limit: int = 500) -> list:
    """Fetch architectural structures with locations."""
    query = f"""
    SELECT DISTINCT ?name ?location WHERE {{
        ?struct a dbo:ArchitecturalStructure ;
                rdfs:label ?name .
        OPTIONAL {{ ?struct dbo:location ?l . ?l rdfs:label ?location . FILTER(lang(?location) = 'en') }}
        FILTER(lang(?name) = 'en')
        FILTER(STRLEN(?name) > 3)
    }} LIMIT {limit}
    """
    facts = []
    results = _sparql_dbpedia(query)
    for r in results:
        name = r.get("name", {}).get("value", "")
        location = r.get("location", {}).get("value", "")
        if name and location:
            facts.append({"subject": name, "predicate": "LOCATED_IN", "object": location,
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
        elif name:
            facts.append({"subject": name, "predicate": "IS_A", "object": "Architectural Structure",
                          "layer": "spatial", "provenance": PROVENANCE_DBPEDIA})
    logger.info(f"DBpedia structures: {len(facts)} facts from {len(results)} results")
    return facts


# ── All DBpedia Fetchers ──────────────────────────────────────

DBPEDIA_FETCHERS = [
    fetch_dbpedia_people,
    fetch_dbpedia_places,
    fetch_dbpedia_countries,
    fetch_dbpedia_achievements,
    fetch_dbpedia_species,
    fetch_dbpedia_organizations,
    fetch_dbpedia_universities,
    fetch_dbpedia_films,
    fetch_dbpedia_books,
    fetch_dbpedia_albums,
    fetch_dbpedia_software,
    fetch_dbpedia_events,
    fetch_dbpedia_diseases,
    fetch_dbpedia_compounds,
    fetch_dbpedia_celestial,
    fetch_dbpedia_languages,
    fetch_dbpedia_scientists,
    fetch_dbpedia_philosophers,
    fetch_dbpedia_athletes,
    fetch_dbpedia_structures,
]

def get_dbpedia_facts(limit: int = 2000) -> list:
    """Run all 20 DBpedia queries at scale."""
    all_facts = []
    for fetcher in DBPEDIA_FETCHERS:
        try:
            all_facts.extend(fetcher(limit))
            time.sleep(RATE_LIMIT)
        except Exception as e:
            logger.error(f"DBpedia fetcher {fetcher.__name__} error: {e}")
    logger.info(f"Total DBpedia facts: {len(all_facts)}")
    return all_facts


# ═══════════════════════════════════════════════════════════════
# 2. ConceptNet API — Commonsense Reasoning
# ═══════════════════════════════════════════════════════════════

CONCEPTNET_API = "http://api.conceptnet.io"

# Map ConceptNet relations to KG layers
CONCEPTNET_LAYER_MAP = {
    "IsA": "categorical",
    "PartOf": "categorical",
    "HasA": "categorical",
    "UsedFor": "procedural",
    "CapableOf": "procedural",
    "AtLocation": "spatial",
    "Causes": "causal",
    "HasPrerequisite": "causal",
    "HasFirstSubevent": "temporal",
    "HasLastSubevent": "temporal",
    "MotivatedByGoal": "motivational",
    "CausesDesire": "motivational",
    "CreatedBy": "causal",
    "SymbolOf": "symbolic",
    "DefinedAs": "semantic",
    "SimilarTo": "analogical",
    "Antonym": "semantic",
    "DerivedFrom": "linguistic",
    "RelatedTo": "semantic",
    "HasProperty": "categorical",
    "MadeOf": "categorical",
    "ReceivesAction": "procedural",
}


def fetch_conceptnet_edges(concepts: list, limit_per: int = 50) -> list:
    """Fetch commonsense edges for a list of concepts.
    Includes fail-fast: aborts after 3 consecutive failures (API down)."""
    facts = []
    seen = set()
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    
    for i, concept in enumerate(concepts):
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(f"ConceptNet: {MAX_CONSECUTIVE_FAILURES} consecutive failures — API appears down, skipping remaining {len(concepts) - i} concepts")
            break
        
        slug = concept.lower().replace(" ", "_")
        url = f"{CONCEPTNET_API}/c/en/{slug}?limit={limit_per}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ErnOS-KG/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                consecutive_failures = 0  # Reset on success
                concept_count = 0
                
                for edge in data.get("edges", []):
                    rel = edge.get("rel", {}).get("label", "RelatedTo")
                    start_label = edge.get("start", {}).get("label", "")
                    end_label = edge.get("end", {}).get("label", "")
                    weight = edge.get("weight", 1.0)
                    
                    # Filter: English only, reasonable weight
                    start_lang = edge.get("start", {}).get("language", "en")
                    end_lang = edge.get("end", {}).get("language", "en")
                    if start_lang != "en" or end_lang != "en":
                        continue
                    if weight < 1.0:
                        continue
                    
                    key = (start_label, rel, end_label)
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    layer = CONCEPTNET_LAYER_MAP.get(rel, "semantic")
                    prov = {**PROVENANCE_CONCEPTNET, "weight": round(weight, 2)}
                    
                    facts.append({
                        "subject": start_label,
                        "predicate": rel.upper().replace(" ", "_"),
                        "object": end_label,
                        "layer": layer,
                        "provenance": prov
                    })
                    concept_count += 1
                
                logger.info(f"  ConceptNet '{concept}': {concept_count} edges [{i+1}/{len(concepts)}]")
                    
        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"ConceptNet error for '{concept}' ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}")
        
        time.sleep(RATE_LIMIT)
    
    logger.info(f"ConceptNet: {len(facts)} commonsense facts from {len(concepts)} concepts")
    return facts


# Core concepts to seed commonsense knowledge about
SEED_CONCEPTS = [
    # Cognition & Mind
    "mind", "thought", "memory", "learning", "intelligence", "consciousness",
    "emotion", "creativity", "language", "reason", "imagination", "attention",
    # Science
    "gravity", "energy", "atom", "evolution", "photosynthesis", "DNA",
    "quantum", "relativity", "entropy", "electricity", "magnetism",
    # Technology
    "computer", "internet", "algorithm", "database", "programming", "robot",
    "artificial intelligence", "machine learning", "neural network",
    # Nature
    "water", "fire", "earth", "air", "sun", "moon", "star", "ocean",
    "forest", "mountain", "river", "rain", "wind", "snow",
    # Society
    "democracy", "justice", "freedom", "art", "music", "philosophy",
    "economics", "history", "culture", "religion", "science", "education",
    # Human
    "love", "fear", "happiness", "sadness", "anger", "trust",
    "friendship", "family", "communication", "cooperation",
    # Abstract
    "time", "space", "truth", "beauty", "knowledge", "wisdom",
    "power", "change", "symmetry", "chaos", "order", "infinity",
]


def get_conceptnet_facts() -> list:
    return fetch_conceptnet_edges(SEED_CONCEPTS, limit_per=30)


# ═══════════════════════════════════════════════════════════════
# 3. RSS News Feeds — Current Events
# ═══════════════════════════════════════════════════════════════

RSS_FEEDS = {
    "tech": [
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    ],
    "science": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        "https://www.newscientist.com/section/news/feed/",
        "https://phys.org/rss-feed/",
    ],
    "world": [
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ],
    "ai": [
        "https://blog.google/technology/ai/rss/",
        "https://openai.com/blog/rss.xml",
        "https://machinelearningmastery.com/feed/",
    ],
}


def fetch_rss_facts(max_per_feed: int = 20) -> list:
    """Fetch news articles from RSS feeds and extract facts."""
    import feedparser
    
    facts = []
    seen = set()
    
    for category, urls in RSS_FEEDS.items():
        for feed_url in urls:
            try:
                # Pre-fetch with timeout (feedparser has no native timeout)
                req = urllib.request.Request(feed_url, headers={"User-Agent": "ErnOS-KG-Seed/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_xml = resp.read()
                feed = feedparser.parse(raw_xml)
                feed_title = feed.feed.get("title", feed_url)
                entry_count = 0
                
                for entry in feed.entries[:max_per_feed]:
                    title = entry.get("title", "").strip()
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    
                    published = entry.get("published", "")
                    link = entry.get("link", "")
                    
                    prov = {**PROVENANCE_RSS, "url": link, "feed": feed_title}
                    
                    # Article → Category
                    facts.append({
                        "subject": title,
                        "predicate": "CATEGORIZED_AS",
                        "object": category.title(),
                        "layer": "categorical",
                        "provenance": prov
                    })
                    
                    # Article → Source
                    facts.append({
                        "subject": title,
                        "predicate": "PUBLISHED_BY",
                        "object": feed_title,
                        "layer": "social",
                        "provenance": prov
                    })
                    
                    # Article → Time
                    if published:
                        facts.append({
                            "subject": title,
                            "predicate": "PUBLISHED_ON",
                            "object": published[:25],
                            "layer": "temporal",
                            "provenance": prov
                        })
                    entry_count += 1
                
                logger.info(f"  RSS '{feed_title}': {entry_count} articles")
                    
            except Exception as e:
                logger.warning(f"RSS feed error {feed_url}: {e}")
            
            time.sleep(0.5)
    
    logger.info(f"RSS: {len(facts)} news facts from {len(RSS_FEEDS)} categories")
    return facts


# ═══════════════════════════════════════════════════════════════
# 4. DuckDuckGo Topic Discovery
# ═══════════════════════════════════════════════════════════════

DISCOVERY_TOPICS = [
    # AI & Computing
    "artificial general intelligence research 2026",
    "large language model architecture breakthroughs",
    "quantum computing advances",
    "neuromorphic computing",
    "autonomous AI systems",
    "reinforcement learning from human feedback",
    "artificial consciousness research",
    "computer vision deep learning",
    "natural language understanding",
    "AI alignment safety research",
    "federated learning privacy AI",
    "generative adversarial networks applications",
    # Science & Physics
    "CRISPR gene editing latest",
    "fusion energy progress",
    "dark matter detection",
    "exoplanet discoveries",
    "neuroscience consciousness research",
    "gravitational wave astronomy",
    "particle physics standard model",
    "quantum entanglement experiments",
    "string theory evidence",
    "dark energy accelerating expansion",
    "superconductor room temperature",
    "antimatter research",
    # Biology & Medicine
    "synthetic biology applications",
    "microbiome human health",
    "epigenetics gene expression",
    "stem cell therapy advances",
    "immunotherapy cancer treatment",
    "mRNA vaccine technology",
    "antibiotic resistance solutions",
    "longevity aging research",
    "brain organoid development",
    "marine biology deep sea discoveries",
    # Philosophy & Mind
    "philosophy of mind artificial consciousness",
    "computational theory of mind",
    "Chinese room argument",
    "hard problem of consciousness",
    "panpsychism consciousness theory",
    "philosophy of language meaning",
    "ethics of artificial intelligence",
    "existentialism contemporary",
    "epistemology justified belief",
    "philosophy of science paradigm shifts",
    # Mathematics
    "Riemann hypothesis progress",
    "topology applications physics",
    "category theory computer science",
    "information theory entropy",
    "game theory applications",
    "chaos theory complex systems",
    "number theory prime gaps",
    "abstract algebra applications",
    # History & Civilization
    "ancient civilizations archaeology",
    "Renaissance scientific revolution",
    "industrial revolution impact technology",
    "Cold War space race",
    "Silk Road trade history",
    "French Revolution enlightenment",
    "Roman Empire rise fall",
    "Mesopotamia cradle civilization",
    "World War II pivotal battles",
    "decolonization 20th century",
    # Technology & Engineering
    "brain computer interface",
    "robotics advances 2026",
    "decentralized internet",
    "nuclear fusion reactor design",
    "space exploration Mars colonization",
    "renewable energy storage solutions",
    "autonomous vehicles self driving",
    "5G 6G telecommunications",
    "nanotechnology applications",
    "3D bioprinting organs",
    # Geography & Earth Science
    "climate change tipping points",
    "plate tectonics earthquakes",
    "ocean currents climate impact",
    "biodiversity hotspots conservation",
    "permafrost melting methane",
    "volcanic eruptions prediction",
    # Arts & Culture
    "history of classical music",
    "modern art movements 21st century",
    "world mythology comparative",
    "evolution of cinema",
    "architecture sustainable design",
    "literature Nobel Prize winners",
    # Economics & Society
    "cryptocurrency decentralized finance",
    "universal basic income experiments",
    "global supply chain economics",
    "behavioral economics cognitive biases",
    "urbanization megacities",
    # Psychology
    "cognitive psychology memory formation",
    "evolutionary psychology human behavior",
    "positive psychology wellbeing",
    "developmental psychology child cognition",
    "social psychology group dynamics",
]


def fetch_ddg_discovery_facts(topics: list = None, max_results: int = 5) -> list:
    """Discover and extract facts via DuckDuckGo search → browse → extract."""
    from ddgs import DDGS
    
    if topics is None:
        topics = DISCOVERY_TOPICS
    
    facts = []
    seen = set()
    
    with DDGS() as ddgs:
        for topic in topics:
            try:
                results = list(ddgs.text(topic, max_results=max_results))
                for r in results:
                    title = r.get("title", "").strip()
                    body = r.get("body", "").strip()
                    url = r.get("href", "")
                    
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    
                    prov = {**PROVENANCE_DDG, "url": url, "query": topic}
                    
                    # Search result → Topic
                    facts.append({
                        "subject": title,
                        "predicate": "RELATES_TO",
                        "object": topic,
                        "layer": "epistemic",
                        "provenance": prov
                    })
                    
                    # Try extracting key entities from body text
                    entities = _extract_simple_entities(body)
                    for entity, entity_type in entities:
                        facts.append({
                            "subject": entity,
                            "predicate": f"MENTIONED_IN",
                            "object": title,
                            "layer": _entity_type_to_layer(entity_type),
                            "provenance": prov
                        })
                    
            except Exception as e:
                logger.warning(f"DDG discovery error for '{topic}': {e}")
            
            time.sleep(RATE_LIMIT)
    
    logger.info(f"DDG discovery: {len(facts)} facts from {len(topics)} topics")
    return facts


# ═══════════════════════════════════════════════════════════════
# 5. Trafilatura Article Extraction
# ═══════════════════════════════════════════════════════════════

# High-value article URLs for deep extraction
ARTICLE_URLS = [
    # ── AI & Computing (30) ────────────────────────────
    "https://en.wikipedia.org/wiki/Artificial_general_intelligence",
    "https://en.wikipedia.org/wiki/Hard_problem_of_consciousness",
    "https://en.wikipedia.org/wiki/Chinese_room",
    "https://en.wikipedia.org/wiki/Computational_theory_of_mind",
    "https://en.wikipedia.org/wiki/Neural_network_(machine_learning)",
    "https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Deep_learning",
    "https://en.wikipedia.org/wiki/Natural_language_processing",
    "https://en.wikipedia.org/wiki/Computer_vision",
    "https://en.wikipedia.org/wiki/Reinforcement_learning",
    "https://en.wikipedia.org/wiki/Turing_test",
    "https://en.wikipedia.org/wiki/Expert_system",
    "https://en.wikipedia.org/wiki/Genetic_algorithm",
    "https://en.wikipedia.org/wiki/Computer_science",
    "https://en.wikipedia.org/wiki/Algorithm",
    "https://en.wikipedia.org/wiki/Data_structure",
    "https://en.wikipedia.org/wiki/Operating_system",
    "https://en.wikipedia.org/wiki/Database",
    "https://en.wikipedia.org/wiki/Cryptography",
    "https://en.wikipedia.org/wiki/Internet",
    "https://en.wikipedia.org/wiki/World_Wide_Web",
    "https://en.wikipedia.org/wiki/Cloud_computing",
    "https://en.wikipedia.org/wiki/Blockchain",
    "https://en.wikipedia.org/wiki/Cybersecurity",
    "https://en.wikipedia.org/wiki/Programming_language",
    "https://en.wikipedia.org/wiki/Software_engineering",
    "https://en.wikipedia.org/wiki/Open-source_software",
    "https://en.wikipedia.org/wiki/Robotics",
    # ── Physics (20) ──────────────────────────────────
    "https://en.wikipedia.org/wiki/Quantum_computing",
    "https://en.wikipedia.org/wiki/Nuclear_fusion",
    "https://en.wikipedia.org/wiki/Dark_matter",
    "https://en.wikipedia.org/wiki/Entropy",
    "https://en.wikipedia.org/wiki/Quantum_mechanics",
    "https://en.wikipedia.org/wiki/General_relativity",
    "https://en.wikipedia.org/wiki/Special_relativity",
    "https://en.wikipedia.org/wiki/Standard_Model",
    "https://en.wikipedia.org/wiki/Higgs_boson",
    "https://en.wikipedia.org/wiki/Black_hole",
    "https://en.wikipedia.org/wiki/Big_Bang",
    "https://en.wikipedia.org/wiki/String_theory",
    "https://en.wikipedia.org/wiki/Thermodynamics",
    "https://en.wikipedia.org/wiki/Electromagnetism",
    "https://en.wikipedia.org/wiki/Wave%E2%80%93particle_duality",
    "https://en.wikipedia.org/wiki/Superconductivity",
    "https://en.wikipedia.org/wiki/Quantum_entanglement",
    "https://en.wikipedia.org/wiki/Speed_of_light",
    "https://en.wikipedia.org/wiki/Antimatter",
    "https://en.wikipedia.org/wiki/Plasma_(physics)",
    # ── Chemistry (10) ────────────────────────────────
    "https://en.wikipedia.org/wiki/Periodic_table",
    "https://en.wikipedia.org/wiki/Chemical_bond",
    "https://en.wikipedia.org/wiki/Organic_chemistry",
    "https://en.wikipedia.org/wiki/Biochemistry",
    "https://en.wikipedia.org/wiki/Polymer",
    "https://en.wikipedia.org/wiki/Catalysis",
    "https://en.wikipedia.org/wiki/Electrochemistry",
    "https://en.wikipedia.org/wiki/Chemical_reaction",
    "https://en.wikipedia.org/wiki/Stoichiometry",
    "https://en.wikipedia.org/wiki/Nanotechnology",
    # ── Biology & Life Sciences (20) ──────────────────
    "https://en.wikipedia.org/wiki/CRISPR_gene_editing",
    "https://en.wikipedia.org/wiki/DNA",
    "https://en.wikipedia.org/wiki/Ecosystem",
    "https://en.wikipedia.org/wiki/Neuroscience",
    "https://en.wikipedia.org/wiki/Evolutionary_biology",
    "https://en.wikipedia.org/wiki/Photosynthesis",
    "https://en.wikipedia.org/wiki/Cell_(biology)",
    "https://en.wikipedia.org/wiki/Genetics",
    "https://en.wikipedia.org/wiki/Protein",
    "https://en.wikipedia.org/wiki/Virus",
    "https://en.wikipedia.org/wiki/Bacteria",
    "https://en.wikipedia.org/wiki/Human_genome",
    "https://en.wikipedia.org/wiki/Biodiversity",
    "https://en.wikipedia.org/wiki/Ecology",
    "https://en.wikipedia.org/wiki/Stem_cell",
    "https://en.wikipedia.org/wiki/Microorganism",
    "https://en.wikipedia.org/wiki/Taxonomy_(biology)",
    "https://en.wikipedia.org/wiki/Mitochondrion",
    "https://en.wikipedia.org/wiki/Endocrine_system",
    "https://en.wikipedia.org/wiki/Immune_system",
    # ── Medicine (10) ─────────────────────────────────
    "https://en.wikipedia.org/wiki/Vaccine",
    "https://en.wikipedia.org/wiki/Antibiotic",
    "https://en.wikipedia.org/wiki/Surgery",
    "https://en.wikipedia.org/wiki/Anesthesia",
    "https://en.wikipedia.org/wiki/Epidemiology",
    "https://en.wikipedia.org/wiki/Oncology",
    "https://en.wikipedia.org/wiki/Cardiology",
    "https://en.wikipedia.org/wiki/Neurology",
    "https://en.wikipedia.org/wiki/Psychiatry",
    "https://en.wikipedia.org/wiki/Public_health",
    # ── Astronomy & Space (10) ────────────────────────
    "https://en.wikipedia.org/wiki/Exoplanet",
    "https://en.wikipedia.org/wiki/Solar_System",
    "https://en.wikipedia.org/wiki/Milky_Way",
    "https://en.wikipedia.org/wiki/Mars",
    "https://en.wikipedia.org/wiki/International_Space_Station",
    "https://en.wikipedia.org/wiki/Hubble_Space_Telescope",
    "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope",
    "https://en.wikipedia.org/wiki/Neutron_star",
    "https://en.wikipedia.org/wiki/Galaxy",
    "https://en.wikipedia.org/wiki/Asteroid",
    # ── Philosophy (15) ───────────────────────────────
    "https://en.wikipedia.org/wiki/Philosophy_of_mind",
    "https://en.wikipedia.org/wiki/Qualia",
    "https://en.wikipedia.org/wiki/Free_will",
    "https://en.wikipedia.org/wiki/Theory_of_knowledge",
    "https://en.wikipedia.org/wiki/Ethics",
    "https://en.wikipedia.org/wiki/Existentialism",
    "https://en.wikipedia.org/wiki/Utilitarianism",
    "https://en.wikipedia.org/wiki/Epistemology",
    "https://en.wikipedia.org/wiki/Metaphysics",
    "https://en.wikipedia.org/wiki/Logic",
    "https://en.wikipedia.org/wiki/Phenomenology_(philosophy)",
    "https://en.wikipedia.org/wiki/Stoicism",
    "https://en.wikipedia.org/wiki/Philosophy_of_science",
    "https://en.wikipedia.org/wiki/Social_contract",
    "https://en.wikipedia.org/wiki/Nihilism",
    # ── Mathematics (15) ──────────────────────────────
    "https://en.wikipedia.org/wiki/Graph_theory",
    "https://en.wikipedia.org/wiki/Category_theory",
    "https://en.wikipedia.org/wiki/Information_theory",
    "https://en.wikipedia.org/wiki/Calculus",
    "https://en.wikipedia.org/wiki/Linear_algebra",
    "https://en.wikipedia.org/wiki/Number_theory",
    "https://en.wikipedia.org/wiki/Topology",
    "https://en.wikipedia.org/wiki/Statistics",
    "https://en.wikipedia.org/wiki/Probability_theory",
    "https://en.wikipedia.org/wiki/Game_theory",
    "https://en.wikipedia.org/wiki/Set_theory",
    "https://en.wikipedia.org/wiki/Abstract_algebra",
    "https://en.wikipedia.org/wiki/Differential_equation",
    "https://en.wikipedia.org/wiki/Fractal",
    "https://en.wikipedia.org/wiki/Chaos_theory",
    # ── History (20) ──────────────────────────────────
    "https://en.wikipedia.org/wiki/Ancient_Egypt",
    "https://en.wikipedia.org/wiki/Roman_Empire",
    "https://en.wikipedia.org/wiki/Renaissance",
    "https://en.wikipedia.org/wiki/Industrial_Revolution",
    "https://en.wikipedia.org/wiki/French_Revolution",
    "https://en.wikipedia.org/wiki/World_War_I",
    "https://en.wikipedia.org/wiki/World_War_II",
    "https://en.wikipedia.org/wiki/Cold_War",
    "https://en.wikipedia.org/wiki/Silk_Road",
    "https://en.wikipedia.org/wiki/Ancient_Greece",
    "https://en.wikipedia.org/wiki/Ottoman_Empire",
    "https://en.wikipedia.org/wiki/Mongol_Empire",
    "https://en.wikipedia.org/wiki/Age_of_Discovery",
    "https://en.wikipedia.org/wiki/Enlightenment_(philosophy)",
    "https://en.wikipedia.org/wiki/Decolonization",
    "https://en.wikipedia.org/wiki/Space_Race",
    "https://en.wikipedia.org/wiki/Civil_rights_movement",
    "https://en.wikipedia.org/wiki/Scientific_Revolution",
    "https://en.wikipedia.org/wiki/Feudalism",
    "https://en.wikipedia.org/wiki/Bronze_Age",
    # ── Geography & Earth Science (10) ────────────────
    "https://en.wikipedia.org/wiki/Climate_change",
    "https://en.wikipedia.org/wiki/Plate_tectonics",
    "https://en.wikipedia.org/wiki/Water_cycle",
    "https://en.wikipedia.org/wiki/Volcano",
    "https://en.wikipedia.org/wiki/Ocean_current",
    "https://en.wikipedia.org/wiki/Atmosphere_of_Earth",
    "https://en.wikipedia.org/wiki/Glacier",
    "https://en.wikipedia.org/wiki/Rainforest",
    "https://en.wikipedia.org/wiki/Coral_reef",
    "https://en.wikipedia.org/wiki/Continental_drift",
    # ── Engineering (10) ──────────────────────────────
    "https://en.wikipedia.org/wiki/Nuclear_power",
    "https://en.wikipedia.org/wiki/Renewable_energy",
    "https://en.wikipedia.org/wiki/Semiconductor",
    "https://en.wikipedia.org/wiki/Integrated_circuit",
    "https://en.wikipedia.org/wiki/3D_printing",
    "https://en.wikipedia.org/wiki/Aerospace_engineering",
    "https://en.wikipedia.org/wiki/Civil_engineering",
    "https://en.wikipedia.org/wiki/Genetic_engineering",
    "https://en.wikipedia.org/wiki/Telecommunications",
    "https://en.wikipedia.org/wiki/Materials_science",
    # ── Psychology (10) ───────────────────────────────
    "https://en.wikipedia.org/wiki/Cognitive_psychology",
    "https://en.wikipedia.org/wiki/Developmental_psychology",
    "https://en.wikipedia.org/wiki/Social_psychology",
    "https://en.wikipedia.org/wiki/Consciousness",
    "https://en.wikipedia.org/wiki/Memory",
    "https://en.wikipedia.org/wiki/Intelligence",
    "https://en.wikipedia.org/wiki/Emotion",
    "https://en.wikipedia.org/wiki/Creativity",
    "https://en.wikipedia.org/wiki/Motivation",
    "https://en.wikipedia.org/wiki/Learning",
    # ── Economics & Political Science (10) ────────────
    "https://en.wikipedia.org/wiki/Economics",
    "https://en.wikipedia.org/wiki/Capitalism",
    "https://en.wikipedia.org/wiki/Globalization",
    "https://en.wikipedia.org/wiki/Democracy",
    "https://en.wikipedia.org/wiki/Human_rights",
    "https://en.wikipedia.org/wiki/Supply_and_demand",
    "https://en.wikipedia.org/wiki/Monetary_policy",
    "https://en.wikipedia.org/wiki/Inflation",
    "https://en.wikipedia.org/wiki/International_trade",
    "https://en.wikipedia.org/wiki/United_Nations",
    # ── Arts & Music (10) ─────────────────────────────
    "https://en.wikipedia.org/wiki/Classical_music",
    "https://en.wikipedia.org/wiki/Jazz",
    "https://en.wikipedia.org/wiki/Opera",
    "https://en.wikipedia.org/wiki/Painting",
    "https://en.wikipedia.org/wiki/Sculpture",
    "https://en.wikipedia.org/wiki/Photography",
    "https://en.wikipedia.org/wiki/Film",
    "https://en.wikipedia.org/wiki/Theatre",
    "https://en.wikipedia.org/wiki/Ballet",
    "https://en.wikipedia.org/wiki/Architecture",
    # ── Literature (10) ───────────────────────────────
    "https://en.wikipedia.org/wiki/Novel",
    "https://en.wikipedia.org/wiki/Poetry",
    "https://en.wikipedia.org/wiki/Shakespeare",
    "https://en.wikipedia.org/wiki/Epic_poetry",
    "https://en.wikipedia.org/wiki/Science_fiction",
    "https://en.wikipedia.org/wiki/Mythology",
    "https://en.wikipedia.org/wiki/Folklore",
    "https://en.wikipedia.org/wiki/Literary_criticism",
    "https://en.wikipedia.org/wiki/Rhetoric",
    "https://en.wikipedia.org/wiki/Linguistics",
]


def fetch_article_facts(urls: list = None, max_entities_per: int = 30) -> list:
    """Extract clean text from URLs using trafilatura, then extract entities."""
    import trafilatura
    
    if urls is None:
        urls = ARTICLE_URLS
    
    facts = []
    
    for url in urls:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                continue
            
            text = trafilatura.extract(downloaded, include_links=False, include_comments=False)
            if not text or len(text) < 100:
                continue
            
            # Extract article title from URL
            title = url.split("/")[-1].replace("_", " ").title()
            
            prov = {**PROVENANCE_ARTICLE, "url": url}
            
            # Extract entities and relationships from article text
            entities = _extract_simple_entities(text[:5000])
            
            for entity, entity_type in entities[:max_entities_per]:
                layer = _entity_type_to_layer(entity_type)
                facts.append({
                    "subject": entity,
                    "predicate": "DESCRIBED_IN",
                    "object": title,
                    "layer": layer,
                    "provenance": prov
                })
            
            # Extract key sentences for relationship mining
            relationships = _extract_relationships(text[:5000], title)
            facts.extend(relationships)
            
            logger.info(f"Article '{title}': {len(entities)} entities, {len(relationships)} rels")
            
        except Exception as e:
            logger.warning(f"Article extraction error {url}: {e}")
        
        time.sleep(RATE_LIMIT)
    
    logger.info(f"Articles: {len(facts)} total facts from {len(urls)} URLs")
    return facts


# ═══════════════════════════════════════════════════════════════
# Entity Extraction Helpers (Regex-based, no LLM needed)
# ═══════════════════════════════════════════════════════════════

def _extract_simple_entities(text: str) -> list:
    """
    Extract named entities from text using regex patterns.
    Returns list of (entity_name, entity_type) tuples.
    """
    entities = []
    seen = set()
    
    # Capitalized multi-word names (Title Case sequences)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        name = match.group(1).strip()
        if name not in seen and len(name) > 4 and len(name) < 60:
            seen.add(name)
            entities.append((name, "named_entity"))
    
    # Technical terms in parentheses or after "is a/an"
    for match in re.finditer(r'(?:is (?:a|an|the)) ([A-Za-z][A-Za-z\s]+?)(?:\.|,|\))', text):
        term = match.group(1).strip()
        if term not in seen and 3 < len(term) < 50:
            seen.add(term)
            entities.append((term, "concept"))
    
    # Years
    for match in re.finditer(r'\b((?:19|20)\d{2})\b', text):
        year = match.group(1)
        if year not in seen:
            seen.add(year)
            entities.append((year, "date"))
    
    # Quoted terms
    for match in re.finditer(r'"([A-Za-z][A-Za-z\s]+?)"', text):
        term = match.group(1).strip()
        if term not in seen and 3 < len(term) < 50:
            seen.add(term)
            entities.append((term, "quoted_concept"))
    
    return entities


def _extract_relationships(text: str, article_title: str) -> list:
    """Extract simple subject-verb-object relationships from text."""
    facts = []
    seen = set()
    
    # Pattern: "X is a Y" / "X is the Y"
    for match in re.finditer(r'([A-Z][A-Za-z\s]{2,30}) (?:is|are|was|were) (?:a|an|the)\s+([A-Za-z][A-Za-z\s]{2,40}?)(?:\.|,|;)', text):
        subj = match.group(1).strip()
        obj = match.group(2).strip()
        key = (subj, "IS_A", obj)
        if key not in seen and len(subj) > 2 and len(obj) > 2:
            seen.add(key)
            facts.append({
                "subject": subj,
                "predicate": "IS_A",
                "object": obj,
                "layer": "categorical",
                "provenance": {**PROVENANCE_ARTICLE, "context": article_title}
            })
    
    # Pattern: "X developed/invented/created Y"
    for match in re.finditer(r'([A-Z][A-Za-z\s]{2,30}) (?:developed|invented|created|discovered|proposed)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]{2,40}?)(?:\.|,|;)', text):
        subj = match.group(1).strip()
        obj = match.group(2).strip()
        key = (subj, "CREATED", obj)
        if key not in seen and len(subj) > 2 and len(obj) > 2:
            seen.add(key)
            facts.append({
                "subject": subj,
                "predicate": "CREATED",
                "object": obj,
                "layer": "causal",
                "provenance": {**PROVENANCE_ARTICLE, "context": article_title}
            })
    
    # Pattern: "X uses/requires/involves Y"
    for match in re.finditer(r'([A-Z][A-Za-z\s]{2,30}) (?:uses|requires|involves|employs|utilizes)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]{2,40}?)(?:\.|,|;)', text):
        subj = match.group(1).strip()
        obj = match.group(2).strip()
        key = (subj, "USES", obj)
        if key not in seen and len(subj) > 2 and len(obj) > 2:
            seen.add(key)
            facts.append({
                "subject": subj,
                "predicate": "USES",
                "object": obj,
                "layer": "procedural",
                "provenance": {**PROVENANCE_ARTICLE, "context": article_title}
            })
    
    return facts


def _entity_type_to_layer(entity_type: str) -> str:
    """Map entity type to cognitive layer."""
    mapping = {
        "named_entity": "social",
        "concept": "semantic",
        "date": "temporal",
        "quoted_concept": "semantic",      # was epistemic — most quoted concepts are general knowledge
        "organization": "social",
        "location": "spatial",
        "person": "social",
        "event": "experiential",
        "theory": "epistemic",             # actual epistemic: theories, evidence, methodology
        "methodology": "epistemic",
        "evidence": "epistemic",
        "artwork": "aesthetic",
        "art_form": "aesthetic",
        "species": "ecological",
        "chemical": "categorical",
        "technology": "procedural",
        "emotion": "emotional",
        "value": "moral",
        "tradition": "cultural",
    }
    return mapping.get(entity_type, "semantic")


# ═══════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════

SOURCE_FETCHERS = {
    "dbpedia": get_dbpedia_facts,
    "conceptnet": get_conceptnet_facts,
    "rss": fetch_rss_facts,
    "ddg": fetch_ddg_discovery_facts,
    "articles": fetch_article_facts,
}


def get_web_crawl_facts(sources: list = None, limit: int = 300) -> list:
    """
    Run selected or all web crawl sources.
    
    Args:
        sources: List of source names, or None for all
        limit: Max results per query (applies to DBpedia)
    """
    if sources is None:
        sources = list(SOURCE_FETCHERS.keys())
    
    all_facts = []
    for source in sources:
        fetcher = SOURCE_FETCHERS.get(source)
        if not fetcher:
            logger.warning(f"Unknown source: {source}")
            continue
        
        logger.info(f"═══ Running {source.upper()} ═══")
        try:
            if source == "dbpedia":
                facts = fetcher(limit=limit)
            else:
                facts = fetcher()
            all_facts.extend(facts)
            logger.info(f"  → {len(facts)} facts from {source}")
        except Exception as e:
            logger.error(f"  → {source} FAILED: {e}")
    
    # Deduplicate
    seen = set()
    unique = []
    for f in all_facts:
        key = (f["subject"], f["predicate"], f["object"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    
    logger.info(f"Total web crawl: {len(unique)} unique facts (from {len(all_facts)} raw)")
    return unique


# ═══════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════

def run_seed(graph, sources: list = None, limit: int = 300, dry_run: bool = False):
    """Crawl the internet and seed facts into KG."""
    facts = get_web_crawl_facts(sources=sources, limit=limit)
    
    if dry_run:
        print(f"\n[DRY RUN] Would seed {len(facts)} web crawl facts")
        # Show source breakdown
        by_source = {}
        for f in facts:
            src = f["provenance"].get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {src}: {count}")
        return {"fetched": len(facts), "seeded": 0}
    
    result = graph.bulk_seed(facts)
    return {**result, "fetched": len(facts)}


if __name__ == "__main__":
    import sys
    import argparse
    
    sys.path.insert(0, ".")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Full-scale web crawl seed")
    parser.add_argument("--source", type=str, default="all",
                        help="Source: all, dbpedia, conceptnet, rss, ddg, articles")
    parser.add_argument("--limit", type=int, default=300,
                        help="Max results per DBpedia query")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch without seeding")
    args = parser.parse_args()
    
    sources = None if args.source == "all" else [args.source]
    
    if args.dry_run:
        run_seed(None, sources=sources, limit=args.limit, dry_run=True)
    else:
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
        try:
            result = run_seed(kg, sources=sources, limit=args.limit)
            print(f"\n✅ Web crawl seed complete: {result}")
        finally:
            kg.close()
