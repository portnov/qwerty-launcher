#!/usr/bin/python3

import sys
import os
from os.path import join, exists, abspath
import re
from collections import defaultdict
import subprocess
import argparse
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QStandardPaths
from Xlib import X, display, Xatom
import Xlib.protocol.event

DIGITS = "1234567890"
LETTERS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
GEOMETRY_RE = re.compile('(\d+)x(\d+)\+(\d+)\+(\d+)')

class LaunchButton(QtWidgets.QToolButton):
    triggered = QtCore.pyqtSignal(str)

    def __init__(self, key_id, hotkey, text, parent, toggle=False):
        super().__init__(parent)
        self.action = QtWidgets.QAction(self)
        self.action.setShortcut(hotkey.upper())
        self.setText(text)
        self.key_id = key_id
        self.action.triggered.connect(self._on_action)
        self.clicked.connect(self._on_click)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QtCore.QSize(48, 48))
        if toggle:
            self.setCheckable(toggle)
        self.is_used = False
        self.is_running = False
        self.is_section = False
        self.actualizeStyle()

    def actualizeStyle(self):
        cls = set()
        if self.is_used:
            cls.add("used")
        else:
            cls.add("unused")
        if self.is_running:
            cls.add("running")
        if self.is_section:
            cls.add("section")
        else:
            cls.add("application")
        self.setProperty("class", " ".join(cls))
        self.setStyleSheet("/**/")

    def _on_action(self, arg=None):
        self.animateClick()
        #self.clicked.emit(self.isChecked())

    def _on_click(self, btn=None):
        self.triggered.emit(self.key_id)

class Application:
    def __init__(self, settings, section_id, letter, fill_empty=False):
        self.settings = settings
        self.letter = letter
        self.section_id = section_id
        self._init_from(section_id)
        if fill_empty:
            if not self.title:
                self._search_section()

    def _init_from(self, section_id):
        self.title = self.settings.value(f"section_{section_id}/{self.letter.upper()}/title")
        self.wm_class = self.settings.value(f"section_{section_id}/{self.letter.upper()}/class")
        self.icon_name = self.settings.value(f"section_{section_id}/{self.letter.upper()}/icon")
        self.command = self.settings.value(f"section_{section_id}/{self.letter.upper()}/command")

    def _search_section(self):
        for section_id in range(len(DIGITS)):
            self._init_from(section_id)
            if self.title:
                break


