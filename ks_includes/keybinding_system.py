import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango


class KeyGroupManager:
    """Manages keygroup definitions and resolves keygroup references."""

    def __init__(self, config):
        self.groups: Dict[str, List[str]] = {}
        self._config = config
        self._load_keygroups()
        self._validate_no_cycles()

    def _load_keygroups(self):
        """Load all [keygroup name] sections from config."""
        for section in self._config.get_config().sections():
            if section.startswith("keygroup "):
                name = section[9:].strip()

                if not self._validate_keygroup_name(name):
                    logging.error(f"Invalid keygroup name: {name}")
                    continue

                keys_str = self._config.get_config().get(section, "keys", fallback="")
                if not keys_str:
                    logging.warning(f"Keygroup [{section}] has no keys defined")
                    continue

                # Store raw key list (will be resolved recursively later)
                self.groups[name] = [k.strip() for k in keys_str.split(",") if k.strip()]
                logging.debug(f"Loaded keygroup '{name}' with {len(self.groups[name])} items")

    def _validate_keygroup_name(self, name: str) -> bool:
        """Validate keygroup name follows snake_case convention."""
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            return False

        # Check for collision with common GTK key names (lowercase versions)
        gtk_reserved = {
            "return",
            "escape",
            "backspace",
            "delete",
            "insert",
            "tab",
            "home",
            "end",
            "space",
            "left",
            "right",
            "up",
            "down",
        }
        if name in gtk_reserved:
            logging.error(f"Keygroup name '{name}' conflicts with GTK key name")
            return False

        return True

    def resolve_keys(self, keys_string: str, visited: Optional[Set[str]] = None) -> List[str]:
        """
        Resolve a comma-separated list of keys and keygroup references.

        Args:
            keys_string: Comma-separated keys and keygroup names
            visited: Set of keygroup names already visited (for cycle detection)

        Returns:
            Flat list of resolved key names
        """
        if visited is None:
            visited = set()

        result = []
        for item in keys_string.split(","):
            item = item.strip()
            if not item:
                continue

            # Check if it's a keygroup reference
            if item in self.groups:
                if item in visited:
                    logging.error(f"Circular reference detected in keygroup '{item}'")
                    continue

                visited.add(item)
                # Recursively resolve keygroup
                for sub_item in self.groups[item]:
                    if sub_item in self.groups:
                        result.extend(self.resolve_keys(sub_item, visited.copy()))
                    else:
                        result.append(sub_item)
                visited.discard(item)
            else:
                # Literal key name
                result.append(item)

        return result

    def _validate_no_cycles(self):
        """Detect circular references in keygroup definitions."""
        for group_name in self.groups:
            if not self._check_cycle(group_name, set()):
                logging.error(f"Circular reference detected in keygroup '{group_name}'")

    def _check_cycle(self, group_name: str, visited: Set[str]) -> bool:
        """
        Recursively check for cycles starting from group_name.

        Returns:
            True if no cycle detected, False if cycle found
        """
        if group_name in visited:
            return False

        visited.add(group_name)

        if group_name in self.groups:
            for item in self.groups[group_name]:
                if item in self.groups:
                    if not self._check_cycle(item, visited.copy()):
                        return False

        return True


