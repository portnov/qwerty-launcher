qwerty-launcher README
======================

`qwerty.py` is a graphical, but keyboard-oriented application launcher for X11.
It is designed to be a faster alternative to application launching menus. 

`qwerty.py` has also dock-like functionality: one press of a key either
launches an application, if it is not running yet, or switches you to already
running application.

Concepts
--------

`qwerty.py` is a keyboard-oriented in a sense that all application are assigned
with a keyboard button. It also has an advantage over fully keyboard-driven
methods of launching programs (when you, for example, assign a keyboard
shortcut for each application in your desktop environment): you do not have to
memoize all shortcuts, as they are shown on the screen. Another advantage is
that you can have more applications than 26 letter keys (applications tend to
compete over global shortcuts: is W for *W*eb browser or for LibreOffice
*W*riter?), thanks to use of sections.

It is assumed that you will assign the launch of `qwerty.py` to a global
keyboard shortcut in your desktop environment, or maybe you have another way to
run it easily.

`qwerty.py` shows you a window with buttons in a keyboard-like layout. You can
click these buttons with a mouse, but usually you will just press corresponding
key on the keyboard.

The top row of buttons, one with digits, represents menu sections. Buttons with
letters represent applications within selected section. So, with standard
keyboard layout you can have up to 10 menu sections, each containing up to 26
applications.

When you activate a letter button, `qwerty.py` does the following:

* If there is an already open window of this application, that window will be
  activated.
* If there are more than one window of this application, a popup menu will be
  shown to select the window to be activated.
* If there is no such window, the application will be launched.

So, for example, to launch LibreOffice Calc (given you did specific
configuration), you will press the following keys:

* One key to run `qwerty.py` itself. For example, I used to bind `qwerty.py` to
  the PauseBreak key.
* One digit key to switch to Office section. For example, the digit 3. You do
  not have to press it if that section is already active.
* One key for the application itself. For example, the letter C. 

Menu sections and their contents are configured in configuration file. At the
moment you have to edit it manually; probably later there will be a GUI to
simplify it's editing.

Visual presentation of launcher window is customized by use of CSS stylesheet.

Configuration file
------------------

The configuration file is in QSettings format, which is a variant of INI file
format. There is an example of configuration file under
`config-samples/qwerty.conf`.

By default, `qwerty.py` looks for it's configuration file named
`~/.config/qwerty-launcher/qwerty.conf`. You can specify another configuration
file with `-c` command-line option.

The configuration file consists of several option groups.

`[global]` group supports one option, `css_path`. There you can specify a
custom path to your CSS stylesheet.

`[state]` group contains `last_used_section` key. It is used to remember the
number of menu section which you used the last time, in order to open it by
default at next launch.

Other groups must be named like `[section_#]`, where `#` is a digit from 0 to
9. They represent menu sections, numbered from left to right.

Each menu section should contain a `title` key, which specifies the title of
the section. It can also contain an `icon` key, which specifies the icon for
the section.

Except for that, each section should contain a series of application
descriptions. Options that describe a single application button must all start
with the same uppercase letter, which denotes the button.

For each application, the following options are used:

* `L\title` (where L is the letter of the button): application title to be
  shown on the button.
* `L\icon`: the name of application icon. The icon is searched by that name in
  your current icon theme.
* `L\command`: the command which will be used to launch te application.
* `L\class`: window class (`WM_CLASS` of the window), which is to be used to
  detect windows of this application.

CSS Stylesheet
--------------

You can find an example of a stylesheet used to customize `qwerty.py`
appearance under `config-samples/qwerty.css`.
See also [Qt documentation](https://doc.qt.io/qt-5/stylesheet-reference.html)
for detailed reference of available selectors and properties.


LICENSE
-------

GPL-3, see LICENSE file.

