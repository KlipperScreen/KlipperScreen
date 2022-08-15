## Create Translations

You can use an editor such as [poedit](https://poedit.net/) to assist in translations. This guide will assume that you
will be using poedit.

This guide will refer to `language designation`. This can be found from running `echo $LANG` on your pi, as long as you
have set your pi up for your preferred language.

#### New Language

* Select `Create a new translation` or `File -> New from POT/PO` and select `ks_includes/locals/KlipperScreen.pot`.
* Enter your language designation.
* Create the translations
* Save the file as `ks_includes/locales/{LANGUAGE DESIGNATION}/KlipperScreen.po`.
* Select `File -> Compile to MO`. Save this file as `ks_includes/locales/{LANGUAGE DESIGNATION}/KlipperScreen.mo`

Once you have followed those steps, restart KlipperScreen, and select it from the list in the settings.
If you edited and recompiled, you need to restart KlipperScreen to reload the translation.

Do not edit the POT file as is automatically generated and your changes will be lost.
[Attach your translation on a GitHub issue or create a PR](Contact.md)
