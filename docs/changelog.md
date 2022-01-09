# Changelog

Breaking changes will be listed here.

#### 2022 01 09
* The Preheat panel has been deprecated in favor of an all in one Temperature panel

Remove preheat panel from your Klipperscreen.conf or replace the occurrences of preheat with temperature

#### 2021 05 20
* Default configuration is not merged if a user configuration is set for a specific option

For instance, if `menu __main` is user defined, the main menu will not have any defaults.
