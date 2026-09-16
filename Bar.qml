import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.plugins.bar as Native
import qs.Ui

// Inherit the installed bar: widgets, theme, popouts, IPC and hidden-state IO
// stay Omarchy-owned. Only the top-edge window placement changes.
Native.Bar {
  id: root

  // BarPanel is an inline component in the native bar. Its Variants expose
  // the windows without copying the bar or reaching into the shell host.
  property var nativeBarVariants: null
  readonly property var peekWindows: nativeBarVariants ? nativeBarVariants.instances : []

  function findBarPanels() {
    for (const child of root.data) {
      if (child === peekControllers) continue
      if (!("instances" in child)) continue
      for (const instance of child.instances) {
        if (instance && "contentItem" in instance && "screen" in instance
            && !("ghostScreen" in instance)) {
          nativeBarVariants = child
          return
        }
      }
    }
  }

  Component.onCompleted: Qt.callLater(findBarPanels)
  Connections {
    target: Quickshell
    function onScreensChanged() { Qt.callLater(root.findBarPanels) }
  }

  // Read native tray state for the live interaction regression check.
  function trayState(window) {
    function find(item) {
      if (item.moduleName === "omarchy.tray" && "drawerExtent" in item) return item
      for (const child of item.children || []) {
        const found = find(child)
        if (found) return found
      }
      return null
    }
    const tray = find(window.contentItem)
    if (!tray) return null
    const point = tray.mapToItem(window.contentItem, 0, 0)
    return { x: point.x, y: point.y, height: tray.height,
      slot: tray.trayItemExtent, extent: tray.drawerExtent,
      expanded: tray.expanded, progress: tray.revealProgress,
      manageOpen: tray.managePopupOpen }
  }

  IpcHandler {
    target: "topbar-peek"
    function status(): string {
      return JSON.stringify({ hidden: root.barHidden, position: root.position,
        screens: peekControllers.instances.map(p => ({
          name: p.modelData.screen.name, revealed: p.revealed,
          held: p.held, offset: p.offset, hover: p.hoverState,
          tray: root.trayState(p.modelData)
        })) })
    }
  }

  Variants {
    id: peekControllers
    model: root.peekWindows

    delegate: Component {
      Item {
        id: peek
        required property var modelData
        property bool ready: false
        Component.onCompleted: Qt.callLater(() => ready = true)
        readonly property bool enabledHere: root.position === "top"
        property bool revealed: false
        readonly property var hoverState: ({ bar: barHover.hovered, edge: edgeHover.hovered, catching: edge.catching })
        readonly property bool held: barHover.hovered || (edge.catching && edgeHover.hovered)
          || (root.activePopout !== null && root.targetBelongsToWindow(root.activePopout, modelData))
          || root.barDragWindow === modelData || root.barMoveWindow === modelData
        property real offset: enabledHere && root.barHidden && !revealed ? -root.barSize : 0

        Behavior on offset {
          // Same duration and easing as Omarchy's PopupCard.
          NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }

        Connections {
          target: root
          function onBarHiddenChanged() { peek.revealed = false }
          function onPositionChanged() { peek.revealed = false }
        }

        Binding {
          target: peek.modelData
          property: "margins.top"
          value: Math.round(peek.offset)
          when: peek.ready && peek.enabledHere
          restoreMode: Binding.RestoreBindingOrValue
        }

        Binding {
          target: peek.modelData.WlrLayershell
          property: "layer"
          value: WlrLayer.Overlay
          when: peek.ready && peek.enabledHere && root.barHidden
          restoreMode: Binding.RestoreBindingOrValue
        }

        HoverHandler {
          id: barHover
          // Observe from an ancestor. A sibling overlay suppresses native
          // widget hover handlers, including the tray drawer, even if passive.
          parent: peek.modelData.contentItem
          blocking: false
          onHoveredChanged: if (hovered && root.barHidden && peek.enabledHere) peek.revealed = true
        }

        Timer {
          interval: 120
          running: peek.revealed && !peek.held
          onTriggered: if (!peek.held) peek.revealed = false
        }

        PanelWindow {
          id: edge
          readonly property bool catching: visible && (!peek.revealed || !barHover.hovered)
          screen: peek.modelData.screen
          visible: peek.ready && peek.enabledHere && root.barHidden && !edgeRemap.remapping
          color: "transparent"
          implicitHeight: 2
          anchors { top: true; left: true; right: true }
          exclusionMode: ExclusionMode.Ignore
          // Hand input back after the pointer enters the bar. Clearing the
          // mask at animation end alone may not generate a new pointer enter.
          mask: Region { width: edge.catching ? edge.width : 0; height: 2 }
          WlrLayershell.namespace: "omarchy-topbar-peek-edge"
          WlrLayershell.layer: WlrLayer.Overlay
          WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

          ScreenMoveRemap { id: edgeRemap; window: edge }

          HoverHandler {
            id: edgeHover
            onHoveredChanged: if (hovered) peek.revealed = true
          }
        }
      }
    }
  }
}
