# Theming

## Custom Printer Select Icons

When multiple printers are configured, you can customize their icons by placing an icon file in the following directory:

`~/KlipperScreen/styles/printers/`

- The icon file name must match the exact printer name as configured in `KlipperScreen.conf`.
- Supported formats for icons are SVG or PNG.

Example:
```sh
cp /path/to/printer_icon.svg ~/KlipperScreen/styles/printers/printer_name.svg
sudo service KlipperScreen restart
```

## Custom Themes

To create a custom theme for KlipperScreen, follow these steps:

1. **Create Theme Directory:**
    -  Navigate to `~/KlipperScreen/styles/`.
    -  Create a new folder with the desired theme name.

2. **Add Icon Images:**
    - Inside the theme folder, create a subfolder named `images`.
    - Place your SVG icon files here. Refer to the code or default theme for specific icon names used by KlipperScreen.

3. **Customize Styles:**
    - Create a CSS file named `style.css` within your theme folder.
    - Use existing themes or the default theme as a reference for CSS styles.

Example procedure for creating a theme named `mytheme`:
```sh

cd ~/KlipperScreen/styles/
# Create the directory
mkdir -p mytheme/images
# Copy required SVG icons
cp material-light/images/* mytheme/images/
# Create custom styles
echo "window { background-color: #FFFFFF; }" > style.css
```

4. **Apply the Theme:**
    - After creating your theme, restart the KlipperScreen service:
```sh
sudo service KlipperScreen restart
```
    - Select you theme from the list in the options.

### Example: Creating a Custom Theme

```sh
cd ~/KlipperScreen/styles/
mkdir -p mytheme/images
cd mytheme
cp ../default_theme/images/* images/
echo "window { background-color: #FFFFFF; }" > style.css
sudo service KlipperScreen restart
```

### Example: Custom Background and CSS

Creating a custom background from Mainsail sidebar using Z-bolt icons:

```css
/* style.css */
window {
    background-image: url("/home/pi/mainsail/img/background.svg");
}

button {
    background-color: rgba(0,0,0,0);
    border-radius: 2em;
}
```

![Custom theme example with background](img/theming/theme_example.png)
