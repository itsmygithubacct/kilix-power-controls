"""Kilix-owned power preferences, using the running desktop power service."""
from dataclasses import dataclass
import os
from pathlib import Path

CHANNEL = "xfce4-power-manager"
PREFIX = "/xfce4-power-manager/"
ACTIONS = {0: "Do nothing", 1: "Suspend", 2: "Hibernate", 3: "Ask", 4: "Shut down", 5: "Hybrid sleep"}
LID = {4: "Do nothing", 0: "Switch off display", 3: "Lock screen", 1: "Suspend", 2: "Hibernate", 5: "Hybrid sleep", 6: "Shut down"}
SLEEP = {1: "Suspend", 2: "Hibernate"}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    section: str
    default: object
    kind: str = "uint"
    minimum: int = 0
    maximum: int = 86400
    choices: object = None
    dim_timeout: bool = False

    def validate(self, value):
        if self.kind == "bool":
            valid = type(value) is bool
        elif self.kind == "string":
            valid = type(value) is str
        else:
            valid = type(value) is int and self.minimum <= value <= self.maximum
        if not valid or (self.choices is not None and value not in self.choices):
            raise ValueError(f"Invalid value for {self.label}")
        if self.dim_timeout and value != 9 and value < 10:
            raise ValueError(f"{self.label}: use 0 for never, or at least 10 seconds")
        return value


FIELDS = [
    Field("power-button-action", "Power button", "General", 0, choices=ACTIONS),
    Field("sleep-button-action", "Sleep button", "General", 0, choices=ACTIONS),
    Field("hibernate-button-action", "Hibernate button", "General", 0, choices=ACTIONS),
    Field("battery-button-action", "Battery button", "General", 0, choices=ACTIONS),
    Field("general-notification", "Show power notifications", "General", True, "bool"),
    Field("presentation-mode", "Presentation mode (prevents idle actions)", "General", False, "bool"),
    Field("handle-brightness-keys", "Handle brightness keys", "General", True, "bool"),
    Field("show-brightness-popup", "Show brightness changes", "General", True, "bool"),
    Field("dpms-enabled", "Enable display power management", "Display", True, "bool"),
    Field("critical-power-level", "Critical battery level (%)", "Battery", 10, minimum=1, maximum=70),
    Field("critical-power-action", "At critical battery level", "Battery", 0, choices={k: v for k, v in ACTIONS.items() if k != 3}),
]
for suffix, section in (("ac", "Plugged In"), ("battery", "Battery")):
    FIELDS.extend([
        Field(f"lid-action-on-{suffix}", "When the lid closes", section, 4, choices=LID),
        Field(f"inactivity-on-{suffix}", "Sleep after idle (minutes; 0 = never)", section, 0, maximum=360),
        Field(f"inactivity-sleep-mode-on-{suffix}", "Idle sleep action", section, 1, choices=SLEEP),
        Field(f"profile-on-{suffix}", "Power profile (when supported)", section, "balanced", "string",
              choices={"balanced": "Balanced", "power-saver": "Power saver", "performance": "Performance"}),
        Field(f"dpms-on-{suffix}-sleep", f"{section}: display sleep (minutes; 0 = never)", "Display", 10 if suffix == "ac" else 5, maximum=360),
        Field(f"dpms-on-{suffix}-off", f"{section}: display off (minutes; 0 = never)", "Display", 15 if suffix == "ac" else 10, maximum=360),
        Field(f"brightness-on-{suffix}", f"{section}: dim after (seconds; 0 = never)", "Dimming", 9 if suffix == "ac" else 300, minimum=9, dim_timeout=True),
        Field(f"brightness-level-on-{suffix}", f"{section}: dimmed brightness (%)", "Dimming", 80 if suffix == "ac" else 20, minimum=1, maximum=100),
    ])
BY_KEY = {field.key: field for field in FIELDS}


