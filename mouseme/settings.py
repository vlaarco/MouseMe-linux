import json
import os

_CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "MouseMe")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "settings.json")


class SettingsKey:
    points = "Points"
    start_delay = "StartDelay"
    loop_delay = "LoopDelay"
    delay = "Delay"
    repetitions = "Repetitions"
    gbg = "GBG"
    qi = "QI"
    stay_on_top = "StayOnTop"
    build_menu = "BuildMenu"
    build_menu_targets = "BuildMenuTargets"
    gbg_target = "GbgTarget"
    army = "Army"
    army_units = "ArmyUnits"
    army_delay = "ArmyDelay"
    army_close_delay = "ArmyCloseDelay"
    army_click_delay = "ArmyClickDelay"
    army_repetitions = "ArmyRepetitions"
    army_targets = "ArmyTargets"
    window_position = "WindowPosition"

    defaults = {
        points: 1,
        start_delay: 1000,
        loop_delay: 1000,
        delay: 250,
        repetitions: 1,
        gbg: False,
        qi: False,
        stay_on_top: False,
        build_menu: False,
        build_menu_targets: None,
        gbg_target: None,
        army: False,
        army_units: 20,
        army_delay: 1500,
        army_close_delay: 1500,
        army_click_delay: 350,
        army_repetitions: 1,
        army_targets: None,
        window_position: None,
    }


# JSON-backed settings; the counterpart of UserDefaults on macOS and Settings.settings on Windows
class Settings:
    def __init__(self):
        self._values = dict(SettingsKey.defaults)

        try:
            with open(_CONFIG_FILE) as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                self._values.update(saved)
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self._values.get(key, SettingsKey.defaults.get(key))

    def __setitem__(self, key, value):
        self._values[key] = value

    def save(self):
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        tmp = _CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._values, f, indent=2)
        os.replace(tmp, _CONFIG_FILE)
