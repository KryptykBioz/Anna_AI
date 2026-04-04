# Filename: BASE/handlers/tool_instruction_builder.py
"""
Tool Instruction Builder - FIXED for ToolManager Interface
===========================================================
Works with actual ToolManager methods:
- get_all_tool_metadata() 
- get_tool_metadata(tool_name)
- _active_tools dict

Extracts ALL information from information.json for action mode
"""

from typing import List, Dict, Optional


class ToolInstructionBuilder:
    """Builds tool instruction sections from information.json metadata"""
    
    __slots__ = ('tool_manager', 'logger')
    
    def __init__(self, tool_manager, logger=None):
        self.tool_manager = tool_manager
        self.logger = logger
    
    # ========================================================================
    # MINIMAL TOOL LIST (for cognitive modes)
    # ========================================================================
    
# BASE/handlers/tool_instruction_builder.py (UPDATE existing method)

    def build_tool_list_section(self) -> str:
        """Build minimal tool list for cognitive modes"""
        enabled_tools = self.tool_manager.get_enabled_tool_names()
        
        if not enabled_tools:
            if self.logger:
                self.logger.warning("[Tool Builder] No enabled tools")
            return ""
        
        if self.logger:
            self.logger.system(
                f"[Tool Builder] Building list for {len(enabled_tools)} enabled tool(s): "
                f"{', '.join(enabled_tools)}"
            )
        
        lines = ["\n## AVAILABLE TOOLS"]
        lines.append("You can use these tools by including them in <actions> tags:")
        lines.append("")
        
        all_metadata = self.tool_manager.get_all_tool_metadata()
        
        found_count = 0
        for tool_name in sorted(enabled_tools):
            metadata = all_metadata.get(tool_name)
            if not metadata:
                if self.logger:
                    self.logger.warning(
                        f"[Tool Builder] No metadata for enabled tool: {tool_name}"
                    )
                continue
            
            description = metadata.get('tool_description', 'No description')
            lines.append(f"**{tool_name}** - {description}")
            lines.append(f"  Format: {{\"tool\": \"{tool_name}\"}}")
            lines.append("")
            found_count += 1
        
        if found_count == 0:
            if self.logger:
                self.logger.error(
                    "[Tool Builder] CRITICAL: Enabled tools found but NO metadata retrieved!"
                )
                self.logger.error(
                    f"[Tool Builder] Enabled: {enabled_tools}"
                )
                self.logger.error(
                    f"[Tool Builder] Metadata keys: {list(all_metadata.keys())}"
                )
            return ""
        
        result = "\n".join(lines)
        
        if self.logger:
            self.logger.success(
                f"[Tool Builder] Built tool list with {found_count}/{len(enabled_tools)} tool(s)"
            )
        
        return result
    
    # ========================================================================
    # DETAILED TOOL INSTRUCTIONS (for action mode ONLY)
    # ========================================================================
    
    def build_retrieved_tool_instructions(self, tool_names: List[str]) -> str:
        """
        Build COMPLETE detailed instructions for action mode
        
        Extracts ALL fields from information.json:
        - Available commands with args
        - Usage examples (all of them)
        - Format specifications
        - Usage guidance
        - Proactive triggers
        - Technical details
        
        Args:
            tool_names: List of base tool names (e.g., ["sound", "calculator"])
        
        Returns:
            Complete documentation for action mode
        """
        if not tool_names:
            return ""
        
        sections = ["\n## RETRIEVED TOOL INSTRUCTIONS"]
        sections.append("\nComplete documentation for tools being executed:\n")
        
        for tool_name in tool_names:
            # Get metadata for this tool
            metadata = self.tool_manager.get_tool_metadata(tool_name)
            if not metadata:
                continue
            
            tool_doc = self._build_complete_tool_documentation(tool_name, metadata)
            if tool_doc:
                sections.append(tool_doc)
                sections.append("\n---\n")
        
        return "\n".join(sections)
    
    def _build_complete_tool_documentation(
        self,
        tool_name: str,
        metadata: Dict
    ) -> str:
        """
        Build COMPLETE documentation from information.json metadata
        
        Extracts every field needed for action mode to construct proper calls
        """
        parts = []
        
        # ====================================================================
        # HEADER
        # ====================================================================
        parts.append(f"### {tool_name.upper()}")
        
        description = metadata.get('tool_description', 'No description available')
        parts.append(f"**Description:** {description}\n")
        
        # ====================================================================
        # AVAILABLE COMMANDS - CRITICAL FOR ACTION MODE
        # ====================================================================
        commands = metadata.get('available_commands', [])
        if commands:
            parts.append("**Available Commands:**\n")
            
            for cmd in commands:
                cmd_name = cmd.get('command', 'execute')
                cmd_args = cmd.get('args', [])
                cmd_desc = cmd.get('description', '')
                cmd_format = cmd.get('format', '')
                
                # Command header: sound.play
                parts.append(f"**{tool_name}.{cmd_name}**")
                
                # Arguments
                if cmd_args:
                    args_formatted = ", ".join(cmd_args)
                    parts.append(f"  - Arguments: {args_formatted}")
                else:
                    parts.append("  - Arguments: None")
                
                # Description
                if cmd_desc:
                    parts.append(f"  - Description: {cmd_desc}")
                
                # Format example (CRITICAL for action mode)
                if cmd_format:
                    parts.append(f"  - Format: `{cmd_format}`")
                
                parts.append("")  # Blank line between commands
        
        # ====================================================================
        # USAGE EXAMPLES - ALL OF THEM
        # ====================================================================
        examples = metadata.get('tool_usage_examples', [])
        if examples:
            parts.append("**Usage Examples:**")
            for example in examples:
                parts.append(f"  - {example}")
            parts.append("")
        
        # ====================================================================
        # USAGE GUIDANCE
        # ====================================================================
        guidance = metadata.get('tool_usage_guidance', [])
        if guidance:
            parts.append("**Usage Guidance:**")
            for guide in guidance:
                parts.append(f"  - {guide}")
            parts.append("")
        
        # ====================================================================
        # PROACTIVE TRIGGERS (when to use this tool)
        # ====================================================================
        triggers = metadata.get('proactive_triggers', [])
        if triggers:
            parts.append("**When to Use:**")
            for trigger in triggers:
                parts.append(f"  - {trigger}")
            parts.append("")
        
        # ====================================================================
        # TECHNICAL DETAILS
        # ====================================================================
        tech_parts = []
        
        if 'timeout_seconds' in metadata:
            tech_parts.append(f"Timeout: {metadata['timeout_seconds']}s")
        
        if 'cooldown_seconds' in metadata:
            tech_parts.append(f"Cooldown: {metadata['cooldown_seconds']}s")
        
        if 'max_retries' in metadata:
            tech_parts.append(f"Max Retries: {metadata['max_retries']}")
        
        if tech_parts:
            parts.append(f"**Technical Details:** {' | '.join(tech_parts)}")
        
        return "\n".join(parts)