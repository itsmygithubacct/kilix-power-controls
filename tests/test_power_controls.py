import copy
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from power_controls import Preferences


class Store:
    def __init__(self):
        self.data = {"lid-action-on-ac": 2, "future-setting": "keep"}
        self.calls = []
        self.fail = None

    def snapshot(self):
        return copy.deepcopy(self.data)

    def write(self, key, value):
        self.calls.append((key, value))
        self.data[key] = value
        if self.fail == key:
            self.fail = None
            raise RuntimeError("connection lost after write")

    def reset(self, key):
        self.data.pop(key, None)


class Transactions(unittest.TestCase):
    def test_unchanged_defaults_unknown_properties_and_existing_lid_choice_are_preserved(self):
        store = Store()
        preferences = Preferences(store)
        draft = dict(preferences.values)
        draft["general-notification"] = False
        self.assertEqual(preferences.apply(draft), 1)
        self.assertEqual(store.calls, [("general-notification", False)])
        self.assertEqual(store.data["lid-action-on-ac"], 2)
        self.assertEqual(store.data["future-setting"], "keep")

    def test_failed_second_write_restores_changed_and_previously_absent_properties(self):
        store = Store()
        before = store.snapshot()
        preferences = Preferences(store)
        draft = dict(preferences.values)
        draft.update({"lid-action-on-ac": 4, "general-notification": False})
        store.fail = "general-notification"
        with self.assertRaisesRegex(RuntimeError, "Previous settings restored"):
            preferences.apply(draft)
        self.assertEqual(store.data, before)

    def test_invalid_draft_or_external_change_is_rejected_before_writing(self):
        store = Store()
        preferences = Preferences(store)
        draft = dict(preferences.values)
        draft["critical-power-level"] = 71
        with self.assertRaises(ValueError):
            preferences.apply(draft)
        self.assertEqual(store.calls, [])
        draft = dict(preferences.values)
        draft["lid-action-on-ac"] = 4
        store.data["lid-action-on-ac"] = 1
        with self.assertRaisesRegex(ValueError, "another window"):
            preferences.apply(draft)
        self.assertEqual(store.calls, [])


@unittest.skipUnless(shutil.which("dbus-run-session") and shutil.which("xfconf-query"), "private xfconf session required")
class RealBackend(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.base), "PYTHONPATH": str(ROOT)}
        for key, name in (("XDG_CONFIG_HOME", "config"), ("XDG_CONFIG_DIRS", "system-config"), ("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"), ("XDG_RUNTIME_DIR", "run")):
            directory = self.base / name
            directory.mkdir(mode=0o700)
            self.env[key] = str(directory)

    def run_private(self, code):
        return subprocess.run(["dbus-run-session", "--", "/usr/bin/python3", "-c", code], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_new_channel_read_write_reset_and_types_against_real_xfconfd(self):
        result = self.run_private('''import json
from power_controls import Backend,Preferences
b=Backend();p=Preferences(b);before=b.snapshot()
draft=dict(p.values);draft.update({'lid-action-on-ac':1,'general-notification':False,'profile-on-ac':'power-saver'})
assert p.apply(draft)==3
assert b.snapshot()==dict(before,**{'lid-action-on-ac':1,'general-notification':False,'profile-on-ac':'power-saver'}),b.snapshot()
b.reset('profile-on-ac');assert 'profile-on-ac' not in b.snapshot()
print('typed xfconf PASS')
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("typed xfconf PASS", result.stdout)

    @unittest.skipUnless(shutil.which("Xvfb") and os.environ.get("KILIX_POWER_TEST_PLEB"), "Xvfb and the candidate Pleb checkout required")
    def test_native_gui_apply_and_shared_screen_lock_page(self):
        pleb = Path(os.environ["KILIX_POWER_TEST_PLEB"]).resolve()
        binaries = self.base / "bin"
        binaries.mkdir()
        (binaries / "pleb").symlink_to(pleb / "bin/pleb")
        self.env.update(PATH=str(binaries) + ":/usr/bin:/bin", PLEB_CONFIG_HOME=str(self.base / "pleb-config"))
        read_fd, write_fd = os.pipe()
        server = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1100x800x24", "-nolisten", "tcp", "-noreset"],
                                  pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write_fd)
        try:
            self.assertTrue(select.select([read_fd], [], [], 5)[0])
            self.env["DISPLAY"] = ":" + os.read(read_fd, 32).decode().strip()
            if os.environ.get("KILIX_POWER_TEST_SCREENSHOT"):
                self.env["KILIX_POWER_TEST_SCREENSHOT"] = os.environ["KILIX_POWER_TEST_SCREENSHOT"]
            result = self.run_private('''import json,os,tkinter as tk
from tkinter import ttk
from main import PowerControls
from power_controls import Backend
before=Backend().snapshot()
root=tk.Tk();ui=PowerControls(root);root.update()
root.geometry('850x700');root.update()
assert ui.apply_button.winfo_rooty()+ui.apply_button.winfo_height()<=root.winfo_rooty()+root.winfo_height()
assert ui.apply_button.winfo_height()>=ui.apply_button.winfo_reqheight()
assert [ui.tabs.tab(tab,'text') for tab in ui.tabs.tabs()]==['General','Plugged In','Battery','Display','Dimming','Screen Lock','Devices']
assert Backend().snapshot()==before
ui.variables['lid-action-on-ac'].set('Suspend');ui.apply()
assert Backend().snapshot()['lid-action-on-ac']==1,ui.status.get()
root.update();assert ui.apply_button.winfo_height()>=ui.apply_button.winfo_reqheight()
page=ui.tabs.nametowidget(ui.tabs.tabs()[5]);children=page.winfo_children()
next(w for w in children if isinstance(w,ttk.Combobox)).set('Disabled')
next(w for w in children if isinstance(w,ttk.Button)).invoke()
import screenlock
assert screenlock.load()['policy']=='off'
if os.environ.get('KILIX_POWER_TEST_SCREENSHOT'):
 from PIL import ImageGrab
 root.geometry('1000x720');root.update();ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(os.environ['KILIX_POWER_TEST_SCREENSHOT'])
root.destroy();print('native GUI and shared lock PASS')
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("native GUI and shared lock PASS", result.stdout)
        finally:
            os.close(read_fd)
            server.terminate()
            server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
