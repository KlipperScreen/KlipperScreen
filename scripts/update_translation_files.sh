#!/bin/sh

# Update pot
xgettext --keyword=_ --keyword=ngettext:1,2 --language=Python --no-location --sort-by-file \
    -o ks_includes/locales/KlipperScreen.pot \
    *.py \
    ks_includes/*.py \
    ks_includes/widgets/*.py \
    panels/*.py \
    config/*.conf
# Update po
for FILE in ks_includes/locales/*; do
    # Only process if it's a directory and contains the .po file
    if [ -d "$FILE" ] && [ -f "$FILE/LC_MESSAGES/KlipperScreen.po" ]; then
        echo "Processing $FILE"

        msgmerge -q --no-fuzzy-matching \
                 -U "$FILE/LC_MESSAGES/KlipperScreen.po" \
                 ks_includes/locales/KlipperScreen.pot

        # Compile mo
        msgfmt -o "$FILE/LC_MESSAGES/KlipperScreen.mo" "$FILE/LC_MESSAGES/KlipperScreen.po"
    fi
done
