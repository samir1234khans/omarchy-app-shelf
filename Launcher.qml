import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var service: null
  property bool opened: false

  function open(payload) {
    opened = true
    if (service) service.refreshSnapshot()
    Qt.callLater(function() { closeFocus.forceActiveFocus() })
  }

  function close() {
    opened = false
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omarchy-app-shelf"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: root.opened
      ? WlrKeyboardFocus.Exclusive
      : WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: "#B3000000"
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.close()
    }

    Rectangle {
      width: Math.min(parent.width - Style.space(48), Style.space(1100))
      height: Math.min(parent.height - Style.space(48), Style.space(720))
      anchors.centerIn: parent
      radius: Math.max(12, Style.cornerRadius)
      color: "#11151A"
      border.width: 1
      border.color: "#2B343E"

      MouseArea { anchors.fill: parent; onClicked: {} }

      Column {
        anchors.fill: parent
        anchors.margins: Style.space(28)
        spacing: Style.space(18)

        Text {
          text: "App Shelf"
          color: "#F2F5F7"
          font.family: Style.font.family
          font.pixelSize: Style.font.display
          font.weight: Font.DemiBold
        }

        Text {
          text: "The Omarchy-native application library is ready for its implementation layers."
          color: "#A8B1BC"
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
          width: parent.width
        }

        Rectangle {
          width: parent.width
          height: Style.space(1)
          color: "#2B343E"
        }

        Text {
          text: service ? service.statusMessage : "Loading service…"
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }

        Text {
          id: closeFocus
          focus: root.opened
          text: "Press Esc to close"
          color: "#707B87"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption

          Keys.onEscapePressed: root.close()
        }
      }
    }
  }
}
