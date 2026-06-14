# KlipperScreen Keybinding System

This directory contains the keybinding system configuration files for KlipperScreen.

## Overview

The keybinding system provides a flexible, config-driven way to bind keyboard keys to actions in KlipperScreen. This improves accessibility and enables alternative input methods beyond touchscreen interaction.

## Features

- **Keygroups**: Reusable sets of keys (e.g., all letters, all digits)
- **Keybindings**: Named actions bound to specific keys or keygroups
- **Accumulators**: Buffers that collect keystrokes for multi-key sequences
- **Panel-specific contexts**: Different keybindings per panel
- **Lock state awareness**: Certain bindings can work even when screen is locked

## Quick Start

To enable keyboard navigation with default Escape/Backspace behavior, include in your `KlipperScreen.conf`:

```ini
[include /path/to/KlipperScreen/keybindings/default_navigation.cfg]
```

Or for more comprehensive keyboard shortcuts:

```ini
[include /path/to/KlipperScreen/keybindings/examples/basic_navigation.cfg]
```

## Configuration Syntax

### Keygroups

Define reusable sets of keys. Keygroup names MUST use snake_case (lowercase with underscores):

```ini
[keygroup lower_case]
keys = a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z

[keygroup my_custom_keys]
keys = lower_case,upper_case,1,2,3  # Can reference other keygroups
```

### Accumulators

Define buffers that collect keystrokes:

```ini
[accumulator gcode_input]
timeout = 2.0  # Auto-clear after 2 seconds of inactivity
```

### Keybindings

Bind keys to actions. Keybinding names MUST use snake_case:

```ini
[keybinding emergency_stop]
key = F1  # Single key
action = exec_gcode
gcode = M112
confirm = Execute emergency stop?  # Optional confirmation
require_unlocked = false  # Works even when locked

[keybinding accumulate_text]
keys = alpha_numeric,special_symbols  # Multiple keys via keygroups
action = accumulate
buffer = gcode_input
```

### Panel Assignment

Assign keybindings to panels:

```ini
[panel __global]
keybindings = emergency_stop,nav_home  # Active on all panels

[panel move]
keybindings = move_up,move_down  # Only active on move panel
```

## Action Types

- `accumulate` - Add key to buffer
- `gcode` - Execute buffer contents as gcode
- `exec_gcode` - Execute literal gcode string
- `clear` - Clear buffer
- `backspace` - Remove last char from buffer
- `function` - Call registered handler function with buffer
- `panel` - Navigate to panel
- `exec_function` - Call handler with no args

## Naming Conventions

- **GTK key names**: PascalCase or Mixed_Case (`Return`, `Escape`, `BackSpace`, `Shift_L`)
- **Keygroup names**: snake_case with underscore (`lower_case`, `num_keys`, `special_symbols`)
- **Keybinding names**: snake_case with underscore (`emergency_stop`, `nav_home`)

This convention prevents naming collisions between GTK keys and custom keygroups.

## Files

- `keygroups_us_ascii.cfg` - Standard US ASCII keyboard keygroups
- `default_navigation.cfg` - Default Escape/Backspace behavior (mimics legacy KlipperScreen)
- `examples/basic_navigation.cfg` - Simple navigation shortcuts
- `examples/advanced_shortcuts.cfg` - Advanced usage with accumulators
- `test_config.cfg` - Test configuration for verification

## Extension API

Extensions can register custom handler functions:

```python
# In your extension __init__
screen.keybinding_system.register_handler("my_handler", self.my_method)

def my_method(self, buffer_contents):
    # Custom processing logic
    pass
```

Then reference in config:

```ini
[keybinding my_action]
key = F5
action = function
function = my_handler
buffer = user_input
```

## Accessibility Benefits

- Keyboard-only navigation for users who prefer or require it
- Support for HID input devices (barcode scanners, RFID readers, etc.)
- Customizable shortcuts for frequent operations
- Headless/kiosk mode operation
- Alternative input methods for makerspace environments

## Backward Compatibility

The keybinding system is fully backward compatible. **However, keyboard functionality is now opt-in via configuration.**

- **Without any keybinding config**: No keyboard shortcuts work (not even Escape/Backspace)
- **With default_navigation.cfg**: Escape and Backspace work as they did in legacy KlipperScreen
- **With custom config**: Only your configured keybindings are active

This design makes all keyboard behavior explicit and config-driven. To restore the original Escape/Backspace behavior, simply include `default_navigation.cfg` in your configuration.

**Why this change?** Previously, Escape and Backspace were hardcoded in the event handler, which created confusion when users wanted to customize those keys. Now, all keyboard behavior is defined in config files, making it clear what keys do what.

## Security

When the screen is locked, all accumulator buffers are automatically cleared for security. Only keybindings with `require_unlocked = false` will function when locked (intended for emergency actions only).
