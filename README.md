# Kilix Power Controls

The Kilix GUI for desktop power preferences. It replaces the Xfce settings
window while using the existing desktop power service. Opening the app makes
no changes. Apply writes only edited preferences; Reload discards the power
draft and reads the current settings.

Installable on demand from the Kilix content catalog as `kilix-power-controls`.
The catalog pins the exact commit; Kilix runs it from that checkout as an X
application in a Kilix pane.

## What it does

Pages cover button actions, separate plugged-in and battery lid/sleep/profile
policies, critical battery behavior, display power, dimming, and power-supply
devices. Sleep actions and power profiles depend on hardware and system support.
The **Screen Lock** page is shared with Pleb Display Settings. Its Save button
stores per-user automatic lock preferences for the next login; manual locking
remains available. `kilix tui screen-lock` edits those same preferences.

| Page | Settings |
|---|---|
| General | power, sleep, hibernate and battery button actions; notifications, presentation mode, brightness keys |
| Plugged In, Battery | lid action, idle sleep time and action, power profile |
| Battery | critical battery level and action |
| Display | display power management; display sleep and off times |
| Dimming | dim-after time and dimmed brightness, per power source |
| Screen Lock | Pleb's automatic screen-lock preferences |
| Devices | type, status, capacity and model of each power-supply device |

## Usage

Launch with `kilix power-controls` or `pleb devices power` for a Kilix app pane.
`kilix-power-controls --native` opens a window on the current display; `--show`
prints power preferences without opening a window. Install through the pinned
Kilix content catalog (`kilix app install kilix-power-controls`).

| Command | What it does |
|---|---|
| `kilix power-controls` | install if needed and open the app in a Kilix pane |
| `pleb devices power` | the same, from Pleb's device settings |
| `kilix-power-controls --native` | open a window on the current X display |
| `kilix-power-controls --show` | print the current power preferences as JSON |
| `kilix-power-controls --version` | print the version |

The app refuses to run as root; run it as the desktop user.

## Requirements

Requires Linux/X11, Python 3, Tk, python3-dbus, xfconf, the desktop power service,
and Pleb with the shared Screen Lock settings module. Inside a private app
display, the host desktop bus must be available as `PLEB_DESKTOP_BUS_ADDRESS`.
No privileged command, daemon restart, suspend or power-off occurs in this app.

## How it works

```
Tk window --> Preferences (draft, validation) --> xfconf over D-Bus --> desktop power service
    |                                              channel xfce4-power-manager
    +--> Pleb screenlock_gui page (shared with Pleb Display Settings)
    +--> /sys/class/power_supply (read-only device list)
```

`kilix-power-controls` is a small shell launcher that runs `main.py` with the
system Python. `power_controls.py` defines every field the app edits, reads
the `xfce4-power-manager` channel from xfconf over D-Bus, and writes only the
fields you changed, checking each value after it is written. The Screen Lock
page is imported from Pleb's installed `screenlock_gui` module, so the same
page appears in both applications.

Setting keys and action values follow the
[Xfce 4.20 power service configuration](https://github.com/xfce-mirror/xfce4-power-manager/blob/xfce4-power-manager-4.20.0/common/xfpm-config.h)
and its [action enums](https://github.com/xfce-mirror/xfce4-power-manager/blob/xfce4-power-manager-4.20.0/common/xfpm-enum-glib.h).
Unrecognized settings are preserved. If another window changes an edited
preference, Apply asks you to reload instead of overwriting it. A failed write
attempts to restore the previous values and reports any restoration failure.

## Testing

Run tests with `/usr/bin/python3 -m unittest discover -s tests -v`.

## Related repositories

- [pleb](https://github.com/itsmygithubacct/pleb#readme): the session that
  provides the shared Screen Lock module and `pleb devices power`.
- [kilix](https://github.com/itsmygithubacct/kilix#readme): the
  `kilix power-controls` and `kilix app` verbs.
- [kilix-content](https://github.com/itsmygithubacct/kilix-content#readme):
  the catalog entry that pins this repository.

## Part of Plebian-OS

Kilix Power Controls is one of the repositories behind
[Plebian-OS](https://github.com/itsmygithubacct/plebian-os#readme), a Debian
install whose desktop is [Kilix](https://github.com/itsmygithubacct/kilix#readme)
running the [Kilix 95](https://github.com/itsmygithubacct/kilix-95#readme)
desktop through [Pleb](https://github.com/itsmygithubacct/pleb#readme).
It is installed on demand from the Kilix content catalog, not shipped in the
installer image. The map of every repository and how it ships is on the
[components page](https://github.com/itsmygithubacct/plebian-os/blob/main/docs/components.md).

## License

MIT; see [LICENSE](LICENSE).
