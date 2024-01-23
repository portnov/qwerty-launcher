#!/usr/bin/python3

import sys
import os
from os.path import join, exists
import subprocess
import argparse
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QStandardPaths
from Xlib import X, display, Xatom
import Xlib.protocol.event

DIGITS = "1234567890"
LETTERS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

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
        if self.isCheckable():
            self.toggle()
        self.clicked.emit(self.isChecked())

    def _on_click(self, btn=None):
        self.triggered.emit(self.key_id)

class Launcher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QtCore.QSettings("qwerty-launcher", "qwerty")

        config_dir = QStandardPaths.locate(QStandardPaths.ConfigLocation, "qwerty-launcher", QStandardPaths.LocateDirectory)
        if config_dir:
            css_path = join(config_dir, "qwerty.css")
            if exists(css_path):
                with open(css_path, 'r') as css_file:
                    css = css_file.read()
                    self.setStyleSheet(css)

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

    def _convert_class(self, clss):
        if isinstance (clss, tuple):
            return clss
        else:
            return [clss]

    def _collect_windows(self):
        if self.display is None:
            self.display = display.Display()
            self.root = self.display.screen().root
            #self.NAME = self.display.intern_atom("_NET_WM_NAME")
            self.CLIENT_LIST = self.display.intern_atom("_NET_CLIENT_LIST")
            self.NET_ACTIVE_WINDOW = self.display.intern_atom("_NET_ACTIVE_WINDOW")

        lst = self.root.get_full_property(self.CLIENT_LIST, Xatom.WINDOW).value
        self.clients_list = [self.display.create_resource_object('window', id) for id in lst]

        self.by_class = dict()
        #self.by_title = dict()
        for w in self.clients_list:
            clss = w.get_wm_class()
            for cls in self._convert_class(clss):
                self.by_class[cls] = w
        print(self.by_class.keys())

    def _setup_sections(self):
        self._collect_windows()
        for i, button in self.section_buttons.items():
            section_title = self.settings.value(f"section_{i}/title")
            if not section_title:
                section_title = ""
                button.is_used = False
            else:
                button.is_used = True
            button.setText(f"{DIGITS[i]}\n{section_title}")
            button.actualizeStyle()

    def _setup_launch_buttons(self, section_id):
        self._setup_sections()
        for letter, button in self.launch_buttons.items():
            title = self.settings.value(f"section_{section_id}/{letter.upper()}/title")
            if title is not None:
                button.setText(f"{letter}\n{title}")
                button.is_used = True
            else:
                button.setText(letter)
                button.is_used = False
            wm_class = self.settings.value(f"section_{section_id}/{letter.upper()}/class")
            if wm_class is not None:
                win = self.by_class.get(wm_class, None)
            else:
                win = None
            running = win is not None
            #print(f"Key {letter} => wm_class {wm_class}, running {running}")
            button.window = win
            button.is_running = running
            icon_name = self.settings.value(f"section_{section_id}/{letter.upper()}/icon")
            button.setIcon(QtGui.QIcon.fromTheme(icon_name))
            button.actualizeStyle()

    def _on_section(self, key_id):
        print(f"Switch to section #{key_id}")
        self.current_section = key_id
        self._setup_launch_buttons(key_id)

    def _send_event(self,win,ctype,data):
        data = (data+[0]*(5-len(data)))[:5]
        ev = Xlib.protocol.event.ClientMessage(window=win, client_type=ctype, data=(32,(data)))
        mask = (X.SubstructureRedirectMask|X.SubstructureNotifyMask)
        self.root.send_event(ev, event_mask=mask)

    def closeEvent(self, ev):
        self.settings.setValue("state/last_used_section", self.current_section)
        self.settings.sync()
        super().closeEvent(ev)

    def _on_key(self, key_id):
        button = self.launch_buttons[key_id]
        if button.is_running:
            win = button.window
            print(f"Press key <{key_id}> => switch to {win}")
            self.display.flush()
            win.configure(stack_mode = X.Above)
            win.set_input_focus(X.RevertToNone, X.CurrentTime)
            win_id = self.winId()
            src = self.display.create_resource_object('window', win_id)
            self._send_event(win, self.NET_ACTIVE_WINDOW, [1, X.CurrentTime, int(src.id)])
            win.map()
            self.display.flush()
        else:
            command = self.settings.value(f"section_{self.current_section}/{key_id}/command")
            print(f"Press key <{key_id}> => execute {command}")
            os.system(command + " &")
        QtWidgets.qApp.quit()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = Launcher()
    win.show()
    sys.exit(app.exec_())

