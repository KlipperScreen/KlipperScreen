# Quicktips
quick tips, without much explanation

### Hide macros, outputs or fans

As you probably already noticed, you can show and hide the gcode macros in the interface settings, but there is more…

Did you know, that you can also hide gcode macros by prefixing the name with an underscore?

```
[gcode_macro MY_AWESOME_GCODE]
gcode:
    _MY_HELPER_CODE
[gcode_macro _MY_HELPER_CODE]
gcode:
    M300
```

MY_AWESOME_GCODE appears in your interface settings, _MY_HELPER_CODE not.

Another example:

Lets hide a temperature_fan:

```
[temperature_fan fan1]
[temperature_fan _fan2]
```

fan1 will show in the interface, but _fan2 will be hidden.

