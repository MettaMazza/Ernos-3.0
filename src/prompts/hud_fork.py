"""
HUD Fork — Load per-user (Fork) HUD data.

Extracted from hud_loaders.py per <300 line modularity standard.
"""
import json
import logging
from typing import Dict

logger = logging.getLogger("PromptManager")


def load_fork_hud(user_id: str, user_name: str) -> Dict[str, str]:
    """
    Load Fork (per-user) HUD data: conversation history, topics, preferences,
    relationship context, glossary, emotional tone, etc.
    
    Returns dict of Fork HUD variable names -> string values.
    """
    fhud = {
        "conversation_summary": "No prior conversations recorded.",
        "recent_topics": "None tracked.",
        "relationship_context": "New relationship - no established context.",
        "user_preferences": "No preferences recorded.",
        "first_interaction": "Unknown",
        "message_count": "0",
        "full_conversation_history": "No conversation history.",
        "topic_history": "No topics tracked.",
        "recurring_themes": "No recurring themes identified.",
        "unfinished_threads": "No unfinished threads.",
        "user_interests": "Unknown",
        "user_values": "Unknown",
        "user_style": "Unknown",
        "questions_asked": "No questions recorded.",
        "private_glossary": "No shared vocabulary.",
        "nicknames": "None",
        "emotional_tone": "Neutral",
        "connection_moments": "None recorded.",
        "sensitive_topics": "None flagged.",
        "implicit_patterns": "No patterns detected.",
        "avoided_topics": "None identified.",
        "promises_made": "None recorded.",
        "remember_next": "Nothing flagged.",
        "open_questions": "None pending.",
        "identity_in_relationship": "Standard persona.",
        "your_role": "Conversational partner.",
        "current_persona_content": "No custom persona defined. Use update_persona to create one.",
    }

    try:
        from collections import Counter
        from src.privacy.scopes import ScopeManager
        user_home = ScopeManager.get_user_home(user_id)

        # Load persona.txt content
        persona_path = user_home / "persona.txt"
        if persona_path.exists():
            try:
                with open(persona_path, "r", encoding="utf-8") as f:
                    content = f.read()
                fhud["current_persona_content"] = content if content.strip() else "[Empty persona file]"
            except Exception as e:
                fhud["current_persona_content"] = f"[Error reading persona: {e}]"

        # Load conversation history from context_private.jsonl
        context_path = user_home / "context_private.jsonl"
        if context_path.exists():
            with open(context_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                fhud["message_count"] = str(len(all_lines))

                conversations = []
                topics_counter = Counter()
                questions_list = []

                for line in all_lines:
                    try:
                        entry = json.loads(line)
                        user_msg = entry.get("user", "")
                        bot_msg = entry.get("bot", "")
                        ts = entry.get("ts", "")[:10]

                        if user_msg:
                            if "?" in user_msg:
                                questions_list.append(user_msg[:500])

                            words = user_msg.lower().split()
                            for i in range(len(words) - 1):
                                bigram = f"{words[i]} {words[i+1]}"
                                if len(bigram) > 6 and not any(w in bigram for w in ["the", "and", "you", "what", "how", "i'm"]):
                                    topics_counter[bigram] += 1

                            conversations.append(f"[{ts}] {user_name}: {user_msg[:1000]}")
                            if bot_msg:
                                conversations.append(f"[{ts}] You: {bot_msg[:1000]}")
                    except Exception:
                        continue

                if conversations:
                    fhud["full_conversation_history"] = "\n".join(conversations[-100:])
                    fhud["conversation_summary"] = "\n".join(conversations[-20:])

                if all_lines:
                    try:
                        first = json.loads(all_lines[0])
                        fhud["first_interaction"] = first.get("ts", "Unknown")[:19]
                    except Exception:
                        pass

                top_topics = topics_counter.most_common(20)
                if top_topics:
                    fhud["recent_topics"] = ", ".join([t[0] for t in top_topics[:10]])
                    fhud["recurring_themes"] = "\n".join([f"• {t[0]} ({t[1]}x)" for t in top_topics[:10]])
                    fhud["topic_history"] = "\n".join([f"• {t[0]}" for t in top_topics])

                if questions_list:
                    fhud["questions_asked"] = "\n".join([f"• {q}..." for q in questions_list[-15:]])

        # Relationship context from timeline
        timeline_path = user_home / "timeline.jsonl"
        if timeline_path.exists():
            with open(timeline_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                interaction_count = len(lines)
                if interaction_count > 50:
                    fhud["relationship_context"] = f"Deep relationship - {interaction_count} interactions over extended period."
                elif interaction_count > 10:
                    fhud["relationship_context"] = f"Established relationship - {interaction_count} interactions recorded."
                elif interaction_count > 0:
                    fhud["relationship_context"] = f"New relationship - {interaction_count} interactions so far."

        # User preferences
        prefs_path = user_home / "preferences.json"
        if prefs_path.exists():
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
                fhud["user_preferences"] = json.dumps(prefs, indent=2)

        # Persona for identity_in_relationship
        if persona_path.exists():
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_content = f.read()
                fhud["identity_in_relationship"] = persona_content.split('\n')[0] if '\n' in persona_content else persona_content
                fhud["your_role"] = "Custom fork identity active."

        # Private glossary
        glossary_path = user_home / "glossary.json"
        if glossary_path.exists():
            with open(glossary_path, "r", encoding="utf-8") as f:
                glossary = json.load(f)
                fhud["private_glossary"] = "\n".join([f"• {k}: {v}" for k, v in list(glossary.items())[:20]])

        # Emotional tone from reasoning
        reasoning_path = user_home / "reasoning_private.log"
        if reasoning_path.exists():
            with open(reasoning_path, "r", encoding="utf-8") as f:
                reasoning_lines = f.readlines()[-200:]
                text = " ".join(reasoning_lines).lower()
                positive = sum(1 for w in ["agree", "yes", "good", "appreciate", "thank", "love", "happy"] if w in text)
                negative = sum(1 for w in ["no", "wrong", "disagree", "issue", "problem", "frustrated"] if w in text)
                if positive > negative * 2:
                    fhud["emotional_tone"] = "Warm and collaborative"
                elif negative > positive * 2:
                    fhud["emotional_tone"] = "Challenging - approach thoughtfully"
                else:
                    fhud["emotional_tone"] = "Balanced engagement"

    except Exception as e:
        logger.error(f"Fork HUD Data Load Failed: {e}")

    return fhud
