# Keybindings

Keybindings provide keyboard navigation and customizable shortcuts for KlipperScreen. This accessibility feature enables keyboard-only operation and supports alternative input devices like barcode scanners, RFID readers, and arcade controls.

## Quick Start

Enable default Escape/Backspace behavior:

```ini title="KlipperScreen.conf"
[include ~/KlipperScreen/keybindings/default_navigation.cfg]
```

Or use the comprehensive navigation example:

```ini title="KlipperScreen.conf"
[include ~/KlipperScreen/keybindings/examples/basic_navigation.cfg]
```

!!! note
    Without a keybinding configuration, keyboard shortcuts are disabled. This is by design—keyboard functionality is opt-in.

## Configuration Sections

The keybinding system uses four section types:

### Keygroups

Reusable sets of keys. Names must use `snake_case` (lowercase with underscores).

```ini
[keygroup lower_case]
keys = a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z

[keygroup num_keys]
keys = 0,1,2,3,4,5,6,7,8,9

# Keygroups can reference other keygroups
[keygroup alpha_numeric]
keys = lower_case,upper_case,num_keys
```

Standard keygroups are provided in `keybindings/keygroups_us_ascii.cfg`.

### Accumulators

Buffers that collect keystrokes for multi-key sequences.

```ini
[accumulator gcode_input]
# Auto-clear after 2 seconds of inactivity
timeout = 2.0
```

### Keybindings

Named actions bound to keys. Names must use `snake_case`.

```ini
[keybinding emergency_stop]
key = F1
action = exec_gcode
gcode = M112
confirm = Execute EMERGENCY STOP?
# Works even when screen is locked (default is true)
require_unlocked = false

[keybinding accumulate_chars]
# Bind multiple keys using a keygroup
keys = alpha_numeric
action = accumulate
buffer = gcode_input
```

### Panel Assignment

Assign keybindings to panels:

```ini
# Active on all panels
[panel __global]
keybindings = emergency_stop,nav_home

# Active only on the move panel
[panel move]
keybindings = move_up,move_down
```

## Action Types

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `accumulate` | Add key to buffer | `buffer` |
| `gcode` | Execute buffer as gcode | `buffer` |
| `exec_gcode` | Execute literal gcode | `gcode` |
| `clear` | Clear buffer | `buffer` |
| `backspace` | Remove last char | `buffer` |
| `function` | Call handler with buffer | `function`, `buffer` (optional) |
| `exec_function` | Call handler without args | `function` |
| `panel` | Navigate to panel | `panel` |

### Action Examples

```ini
# Execute accumulated gcode on Enter
[keybinding execute_gcode]
key = Return
action = gcode
buffer = gcode_input
confirm = Execute this G-code?

# Navigate to temperature panel
[keybinding nav_temp]
key = t
action = panel
panel = temperature

# Quick movement
[keybinding move_up]
key = Page_Up
action = exec_gcode
gcode = G91\nG1 Z1 F300\nG90

# Custom function handler
[keybinding custom_action]
key = F5
action = exec_function
function = my_handler
```

## Key Naming

KlipperScreen uses GTK key names for keyboard keys:

**Common keys:**
- Letters: `a`-`z`, `A`-`Z`
- Numbers: `0`-`9`
- Function: `F1`-`F12`
- Navigation: `Left`, `Right`, `Up`, `Down`, `Home`, `End`, `Page_Up`, `Page_Down`
- Special: `Return`, `Escape`, `BackSpace`, `Delete`, `Insert`, `Tab`, `space`
- Modifiers: `Shift_L`, `Shift_R`, `Control_L`, `Control_R`, `Alt_L`, `Alt_R`

!!! tip
    GTK key names use PascalCase or Mixed_Case (`BackSpace`, `Page_Up`). Custom keygroup names must use snake_case to avoid collisions.

## Advanced Configuration

### Accumulator Pattern

Collect keystrokes and execute on trigger:

```ini
[accumulator gcode_buffer]
timeout = 2.0

[keybinding collect_text]
keys = alpha_numeric,special_symbols
action = accumulate
buffer = gcode_buffer

[keybinding execute_on_enter]
key = Return
action = gcode
buffer = gcode_buffer

[keybinding clear_on_escape]
key = Escape
action = clear
buffer = gcode_buffer

[panel __global]
keybindings = collect_text,execute_on_enter,clear_on_escape
```

### Panel-Specific Shortcuts

```ini
[keybinding move_z_up]
key = Page_Up
action = exec_gcode
gcode = G91\nG1 Z1 F300\nG90

[keybinding move_z_down]
key = Page_Down
action = exec_gcode
gcode = G91\nG1 Z-1 F300\nG90

# Only active on move panel
[panel move]
keybindings = move_z_up,move_z_down
```

### Emergency Actions

Emergency actions can work even when the screen is locked:

```ini
[keybinding emergency_stop]
key = F1
action = exec_gcode
gcode = M112
confirm = Execute EMERGENCY STOP?
require_unlocked = false

[keybinding emergency_pause]
key = F2
action = exec_gcode
gcode = PAUSE
require_unlocked = false

[panel __global]
keybindings = emergency_stop,emergency_pause
```

## Extension API

Extensions can register custom handler functions:

```python
# In your extension __init__
screen.keybinding_system.register_handler("my_handler", self.my_method)

def my_method(self, buffer_contents):
    # buffer_contents is empty string for exec_function action
    logging.info(f"Handler called with: {buffer_contents}")
    # Your custom logic here
```

Reference in config:

```ini
[keybinding custom_action]
key = F5
action = function
function = my_handler
buffer = user_input
```

## Security

When the screen locks, all accumulator buffers are automatically cleared for security. Only keybindings with `require_unlocked = false` function when locked.

!!! warning "Security Notice"
    Only use `require_unlocked = false` for emergency actions. Regular shortcuts should require the screen to be unlocked.

## Troubleshooting

**Keys not working:**
- Verify you've included a keybinding config file
- Check logs for "Keybinding system initialized"
- Ensure keygroup/keybinding names use snake_case

**Text entry broken:**
- Text entry widgets automatically receive keyboard input
- Keybindings don't intercept text entry focus

**Escape/Backspace not working:**
- These are no longer hardcoded
- Include `default_navigation.cfg` or define custom bindings

**Screensaver interference:**
- Any key wakes the screensaver
- Keybindings only process after wake

## Example Configurations

See the `keybindings/examples/` directory:
- `basic_navigation.cfg` - Simple navigation shortcuts
- `advanced_shortcuts.cfg` - Accumulator usage and complex actions

See `keybindings/keygroups_us_ascii.cfg` for standard keygroup definitions.
