"""
ResearchAbility — Delegates research to a full Agent via AgentSpawner.

Previously did a simple search_web + LLM synthesis; now spawns a proper
research agent with full tool access for higher-quality results.

After research completes, extracts structured KG triples from the report
and stores them via the OntologistAbility for full validation/scoring.
"""
from ..base import BaseAbility
import json
import logging

logger = logging.getLogger("Lobe.Interaction.Researcher")


class ResearchAbility(BaseAbility):
    """
    Web Search & Synthesis — powered by AgentSpawner.
    """
    async def execute(self, query: str):
        logger.info(f"Researcher delegating to agent: {query}")

        try:
            from src.agents.spawner import AgentSpawner, AgentSpec

            spec = AgentSpec(
                task=(
                    f"Conduct comprehensive, multi-angle research on the following topic:\n\n"
                    f"**{query}**\n\n"
                    f"Instructions:\n"
                    f"1. Start with broad web searches to establish the landscape.\n"
                    f"2. Browse the most relevant pages for detailed information.\n"
                    f"3. Search from multiple angles — different perspectives, controversies, recent developments.\n"
                    f"4. Cross-reference findings across sources.\n"
                    f"5. Produce a comprehensive markdown report with:\n"
                    f"   - Executive summary\n"
                    f"   - Key findings organized by theme\n"
                    f"   - Sources cited inline\n"
                    f"   - Areas of uncertainty or conflicting information noted\n\n"
                    f"Be thorough. Use at least 5 different searches and browse at least 3 key pages."
                ),
                max_steps=50,
                timeout=1200,
                scope="CORE",
                user_id="CORE",
            )

            result = await AgentSpawner.spawn(spec, self.bot)

            if result.status.value == "completed" and result.output:
                report = result.output
            else:
                report = f"Research agent failed: {result.error or 'Unknown error'}"

        except Exception as e:
            logger.error(f"Agent-based research failed, falling back: {e}")
            # Fallback to simple search if spawner fails
            from src.tools.registry import ToolRegistry
            raw_results = await ToolRegistry.execute("search_web", query)
            report = f"Basic Search Results:\n{raw_results}"

        # Knowledge Graph extraction (best-effort)
        try:
            await self._extract_and_store_knowledge(query, report)
        except Exception as e:
            logger.warning(f"KG extraction warning: {e}")

        return f"Research Findings:\n{report}"

    async def _extract_and_store_knowledge(self, topic: str, report: str):
        """
        Extracts structured knowledge triples from the research report
        and stores each one via the OntologistAbility for full
        validation, confidence scoring, and contradiction checking.
        """
        logger.info(f"Extracting KG triples from research on: {topic}")

        try:
            from src.bot import globals

            if not (globals.bot and globals.bot.cerebrum):
                logger.warning("KG extraction skipped: bot or cerebrum not available")
                return

            memory_lobe = globals.bot.cerebrum.get_lobe_by_name("MemoryLobe")
            if not memory_lobe:
                logger.warning("KG extraction skipped: MemoryLobe not found")
                return

            ontologist = memory_lobe.get_ability("OntologistAbility")
            if not ontologist:
                logger.error("KG extraction skipped: OntologistAbility not found")
                return

            # 1. Always store the metadata triple
            await ontologist.execute("Ernos", "RESEARCHED", topic)

            # 2. Use LLM to extract structured triples from the report
            engine = globals.bot.engine_manager.get_active_engine() if globals.bot else None
            if not engine:
                logger.warning("KG extraction: No active engine for triple extraction")
                return

            # Truncate report for LLM context (keep most important parts)
            report_excerpt = report[:4000] if len(report) > 4000 else report

            extraction_prompt = (
                "You are a Knowledge Graph extraction engine. "
                "Extract the KEY factual relationships from this research report as structured triples.\n\n"
                f"RESEARCH TOPIC: {topic}\n\n"
                f"REPORT:\n{report_excerpt}\n\n"
                "RULES:\n"
                "- Extract 5-15 of the most important factual relationships\n"
                "- Each triple must have: subject (concise entity), predicate (relationship verb), object (concise entity)\n"
                "- Subjects and objects should be proper nouns, concepts, or entities — NOT sentences\n"
                "- Predicates should be relationship types like: IS_A, HAS_PROPERTY, DEVELOPED_BY, "
                "RELATED_TO, PART_OF, USED_FOR, CAUSES, ENABLES, CONTRADICTS, PRECEDED_BY, etc.\n"
                "- Include key entities, relationships, dates, organizations, and concepts\n"
                "- Do NOT include generic/vague triples\n\n"
                "OUTPUT FORMAT: Return ONLY a JSON array of objects, each with 'subject', 'predicate', 'object' keys.\n"
                "Example: [{\"subject\": \"GPT-4\", \"predicate\": \"DEVELOPED_BY\", \"object\": \"OpenAI\"}, ...]\n\n"
                "JSON ARRAY:"
            )

            import asyncio
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(
                None, engine.generate_response, extraction_prompt
            )

            if not raw_response:
                logger.warning("KG extraction: LLM returned empty response")
                return

            # Parse the JSON response
            triples = _parse_triples_response(raw_response)

            if not triples:
                logger.warning("KG extraction: No valid triples parsed from LLM response")
                return

            logger.info(f"KG extraction: Parsed {len(triples)} triples, storing via Ontologist...")

            # 3. Feed each triple through the OntologistAbility for validation
            stored_count = 0
            for triple in triples[:15]:  # Cap at 15 to avoid overload
                subject = triple.get("subject", "").strip()
                predicate = triple.get("predicate", "").strip()
                obj = triple.get("object", "").strip()

                if not subject or not obj:
                    continue

                # Normalize predicate to uppercase with underscores
                predicate = predicate.upper().replace(" ", "_").replace("-", "_")
                if not predicate:
                    predicate = "RELATED_TO"

                try:
                    result = await ontologist.execute(
                        subject, predicate, obj,
                        request_scope="CORE",
                        user_id="CORE",
                        source_url=f"research:{topic}"
                    )
                    if result and "Learned" in str(result):
                        stored_count += 1
                        logger.debug(f"  KG stored: {subject} -[{predicate}]-> {obj}")
                    else:
                        logger.debug(f"  KG skipped/rejected: {subject} -[{predicate}]-> {obj}: {result}")
                except Exception as e:
                    logger.debug(f"  KG triple error: {subject} -[{predicate}]-> {obj}: {e}")

            logger.info(
                f"KG extraction complete for '{topic}': "
                f"{stored_count}/{len(triples)} triples stored"
            )

        except Exception as e:
            logger.warning(f"KG extraction error: {e}")


def _parse_triples_response(raw: str) -> list[dict]:
    """
    Parse the LLM's JSON response into a list of triple dicts.
    Handles common LLM output quirks (code fences, preamble text, etc.)
    """
    # Strip code fences
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]

    # Try to find JSON array
    text = text.strip()

    # Find the first [ and last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            # Validate each item has the required keys
            valid = []
            for item in parsed:
                if isinstance(item, dict) and "subject" in item and "object" in item:
                    valid.append(item)
            return valid
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: try line-by-line JSON object parsing
    results = []
    for line in raw.split("\n"):
        line = line.strip().rstrip(",")
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if "subject" in obj and "object" in obj:
                    results.append(obj)
            except (json.JSONDecodeError, ValueError):
                continue
    return results
