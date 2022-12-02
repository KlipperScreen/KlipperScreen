# Translations

## Updating an existing translation:

You can use an editor such as [poedit](https://poedit.net/) to assist in translations.

* Edit `ks_includes/locals/{ISO 639 lang code}/LC_MESSAGES/KlipperScreen.po`

To test your translation:

In poedit go to `File -> Compile to MO`. Save it on the same folder, and restart KlipperScreen


## Adding a new Language:

Example using poedit

* Select `Create a new translation` or `File -> New from POT/PO` and select `ks_includes/locals/KlipperScreen.pot`.
!!! important
    Do not edit the POT file as is automatically generated and your changes will be lost.
* Save the file as `ks_includes/locales/{ISO 639 lang code}/LC_MESSAGES/KlipperScreen.po`
* Select `File -> Compile to MO`.  Save it on the same folder, and restart KlipperScreen

!!! note
    [Wikipedia ISO 639 Language Codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)

Once you have restarted KlipperScreen, select it from the list in the settings.
If you edited and recompiled, you need to restart KlipperScreen to reload the translation.


## Contributing:
[Attach your translation on a GitHub issue or create a PR](Contact.md)
