import QtQuick
import QtQuick.Controls as Controls
import qs.Commons as Commons

Item {
  id: root
  property var layout: null
  property var slots: []
  property var colors: []
  property var annotations: ({})
  property bool hardwareView: false
  property bool painting: false
  property int selectedSlot: -1
  signal chosen(int slot)
  signal painted(int slot, bool erase)
  readonly property bool physical: !hardwareView && layout !== null && layout.keys.length > 0
  readonly property real columns: physical ? layout.width : 16
  readonly property real unit: width / columns
  readonly property real rowHeight: physical ? unit : Math.max(34, unit)
  readonly property var cells: {
    if (physical) return layout.keys
    return slots.map(function(key, i) { return {slot: key.slot, x: i % 16, y: Math.floor(i / 16), w: 1, h: 1, label: key.label.replace(/^\d+ · /, ""), assignment: key.label} })
  }
  implicitHeight: physical ? unit * layout.height : Math.ceil(slots.length / 16) * rowHeight
  activeFocusOnTab: true
  Keys.onPressed: function(event) {
    if (painting || !slots.length) return
    var offset = event.key === Qt.Key_Left ? -1 : event.key === Qt.Key_Right ? 1 : event.key === Qt.Key_Up ? -16 : event.key === Qt.Key_Down ? 16 : 0
    if (offset) {
      var at = slots.findIndex(function(key) { return key.slot === root.selectedSlot })
      chosen(slots[Math.max(0, Math.min(slots.length - 1, at + offset))].slot)
      event.accepted = true
    }
  }
  Rectangle {
    visible: root.physical
    x: root.unit * 14; y: 0
    width: root.unit * 2 - 4; height: root.unit - 4
    color: "transparent"; border.color: Commons.Color.foreground; opacity: 0.3
    radius: Commons.Style.cornerRadius
    Text { anchors.centerIn: parent; text: "DISPLAY"; color: Commons.Color.foreground; font.family: Commons.Style.font.family; font.pixelSize: Commons.Style.font.caption }
  }
  Repeater {
    model: root.cells
    Rectangle {
      id: cap
      required property var modelData
      readonly property bool resolved: modelData.slot >= 0 && (!root.painting || modelData.slot < root.colors.length)
      readonly property bool selected: resolved && modelData.slot === root.selectedSlot
      readonly property bool hot: resolved && pointer.hoverSlot === modelData.slot
      readonly property color ink: Commons.Color.foreground
      x: modelData.x * root.unit
      y: modelData.y * root.rowHeight
      width: modelData.w * root.unit - 4
      height: modelData.h * root.rowHeight - 4
      radius: Commons.Style.cornerRadius
      color: root.painting && resolved ? root.colors[modelData.slot] : selected ? Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.22) : Qt.rgba(ink.r, ink.g, ink.b, hot ? 0.14 : 0.05)
      border.width: selected || hot ? 2 : 1
      border.color: selected || hot ? Commons.Color.accent : Qt.rgba(ink.r, ink.g, ink.b, 0.22)
      opacity: resolved ? 1 : 0.35
      Text {
        anchors.fill: parent; anchors.margins: 3
        text: cap.modelData.label + (root.annotations[cap.modelData.slot] ? "\n" + root.annotations[cap.modelData.slot] : "")
        color: root.painting && cap.resolved ? (cap.color.r * 0.299 + cap.color.g * 0.587 + cap.color.b * 0.114 > 0.55 ? "#111111" : "#ffffff") : cap.ink
        font.family: Commons.Style.font.family
        font.pixelSize: Math.min(Commons.Style.font.caption, Math.max(8, root.unit * 0.23))
        font.bold: cap.selected
        wrapMode: Text.Wrap; elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
      }
    }
  }
  MouseArea {
    id: pointer
    objectName: "keydousKeyPointer"
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: root.painting ? Qt.LeftButton | Qt.RightButton : Qt.LeftButton
    cursorShape: hoverSlot >= 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
    property int hoverSlot: -1
    property int lastSlot: -1
    property string hint: ""
    function hit(mouse, draw) {
      hoverSlot = -1; hint = ""
      for (var i = 0; i < root.cells.length; i++) {
        var key = root.cells[i]
        if (mouse.x >= key.x * root.unit && mouse.x < (key.x + key.w) * root.unit - 4 && mouse.y >= key.y * root.rowHeight && mouse.y < (key.y + key.h) * root.rowHeight - 4) {
          hoverSlot = key.slot
          var live = root.slots.find(function(k) { return k.slot === key.slot })
          hint = key.label + " · " + (live ? live.label : key.assignment)
          break
        }
      }
      if (draw && hoverSlot >= 0 && hoverSlot !== lastSlot) {
        if (root.painting) {
          if (hoverSlot < root.colors.length) root.painted(hoverSlot, (mouse.buttons & Qt.RightButton) !== 0)
        }
        else root.chosen(hoverSlot)
      }
      lastSlot = hoverSlot
    }
    onPressed: function(mouse) { root.forceActiveFocus(); lastSlot = -1; hit(mouse, true) }
    onPositionChanged: function(mouse) { hit(mouse, pressed && root.painting) }
    onReleased: lastSlot = -1
    onExited: { hoverSlot = -1; hint = "" }
    Controls.ToolTip.visible: containsMouse && hint.length > 0 && !pressed
    Controls.ToolTip.text: hint
    Controls.ToolTip.delay: 500
  }
}