class Launcher(QtWidgets.QMainWindow):
    def __init__(self, args):
        super().__init__()
        if args.config:
            config = abspath(args.config[0])
            self.settings = QtCore.QSettings(config, QtCore.QSettings.Format.NativeFormat)
        else:
            self.settings = QtCore.QSettings("qwerty-launcher", "qwerty")

        css_path = self.settings.value("global/css_path")
        if css_path is None:
            config_dir = QStandardPaths.locate(QStandardPaths.ConfigLocation, "qwerty-launcher", QStandardPaths.LocateDirectory)
            if config_dir:
                css_path = join(config_dir, "qwerty.css")
        if exists(css_path):
            with open(css_path, 'r') as css_file:
                css = css_file.read()
                self.setStyleSheet(css)
        self.fill_empty = args.fill_empty or self.settings.value("global/fill_empty", False, type=bool)
        self.no_close = args.no_close or self.settings.value("global/no_close", False, type=bool)

        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        layout = QtWidgets.QVBoxLayout()

        self.section_buttons = dict()
        digits_widget = QtWidgets.QWidget(self)
        digits_layout = QtWidgets.QHBoxLayout()
        digits_widget.setLayout(digits_layout)
        digits_group = QtWidgets.QButtonGroup(self)
        digits_group.setExclusive(True)
        for i, digit in enumerate(DIGITS):
            self.section_buttons[i] = button = LaunchButton(str(i), digit, str(digit), self, toggle=True)
            self.addAction(button.action)
            button.triggered.connect(self._on_section)
            button.is_section = True
            digits_group.addButton(button)
            digits_layout.addWidget(button, 1)
        layout.addWidget(digits_widget, 1)
        
        self.launch_buttons = dict()
        for row in LETTERS:
            row_widget = QtWidgets.QWidget(self)
            row_layout = QtWidgets.QHBoxLayout()
            row_widget.setLayout(row_layout)
            for letter in row:
                self.launch_buttons[letter] = button = LaunchButton(letter, letter, letter, self)
                self.addAction(button.action)
                button.triggered.connect(self._on_key)
                row_layout.addWidget(button, 1)
            layout.addWidget(row_widget, 1)
        self.main_widget.setLayout(layout)

        self.display = None
        
        self.current_section = self.settings.value("state/last_used_section", type=int)
        if self.current_section is None:
            self.current_section = 0
        self._setup_launch_buttons(self.current_section)
        self.section_buttons[self.current_section].toggle()

        self.exit_action = QtWidgets.QAction(self)
        self.exit_action.setShortcut("Esc")
        self.exit_action.triggered.connect(self._on_exit)

        if args.geometry:
            geometry = args.geometry[0]
            self.setGeometry(*geometry)
        if args.undecorated:
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.FramelessWindowHint)

    def _convert_class(self, clss):
        if isinstance (clss, tuple):
            return clss
        else:
            return [clss]

    def _collect_windows(self):
        if self.display is None:
            self.display = display.Display()
            self.root = self.display.screen().root
            self.NAME = self.display.intern_atom("_NET_WM_NAME")
            self.CLIENT_LIST = self.display.intern_atom("_NET_CLIENT_LIST")
            self.NET_ACTIVE_WINDOW = self.display.intern_atom("_NET_ACTIVE_WINDOW")
            self.NET_WM_DESKTOP = self.display.intern_atom("_NET_WM_DESKTOP")
            self.NET_CURRENT_DESKTOP = self.display.intern_atom("_NET_CURRENT_DESKTOP")

        lst = self.root.get_full_property(self.CLIENT_LIST, Xatom.WINDOW).value
        self.clients_list = [self.display.create_resource_object('window', id) for id in lst]

        self.by_class = defaultdict(set)
        #self.by_title = dict()
        for w in self.clients_list:
            clss = w.get_wm_class()
            for cls in self._convert_class(clss):
                self.by_class[cls].add(w)

    def _setup_sections(self):
        self._collect_windows()
        for i, button in self.section_buttons.items():
            section_title = self.settings.value(f"section_{i}/title")
            if not section_title:
                section_title = ""
                button.is_used = False
            else:
                button.is_used = True
            icon_name = self.settings.value(f"section_{i}/icon")
            button.setIcon(QtGui.QIcon.fromTheme(icon_name))
            button.setText(f"{DIGITS[i]}\n{section_title}")
            button.actualizeStyle()

    def _setup_launch_buttons(self, section_id):
        self._setup_sections()
        for letter, button in self.launch_buttons.items():
            app = Application(self.settings, section_id, letter, self.fill_empty)
            title = app.title
            if title is not None:
                button.setText(f"{letter}\n{title}")
                button.is_used = True
            else:
                button.setText(letter)
                button.is_used = False
            wm_class = app.wm_class
            if wm_class is not None:
                wins = self.by_class.get(wm_class, None)
            else:
                wins = None
            running = wins is not None
            #print(f"Key {letter} => wm_class {wm_class}, running {running}")
            button.windows = wins
            button.is_running = running
            button.setIcon(QtGui.QIcon.fromTheme(app.icon_name))
            button.actualizeStyle()

    def _on_section(self, key_id):
        #print(f"Switch to section #{key_id}")
        self.current_section = key_id
        self._setup_launch_buttons(key_id)

    def _send_event(self,win,ctype,data):
        data = (data+[0]*(5-len(data)))[:5]
        ev = Xlib.protocol.event.ClientMessage(window=win, client_type=ctype, data=(32,(data)))
        mask = (X.SubstructureRedirectMask|X.SubstructureNotifyMask)
        self.root.send_event(ev, event_mask=mask)

    def _switch_to_window(self, win):
        self.display.flush()

        desk = win.get_full_property(self.NET_WM_DESKTOP, 0).value[0]
        self._send_event(self.root, self.NET_CURRENT_DESKTOP, [desk, X.CurrentTime])

        win.configure(stack_mode = X.Above)
        win.set_input_focus(X.RevertToNone, X.CurrentTime)
        win_id = self.winId()
        src = self.display.create_resource_object('window', win_id)
        self._send_event(win, self.NET_ACTIVE_WINDOW, [1, X.CurrentTime, int(src.id)])
        win.map()
        self.display.flush()

    def _select_window(self, wins):
        def get_window_title(win):
            try:
                name = win.get_full_property(self.NAME, 0) or win.get_full_property(Xatom.WM_NAME, 0)
                return name.value.decode('utf-8')
            except:
                return "(unknown)"

        def menu_handler(win):
            def handler(checked=None):
                self._switch_to_window(win)
            return handler

        menu = QtWidgets.QMenu(self)
        for win in wins:
            title = get_window_title(win)
            #print(f"{win} => {title}")
            action = menu.addAction(title)
            action.triggered.connect(menu_handler(win))
        menu.exec_(QtGui.QCursor.pos())

    def _switch_to_windows(self, wins):
        if len(wins) == 1:
            self._switch_to_window(list(wins)[0])
        elif len(wins) > 0:
            self._select_window(wins)

    def _on_key(self, key_id):
        button = self.launch_buttons[key_id]
        app = Application(self.settings, self.current_section, key_id, self.fill_empty)
        if button.is_running:
            wins = button.windows
            #print(f"Press key <{key_id}> => switch to {wins}")
            self._switch_to_windows(wins)
        else:
            command = app.command
            #print(f"Press key <{key_id}> => execute {command}")
            if command:
                os.system(command + " &")
        if not self.no_close:
            self._on_exit()

    def _on_exit(self, arg=None):
        self._save()
        QtWidgets.qApp.quit()

    def _save(self):
        self.settings.setValue("state/last_used_section", self.current_section)
        self.settings.sync()

    def closeEvent(self, ev):
        self._save()
        super().closeEvent(ev)

def parse_geometry(geometry):
    m = GEOMETRY_RE.match(geometry)
    if m:
        w,h,x,y = m.groups()
        return int(x), int(y), int(w), int(h)
    else:
        raise ValueError("Incorrect specification of geometry")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="qwerty.py", description = "Keyboard-oriented graphical programs launcher with dock-like functionality")
    parser.add_argument('-a', '--fill-empty', action='store_true', help = "For keys that are not assigned with an application, show application from another section if there are any")
    parser.add_argument('-c', '--config', nargs=1, metavar="QWERTY.CONF", help = "Specify path to config file")
    parser.add_argument('-g', '--geometry', nargs=1, metavar="WIDTHxHEIGHT+X+Y", type=parse_geometry, help = "Specify window geometry")
    parser.add_argument('-f', '--fullscreen', action='store_true', help = "Show window in fullscreen mode")
    parser.add_argument('-d', '--undecorated', action='store_true', help = "Show window without decorations")
    parser.add_argument('-s', '--no-close', action='store_true', help = "Do not close the window after action executed")

    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = Launcher(args)
    if args.fullscreen:
        win.showFullScreen()
    else:
        win.show()
    sys.exit(app.exec_())

