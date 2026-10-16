"""Smoke test de la interfaz (se omite si no hay display)."""

import os
import sys
import tempfile
import tkinter as tk
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import screentime.logger as logger_module
from screentime.gui import MainGUI
from screentime.logger import UsageLogger


class _StubNotifier:
    is_paused = False


def _display_available() -> bool:
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(_display_available(), "sin display para tkinter")
class GuiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_data = logger_module.DATA_DIR
        self._old_file = logger_module.HISTORY_FILE
        logger_module.DATA_DIR = self.tmp
        logger_module.HISTORY_FILE = os.path.join(self.tmp, "history.json")

    def tearDown(self):
        logger_module.DATA_DIR = self._old_data
        logger_module.HISTORY_FILE = self._old_file

    def test_window_builds_and_scrolls(self):
        gui = MainGUI(UsageLogger(), _StubNotifier(), {})
        try:
            gui.create_window(start_minimized=True)
            gui.root.update()
            gui.root.update_idletasks()

            before = gui._canvas.yview()
            for _ in range(3):
                gui._canvas.event_generate("<MouseWheel>", delta=-120)
            gui.root.update()
            self.assertGreater(gui._canvas.yview()[0], before[0])

            if tk.TkVersion >= 9:
                before_touch = gui._canvas.yview()
                for _ in range(10):
                    gui._canvas.event_generate("<TouchpadScroll>", delta=65496)
                gui.root.update()
                self.assertGreater(gui._canvas.yview()[0], before_touch[0])
        finally:
            gui.destroy()


if __name__ == "__main__":
    unittest.main()