class AccumulatorManager:
    """Manages keystroke accumulator buffers."""

    def __init__(self, config):
        self.buffers: Dict[str, Dict[str, Any]] = {}
        self._config = config
        self._load_accumulators()

    def _load_accumulators(self):
        """Load all [accumulator name] sections from config."""
        for section in self._config.get_config().sections():
            if section.startswith("accumulator "):
                name = section[12:].strip()

                timeout = self._config.get_config().getfloat(section, "timeout", fallback=1.0)
                handler = self._config.get_config().get(section, "handler", fallback=None)

                self.buffers[name] = {
                    "buffer": "",
                    "timeout": timeout,
                    "last_update": 0,
                    "handler": handler,
                }
                logging.debug(f"Loaded accumulator '{name}' with timeout {timeout}s")

    def add_char(self, buffer_name: str, char: str):
        """Add character to buffer, auto-clear if timeout exceeded."""
        if buffer_name not in self.buffers:
            logging.warning(f"Accumulator '{buffer_name}' not defined")
            return

        buf = self.buffers[buffer_name]
        current_time = time.time()

        # Check timeout
        if buf["last_update"] > 0 and (current_time - buf["last_update"]) > buf["timeout"]:
            buf["buffer"] = ""

        buf["buffer"] += char
        buf["last_update"] = current_time
        logging.debug(f"Accumulator '{buffer_name}': '{buf['buffer']}'")

    def get_buffer(self, buffer_name: str) -> str:
        """Get current buffer contents."""
        if buffer_name not in self.buffers:
            return ""
        return self.buffers[buffer_name]["buffer"]

    def clear(self, buffer_name: str):
        """Clear buffer contents."""
        if buffer_name in self.buffers:
            self.buffers[buffer_name]["buffer"] = ""
            self.buffers[buffer_name]["last_update"] = 0
            logging.debug(f"Cleared accumulator '{buffer_name}'")

    def clear_all(self):
        """Clear all buffers (used when locking screen)."""
        for name in self.buffers:
            self.clear(name)

    def backspace(self, buffer_name: str):
        """Remove last character from buffer."""
        if buffer_name in self.buffers and self.buffers[buffer_name]["buffer"]:
            self.buffers[buffer_name]["buffer"] = self.buffers[buffer_name]["buffer"][:-1]
            logging.debug(f"Backspace in '{buffer_name}': '{self.buffers[buffer_name]['buffer']}'")

    def get_handler(self, buffer_name: str) -> Optional[str]:
        """Get registered handler name for buffer."""
        if buffer_name in self.buffers:
            return self.buffers[buffer_name]["handler"]
        return None


class KeyBindingManager:
    """Manages keybinding definitions."""

    def __init__(self, config, keygroup_manager: KeyGroupManager):
        self.bindings: Dict[str, Dict[str, Any]] = {}
        self._config = config
        self._keygroup_manager = keygroup_manager
        self._load_keybindings()

    def _load_keybindings(self):
        """Load all [keybinding name] sections from config."""
        for section in self._config.get_config().sections():
            if section.startswith("keybinding "):
                name = section[11:].strip()

                # Extract all keybinding fields
                binding = {
                    "name": name,
                    "key": self._config.get_config().get(section, "key", fallback=None),
                    "keys": self._config.get_config().get(section, "keys", fallback=None),
                    "action": self._config.get_config().get(section, "action", fallback=None),
                    "buffer": self._config.get_config().get(section, "buffer", fallback=None),
                    "gcode": self._config.get_config().get(section, "gcode", fallback=None),
                    "panel": self._config.get_config().get(section, "panel", fallback=None),
                    "confirm": self._config.get_config().get(section, "confirm", fallback=None),
                    "function": self._config.get_config().get(section, "function", fallback=None),
                    "require_unlocked": self._config.get_config().getboolean(
                        section, "require_unlocked", fallback=True
                    ),
                }

                if not binding["action"]:
                    logging.warning(f"Keybinding [{section}] has no action defined")
                    continue

                # Expand keygroup references if using 'keys' field
                if binding["keys"]:
                    binding["resolved_keys"] = self._keygroup_manager.resolve_keys(binding["keys"])
                elif binding["key"]:
                    binding["resolved_keys"] = [binding["key"]]
                else:
                    logging.warning(f"Keybinding [{section}] has neither 'key' nor 'keys' defined")
                    continue

                self.bindings[name] = binding
                logging.debug(f"Loaded keybinding '{name}' with action '{binding['action']}'")

    def get_binding(self, name: str) -> Optional[Dict[str, Any]]:
        """Get keybinding definition by name."""
        return self.bindings.get(name)

    def get_all_bindings(self) -> Dict[str, Dict[str, Any]]:
        """Get all keybinding definitions."""
        return self.bindings


