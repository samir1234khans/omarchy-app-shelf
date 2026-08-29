import QtQuick
import qs.Ui
import qs.Commons

BarWidget {
  id: root
  moduleName: "io.github.samir1234khans.appshelf"

  readonly property var appShelfService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName)
    : null
  readonly property int pendingCount: appShelfService
    ? Number(appShelfService.pendingReviewCount || 0)
    : 0

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: pendingCount > 0 && root.setting("showCount", true)
      ? "󱂬 " + pendingCount
      : "󱂬"
    tooltipText: pendingCount > 0
      ? "App Shelf · " + pendingCount + " changes to review"
      : "App Shelf"
    active: pendingCount > 0

    onPressed: function(mouseButton) {
      if (!root.bar) return
      if (mouseButton === Qt.MiddleButton) {
        if (root.appShelfService) root.appShelfService.refreshSnapshot()
      } else if (mouseButton === Qt.RightButton) {
        root.bar.run("omarchy-shell shell toggle io.github.samir1234khans.appshelf '{\"view\":\"sync\"}'")
      } else {
        root.bar.run("omarchy-shell shell toggle io.github.samir1234khans.appshelf '{}'")
      }
    }
  }
}
