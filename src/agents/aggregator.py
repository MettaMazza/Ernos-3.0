"""
ResultAggregator — Collects, ranks, deduplicates, and synthesizes
results from multiple parallel sub-agents.
"""
import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("Agents.Aggregator")


@dataclass
class RankedResult:
    """A result with a relevance/quality score."""
    content: str
    score: float = 0.0
    source_agent_id: str = ""
    metadata: dict = field(default_factory=dict)


class ResultAggregator:
    """
    Aggregates results from multiple agents using various strategies.
    """

    @classmethod
    async def collect_with_timeout(cls, tasks: list[asyncio.Task],
                                    timeout: float = 120.0) -> list:
        """
        Wait for tasks with timeout. Returns all completed results,
        even if some timed out.
        """
        done, pending = await asyncio.wait(tasks, timeout=timeout)

        results = []
        for task in done:
            try:
                results.append(task.result())
            except Exception as e:
                logger.error(f"Task failed during collection: {e}")

        for task in pending:
            task.cancel()
            logger.warning(f"Task cancelled due to timeout")

        return results

    @classmethod
    async def synthesize(cls, results: list[str], bot=None,
                         strategy: str = "llm_merge",
                         prompt_hint: str = "") -> str:
        """
        Synthesize multiple result strings into a unified response.

        Strategies:
        - concat: Simple concatenation with separators
        - deduplicate: Remove near-duplicate results
        - vote: Most common answer wins (for factual queries)
        - llm_merge: Use LLM to intelligently merge (best quality)
        - best_of_n: Score each result and pick the best
        - hierarchical: Group by theme, then merge within groups
        """
        if not results:
            return "No results to synthesize."

        if len(results) == 1:
            return results[0]

        # Filter out empty/error results
        valid_results = [r for r in results if r and not r.startswith("Error:")]
        if not valid_results:
            return "All agents returned errors."

        if strategy == "concat":
            return cls._concat(valid_results)
        elif strategy == "deduplicate":
            return cls._deduplicate(valid_results)
        elif strategy == "vote":
            return cls._vote(valid_results)
        elif strategy == "best_of_n":
            return await cls._best_of_n(valid_results, bot)
        elif strategy == "hierarchical":
            return await cls._hierarchical(valid_results, bot, prompt_hint)
        elif strategy == "llm_merge":
            return await cls._llm_merge(valid_results, bot, prompt_hint)
        else:
            return await cls._llm_merge(valid_results, bot, prompt_hint)

    @classmethod
    def _concat(cls, results: list[str]) -> str:
        """Simple concatenation with numbered sections."""
        parts = []
        for i, r in enumerate(results):
            parts.append(f"### Result {i+1}\n{r}")
        return "\n\n---\n\n".join(parts)

    @classmethod
    def _deduplicate(cls, results: list[str]) -> str:
        """Remove near-duplicate results based on content similarity."""
        unique = []
        for r in results:
            is_dup = False
            for u in unique:
                similarity = cls._jaccard_similarity(r, u)
                if similarity > 0.7:
                    # Keep the longer one
                    if len(r) > len(u):
                        unique.remove(u)
                        unique.append(r)
                    is_dup = True
                    break
            if not is_dup:
                unique.append(r)
        return "\n\n---\n\n".join(unique)

    @classmethod
    def _vote(cls, results: list[str]) -> str:
        """Pick the most common answer (best for factual yes/no queries)."""
        normalized = [r.strip().lower()[:500] for r in results]
        counter = Counter(normalized)
        winner_norm = counter.most_common(1)[0][0]

        for r in results:
            if r.strip().lower()[:500] == winner_norm:
                return r

        return results[0]

    @classmethod
    async def _best_of_n(cls, results: list[str], bot=None) -> str:
        """Score each result and return the highest quality one."""
        if not bot:
            return max(results, key=len)

        try:
            engine = bot.engine_manager.get_active_engine()
            scores = []

            for i, result in enumerate(results):
                score_prompt = (
                    f"Rate the quality of this response on a scale of 1-10. "
                    f"Consider accuracy, completeness, and clarity. "
                    f"Respond with ONLY a number.\n\n"
                    f"Response:\n{result[:3000]}"
                )
                loop = asyncio.get_event_loop()
                score_text = await loop.run_in_executor(
                    None, engine.generate_response, score_prompt, []
                )
                try:
                    import re
                    nums = re.findall(r'\d+', score_text)
                    score = int(nums[0]) if nums else 5
                except Exception:
                    score = 5
                scores.append((score, i))

            scores.sort(reverse=True)
            return results[scores[0][1]]
        except Exception as e:
            logger.error(f"Best-of-N scoring failed: {e}")
            return max(results, key=len)

    @classmethod
    async def _hierarchical(cls, results: list[str], bot=None,
                            prompt_hint: str = "") -> str:
        """Group results by theme, then merge within groups recursively."""
        if not bot:
            return cls._concat(results)

        try:
            engine = bot.engine_manager.get_active_engine()
            loop = asyncio.get_event_loop()

            # 1. Cluster indices by theme via LLM analysis
            cluster_prompt = (
                f"Analyze these {len(results)} research results. Group them into logical themes (2-4 themes total).\n"
                "Respond ONLY with a mapping of theme names to result indices.\n"
                "Format: Theme Name: [index1, index2...]\n\n"
            )
            for i, r in enumerate(results):
                cluster_prompt += f"[{i}]: {r[:300]}...\n"

            cluster_text = await loop.run_in_executor(None, engine.generate_response, cluster_prompt, [])
            
            # Parse clusters from LLM output
            import re
            clusters = {}
            for line in cluster_text.split('\n'):
                if ':' in line:
                    theme, idx_str = line.split(':', 1)
                    indices = [int(i) for i in re.findall(r'\d+', idx_str)]
                    clusters[theme.strip()] = indices
            
            if not clusters:
                return cls._concat(results)
                
            merged_results = []
            for theme, idxs in clusters.items():
                group_results = [results[i] for i in idxs if i < len(results)]
                if group_results:
                    theme_merged = await cls._llm_merge(group_results, bot, f"Theme: {theme}")
                    merged_results.append(f"## {theme}\n{theme_merged}")
            
            return "\n\n".join(merged_results)
        except Exception as e:
            logger.error(f"Hierarchical merge failed: {e}")
            return cls._concat(results)

    @classmethod
    async def _llm_merge(cls, results: list[str], bot=None,
                         prompt_hint: str = "") -> str:
        """Use LLM to intelligently merge all results into a coherent response."""
        if not bot:
            return cls._deduplicate(results)

        try:
            engine = bot.engine_manager.get_active_engine()

            merge_prompt = (
                "You are a synthesis agent. Multiple research agents have gathered "
                "information in parallel. Your job is to merge their findings into "
                "a single, coherent, comprehensive response.\n\n"
                "Rules:\n"
                "- Remove duplicate information\n"
                "- Resolve contradictions by noting both perspectives\n"
                "- Organize logically with clear structure\n"
                "- Preserve all unique insights from each agent\n"
                "- Be comprehensive but not repetitive\n"
            )

            if prompt_hint:
                merge_prompt += f"\nOriginal question context: {prompt_hint}\n"

            merge_prompt += "\n--- Agent Results ---\n\n"

            for i, r in enumerate(results):
                merge_prompt += f"=== Agent {i+1} ===\n{r}\n\n"

            merge_prompt += "--- Your Synthesized Response ---\n"

            loop = asyncio.get_event_loop()
            synthesis = await loop.run_in_executor(
                None, engine.generate_response, merge_prompt, []
            )
            return synthesis
        except Exception as e:
            logger.error(f"LLM merge failed: {e}")
            return cls._deduplicate(results)

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        """Compute Jaccard similarity between two texts."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
