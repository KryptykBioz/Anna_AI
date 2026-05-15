# Filename: BASE/interface/dynamic_tool_panel_loader.py
"""
Dynamic Tool Panel Loader
Discovers and loads GUI components from installed tools
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
import importlib.util
import sys


class DynamicToolPanelLoader:
    """
    Discovers and loads GUI components from tools/installed/ directory
    Each tool can optionally provide a component.py file with GUI panel
    """

    __slots__ = ('project_root', 'logger', 'hot_reload_manager', 'tools_dir', 
                 '_components', '_component_metadata')

    def __init__(self, project_root: Path, logger=None, hot_reload_manager=None):
        """
        Initialize panel loader
        
        Args:
            project_root: Project root path
            logger: Optional logger instance
            hot_reload_manager: Optional HotReloadManager for tool reloading
        """
        self.project_root = project_root
        self.logger = logger
        self.hot_reload_manager = hot_reload_manager
        self.tools_dir = project_root / 'BASE' / 'tools' / 'installed'
        
        # Discovered components
        self._components: Dict[str, Any] = {}
        self._component_metadata: Dict[str, Dict] = {}
    
    def discover_tool_panels(self) -> List[Dict[str, Any]]:
        """
        Discover all tools with GUI components
        
        Returns:
            List of dicts with tool panel metadata:
            {
                'tool_name': str,
                'display_name': str,
                'category': str,
                'has_component': bool,
                'component_path': Path or None
            }
        """
        panels = []
        
        if not self.tools_dir.exists():
            if self.logger:
                self.logger.warning(f"[Panel Loader] Tools directory not found: {self.tools_dir}")
            return panels
        
        # Scan each tool directory
        for tool_dir in self.tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue
            
            # Skip special directories
            if tool_dir.name.startswith('_') or tool_dir.name.startswith('.'):
                continue
            
            # Check for component.py
            component_file = tool_dir / 'component.py'
            info_file = tool_dir / 'information.json'
            
            # Load tool metadata
            metadata = self._load_tool_metadata(tool_dir, info_file)
            
            if not metadata:
                continue
            
            # Check if component exists
            has_component = component_file.exists()
            
            # FIX: Ensure display_name is never None
            tool_name = metadata.get('tool_name', tool_dir.name)
            display_name = metadata.get('display_name')
            if not display_name:
                # Fallback: convert tool_name to readable format
                display_name = tool_name.replace('_', ' ').title()
            
            panel_info = {
                'tool_name': tool_name,
                'display_name': display_name,  # Guaranteed non-None
                'category': metadata.get('category', 'Other Tools'),
                'control_variable_name': metadata.get('control_variable_name'),
                'has_component': has_component,
                'component_path': component_file if has_component else None,
                'description': metadata.get('description', 'No description'),
                'icon': metadata.get('icon', '🔧')
            }
            
            panels.append(panel_info)
            
            # if self.logger and has_component:
            #     self.logger.system(
            #         f"[Panel Loader] Found component for {panel_info['tool_name']}"
            #     )
        
        # Sort by category and name
        panels.sort(key=lambda x: (x['category'], x['display_name']))
        
        if self.logger:
            component_count = sum(1 for p in panels if p['has_component'])
            self.logger.system(
                f"[Panel Loader] Discovered {len(panels)} tools, "
                f"{component_count} with GUI components"
            )
        
        return panels
    
    def _load_tool_metadata(self, tool_dir: Path, info_file: Path) -> Optional[Dict]:
        """
        Load tool metadata from information.json
        
        Args:
            tool_dir: Tool directory
            info_file: information.json path
            
        Returns:
            Metadata dict or None
        """
        if not info_file.exists():
            return None
        
        try:
            import json
            
            with open(info_file, 'r') as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            
            # Extract display name with multiple fallbacks
            display_name = (
                metadata.get('gui_label') or 
                metadata.get('display_name') or
                data.get('tool_name', '').replace('_', ' ').title()
            )
            
            return {
                'tool_name': data.get('tool_name'),
                'display_name': display_name,  # Never None
                'category': metadata.get('category', 'Other Tools'),
                'control_variable_name': data.get('control_variable_name'),
                'description': data.get('tool_description', ''),
                'icon': metadata.get('gui_icon', '🔧')
            }
        
        except Exception as e:
            # if self.logger:
            #     self.logger.warning(f"[Panel Loader] Failed to load metadata from {tool_dir.name}: {e}")
            return None
    
    def load_component(self, tool_name: str, component_path: Path, parent_gui, ai_core) -> Optional[Any]:
        if tool_name in self._components:
            # if self.logger:
            #     self.logger.system(f"[Panel Loader] Component already loaded: {tool_name}")
            return self._components[tool_name]

        try:
            module_name = f"tool_component_{tool_name}"

            # Evict stale cached module so file changes are picked up on reload
            sys.modules.pop(module_name, None)

            spec = importlib.util.spec_from_file_location(module_name, str(component_path))

            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module from {component_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, 'create_component'):
                if self.logger:
                    self.logger.error(
                        f"[Panel Loader] {tool_name} component missing create_component() function"
                    )
                return None

            create_func = getattr(module, 'create_component')
            component = create_func(parent_gui, ai_core, self.logger)

            self._components[tool_name] = component

            # if self.logger:
            #     self.logger.success(f"[Panel Loader] Loaded component: {tool_name}")

            return component

        except Exception as e:
            if self.logger:
                self.logger.error(f"[Panel Loader] Failed to load {tool_name} component: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_component(self, tool_name: str) -> Optional[Any]:
        """
        Get loaded component instance
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Component instance or None
        """
        return self._components.get(tool_name)
    
    def unload_component(self, tool_name: str):
        """
        Unload a component and cleanup resources
        
        Args:
            tool_name: Name of tool
        """
        if tool_name not in self._components:
            return
        
        component = self._components[tool_name]
        
        # Call cleanup if available
        if hasattr(component, 'cleanup'):
            try:
                component.cleanup()
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"[Panel Loader] Error cleaning up {tool_name}: {e}")
        
        # Remove from cache
        del self._components[tool_name]
        
        if self.logger:
            self.logger.system(f"[Panel Loader] Unloaded component: {tool_name}")
    
    def cleanup_all(self):
        """Cleanup all loaded components"""
        tool_names = list(self._components.keys())
        
        for tool_name in tool_names:
            self.unload_component(tool_name)
        
        # if self.logger:
        #     self.logger.system("[Panel Loader] Cleaned up all components")
    
    def get_loaded_components(self) -> Dict[str, Any]:
        """Get all loaded components"""
        return self._components.copy()
    
    def create_reload_button_for_tool(self, parent, tool_name: str):
        """
        Create a reload button for a specific tool
        
        Args:
            parent: Parent widget (tkinter)
            tool_name: Name of tool
        
        Returns:
            Reload button widget or None
        """
        if not self.hot_reload_manager:
            return None
        
        return self.hot_reload_manager.create_reload_button(
            parent=parent,
            tool_name=tool_name
        )