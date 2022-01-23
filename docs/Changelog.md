# Changelog

Breaking changes will be listed here.

#### [2022 01 11](https://github.com/jordanruthe/KlipperScreen/commit/8a8c6c064cc6d097b1b34a5c42b4001367e545a6)
* The Preheat panel has been deprecated in favor of an all in one Temperature panel

Remove preheat panel from your Klipperscreen.conf or replace the occurrences of preheat with temperature

#### [2021 05 20](https://github.com/jordanruthe/KlipperScreen/commit/8a8c6c064cc6d097b1b34a5c42b4001367e545a6)
* Default configuration is not merged if a user configuration is set for a specific option

For instance, if `menu __main` is user defined, the main menu will not have any defaults.
