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

Once you have followed those steps, as long as your pi is set up for your preferred language, KlipperScreen will
automatically use the translations provided in the file. KlipperScreen currently does not detect RTL languages, but
support for RTL is planned in the near future. 