class KeyBindingResolver:
    """Resolves active keybindings based on current context."""

    def __init__(self, config, keybinding_manager: KeyBindingManager):
        self.panel_bindings: Dict[str, List[str]] = {}
        self._config = config
        self._keybinding_manager = keybinding_manager
        self._load_panel_bindings()

    def _load_panel_bindings(self):
        """Load all [panel name] sections from config."""
        for section in self._config.get_config().sections():
            if section.startswith("panel "):
                name = section[6:].strip()

                keybindings_str = self._config.get_config().get(section, "keybindings", fallback="")
                if keybindings_str:
                    keybindings = [k.strip() for k in keybindings_str.split(",") if k.strip()]
                    self.panel_bindings[name] = keybindings
                    logging.debug(f"Loaded panel '{name}' with {len(keybindings)} keybindings")

    def get_active_bindings(self, screen) -> Dict[str, Dict[str, Any]]:
        """
        Determine active keybindings based on current context.

        Returns:
            Dictionary mapping key_name -> binding_definition
        """
        # Start with global bindings
        active_binding_names = self.panel_bindings.get("__global", []).copy()

        # Add current panel bindings
        if hasattr(screen, "_cur_panels") and screen._cur_panels:
            current_panel = screen._cur_panels[-1]
            panel_name = (
                current_panel
                if isinstance(current_panel, str)
                else current_panel.__class__.__name__
            )

            if panel_name in self.panel_bindings:
                active_binding_names.extend(self.panel_bindings[panel_name])

        # Resolve binding names to actual bindings
        active_bindings = {}
        for binding_name in active_binding_names:
            binding = self._keybinding_manager.get_binding(binding_name)
            if binding:
                # Map each resolved key to this binding
                for key in binding["resolved_keys"]:
                    # Later bindings override earlier ones (last defined wins)
                    active_bindings[key] = binding

        # Filter by lock state if locked
        if hasattr(screen, "lock") and screen.lock.is_locked():
            active_bindings = {
                key: binding
                for key, binding in active_bindings.items()
                if not binding["require_unlocked"]
            }

        return active_bindings


