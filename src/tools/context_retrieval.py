import logging
import json
from .registry import ToolRegistry
from src.security.provenance import ProvenanceManager
from pathlib import Path

logger = logging.getLogger("Tools.ContextRetrieval")

@ToolRegistry.register(name="check_creation_context", description="Retrieve intention and context for a specific file/artifact.")
async def check_creation_context(filename_or_query: str, **kwargs) -> str:
    """
    Looks up an artifact in the Provenance Ledger or Knowledge Graph to verify
    its origin, the intention behind it, and the prompt used.
    
    Args:
        filename_or_query: The filename (e.g., 'generated_image_123.png') or text snippet from the prompt.
    """
    try:
        # 1. Check Provenance Ledger (Direct Filename Match)
        # Scan ledger for matching filename
        ledger_file = ProvenanceManager.LEDGER_FILE
        if not ledger_file.exists():
            return "Provenance Ledger not found."
            
        found_records = []
        
        with open(ledger_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    fname = entry.get("filename", "")
                    meta = entry.get("metadata", {})
                    prompt = meta.get("prompt", "")
                    intention = meta.get("intention", "")
                    
                    # Match Logic
                    if filename_or_query.lower() in fname.lower() or \
                       filename_or_query.lower() in prompt.lower() or \
                       (intention and filename_or_query.lower() in intention.lower()):
                        found_records.append(entry)
                except Exception:
                    continue
        
        if not found_records:
            return f"No context found for '{filename_or_query}'."
            
        # Format Results (limit to top 3)
        output = [f"Found {len(found_records)} matching artifacts:"]
        for record in found_records[-3:]:
             meta = record.get("metadata", {})
             output.append(
                 f"\n--- Artifact: {record.get('filename')} ---\n"
                 f"Created: {record.get('timestamp')}\n"
                 f"Intention: {meta.get('intention', 'None recorded')}\n"
                 f"Prompt: {meta.get('prompt', 'Unknown')}\n"
                 f"Scope: {meta.get('scope', 'Unknown')}\n"
                 f"Checksum: {record.get('checksum')[:8]}..."
             )
             
        return "\n".join(output)

    except Exception as e:
        logger.error(f"Context retrieval failed: {e}")
        return f"Context Retrieval Error: {str(e)}"
