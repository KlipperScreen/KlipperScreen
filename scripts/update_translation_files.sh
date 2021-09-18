xgettext --keyword=_ --language=Python --no-location --sort-output \
    -o ks_includes/locales/KlipperScreen.pot \
    *.py \
    ks_includes/*.py \
    panels/*.py \
    ks_includes/defaults.conf

langs=(de_DE en es fr_FR he_IL it ru_RU zh_CN)
for lang in ${langs[@]}; do
    msgmerge ks_includes/locales/$lang/LC_MESSAGES/KlipperScreen.po \
             ks_includes/locales/KlipperScreen.pot \
          -o ks_includes/locales/$lang/LC_MESSAGES/KlipperScreen.po
done