class KeyBindingSystem:
    """Main coordinator for the keybinding system."""

    def __init__(
        self,
        screen,
        keybinding_resolver: KeyBindingResolver,
        accumulator_manager: AccumulatorManager,
    ):
        self._screen = screen
        self._resolver = keybinding_resolver
        self._accumulator_manager = accumulator_manager
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, name: str, handler: Callable):
        """Register a custom function handler."""
        self._handlers[name] = handler
        logging.info(f"Registered keybinding handler: {name}")

    def handle_key_event(self, event) -> bool:
        """
        Handle key press event.

        Returns:
            True if event was handled, False to pass through
        """
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)

        if not keyname:
            return False

        # Get active bindings for current context
        active_bindings = self._resolver.get_active_bindings(self._screen)

        if keyname not in active_bindings:
            return False

        binding = active_bindings[keyname]
        action = binding["action"]

        logging.debug(f"Key '{keyname}' triggered action '{action}'")

        # Execute action
        try:
            if action == "accumulate":
                self._action_accumulate(binding, keyname)
            elif action == "gcode":
                self._action_gcode(binding)
            elif action == "exec_gcode":
                self._action_exec_gcode(binding)
            elif action == "clear":
                self._action_clear(binding)
            elif action == "backspace":
                self._action_backspace(binding)
            elif action == "function":
                self._action_function(binding)
            elif action == "panel":
                self._action_panel(binding)
            elif action == "exec_function":
                self._action_exec_function(binding)
            else:
                logging.warning(f"Unknown action type: {action}")
                return False

            return True
        except Exception as e:
            logging.exception(f"Error executing keybinding action '{action}': {e}")
            return False

    def _action_accumulate(self, binding: Dict[str, Any], keyname: str):
        """Add key to accumulator buffer."""
        buffer_name = binding.get("buffer")
        if not buffer_name:
            logging.warning("Accumulate action requires 'buffer' field")
            return

        self._accumulator_manager.add_char(buffer_name, keyname)

    def _action_gcode(self, binding: Dict[str, Any]):
        """Execute buffer contents as gcode."""
        buffer_name = binding.get("buffer")
        if not buffer_name:
            logging.warning("Gcode action requires 'buffer' field")
            return

        gcode = self._accumulator_manager.get_buffer(buffer_name)
        if not gcode:
            logging.debug("Buffer empty, nothing to execute")
            return

        # Show confirmation dialog if configured
        if binding.get("confirm"):
            self._show_keybinding_confirm(binding["confirm"], lambda: self._execute_gcode(gcode))
        else:
            self._execute_gcode(gcode)

    def _action_exec_gcode(self, binding: Dict[str, Any]):
        """Execute literal gcode string."""
        gcode = binding.get("gcode")
        if not gcode:
            logging.warning("Exec_gcode action requires 'gcode' field")
            return

        # Show confirmation dialog if configured
        if binding.get("confirm"):
            self._show_keybinding_confirm(binding["confirm"], lambda: self._execute_gcode(gcode))
        else:
            self._execute_gcode(gcode)

    def _execute_gcode(self, gcode: str):
        """Execute gcode via printer interface."""
        if hasattr(self._screen, "_printer") and self._screen._printer:
            self._screen._printer.gcode_script(gcode)
            logging.info(f"Executed gcode: {gcode[:50]}...")
        else:
            logging.error("Printer interface not available")

    def _action_clear(self, binding: Dict[str, Any]):
        """Clear accumulator buffer."""
        buffer_name = binding.get("buffer")
        if not buffer_name:
            logging.warning("Clear action requires 'buffer' field")
            return

        self._accumulator_manager.clear(buffer_name)

    def _action_backspace(self, binding: Dict[str, Any]):
        """Remove last character from buffer."""
        buffer_name = binding.get("buffer")
        if not buffer_name:
            logging.warning("Backspace action requires 'buffer' field")
            return

        self._accumulator_manager.backspace(buffer_name)

    def _action_function(self, binding: Dict[str, Any]):
        """Call registered handler function with buffer contents."""
        function_name = binding.get("function")
        buffer_name = binding.get("buffer")

        if not function_name:
            logging.warning("Function action requires 'function' field")
            return

        if function_name not in self._handlers:
            logging.error(f"Handler '{function_name}' not registered")
            return

        buffer_contents = self._accumulator_manager.get_buffer(buffer_name) if buffer_name else ""

        # Show confirmation dialog if configured
        if binding.get("confirm"):
            self._show_keybinding_confirm(
                binding["confirm"], lambda: self._handlers[function_name](buffer_contents)
            )
        else:
            self._handlers[function_name](buffer_contents)

    def _action_exec_function(self, binding: Dict[str, Any]):
        """Call registered handler function without arguments."""
        function_name = binding.get("function")

        if not function_name:
            logging.warning("Exec_function action requires 'function' field")
            return

        if function_name not in self._handlers:
            logging.error(f"Handler '{function_name}' not registered")
            return

        # Show confirmation dialog if configured
        if binding.get("confirm"):
            self._show_keybinding_confirm(
                binding["confirm"], lambda: self._handlers[function_name]()
            )
        else:
            self._handlers[function_name]()

    def _action_panel(self, binding: Dict[str, Any]):
        """Navigate to panel."""
        panel_name = binding.get("panel")
        if not panel_name:
            logging.warning("Panel action requires 'panel' field")
            return

        if hasattr(self._screen, "show_panel"):
            self._screen.show_panel(panel_name)
            logging.info(f"Navigated to panel: {panel_name}")
        else:
            logging.error("Screen does not support panel navigation")

    def on_lock(self):
        """Called when screen is locked - clear all accumulators for security."""
        self._accumulator_manager.clear_all()
        logging.info("Keybinding system: cleared all accumulators on lock")

    def _show_keybinding_confirm(self, text: str, callback: Callable):
        """Show confirmation dialog for keybinding action."""
        if not hasattr(self._screen, "gtk"):
            logging.error("GTK interface not available for confirmation dialog")
            return

        buttons = [
            {"name": "Accept", "response": Gtk.ResponseType.OK, "style": "dialog-info"},
            {"name": "Cancel", "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"},
        ]

        label = Gtk.Label(
            hexpand=True,
            vexpand=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        label.set_markup(text)

        def response_handler(dialog, response_id):
            self._screen.gtk.remove_dialog(dialog)
            if response_id == Gtk.ResponseType.OK:
                callback()

        self._screen.gtk.Dialog("KlipperScreen", buttons, label, response_handler)
