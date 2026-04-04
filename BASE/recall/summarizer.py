# Filename: BASE/memory/summarizer.py
"""
Summarizer for Memory System
Only summarizes PREVIOUS days, never the current day.
Current day entries persist until the entire day has passed.

IMPORTANT: This is only called on GUI startup to check for date rollovers,
NOT on every interaction save.
"""

import requests
from typing import Optional

from personality.bot_info import agentname, username

def summarize_previous_day(memory_manager, previous_date: str) -> bool:
    """
    Create a summary of a PREVIOUS day's conversation and archive it.
    Only summarizes completed days, never the current day.
    
    Args:
        memory_manager: The memory manager instance
        previous_date: The date of the conversation to summarize (YYYY-MM-DD format)
                      This is the conversation date, NOT the current date
    
    Returns:
        True if successful, False otherwise
    """
    # Get entries from the specified previous date
    entries_from_date = []
    
    # Collect from medium memory
    for entry in memory_manager.medium_memory:
        if entry.get('date') == previous_date:
            entries_from_date.append(entry)
    
    # Collect from short memory (in case date just rolled over)
    for entry in memory_manager.short_memory:
        if entry.get('date') == previous_date:
            entries_from_date.append(entry)
    
    if not entries_from_date:
        print(f"[Summarizer] No entries found for previous day: {previous_date}")
        return False
    
    # CHANGED: Reduced minimum from 4 to 2 entries
    # Even brief conversations should be preserved in long-term memory
    if len(entries_from_date) < 2:
        print(f"[Summarizer] Only {len(entries_from_date)} entry/entries for {previous_date} - creating minimal summary")
        # For single entries, create a minimal summary
        if len(entries_from_date) == 1:
            entry = entries_from_date[0]
            role = memory_manager.username if entry['role'] == 'user' else memory_manager.agentname
            content = entry['content']
            summary = f"Brief interaction: {role} said: {content}"
            # Store with the conversation date (previous_date), not today's date
            memory_manager.archive_previous_day(summary, previous_date)
            return True
    
    # Sort by timestamp to ensure chronological order
    entries_from_date.sort(key=lambda x: x.get('timestamp', ''))
    
    # Format conversation
    lines = []
    for entry in entries_from_date:
        role = memory_manager.username if entry['role'] == 'user' else memory_manager.agentname
        lines.append(f"{role}: {entry['content']}")
    
    conversation = "\n".join(lines)
    
    # Generate summary with explicit date context
    # The prompt emphasizes the conversation date to ensure the LLM understands
    # this is a retrospective summary of a past conversation
    prompt = f"""Create a concise summary of this full day's conversation between {username}, other humans and AI agents, and {agentname} that took place on {previous_date}. 
Summarize in the first person from the perspective of {agentname}, the AI assistant, creating a short diary entry from {agentname} reflecting on that day. 
Focus on key topics, important information, decisions made, emotional context, personal preferences, ongoing plans, and anything else the assistant, {agentname}, should later recall about that day's interactions. 
Do not include formatting such as headers, subsections, bullet points, line breaks, or other extraneous details. Write this diary entry in complete sentences and a reflective tone. 
No more than 2000 characters.

Conversation from {previous_date} ({len(entries_from_date)} messages):
{conversation}

Summary of {previous_date}:"""

    
    summary = _call_llm(memory_manager.ollama_endpoint, prompt)
    
    if summary:
        # CRITICAL: Store the summary with the conversation date (previous_date)
        # NOT the current date when the summary is being created
        memory_manager.archive_previous_day(summary, previous_date)
        print(f"[Summarizer] Successfully summarized and archived {previous_date} ({len(entries_from_date)} entries)")
        return True
    
    print(f"[Summarizer] Failed to generate summary for {previous_date}")
    return False

def _call_llm(endpoint: str, prompt: str) -> Optional[str]:
    """Call Ollama to generate summary"""
    try:
        r = requests.post(f"{endpoint}/api/generate",
                         json={
                             "model": "llama3.2:latest",
                             "prompt": prompt,
                             "stream": False,
                             "temperature": 0.3,
                             "max_tokens": 500
                         },
                         timeout=120)
        r.raise_for_status()
        
        summary = r.json().get("response", "").strip()
        
        # Clean up common prefixes
        for prefix in ["summary:", "daily summary:"]:
            if summary.lower().startswith(prefix):
                summary = summary[len(prefix):].strip()
        
        return summary if summary else None
        
    except Exception as e:
        print(f"[Summarizer] LLM call failed: {e}")
        return None