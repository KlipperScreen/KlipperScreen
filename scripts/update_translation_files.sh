#!/bin/sh

# Update pot
xgettext --keyword=_ --keyword=ngettext:1,2 --language=Python --no-location --sort-output \
    -o ks_includes/locales/KlipperScreen.pot \
    *.py \
    ks_includes/*.py \
    panels/*.py \
    ks_includes/defaults.conf
# Update po
for FILE in ks_includes/locales/*; do
    if [ -d $FILE ]; then
        echo Processing $FILE
        msgmerge -q $FILE/LC_MESSAGES/KlipperScreen.po \
                 ks_includes/locales/KlipperScreen.pot \
              -o $FILE/LC_MESSAGES/KlipperScreen.po
        # Clean Fuzzy translations
        msgattrib --clear-fuzzy --empty -o $FILE/LC_MESSAGES/KlipperScreen.po $FILE/LC_MESSAGES/KlipperScreen.po
        # Compile mo
        msgfmt -o  $FILE/LC_MESSAGES/KlipperScreen.mo $FILE/LC_MESSAGES/KlipperScreen.po
    fi
done
