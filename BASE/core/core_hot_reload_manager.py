# Filename: BASE/core/core_hot_reload_manager.py
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
    __slots__ = ('name', 'file_path', 'module_ref', 'reload_count', 'last_reload',
                 'last_error', 'backup_ref', 'dependencies', 'dependents')

    def __init__(self, name, file_path, module_ref, reload_count=0,
                 last_reload=None, last_error=None, backup_ref=None, dependencies=None):
        self.name = name
        self.file_path = file_path
        self.module_ref = module_ref
        self.reload_count = reload_count
        self.last_reload = last_reload
        self.last_error = last_error
        self.backup_ref = backup_ref
        self.dependencies = dependencies if dependencies is not None else []
        self.dependents: Set[str] = set()


class ReloadResult:
    __slots__ = ('success', 'module_name', 'error', 'elapsed_time', 'reload_count')

    def __init__(self, success, module_name, error=None, elapsed_time=0.0, reload_count=0):
        self.success = success
        self.module_name = module_name
        self.error = error
        self.elapsed_time = elapsed_time
        self.reload_count = reload_count


class CoreFileChangeHandler(FileSystemEventHandler):
    """Handles file system events — covers both modify-in-place and delete+create saves."""

    def __init__(self, reload_callback: Callable[[str], None], logger=None):
        self.reload_callback = reload_callback
        self.logger = logger
        self._cooldown: Dict[str, float] = {}
        self._cooldown_period = 1.0

    def _handle(self, path: str):
        if not path.endswith('.py'):
            return
        now = time.time()
        if now - self._cooldown.get(path, 0) < self._cooldown_period:
            return
        self._cooldown[path] = now
        # if self.logger:
        #     self.logger.system(f"[Hot Reload] Detected change: {Path(path).name}")
        self.reload_callback(path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_created(self, event):
        # Some editors (vim, PyCharm safe-write) save via rename/create
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        # rename-based saves emit a moved event with dest = original filename
        if not event.is_directory:
            self._handle(event.dest_path)


class CoreHotReloadManager:
    __slots__ = (
        'project_root', 'logger', 'enabled', 'modules', 'observer',
        'thought_processor_ref', 'processing_delegator_ref',
        'reload_history', 'max_history', 'watched_directories',
        'module_path_cache'
    )

    def __init__(self, project_root: Path, logger=None):
        self.project_root = project_root
        self.logger = logger
        self.enabled = WATCHDOG_AVAILABLE

        self.modules: Dict[str, ReloadableModule] = {}
        self.observer = None

        self.thought_processor_ref = None
        self.processing_delegator_ref = None

        self.reload_history: List[ReloadResult] = []
        self.max_history = 100

        self.watched_directories: Set[Path] = set()
        self.module_path_cache: Dict[Path, str] = {}

        if not WATCHDOG_AVAILABLE:
            if logger:
                logger.warning("[Hot Reload] Watchdog not available - hot reload disabled")
            return

        if logger:
            logger.system("[Hot Reload] Manager initialized")

    # ========================================================================
    # REGISTRATION
    # ========================================================================

    def register_constructor(self, name, file_path, module_ref,
                             auto_detect_dependencies=True):
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

        self._update_dependents_graph()

        # if self.logger:
        #     dep_str = f" (depends on: {', '.join(dependencies)})" if dependencies else ""
        #     self.logger.system(f"[Hot Reload] Registered: {name}{dep_str}")

    def watch_directory_recursively(self, directory: Path, pattern: str = "*.py"):
        if not self.enabled:
            return

        if not directory.exists():
            # if self.logger:
            #     self.logger.warning(f"[Hot Reload] Directory not found: {directory}")
            return

        registered_count = 0

        for py_file in directory.rglob(pattern):
            if py_file.stem.startswith(('_', '.')):
                continue

            module_path = self._get_module_path(py_file)
            if not module_path:
                continue

            module_ref = sys.modules.get(module_path)
            if not module_ref:
                if self.logger:
                    self.logger.system(
                        f"[Hot Reload] Module not loaded, skipping: {module_path}"
                    )
                continue

            module_name = py_file.stem
            if module_name not in self.modules:
                self.register_constructor(
                    name=module_name,
                    file_path=py_file,
                    module_ref=module_ref,
                    auto_detect_dependencies=True
                )
                registered_count += 1

        # if self.logger and registered_count > 0:
        #     self.logger.system(
        #         f"[Hot Reload] Auto-registered {registered_count} modules from {directory.name}/"
        #     )

    def _detect_dependencies(self, module_ref, file_path: Path) -> List[str]:
        dependencies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            dependencies.extend(re.findall(r'from\s+\.(\w+)\s+import', source))
            dependencies.extend(re.findall(r'from\s+\.\.[\w.]+\.(\w+)\s+import', source))
            dependencies.extend(re.findall(r'import\s+\.(\w+)', source))

            try:
                module_path = self._get_module_path(file_path)
                if module_path and '.' in module_path:
                    package_parts = module_path.rsplit('.', 1)[0]
                    pattern = rf'from\s+{re.escape(package_parts)}\.(\w+)\s+import'
                    dependencies.extend(re.findall(pattern, source))
            except Exception:
                pass

            module_name = file_path.stem
            dependencies = list(set(d for d in dependencies if d != module_name))

        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"[Hot Reload] Could not detect dependencies for {file_path.name}: {e}"
                )

        return dependencies

    def _update_dependents_graph(self):
        for module in self.modules.values():
            module.dependents.clear()
        for module_name, module in self.modules.items():
            for dep_name in module.dependencies:
                if dep_name in self.modules:
                    self.modules[dep_name].dependents.add(module_name)

    # ========================================================================
    # FILE WATCHING
    # ========================================================================

    def register_thought_processor(self, thought_processor):
        self.thought_processor_ref = thought_processor
        if self.logger:
            self.logger.system("[Hot Reload] Thought processor registered")

    def register_processing_delegator(self, processing_delegator):
        self.processing_delegator_ref = processing_delegator
        if self.logger:
            self.logger.system("[Hot Reload] Processing delegator registered")

    def start_watching(self):
        if not self.enabled or not self.modules:
            if self.logger:
                self.logger.warning(
                    "[Hot Reload] start_watching called but "
                    f"enabled={self.enabled}, modules={len(self.modules)}"
                )
            return

        # Collect unique directories from registered modules
        dirs_to_watch: Set[Path] = set()
        for module in self.modules.values():
            dirs_to_watch.add(module.file_path.resolve().parent)

        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self.observer = Observer()

        for directory in dirs_to_watch:
            handler = CoreFileChangeHandler(
                reload_callback=self._on_file_changed,
                logger=self.logger
            )
            # recursive=True so nested helper files are also caught
            self.observer.schedule(handler, str(directory), recursive=True)
            self.watched_directories.add(directory)

        self.observer.start()

        if self.logger:
            self.logger.system(
                f"[Hot Reload] Watching {len(dirs_to_watch)} directories "
                f"for {len(self.modules)} modules"
            )
            for d in sorted(dirs_to_watch):
                self.logger.system(f"[Hot Reload]   -> {d}")

    def stop_watching(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            if self.logger:
                self.logger.system("[Hot Reload] Stopped watching")

    def _on_file_changed(self, file_path: str):
        changed = Path(file_path).resolve()

        # Direct match
        module_name = None
        for name, module in self.modules.items():
            if module.file_path.resolve() == changed:
                module_name = name
                break

        # Helper file → find related constructor
        if not module_name:
            module_name = self._find_related_constructor(changed)
            if module_name and self.logger:
                self.logger.system(
                    f"[Hot Reload] Helper changed: {changed.name} -> reloading {module_name}"
                )

        if not module_name:
            if self.logger:
                self.logger.system(
                    f"[Hot Reload] No registered module for {changed.name}, skipping"
                )
            return

        self._reload_with_dependents(module_name)

    def _find_related_constructor(self, file_path: Path) -> Optional[str]:
        stem = file_path.stem
        for suffix in ('_parts', '_utils', '_helpers', '_components'):
            if stem.endswith(suffix):
                base = stem.replace(suffix, '')
                candidate = f"{base}_constructor"
                if candidate in self.modules:
                    return candidate
        return None

    def _reload_with_dependents(self, module_name: str):
        # if self.logger:
        #     self.logger.system(f"[Hot Reload] Reloading: {module_name}")

        result = self.reload_module(module_name)

        if result.success:
            # if self.logger:
            #     self.logger.success(
            #         f"[Hot Reload] SUCCESS: {module_name} "
            #         f"(#{result.reload_count}, {result.elapsed_time:.2f}s)"
            #     )
            if module_name in self.modules:
                for dep in list(self.modules[module_name].dependents):
                    self._reload_with_dependents(dep)
        else:
            if self.logger:
                self.logger.error(
                    f"[Hot Reload] FAILED: {module_name}\nError: {result.error}"
                )

    # ========================================================================
    # MODULE RELOADING
    # ========================================================================

    def reload_module(self, module_name: str) -> ReloadResult:
        if module_name not in self.modules:
            return ReloadResult(False, module_name, error="Module not registered")

        start_time = time.time()
        module_info = self.modules[module_name]

        try:
            module_info.backup_ref = module_info.module_ref

            module_path = self._get_module_path(module_info.file_path)
            # if not module_path:
            #     raise RuntimeError(
            #         f"Cannot determine module path for {module_info.file_path}"
            #     )

            # if self.logger:
            #     self.logger.system(
            #         f"[Hot Reload] Reloading module path: {module_path}"
            #     )

            if module_path in sys.modules:
                new_module = importlib.reload(sys.modules[module_path])
            else:
                new_module = importlib.import_module(module_path)

            module_info.module_ref = new_module
            module_info.reload_count += 1
            module_info.last_reload = time.time()
            module_info.last_error = None

            self._update_references(module_name, new_module)

            elapsed = time.time() - start_time
            result = ReloadResult(
                True, module_name,
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
                False, module_name,
                error=str(e),
                elapsed_time=elapsed,
                reload_count=module_info.reload_count
            )
            self._add_to_history(result)

            if self.logger:
                import traceback as tb
                self.logger.error(
                    f"[Hot Reload] Reload error for {module_name}: {e}\n"
                    f"{tb.format_exc()}"
                )
            return result

    def _get_module_path(self, file_path: Path) -> str:
        resolved = file_path.resolve()
        if resolved in self.module_path_cache:
            return self.module_path_cache[resolved]

        # Strategy 1: derive from project root
        try:
            rel = resolved.relative_to(self.project_root.resolve())
            parts = list(rel.parts[:-1]) + [rel.stem]
            path = '.'.join(parts)
            self.module_path_cache[resolved] = path
            return path
        except ValueError:
            pass

        # Strategy 2: search sys.modules by matching file path
        for mod_name, mod in list(sys.modules.items()):
            spec = getattr(mod, '__spec__', None)
            if spec and spec.origin:
                try:
                    if Path(spec.origin).resolve() == resolved:
                        self.module_path_cache[resolved] = mod_name
                        return mod_name
                except Exception:
                    pass

        return ""

    def _update_references(self, module_name: str, new_module: Any):
        """Instantiate fresh constructor from reloaded module and swap live references."""
        if 'constructor' not in module_name:
            return

        class_name = self._get_constructor_class_name(module_name)
        if not class_name:
            if self.logger:
                self.logger.warning(
                    f"[Hot Reload] No class name mapping for {module_name}"
                )
            return

        if not hasattr(new_module, class_name):
            if self.logger:
                self.logger.warning(
                    f"[Hot Reload] Class {class_name} not found in {module_name}"
                )
            return

        new_class = getattr(new_module, class_name)

        tp = self.thought_processor_ref
        pd = self.processing_delegator_ref

        try:
            if 'reactive' in module_name and tp:
                old = tp.reactive_constructor
                tp.reactive_constructor = new_class(
                    tool_manager=old.tool_manager,
                    logger=old.logger
                )
                # if self.logger:
                #     self.logger.system("[Hot Reload] Updated: thought_processor.reactive_constructor")

            elif 'reflective' in module_name and tp:
                old = tp.reflective_constructor
                tp.reflective_constructor = new_class(
                    memory_search=old.memory_search,
                    tool_manager=old.tool_manager,
                    logger=old.logger
                )
                # if self.logger:
                #     self.logger.system("[Hot Reload] Updated: thought_processor.reflective_constructor")

            elif 'proactive' in module_name and tp:
                old = tp.proactive_constructor
                tp.proactive_constructor = new_class(
                    tool_manager=old.tool_manager,
                    logger=old.logger
                )
                # if self.logger:
                #     self.logger.system("[Hot Reload] Updated: thought_processor.proactive_constructor")

            elif 'action' in module_name and tp:
                old = tp.action_constructor
                tp.action_constructor = new_class(
                    tool_manager=old.tool_manager,
                    logger=old.logger
                )
                # if self.logger:
                #     self.logger.system("[Hot Reload] Updated: thought_processor.action_constructor")

            elif 'responsive' in module_name and pd:
                old = pd.responsive_constructor
                pd.responsive_constructor = new_class(
                    memory_search=old.memory_search,
                    logger=old.logger
                )
                # if self.logger:
                #     self.logger.system("[Hot Reload] Updated: processing_delegator.responsive_constructor")

        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"[Hot Reload] Reference update failed for {module_name}: {e}"
                )
            import traceback
            traceback.print_exc()

    def _get_constructor_class_name(self, module_name: str) -> str:
        name_map = {
            'reactive_constructor': 'ReactiveConstructor',
            'reflective_constructor': 'ReflectiveConstructor',
            'proactive_constructor': 'ProactiveConstructor',
            'action_constructor': 'ActionConstructor',
            'responsive_constructor': 'ResponsiveConstructor',
        }
        return name_map.get(module_name, '')

    def _rollback_module(self, module_name: str, backup_ref: Any):
        module_info = self.modules[module_name]
        module_info.module_ref = backup_ref
        self._update_references(module_name, backup_ref)
        # if self.logger:
        #     self.logger.warning(f"[Hot Reload] Rolled back: {module_name}")

    def _add_to_history(self, result: ReloadResult):
        self.reload_history.append(result)
        if len(self.reload_history) > self.max_history:
            self.reload_history.pop(0)

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_statistics(self) -> Dict:
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
                'last_reload': (
                    datetime.fromtimestamp(module.last_reload).strftime('%H:%M:%S')
                    if module.last_reload else 'Never'
                ),
                'last_error': module.last_error,
                'dependencies': module.dependencies,
                'dependents': list(module.dependents),
                'file_path': str(module.file_path)
            }

        return stats

    def get_recent_history(self, count: int = 10) -> List[Dict]:
        return [
            {
                'success': r.success,
                'module': r.module_name,
                'error': r.error,
                'elapsed': f"{r.elapsed_time:.2f}s",
                'reload_count': r.reload_count
            }
            for r in self.reload_history[-count:]
        ]