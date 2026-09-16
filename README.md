# Omarchy Top Bar Peek

Hide your top bar with the usual Omarchy toggle. Touch the top two logical pixels of
the screen to slide it back over your windows. Move away and it slides out.

Top Bar Peek runs inside Omarchy's existing Quickshell process and inherits the
installed bar. Your widgets, layout, colors, fonts, transparency, menus and
popouts remain native. Hover never changes the saved hidden preference or
reserves desktop space. A normally visible bar behaves as usual.

## See it in action

[Watch the 19-second demo](media/demo.mp4): edge reveal, movement across the
bar, a calendar popout, and automatic hiding. Recorded on an empty workspace
with Omarchy's screen recorder, at 1080p/60 fps without audio.

| Hidden | Revealed at the top edge |
|---|---|
| ![Empty workspace with the top bar hidden](media/hidden.png) | ![The native top bar revealed above the same wallpaper](preview.png) |

## Install

Requires Omarchy 4's Quickshell bar. Tested on Omarchy **4.0.4-1**.
There are no extra runtime dependencies. The optional live regression check
uses Python 3 and `python-evdev` with access to `/dev/uinput`.

```sh
omarchy plugin add https://github.com/WhiteHades/omarchy-topbar-peek --enable --yes
```

Use **Super + Shift + Space** to toggle the bar. While hidden, hover at the
top edge. The bar stays open over its widgets and while a widget popout is
open. After leaving, it waits 120 ms and slides out over 140 ms using the same
`OutCubic` easing and duration as Omarchy's popup cards.

This behavior applies to top bars only. Other bar positions retain their stock
behavior. Each screen gets its own reveal trigger. The bar appears in the
overlay layer, including above fullscreen applications. Session locking is
still controlled by Omarchy.

Sizing stays in Qt/Wayland logical coordinates. Each output applies its own
scale to the native widgets, bar height, slide distance, and two-pixel edge
trigger. For example, the trigger occupies four physical pixels at 200%.
Mixed-DPI outputs do not share a hard-coded physical bar size.

Update or return to the stock bar:

```sh
omarchy plugin update io.github.whitehades.topbar-peek --yes
omarchy bar use omarchy.bar
# Optional, after switching back:
omarchy plugin remove io.github.whitehades.topbar-peek --yes
```

## How it works

`Bar.qml` inherits `qs.plugins.bar.Bar`. It finds that bar's native panel
windows and adds a two-pixel Wayland edge trigger plus a passive hover
observer on the widgets' shared parent. This lets native hover handlers,
including the tray drawer, receive pointer events. While hidden, it animates
only the top margin and promotes the window to the overlay layer. The stock bar keeps `ExclusionMode.Ignore`
because its `barHidden` state stays true. No polling process, extra daemon,
copied widget implementation, packaged-file edit, or Hyprland rule is needed.

Installation and selection use Omarchy's official plugin commands. The QML
inheritance and panel discovery use **internal bar implementation details**,
not a promised stable Omarchy API. Changes to those internals may require a
Top Bar Peek update. The plugin is independent of Omarchy and replaces any other
selected full-bar plugin. Third-party widget service access follows Omarchy's
normal restrictions for replacement bars.

Once the pointer enters the bar below the trigger, the trigger releases input,
including its top two pixels. Popouts hold the bar until dismissed so you can
move into them without losing their anchor.

## Verify or develop

```sh
omarchy plugin validate .
python check.py
python check.py --appearance
python check.py --monitor DP-1
omarchy shell topbar-peek status
```

Run the check from an active Hyprland session with Top Bar Peek selected and the bar
at the top. Install the check dependency with `omarchy pkg add python-evdev`
if needed. Your session must have write access to `/dev/uinput` for its temporary
test pointer. Compositor pointer warps alone do not deliver motion within a
surface, so interaction checks use actual input events.

It moves the pointer, opens/closes the clock and tray management popouts, and
toggles the bar; it restores the pointer and hidden preference afterward. It checks edge
reveal, widget hover, overlay placement, unchanged window geometry and monitor
reserved space, popup retention, hide, and normal pinned visibility. It also
checks native tray expansion, movement across app icons, right-click management,
and collapse in both hidden and pinned modes. Tray checks report a skip when
there are no drawer items. It assumes the stock clock widget is enabled and no
popout is already open.

`--monitor` selects an existing output for DPI checks. It verifies the bar and
edge trigger's full logical width and position against the compositor, along
with the usual hover, tray, popup, and geometry checks. It uses tray clicks for
popup coverage when drawer items exist, because native clock IPC has no output
selector. Headless outputs need an active screencopy consumer during these
checks so Hyprland continues presenting frames.

Leave the pointer idle during the check. `--appearance` repeats it with
`omarchy bar transparent true/false` and `omarchy plugin enable/disable
omarchy.background`, then restores both settings. Bar transparency and desktop
wallpaper are independent: all four combinations work.

Live checks on Omarchy 4.0.4-1 covered:

| Scenario | Result |
|---|---|
| Hidden edge reveal, widget hover, exit and rapid re-entry | Passed |
| Clock popout interaction and dismissal | Passed |
| Tray hover expansion, icon hover, right-click management and collapse | Passed |
| Normal pinned mode and 16 consecutive native toggles | Passed |
| Opaque and transparent bars, with and without desktop wallpaper | Passed |
| Overlay above a fullscreen application, unchanged window geometry | Passed |
| Physical display at 125%, with an actively captured virtual output at 100%, 125%, 150%, 175%, 200%, 250%, and 300% | Passed |
| Physical display changed live to 150%, then restored to 125% | Passed |
| Virtual output hotplug, removal and monitor-origin change | Passed |

After editing an installed checkout, use `omarchy restart shell` if plugin
hot-reload has retained cached QML. DPI checks used a 3360×2100 virtual output
alongside the 1920×1080 physical display, including live scale changes after
the output settled. The virtual output had an active screencopy consumer;
without one, its compositor could leave a parked layer at its old position
despite QML reporting the new margin. Physical monitor unplug/replug and other hardware/scale
combinations have not been verified.

## Existing work

Omarchy's [native bar](https://github.com/omacom/omarchy/blob/quattro/shell/plugins/bar/Bar.qml)
already parks hidden windows off-screen, but does not expose an edge-reveal
setting. Its [plugin system](https://omarchy.org/manual/shell-plugins/) provides
installation and full-bar selection.

[ericvrp's autohide plugin](https://github.com/ericvrp/omarchy-bar-autohide)
provided a useful edge-trigger and hover-observer reference. Its reveal removes
the hidden flag, which restores the native reserved area, and it has no slide
animation. [Bar Control](https://github.com/radyalz/omarchy-bar-control) adds
animated autohide through a full bar copy, but also reserves space when shown.
Top Bar Peek keeps the stock hidden state throughout the overlay reveal.
