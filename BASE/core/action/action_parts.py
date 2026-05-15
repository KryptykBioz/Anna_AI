# Filename: BASE/core/action/action_parts.py
"""
Action Mode Prompt Parts
=========================
Tool execution only. Receives base tool names from cognitive modes and constructs
full commands with correct parameters. Does not determine next mode — the system
resumes the agent's last requested next_mode after action completion.
"""


class ActionPromptParts:
    __slots__ = ()

    @staticmethod
    def get_mode_instructions() -> str:
        return """
<mode_instructions>
## ACTION MODE

When a cognitive mode decides to use a tool, construct the complete tool command with proper parameters. Construct the complete tool command with proper parameters.

**Example Flow:**
1. Cognitive mode output: `{"tool": "warudo"}`
2. You read tool docs: available commands are warudo.animation, warudo.emotion
3. You check recent thoughts: "that's really funny haha"
4. You output:
```
{"tool": "warudo.emotion", "args": ["happy"]},
{"tool": "warudo.animation", "args": ["laugh"]}
```

**Your Task:**
1. Identify which base tool names were decided (e.g. "sound", "calculator")
2. Read the detailed tool documentation below
3. Choose the appropriate command for each tool (e.g. sound.play, calculator.evaluate)
4. Extract parameters from recent thoughts, ensuring the tool selected matches the information source (e.g., internal memory vs. external web search).
5. Output the complete tool calls with tool.command and args, ensuring the underlying intent maintains Anna's warm and cheerful tone.

**Rules:**
- Add the COMMAND after the tool name: `{"tool": "sound.play", "args": ["cheer"]}`
- Extract parameters from thoughts and tool docs — do not invent values
- If a tool offers a list/retrieve command and you lack needed info, call that first
- Follow tool documentation format EXACTLY
- Output ONLY the `<actions>` block — nothing else
</mode_instructions>
"""

    @staticmethod
    def get_execution_principles() -> str:
        return """
<execution_principles>
## EXECUTION PRINCIPLES

**Command construction:**
- Base tool: "sound" → "sound.play"
- Base tool: "calculator" → "calculator.evaluate"
- Base tool: "wiki_search" → "wiki_search.search"
- Read documentation to find available commands

**Parameter extraction:**
- Find relevant values in recent thoughts
- Use exact phrases when available
- Example: "add epic battle sounds" + tool docs contain "battle" → `{"tool": "sound.play", "args": ["battle"]}`

**Following documentation:**
- Match the format shown in examples EXACTLY
- Wrong format = tool fails

**Output:**
- ONLY the `<actions>` block
- No text before or after
- Clean JSON with tool.command syntax
</execution_principles>
"""

    @staticmethod
    def get_output_format() -> str:
        return """
<output_format>
## OUTPUT FORMAT

Output ONLY this block:

```xml
<actions>
[
  {"tool": "tool_name.command", "args": ["param1", "param2"]},
  {"tool": "another_tool.command", "args": ["param1"]}
]
</actions>
```

**Format rules:**
- NOT: `{"tool": "sound"}` — missing command
- YES: `{"tool": "sound.play", "args": ["cheer"]}` — complete
- Only use commands that exist in the tool documentation
- Nothing before or after the `<actions>` block
</output_format>
"""

    @staticmethod
    def get_grounding_rules() -> str:
        return """
<grounding_rules>
## GROUNDING RULES

- Only execute tools decided by cognitive modes
- Extract parameters from actual thoughts
- Don't invent information not in your thoughts
- If unsure about a parameter, make a reasonable inference from context
- Check if a tool already contains relevant info before adding duplicates
</grounding_rules>
"""