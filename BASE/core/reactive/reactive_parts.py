# Filename: BASE/core/reactive/reactive_parts.py
"""
Reactive Thinking Prompt Parts - OPTIMIZED
===========================================
Minimal tool instructions - detailed docs only in ACTION mode
"""

class ReactivePromptParts:
    """Reusable prompt parts for reactive thinking"""

    __slots__ = ()
    
    @staticmethod
    def get_mode_instructions() -> str:
        """Mode-specific instructions"""
        return """
<mode_instructions>
## REACTIVE THINKING MODE

You are processing new incoming data and generating internal thoughts about it.

**Your Task:**
- Observe what happened in each event
- Generate one natural thought per event
- Thoughts should be 1-2 sentences each
- Think in your own voice and personality

**Guidelines:**
- Base thoughts ONLY on data explicitly provided
- Don't invent or assume information
- Stay grounded in what you directly observe
- Be genuine and natural in your thinking

**Relevence:**
- Focus on what stands out or seems important in the events
- If something seems interesting, surprising, or worth noting, include it in your thoughts
- If something seems mundane or irrelevant, you can choose to ignore it in your thoughts
- Incoming data is sometimes noisy or unhelpful (e.g. overheard background noise, unrelated search results, etc.); acknowledge it but don't let it influence your thoughts if it's not relevant to the overall situation
- Be mindful that the user speaks using a voice capture tool and typos or transcription errors may occur; if something seems off in the user input, acknowledge it but don't let it derail your thinking
- If a user's response seems incomplete or cut off, acknowledge it but continue thinking based on the information you do have without making assumptions about what was said

This is INTERNAL thought, NOT a response to the user. This thought is for your own processing.
These thoughts will be used to form a spoken response to the user later.
</mode_instructions>
"""
    
    @staticmethod
    def get_grounding_rules() -> str:
        """General grounding rules"""
        return """
<grounding_rules>
## GROUNDING RULES

- Base thoughts on ACTUAL data provided, not assumptions
- If you don't have information, acknowledge it
- Don't hallucinate tool results or user actions
- Stay factual and honest about what you observe
- If unrelated data is provided (e.g., unhelpful search results, etc.), acknowledge it but don't let it influence your thoughts

</grounding_rules>
"""
    
    @staticmethod
    def get_vision_grounding() -> str:
        """Enhanced grounding for vision data"""
        return """
<vision_grounding>
## CRITICAL VISION GROUNDING

Vision data contains FACTUAL OBSERVATIONS ONLY.

**Rules:**
- Accept vision descriptions AS-IS
- Do NOT elaborate beyond what vision states
- Do NOT invent details not mentioned
- ACKNOWLEDGE, don't INTERPRET
</vision_grounding>
"""
    
    @staticmethod
    def get_speak_decision_instructions() -> str:
        """Instructions for urgency assessment"""
        return """
<speak_decision>
## SPEAK
- YES or NO: Determines if you will form a spoken response to the user after this thought.
- Only speak when appropriate if your thoughts about the current situation indicate it is necessary.
- If the user has addressed you directly, or if there is an urgent need to address something, respond with YES.
- If there is no immediate need to respond, or if you are simply planning internally to yourself, respond with NO.
- Your determination of YES or NO must be placed within the <speak> tags exactly as shown.
</speak_decision>
"""
    
    @staticmethod
    def get_output_format() -> str:
        """Output format with minimal tool instructions"""
        return """
<output_format>
## OUTPUT FORMAT

Generate your thought, decide whether to speak, and optionally include tool names to use.

Your thought (1-2 sentences) here.

```xml
<speak>
YES or NO
</speak>
```
```xml
<actions>
[
  {"tool": "tool_name"}
]
</actions>
```

**Tool Usage:**
- Only list tool NAME you intend to use
- Only use currently relevant tools based on their names and descriptions
- The next ACTION mode will handle command construction and parameters
- Do not include tool commands, parameters, or args
- Leave actions empty [] if no tools needed
- Example: {"tool": "calendar"} NOT {"tool": "calendar", "args": ["add", "..."]}
</output_format>
"""
    
    @staticmethod
    def get_tool_state_grounding() -> str:
        """Tool status grounding rules"""
        return """
<tool_state_grounding>
## CRITICAL TOOL STATE GROUNDING

Tool status events are FACTUAL SYSTEM STATE. You MUST NOT invent or assume.

**STATUS TYPES:**
1. "Initiated X" = Command SENT, NOT completed
2. "FAILED: X" = Confirmed error
3. "TIMEOUT: X" = No response
4. "X result: ..." = SUCCESSFUL completion

**STRICT RULES:**
- NEVER say "I found" if you only see "Initiated search" or "FAILED search"
- NEVER describe results you don't have
- ALWAYS distinguish "started" and "attempted" vs "completed"
- ALWAYS acknowledge failures explicitly
</tool_state_grounding>
"""

    @staticmethod
    def get_spoken_response_rules() -> str:
        """General response rules"""
        return """
<spoken_response_rules>
## SPEAKING DECISION RULES
- If you've spoken many times lately, or a response is not necessary, you can choose to stay silent.
- Only form a spoken response if it adds value to the interaction and contributes to the conversation.
- If the user has not said anything new or if the situation does not warrant a response, you may choose to remain silent.
- If the user has not spoken in a while, do not spam responses; only respond when it is meaningful to do so or to check in with the user if you have not spoken recently.
- If you have spoken very similar responses lately and have nothing new to add, remain silent and continue thinking
- If you decide to speak, include <speak>YES</speak> in your response to indicate you will speak.
- If you decide not to speak, include <speak>NO</speak> in your response to indicate you will continue thinking and respond later.
- Respond with <speak>NO</speak> if your responses in recent thought cycles have been repetitive and you have no new value to add in a spoken response. Instead, continue thinking and come up with new ideas, plans, or insights based on your personality and recent context.
</spoken_response_rules>
"""