class Backend:
    def __init__(self):
        import dbus
        self.dbus = dbus
        address = os.environ.get("PLEB_DESKTOP_BUS_ADDRESS")
        if os.environ.get("KILIX_PRIVATE_XAPP") == "1" and not address:
            raise RuntimeError("The physical desktop session bus is unavailable")
        self.bus = dbus.bus.BusConnection(address) if address else dbus.SessionBus()
        self.proxy = dbus.Interface(self.bus.get_object("org.xfce.Xfconf", "/org/xfce/Xfconf"), "org.xfce.Xfconf")

    def snapshot(self):
        try:
            values = self.proxy.GetAllProperties(CHANNEL, PREFIX.rstrip("/"), timeout=3)
        except self.dbus.DBusException as error:
            if error.get_dbus_name() == "org.xfce.Xfconf.Error.ChannelNotFound":
                return {}
            raise RuntimeError(f"Cannot read desktop power preferences: {error}") from error
        result = {}
        for path, value in values.items():
            key = str(path).removeprefix(PREFIX)
            if key not in BY_KEY:
                continue
            if isinstance(value, self.dbus.Boolean):
                value = bool(value)
            elif isinstance(value, (self.dbus.UInt32, self.dbus.Int32)):
                value = int(value)
            elif isinstance(value, self.dbus.String):
                value = str(value)
            result[key] = value
        return result

    def write(self, key, value):
        field = BY_KEY[key]
        field.validate(value)
        constructors = {"bool": self.dbus.Boolean, "uint": self.dbus.UInt32, "string": self.dbus.String}
        self.proxy.SetProperty(CHANNEL, PREFIX + key, constructors[field.kind](value), timeout=3)
        if self.proxy.GetProperty(CHANNEL, PREFIX + key, timeout=3) != value:
            raise RuntimeError(f"Could not save {field.label}")

    def reset(self, key):
        self.proxy.ResetProperty(CHANNEL, PREFIX + key, False, timeout=3)


class Preferences:
    def __init__(self, backend):
        self.backend = backend
        self.original = backend.snapshot()
        self.values = {field.key: self.original.get(field.key, field.default) for field in FIELDS}

    def apply(self, values):
        # Validate the complete draft before the first write. Only edited
        # fields are sent, preserving absent defaults and unknown settings.
        changes = {key: value for key, value in values.items() if value != self.values[key]}
        for key, value in changes.items():
            BY_KEY[key].validate(value)
        for suffix in ("ac", "battery"):
            keys = [f"dpms-on-{suffix}-{stage}" for stage in ("sleep", "off")]
            sleep, off = ({**self.values, **values}[key] for key in keys)
            if any(key in changes for key in keys) and sleep and off and off < sleep:
                raise ValueError("Display off must be at or after display sleep, or 0 for never")
        current = self.backend.snapshot()
        if any(current.get(key) != self.original.get(key) for key in changes):
            raise ValueError("Power settings changed in another window. Reload before applying this draft.")
        written = []
        try:
            for key, value in changes.items():
                # Include an attempted write: a disconnected reply can follow
                # a successful remote mutation.
                written.append(key)
                self.backend.write(key, value)
        except Exception as error:
            failures = []
            for key in reversed(written):
                try:
                    if key in current:
                        self.backend.write(key, current[key])
                    else:
                        self.backend.reset(key)
                except Exception:
                    failures.append(BY_KEY[key].label)
            detail = " Some changes could not be restored: " + ", ".join(failures) if failures else " Previous settings restored."
            raise RuntimeError(str(error) + detail) from error
        self.original.update(changes)
        self.values.update(changes)
        return len(changes)


def devices(root=Path("/sys/class/power_supply")):
    result = []
    for path in sorted(root.glob("*")):
        fields = {}
        for key in ("type", "manufacturer", "model_name", "status", "capacity", "online"):
            try:
                fields[key] = (path / key).read_text().strip()
            except OSError:
                pass
        result.append((path.name, fields))
    return result
