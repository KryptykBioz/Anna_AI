# Filename: BASE/core/action/action_parts.py
"""
Action Mode Prompt Parts - FIXED
=================================
Clear instructions for ACTION mode to construct full tool commands

ACTION MODE receives base tool names from cognitive modes:
- Input: {"tool": "sound"}
- Output: {"tool": "sound.play", "args": ["battle_sound"]}

Focus: Read tool docs, extract parameters from thoughts, format properly
"""


class ActionPromptParts:
    """Reusable prompt parts for action mode"""

    __slots__ = ()
    
    @staticmethod
    def get_mode_instructions() -> str:
        """Action mode instructions - UPDATED for command construction"""
        return """
<mode_instructions>
## ACTION MODE

You've just decided to use a tool.
You must now construct the complete tool command with proper parameters.

**Example Flow:**
1. Cognitive mode decided: `{"tool": "warudo"}`
2. You read tool docs and see available commands: warudo.animation, warudo.emotion
3. You check your recent thoughts: "that's really funny haha"
4. You identify the closest available emotions and animations to the current context
4. You output: 
`
{"tool": "warudo.emotion", "args": ["happy"]},
{"tool": "warudo.animation", "args": ["laugh"]}
`

**Your Task:**
1. Review which BASE tool names were decided (e.g., "sound", "calculator")
2. Read the detailed tool documentation below
3. Choose the appropriate COMMAND for each tool (e.g., sound.play, calculator.evaluate)
4. Extract parameters from your recent thoughts
5. Format the COMPLETE tool calls with tool.command and args

**Critical Rules:**
- Your previous thought decided to use a tool by name (e.g., "sound")
- You must add the COMMAND (e.g., "sound.play") and any required parameters (e.g., ["squee"])
- Format: {"tool": "tool_name.command", "args": ["param1", "param2"]}
- Extract parameters from your thoughts and tool-specific instructions, NOT from thin air
- If a tool has commands to retrieve information (e.g., list of sounds), use that first to inform your parameter choices
- If your thoughts don't contain information retrieved from the tool when retrieval is available, use the tool to get that information first before executing further commands
- Follow the tool documentation format EXACTLY
- Output ONLY the <actions> JSON block containing properly formatted tool calls, nothing else

This is INTERNAL tool execution. Results will be provided once the tool finishes execution.
</mode_instructions>
"""
    
    @staticmethod
    def get_execution_principles() -> str:
        """Principles for tool execution - UPDATED"""
        return """
<execution_principles>
## EXECUTION PRINCIPLES

**Command Construction:**
- Base tool: "sound" → Full command: "sound.play"
- Base tool: "calculator" → Full command: "calculator.evaluate"
- Base tool: "wiki_search" → Full command: "wiki_search.search"
- Read documentation to find available commands for each tool

**Parameter Extraction:**
- Find relevant values in your recent thoughts
- Use exact phrases when available
- Convert natural language to tool format
- Example: "add epic battle sounds" → tool instructions contain available sound "battle" → `{"tool": "sound.play", "args": ["battle"]}`

**Following Documentation:**
- Each command has specific parameter requirements
- Some commands need 1 arg, some need 2+
- Match the format shown in examples EXACTLY
- Wrong format = tool fails

**Output Format:**
- ONLY output the <actions> block
- No extra text before or after
- No explanations or notes
- Clean JSON format with tool.command syntax
</execution_principles>
"""
    
    @staticmethod
    def get_output_format() -> str:
        """Output format for action mode - UPDATED for clarity"""
        return """
<output_format>
## OUTPUT FORMAT

Output ONLY this format, nothing else:

```xml
<actions>
[
  {"tool": "tool_name.command", "args": ["param1", "param2"]},
  {"tool": "another_tool.command", "args": ["param1"]}
]
</actions>
```

**CRITICAL - Tool Command Format:**
- NOT: {"tool": "sound"} ← Missing command
- YES: {"tool": "sound.play", "args": ["cheer"]} ← Complete with command

**Examples:**

Sound effect with one parameter:
```xml
<actions>
[
  {"tool": "sound.play", "args": ["squee"]}
]
</actions>
```

Calculator:
```xml
<actions>
[
  {"tool": "calculator.evaluate", "args": ["2 + 2"]}
]
</actions>
```

Wiki search:
```xml
<actions>
[
  {"tool": "wiki_search.search", "args": ["VTubers"]}
]
</actions>
```

Multiple tools:
```xml
<actions>
[
  {"tool": "sound.play", "args": ["squee"]},
  {"tool": "warudo.emotion", "args": ["happy"]}
]
</actions>
```

**CRITICAL:**
- Always include the COMMAND after the tool name (tool.command)
- Output ONLY the <actions> block
- Nothing before it
- Nothing after it
- No explanations
- No commentary
- Just properly formatted tool calls with commands
</output_format>
"""
    
    @staticmethod
    def get_grounding_rules() -> str:
        """Grounding rules for action mode"""
        return """
<grounding_rules>
## GROUNDING RULES

**When executing tools:**
- Only execute tools explicitly decided by cognitive modes
- Extract parameters from your actual thoughts
- Don't invent information not in your thoughts
- Use the tool documentation to format correctly
- If unsure about a parameter, make reasonable inference from context
- Use the tool in a way that fits the current context

**Command Selection:**
- Read available commands in documentation
- Choose command that matches your thoughts
- Example: thoughts mention "play sound" → use sound.play command
- Example: thoughts mention "list sounds" → use sound.list command
</grounding_rules>
"""