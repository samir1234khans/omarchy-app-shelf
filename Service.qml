import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
  id: root

  property var shell: null
  property var manifest: null
  readonly property string home: Quickshell.env("HOME")
  readonly property string pluginDir: manifest && manifest.__sourceDir
    ? String(manifest.__sourceDir)
    : home + "/.config/omarchy/plugins/io.github.samir1234khans.appshelf"
  readonly property string helperPath: pluginDir + "/helper/appshelf"

  property var snapshot: ({
    schemaVersion: 1,
    apps: [],
    folders: [],
    layout: {},
    settings: {},
    usage: {},
    providers: {},
    pendingPlan: null
  })
  property bool busy: false
  property string statusMessage: "Starting App Shelf"
  property string lastError: ""
  property int pendingReviewCount: 0

  signal refreshed()
  signal commandFailed(string code, string message)

  function refreshSnapshot() {
    statusMessage = "App Shelf foundation loaded"
    refreshed()
  }

  function openCredentialSetup(provider) {
    Quickshell.execDetached(["xdg-terminal-exec", helperPath, "credentials", "set", String(provider)])
  }

  Component.onCompleted: refreshSnapshot()
}
