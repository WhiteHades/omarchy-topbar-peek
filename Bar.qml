import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.plugins.bar as Native

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

  IpcHandler {
    target: "peek"
    function status(): string {
      return JSON.stringify({ hidden: root.barHidden, position: root.position,
        screens: peekControllers.instances.map(p => ({
          name: p.modelData.screen.name, revealed: p.revealed,
          held: p.held, offset: p.offset
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
        readonly property bool enabledHere: root.position === "top"
        property bool revealed: false
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
          when: peek.enabledHere
          restoreMode: Binding.RestoreBindingOrValue
        }

        Binding {
          target: peek.modelData.WlrLayershell
          property: "layer"
          value: WlrLayer.Overlay
          when: peek.enabledHere && root.barHidden
          restoreMode: Binding.RestoreBindingOrValue
        }

        Item {
          parent: peek.modelData.contentItem
          anchors.fill: parent
          z: 1000000
          HoverHandler {
            id: barHover
            blocking: false
          }
        }

        Timer {
          interval: 120
          running: peek.revealed && !peek.held
          onTriggered: peek.revealed = false
        }

        PanelWindow {
          id: edge
          readonly property bool catching: visible && (!peek.revealed || peek.offset < 0)
          screen: peek.modelData.screen
          visible: peek.enabledHere && root.barHidden
          color: "transparent"
          implicitHeight: 2
          anchors { top: true; left: true; right: true }
          exclusionMode: ExclusionMode.Ignore
          // Once the bar reaches the edge, hand even its topmost pixels back
          // to the widgets without unmapping the trigger during the slide.
          mask: Region { width: edge.catching ? edge.width : 0; height: 2 }
          WlrLayershell.namespace: "omarchy-peek-edge"
          WlrLayershell.layer: WlrLayer.Overlay
          WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

          HoverHandler {
            id: edgeHover
            onHoveredChanged: if (hovered) peek.revealed = true
          }
        }
      }
    }
  }
}
