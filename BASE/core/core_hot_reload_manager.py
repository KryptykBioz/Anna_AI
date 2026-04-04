# Filename: BASE/core/core_hot_reload_manager.py
"""
Core Module Hot-Reload Manager - HYBRID APPROACH
=================================================
Enhanced hot-reloading with automatic dependency detection and directory watching

Features:
- Automatic dependency detection by parsing imports
- Recursive directory watching
- Smart invalidation of dependent modules
- Pattern-based helper file detection
- Comprehensive logging and rollback

Phase 1: Prompt constructors (stateless, safe to reload)
- reactive_constructor + helpers
- reflective_constructor + helpers
- proactive_constructor + helpers
- action_constructor + helpers
- responsive_constructor + helpers
"""

import sys
import importlib
import time
import re
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None


class ReloadableModule:
    """Metadata for a reloadable module"""
    __slots__ = ('name', 'file_path', 'module_ref', 'reload_count', 'last_reload', 
                 'last_error', 'backup_ref', 'dependencies', 'dependents')
    
    def __init__(
        self,
        name: str,
        file_path: Path,
        module_ref: Any,
        reload_count: int = 0,
        last_reload: Optional[float] = None,
        last_error: Optional[str] = None,
        backup_ref: Any = None,
        dependencies: Optional[List[str]] = None
    ):
        self.name = name
        self.file_path = file_path
        self.module_ref = module_ref
        self.reload_count = reload_count
        self.last_reload = last_reload
        self.last_error = last_error
        self.backup_ref = backup_ref
        self.dependencies = dependencies if dependencies is not None else []
        self.dependents: Set[str] = set()  # Modules that depend on this one


class ReloadResult:
    """Result of a reload operation"""
    __slots__ = ('success', 'module_name', 'error', 'elapsed_time', 'reload_count')
    
    def __init__(
        self,
        success: bool,
        module_name: str,
        error: Optional[str] = None,
        elapsed_time: float = 0.0,
        reload_count: int = 0
    ):
        self.success = success
        self.module_name = module_name
        self.error = error
        self.elapsed_time = elapsed_time
        self.reload_count = reload_count


class CoreFileChangeHandler(FileSystemEventHandler):
    """Handles file system events for core modules"""
    
    def __init__(self, reload_callback: Callable[[str], None], logger=None):
        self.reload_callback = reload_callback
        self.logger = logger
        self.cooldown = {}
        self.cooldown_period = 1.0
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        if file_path.suffix != '.py':
            return
        
        current_time = time.time()
        last_reload = self.cooldown.get(str(file_path), 0)
        
        if current_time - last_reload < self.cooldown_period:
            return
        
        self.cooldown[str(file_path)] = current_time
        
        if self.logger:
            self.logger.system(f"[Hot Reload] Detected change: {file_path.name}")
        
        self.reload_callback(str(file_path))


