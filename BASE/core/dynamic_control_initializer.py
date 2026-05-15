# Filename: BASE/core/dynamic_control_initializer.py
"""
Dynamic Control Variable Initializer
Reads all information.json files from both external and internal tools
and creates control variables with correct defaults.
MUST run before GUI initialization.

Architecture:
- External tools: BASE/tools/installed/
- Internal tools: BASE/tools/internal/
"""
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional


class DynamicControlInitializer:
    """Initialize control variables from tool information.json files"""
    
    __slots__ = ('project_root', 'controls_module', 'logger', 
                 'external_tools_dir', 'internal_tools_dir')
    
    def __init__(self, project_root: Path, controls_module, logger=None):
        self.project_root = project_root
        self.controls_module = controls_module
        self.logger = logger
        
        self.external_tools_dir = project_root / 'BASE' / 'tools' / 'installed'
        self.internal_tools_dir = project_root / 'BASE' / 'tools' / 'internal'
    
    def initialize_all_controls(self) -> Dict[str, int]:
        """
        Initialize all control variables from external and internal tools
        
        Returns:
            Dict with counts: {'external': N, 'internal': M, 'total': N+M}
        """
        external_count = self.initialize_external_tool_controls()
        internal_count = self.initialize_internal_tool_controls()
        
        total = external_count + internal_count
        
        if self.logger:
            self.logger.success(
                f"[Control Init] Initialized {total} control variables "
                f"({external_count} external, {internal_count} internal)"
            )
        
        return {
            'external': external_count,
            'internal': internal_count,
            'total': total
        }
    
    def initialize_external_tool_controls(self) -> int:
        """
        Initialize control variables for external tools (BASE/tools/installed)
        
        Returns:
            Number of control variables initialized
        """
        if not self.external_tools_dir.exists():
            if self.logger:
                self.logger.warning(
                    f"[Control Init] External tools directory not found: "
                    f"{self.external_tools_dir}"
                )
            return 0
        
        controls = self.controls_module
        initialized = []
        
        for tool_dir in self.external_tools_dir.iterdir():
            if not tool_dir.is_dir() or tool_dir.name[0] in ('_', '.'):
                continue
            
            info_file = tool_dir / 'information.json'
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                
                control_var = info.get('control_variable_name')
                if not control_var:
                    continue
                
                # Skip if already exists
                if hasattr(controls, control_var):
                    continue
                
                # Get default value
                default_value = info.get('control_variable_value', False)
                tool_name = info.get('tool_name', tool_dir.name)
                
                # Create control variable
                setattr(controls, control_var, default_value)
                initialized.append((control_var, default_value, tool_name, 'external'))
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(
                        f"[Control Init] Failed to load {tool_dir.name}: {e}"
                    )
                continue
        
        if self.logger and initialized:
            self.logger.system(
                f"[Control Init] Initialized {len(initialized)} external tool controls"
            )
            for control_var, default_value, tool_name, _ in initialized:
                self.logger.system(f"  • {control_var} = {default_value} ({tool_name})")
        
        return len(initialized)
    
    def initialize_internal_tool_controls(self) -> int:
        """
        Initialize control variables for internal tools (BASE/tools/internal)
        
        Internal tools have special rules:
        - Service types enforce mutual exclusivity (only one TTS, one voice_input, etc.)
        - Default values based on priority (highest priority = default ON)
        - control_logic field determines enabled_when_true/enabled_when_false
        
        Returns:
            Number of control variables initialized
        """
        if not self.internal_tools_dir.exists():
            if self.logger:
                self.logger.warning(
                    f"[Control Init] Internal tools directory not found: "
                    f"{self.internal_tools_dir}"
                )
            return 0
        
        controls = self.controls_module
        
        # Discover all internal tools
        discovered_tools = self._discover_internal_tools()
        
        if not discovered_tools:
            return 0
        
        # Group by service_type for mutual exclusivity
        service_groups = self._group_by_service_type(discovered_tools)
        
        # Initialize control variables with smart defaults
        initialized = []
        
        for service_type, tools in service_groups.items():
            # Sort by priority (highest first)
            tools.sort(key=lambda t: t['priority'], reverse=True)
            
            # Only highest priority tool is enabled by default
            for idx, tool in enumerate(tools):
                control_var = tool['control_var']
                
                # Skip if already exists
                if hasattr(controls, control_var):
                    continue
                
                # Highest priority tool = enabled by default
                # All others = disabled by default
                default_value = (idx == 0)
                
                # Apply control_logic override if specified
                control_logic = tool.get('control_logic', 'enabled_when_true')
                if control_logic == 'enabled_when_false':
                    default_value = not default_value
                
                # Create control variable
                setattr(controls, control_var, default_value)
                
                initialized.append((
                    control_var,
                    default_value,
                    tool['tool_name'],
                    service_type,
                    tool['priority']
                ))
        
        if self.logger and initialized:
            self.logger.system(
                f"[Control Init] Initialized {len(initialized)} internal tool controls"
            )
            
            # Group log output by service type
            by_service = {}
            for control_var, value, name, service, priority in initialized:
                if service not in by_service:
                    by_service[service] = []
                by_service[service].append((control_var, value, name, priority))
            
            for service_type, tools in by_service.items():
                self.logger.system(f"  [{service_type.upper()}]")
                for control_var, value, name, priority in tools:
                    status = "[Confirmed] ON" if value else "OFF"
                    self.logger.system(
                        f"    • {control_var} = {value} ({name}, priority={priority}) {status}"
                    )
        
        return len(initialized)
    
    def _discover_internal_tools(self) -> List[Dict]:
        """
        Discover all internal tools by scanning information.json files
        
        Returns:
            List of tool metadata dicts
        """
        discovered = []
        
        for tool_dir in self.internal_tools_dir.iterdir():
            if not tool_dir.is_dir() or tool_dir.name[0] in ('_', '.'):
                continue
            
            # Skip shared utilities
            if tool_dir.name == 'shared':
                continue
            
            info_file = tool_dir / 'information.json'
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                
                tool_name = info.get('tool_name')
                control_var = info.get('control_variable_name')
                service_type = info.get('service_type')
                
                if not tool_name or not control_var or not service_type:
                    if self.logger:
                        self.logger.warning(
                            f"[Control Init] {tool_dir.name}/information.json missing "
                            f"required fields (tool_name, control_variable_name, service_type)"
                        )
                    continue
                
                discovered.append({
                    'tool_name': tool_name,
                    'control_var': control_var,
                    'service_type': service_type,
                    'priority': info.get('priority', 0),
                    'control_logic': info.get('control_logic', 'enabled_when_true'),
                    'description': info.get('tool_description', ''),
                    'features': info.get('features', {}),
                    'requirements': info.get('requirements', {})
                })
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(
                        f"[Control Init] Failed to load {tool_dir.name}/information.json: {e}"
                    )
                continue
        
        return discovered
    
    def _group_by_service_type(self, tools: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group tools by service_type for mutual exclusivity handling
        
        Args:
            tools: List of tool metadata dicts
        
        Returns:
            Dict mapping service_type -> list of tools
        """
        groups = {}
        
        for tool in tools:
            service_type = tool['service_type']
            
            if service_type not in groups:
                groups[service_type] = []
            
            groups[service_type].append(tool)
        
        return groups
    
    def get_tool_metadata(self, control_var: str) -> Optional[Dict]:
        """
        Get metadata for a specific tool by its control variable
        
        Args:
            control_var: Control variable name (e.g., 'USE_GPT_SOVITS')
        
        Returns:
            Tool metadata dict or None if not found
        """
        # Check external tools
        for tool_dir in self.external_tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue
            
            info_file = tool_dir / 'information.json'
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r') as f:
                    info = json.load(f)
                
                if info.get('control_variable_name') == control_var:
                    return {
                        'tool_name': info.get('tool_name'),
                        'category': 'external',
                        'service_type': info.get('service_type'),
                        'description': info.get('tool_description'),
                        'info': info
                    }
            except:
                continue
        
        # Check internal tools
        for tool_dir in self.internal_tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue
            
            info_file = tool_dir / 'information.json'
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r') as f:
                    info = json.load(f)
                
                if info.get('control_variable_name') == control_var:
                    return {
                        'tool_name': info.get('tool_name'),
                        'category': 'internal',
                        'service_type': info.get('service_type'),
                        'priority': info.get('priority', 0),
                        'description': info.get('tool_description'),
                        'features': info.get('features', {}),
                        'requirements': info.get('requirements', {}),
                        'info': info
                    }
            except:
                continue
        
        return None
    
    def list_all_controls(self) -> Dict[str, List[Tuple[str, bool, str]]]:
        """
        List all dynamically created control variables
        
        Returns:
            Dict with 'external' and 'internal' lists of (control_var, value, tool_name)
        """
        controls = self.controls_module
        
        result = {
            'external': [],
            'internal': []
        }
        
        # External tools
        if self.external_tools_dir.exists():
            for tool_dir in self.external_tools_dir.iterdir():
                if not tool_dir.is_dir():
                    continue
                
                info_file = tool_dir / 'information.json'
                if not info_file.exists():
                    continue
                
                try:
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                    
                    control_var = info.get('control_variable_name')
                    if control_var and hasattr(controls, control_var):
                        value = getattr(controls, control_var)
                        tool_name = info.get('tool_name')
                        result['external'].append((control_var, value, tool_name))
                except:
                    continue
        
        # Internal tools
        if self.internal_tools_dir.exists():
            for tool_dir in self.internal_tools_dir.iterdir():
                if not tool_dir.is_dir() or tool_dir.name == 'shared':
                    continue
                
                info_file = tool_dir / 'information.json'
                if not info_file.exists():
                    continue
                
                try:
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                    
                    control_var = info.get('control_variable_name')
                    if control_var and hasattr(controls, control_var):
                        value = getattr(controls, control_var)
                        tool_name = info.get('tool_name')
                        service_type = info.get('service_type')
                        result['internal'].append((control_var, value, tool_name, service_type))
                except:
                    continue
        
        return result


# ============================================================================
# Usage Example
# ============================================================================

def initialize_dynamic_controls(project_root: Path, controls_module, logger=None):
    """
    Helper function to initialize all dynamic controls
    
    Usage in main.py or gui startup:
        from BASE.core.dynamic_control_initializer import initialize_dynamic_controls
        from pathlib import Path
        import BASE.config.controls as controls
        
        project_root = Path(__file__).parent
        initialize_dynamic_controls(project_root, controls, logger)
    
    Args:
        project_root: Path to project root directory
        controls_module: BASE.config.controls module
        logger: Optional logger instance
    
    Returns:
        DynamicControlInitializer instance for further queries
    """
    initializer = DynamicControlInitializer(project_root, controls_module, logger)
    initializer.initialize_all_controls()
    return initializer