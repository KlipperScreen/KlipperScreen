xgettext --keyword=_ --keyword=_n:1,2 --language=Python --no-location --sort-output \
    -o ks_includes/locales/KlipperScreen.pot \
    *.py \
    ks_includes/*.py \
    panels/*.py \
    ks_includes/defaults.conf

for FILE in ks_includes/locales/*; do
    if [ -d $FILE ]; then
        echo $FILE
        msgmerge $FILE/LC_MESSAGES/KlipperScreen.po \
                 ks_includes/locales/KlipperScreen.pot \
              -o $FILE/LC_MESSAGES/KlipperScreen.po
        msgfmt -o  $FILE/LC_MESSAGES/KlipperScreen.mo $FILE/LC_MESSAGES/KlipperScreen.po
    fi
done
