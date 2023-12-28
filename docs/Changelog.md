# Changelog

Breaking changes will be listed here.

#### [2023 10 08](https://github.com/KlipperScreen/KlipperScreen/commit/b6199a4f24beb02dc0f8956f60c88e3ba3468927)
* Deprecated [bed_screws] and [z_calibrate_position] sections those configs should go in [printer name]

#### [2023 07 23](https://github.com/KlipperScreen/KlipperScreen/commit/8053e97d1041f136118d40669442e910df6cf186)
* Deprecated `camera_url` option of printer, the camera config is read from moonraker

#### [2022 03 21](https://github.com/KlipperScreen/KlipperScreen/commit/bc34b3c8d6761c27a0b0c62fc4dfa11442b417f6)
* Default configuration is now merged again.
Fixing [2021 05 20](https://github.com/KlipperScreen/KlipperScreen/commit/eb801486928bf02709033dcbc5f0a45ca43b23c1)

#### [2022 03 10](https://github.com/KlipperScreen/KlipperScreen/commit/490dc929bd11e3c4200b999ce7204d84fa0bc184)
* The "Power On Printer" button now requires power_devices under the printer section in KlipperScreen.conf
the power_devices allowed are those defined in the config of moonraker of the printer
The "Power" panel will be in the Menu if there are power devices found

#### [2022 03 01](https://github.com/KlipperScreen/KlipperScreen/commit/49ab84e8d51535d3469d97fdee53099cca6abc39)
* The "Power On Printer" button now requires that the printer name in KlipperScreen.conf
and the power device in moonraker.conf to have the same name.
The "Power" panel will be in the Menu if there are power devices found

#### [2022 01 11](https://github.com/KlipperScreen/KlipperScreen/commit/8a8c6c064cc6d097b1b34a5c42b4001367e545a6)
* The Preheat panel has been deprecated in favor of an all in one Temperature panel

Remove preheat panel from your Klipperscreen.conf or replace the occurrences of preheat with temperature

#### [2021 05 20](https://github.com/KlipperScreen/KlipperScreen/commit/eb801486928bf02709033dcbc5f0a45ca43b23c1)
* Default configuration is not merged if a user configuration is set for a specific option

For instance, if `menu __main` is user defined, the main menu will not have any defaults.