class CoreHotReloadManager:
    """
    Manages hot-reloading of core system modules with automatic dependency tracking
    
    HYBRID APPROACH:
    - Auto-detects dependencies by parsing imports
    - Watches directories recursively
    - Smart cascade reloading of dependents
    """
    
    __slots__ = (
        'project_root', 'logger', 'enabled', 'modules', 'observer',
        'thought_processor_ref', 'processing_delegator_ref',
        'reload_history', 'max_history', 'watched_directories',
        'module_path_cache'
    )
    
    def __init__(self, project_root: Path, logger=None):
        """
        Initialize core hot-reload manager
        
        Args:
            project_root: Project root directory
            logger: Logger instance
        """
        self.project_root = project_root
        self.logger = logger
        self.enabled = WATCHDOG_AVAILABLE
        
        self.modules: Dict[str, ReloadableModule] = {}
        self.observer = None
        
        self.thought_processor_ref = None
        self.processing_delegator_ref = None
        
        self.reload_history: List[ReloadResult] = []
        self.max_history = 50
        
        self.watched_directories: Set[Path] = set()
        self.module_path_cache: Dict[Path, str] = {}
        
        if not WATCHDOG_AVAILABLE:
            if logger:
                logger.warning("[Hot Reload] Watchdog not available - hot reload disabled")
            return
        
        if logger:
            logger.system("[Hot Reload] Manager initialized")
    
    # ========================================================================
    # REGISTRATION - HYBRID APPROACH
    # ========================================================================
    
    def register_constructor(
        self,
        name: str,
        file_path: Path,
        module_ref: Any,
        auto_detect_dependencies: bool = True
    ):
        """
        Register a constructor with optional auto-dependency detection
        
        Args:
            name: Constructor name (e.g., 'reactive_constructor')
            file_path: Path to the .py file
            module_ref: Current module object
            auto_detect_dependencies: Auto-detect imports (default True)
        """
        if not self.enabled:
            return
        
        dependencies = []
        
        if auto_detect_dependencies and module_ref:
            dependencies = self._detect_dependencies(module_ref, file_path)
        
        self.modules[name] = ReloadableModule(
            name=name,
            file_path=file_path,
            module_ref=module_ref,
            dependencies=dependencies
        )
        
        # Update reverse dependency graph
        self._update_dependents_graph()
        
        if self.logger:
            dep_str = f" (depends on: {', '.join(dependencies)})" if dependencies else ""
            self.logger.system(f"[Hot Reload] Registered: {name}{dep_str}")
    
    def watch_directory_recursively(self, directory: Path, pattern: str = "*.py"):
        """
        Watch a directory and auto-register all Python files
        
        Args:
            directory: Directory to watch
            pattern: File pattern to match (default: *.py)
        """
        if not self.enabled:
            return
        
        if not directory.exists():
            if self.logger:
                self.logger.warning(f"[Hot Reload] Directory not found: {directory}")
            return
        
        registered_count = 0
        
        # Find all Python files
        for py_file in directory.rglob(pattern):
            if py_file.stem.startswith('_'):
                continue
            
            if py_file.stem.startswith('.'):
                continue
            
            # Get module path
            module_path = self._get_module_path(py_file)
            
            if not module_path:
                continue
            
            # Check if already loaded
            module_ref = sys.modules.get(module_path)
            
            if not module_ref:
                # Module not loaded yet - skip
                continue
            
            # Register with auto-detection
            module_name = py_file.stem
            
            if module_name not in self.modules:
                self.register_constructor(
                    name=module_name,
                    file_path=py_file,
                    module_ref=module_ref,
                    auto_detect_dependencies=True
                )
                registered_count += 1
        
        if self.logger and registered_count > 0:
            self.logger.system(
                f"[Hot Reload] Auto-registered {registered_count} modules from {directory.name}/"
            )
    
    def _detect_dependencies(self, module_ref: Any, file_path: Path) -> List[str]:
        """
        Auto-detect module dependencies by parsing imports
        
        Args:
            module_ref: Module object
            file_path: Path to module file
        
        Returns:
            List of dependency module names
        """
        dependencies = []
        
        try:
            # Read source file
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            # Pattern 1: from .module import ...
            relative_imports = re.findall(r'from\s+\.(\w+)\s+import', source)
            dependencies.extend(relative_imports)
            
            # Pattern 2: from ..package.module import ...
            package_imports = re.findall(r'from\s+\.\.[\w.]+\.(\w+)\s+import', source)
            dependencies.extend(package_imports)
            
            # Pattern 3: import .module (less common)
            direct_imports = re.findall(r'import\s+\.(\w+)', source)
            dependencies.extend(direct_imports)
            
            # Pattern 4: from BASE.core.proactive.module import ... (absolute imports in same package)
            # Extract the package path from current file
            try:
                module_path = self._get_module_path(file_path)
                if module_path:
                    # Get package prefix (e.g., "BASE.core.proactive")
                    package_parts = module_path.rsplit('.', 1)[0] if '.' in module_path else ''
                    
                    if package_parts:
                        # Find imports from same package
                        pattern = rf'from\s+{re.escape(package_parts)}\.(\w+)\s+import'
                        same_package_imports = re.findall(pattern, source)
                        dependencies.extend(same_package_imports)
            except:
                pass
            
            # Remove duplicates and self-references
            module_name = file_path.stem
            dependencies = list(set(dep for dep in dependencies if dep != module_name))
            
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Hot Reload] Could not detect dependencies for {file_path.name}: {e}")
        
        return dependencies
    
    def _update_dependents_graph(self):
        """Update the reverse dependency graph (who depends on whom)"""
        # Clear existing dependents
        for module in self.modules.values():
            module.dependents.clear()
        
        # Rebuild dependents
        for module_name, module in self.modules.items():
            for dep_name in module.dependencies:
                if dep_name in self.modules:
                    self.modules[dep_name].dependents.add(module_name)
    
    # ========================================================================
    # SMART PATTERN-BASED DETECTION
    # ========================================================================
    
    def _find_related_constructor(self, file_path: Path) -> Optional[str]:
        """
        Find the main constructor related to a helper file
        
        Examples:
            proactive_parts.py -> proactive_constructor
            reflective_utils.py -> reflective_constructor
        """
        stem = file_path.stem
        
        # Pattern: [name]_parts, [name]_utils, [name]_helpers
        for suffix in ['_parts', '_utils', '_helpers', '_components']:
            if stem.endswith(suffix):
                base_name = stem.replace(suffix, '')
                constructor_name = f"{base_name}_constructor"
                
                if constructor_name in self.modules:
                    return constructor_name
        
        return None
    
    # ========================================================================
    # FILE WATCHING
    # ========================================================================
    
    def register_thought_processor(self, thought_processor):
        """Register thought processor for reference updating"""
        self.thought_processor_ref = thought_processor
        if self.logger:
            self.logger.system("[Hot Reload] Thought processor registered")
    
    def register_processing_delegator(self, processing_delegator):
        """Register processing delegator for reference updating"""
        self.processing_delegator_ref = processing_delegator
        if self.logger:
            self.logger.system("[Hot Reload] Processing delegator registered")
    
    def start_watching(self):
        """Start file watching for registered modules"""
        if not self.enabled or not self.modules:
            return
        
        watched_dirs = set()
        for module in self.modules.values():
            watched_dirs.add(module.file_path.parent)
        
        self.observer = Observer()
        
        for directory in watched_dirs:
            handler = CoreFileChangeHandler(
                reload_callback=self._on_file_changed,
                logger=self.logger
            )
            self.observer.schedule(handler, str(directory), recursive=False)
            self.watched_directories.add(directory)
        
        self.observer.start()
        
        if self.logger:
            self.logger.system(
                f"[Hot Reload] Watching {len(watched_dirs)} directories "
                f"for {len(self.modules)} modules"
            )
    
    def stop_watching(self):
        """Stop file watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            
            if self.logger:
                self.logger.system("[Hot Reload] Stopped watching")
    
    def _on_file_changed(self, file_path: str):
        """Handle file change event with smart cascade reloading"""
        file_path = Path(file_path)
        
        # Find the module by exact path match
        module_name = None
        for name, module in self.modules.items():
            if module.file_path.resolve() == file_path.resolve():
                module_name = name
                break
        
        # If not found, check if it's a helper file
        if not module_name:
            module_name = self._find_related_constructor(file_path)
            
            if module_name and self.logger:
                self.logger.system(
                    f"[Hot Reload] Helper file changed: {file_path.name} -> "
                    f"reloading {module_name}"
                )
        
        if not module_name:
            return
        
        # Reload the module and its dependents
        self._reload_with_dependents(module_name)
    
    def _reload_with_dependents(self, module_name: str):
        """Reload a module and cascade to all dependents"""
        if self.logger:
            self.logger.system(f"[Hot Reload] Reloading: {module_name}")
        
        result = self.reload_module(module_name)
        
        if result.success:
            if self.logger:
                self.logger.success(
                    f"[Hot Reload] SUCCESS: {module_name} "
                    f"(#{result.reload_count}, {result.elapsed_time:.2f}s)"
                )
            
            # Cascade to dependents
            if module_name in self.modules:
                dependents = self.modules[module_name].dependents
                
                if dependents and self.logger:
                    self.logger.system(
                        f"[Hot Reload] Cascading to {len(dependents)} dependent(s): "
                        f"{', '.join(dependents)}"
                    )
                
                for dependent_name in dependents:
                    self._reload_with_dependents(dependent_name)
        
        else:
            if self.logger:
                self.logger.error(
                    f"[Hot Reload] FAILED: {module_name}\n"
                    f"Error: {result.error}"
                )
    
    # ========================================================================
    # MODULE RELOADING
    # ========================================================================
    
    def reload_module(self, module_name: str) -> ReloadResult:
        """
        Reload a registered module
        
        Args:
            module_name: Name of module to reload
        
        Returns:
            ReloadResult with success status
        """
        if module_name not in self.modules:
            return ReloadResult(
                success=False,
                module_name=module_name,
                error="Module not registered"
            )
        
        start_time = time.time()
        module_info = self.modules[module_name]
        
        try:
            module_info.backup_ref = module_info.module_ref
            
            module_path = self._get_module_path(module_info.file_path)
            
            if module_path in sys.modules:
                old_module = sys.modules[module_path]
                
                importlib.reload(old_module)
                new_module = sys.modules[module_path]
            else:
                new_module = importlib.import_module(module_path)
            
            module_info.module_ref = new_module
            module_info.reload_count += 1
            module_info.last_reload = time.time()
            module_info.last_error = None
            
            self._update_references(module_name, new_module)
            
            elapsed = time.time() - start_time
            
            result = ReloadResult(
                success=True,
                module_name=module_name,
                elapsed_time=elapsed,
                reload_count=module_info.reload_count
            )
            
            self._add_to_history(result)
            
            return result
        
        except Exception as e:
            module_info.last_error = str(e)
            
            if module_info.backup_ref:
                self._rollback_module(module_name, module_info.backup_ref)
            
            elapsed = time.time() - start_time
            
            result = ReloadResult(
                success=False,
                module_name=module_name,
                error=str(e),
                elapsed_time=elapsed,
                reload_count=module_info.reload_count
            )
            
            self._add_to_history(result)
            
            return result
    
    def _get_module_path(self, file_path: Path) -> str:
        """Convert file path to module import path"""
        # Check cache first
        if file_path in self.module_path_cache:
            return self.module_path_cache[file_path]
        
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            # File is outside project root
            return ""
        
        parts = list(rel_path.parts[:-1])
        parts.append(rel_path.stem)
        
        module_path = '.'.join(parts)
        
        # Cache it
        self.module_path_cache[file_path] = module_path
        
        return module_path
    
    def _update_references(self, module_name: str, new_module: Any):
        """
        Update references in dependent objects
        
        This is the critical part - updating live references to the reloaded module
        """
        if 'constructor' not in module_name:
            return
        
        class_name = self._get_constructor_class_name(module_name)
        
        if not hasattr(new_module, class_name):
            if self.logger:
                self.logger.warning(
                    f"[Hot Reload] Class {class_name} not found in {module_name}"
                )
            return
        
        new_class = getattr(new_module, class_name)
        
        if 'reactive' in module_name and self.thought_processor_ref:
            old_constructor = self.thought_processor_ref.reactive_constructor
            
            new_constructor = new_class(
                tool_manager=old_constructor.tool_manager,
                logger=old_constructor.logger
            )
            
            self.thought_processor_ref.reactive_constructor = new_constructor
            
            if self.logger:
                self.logger.system("[Hot Reload] Updated: thought_processor.reactive_constructor")
        
        if 'reflective' in module_name and self.thought_processor_ref:
            old_constructor = self.thought_processor_ref.reflective_constructor
            
            new_constructor = new_class(
                memory_search=old_constructor.memory_search,
                tool_manager=old_constructor.tool_manager,
                logger=old_constructor.logger
            )
            
            self.thought_processor_ref.reflective_constructor = new_constructor
            
            if self.logger:
                self.logger.system("[Hot Reload] Updated: thought_processor.reflective_constructor")
        
        if 'proactive' in module_name and self.thought_processor_ref:
            old_constructor = self.thought_processor_ref.proactive_constructor
            
            new_constructor = new_class(
                tool_manager=old_constructor.tool_manager,
                logger=old_constructor.logger
            )
            
            self.thought_processor_ref.proactive_constructor = new_constructor
            
            if self.logger:
                self.logger.system("[Hot Reload] Updated: thought_processor.proactive_constructor")
        
        if 'action' in module_name and self.thought_processor_ref:
            old_constructor = self.thought_processor_ref.action_constructor
            
            new_constructor = new_class(
                tool_manager=old_constructor.tool_manager,
                logger=old_constructor.logger
            )
            
            self.thought_processor_ref.action_constructor = new_constructor
            
            if self.logger:
                self.logger.system("[Hot Reload] Updated: thought_processor.action_constructor")
        
        if 'responsive' in module_name and self.processing_delegator_ref:
            old_constructor = self.processing_delegator_ref.responsive_constructor
            
            new_constructor = new_class(
                memory_search=old_constructor.memory_search,
                logger=old_constructor.logger
            )
            
            self.processing_delegator_ref.responsive_constructor = new_constructor
            
            if self.logger:
                self.logger.system("[Hot Reload] Updated: processing_delegator.responsive_constructor")
    
    def _get_constructor_class_name(self, module_name: str) -> str:
        """Get class name from module name"""
        name_map = {
            'reactive_constructor': 'ReactiveConstructor',
            'reflective_constructor': 'ReflectiveConstructor',
            'proactive_constructor': 'ProactiveConstructor',
            'action_constructor': 'ActionConstructor',
            'responsive_constructor': 'ResponsiveConstructor'
        }
        return name_map.get(module_name, '')
    
    def _rollback_module(self, module_name: str, backup_ref: Any):
        """Rollback to previous module version on error"""
        module_info = self.modules[module_name]
        module_info.module_ref = backup_ref
        
        self._update_references(module_name, backup_ref)
        
        if self.logger:
            self.logger.warning(f"[Hot Reload] Rolled back: {module_name}")
    
    def _add_to_history(self, result: ReloadResult):
        """Add reload result to history"""
        self.reload_history.append(result)
        
        if len(self.reload_history) > self.max_history:
            self.reload_history.pop(0)
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_statistics(self) -> Dict:
        """Get reload statistics"""
        total_reloads = sum(m.reload_count for m in self.modules.values())
        
        successful = sum(1 for r in self.reload_history if r.success)
        failed = len(self.reload_history) - successful
        
        stats = {
            'enabled': self.enabled,
            'registered_modules': len(self.modules),
            'total_reloads': total_reloads,
            'successful_reloads': successful,
            'failed_reloads': failed,
            'modules': {}
        }
        
        for name, module in self.modules.items():
            stats['modules'][name] = {
                'reload_count': module.reload_count,
                'last_reload': datetime.fromtimestamp(module.last_reload).strftime('%H:%M:%S') if module.last_reload else 'Never',
                'last_error': module.last_error,
                'dependencies': module.dependencies,
                'dependents': list(module.dependents)
            }
        
        return stats
    
    def get_recent_history(self, count: int = 10) -> List[Dict]:
        """Get recent reload history"""
        recent = self.reload_history[-count:]
        
        return [
            {
                'success': r.success,
                'module': r.module_name,
                'error': r.error,
                'elapsed': f"{r.elapsed_time:.2f}s",
                'reload_count': r.reload_count
            }
            for r in recent
        ]