import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui

Panel {
  id: root
  moduleName: "eg.keydous"
  ipcTarget: "keydous"
  implicitWidth: 30
  implicitHeight: bar ? bar.barSize : 26
  property var state: ({connected: false})
  property var paintData: null
  property var paintColors: []
  property bool paintDirty: false
  property var keysData: null
  property var switchData: null
  property var deviceData: null
  property var firmwareData: null
  property var macroData: null
  property string message: "Open to read keyboard settings"
  property string compatMessage: "Stopped"
  property bool busy: worker.running
  property bool nativeJob: false
  property bool compatibilityReady: false
  property bool firmwareBridge: false
  property url pictureFile
  readonly property var caps: state.capabilities || ({})
  readonly property bool ready: state.connected === true && !busy && !compat.running
  readonly property var selectedKey: keysData && keysData.keys[keySelect.currentIndex] ? keysData.keys[keySelect.currentIndex] : null
  readonly property string folder: Qt.resolvedUrl(".").toString().replace(/^file:\/\//, "")
  readonly property color fg: Commons.Color.foreground

  component Label: Text {
    color: root.fg
    wrapMode: Text.Wrap
    Layout.fillWidth: true
    font.pixelSize: 13
  }
  component Action: Controls.Button {
    enabled: !root.busy && !compat.running
  }

  function run(args) {
    if (busy || compat.running) return
    nativeJob = false
    message = "Reading keyboard…"
    worker.command = ["python3", "-B", folder + "bridge.py"].concat(args)
    worker.running = true
  }
  function request(data) {
    if (busy || compat.running) return
    nativeJob = true
    message = "Working…"
    worker.command = ["python3", "-B", folder + "native.py", JSON.stringify(data)]
    worker.running = true
  }
  function context(action) {
    return {action: action, profile: state.profile, host: hostSelect.currentIndex, layer: layerSelect.currentIndex === 0 ? "base" : "fn"}
  }
  function loadKeys() { request(context("keys")) }
  function loadSwitches() {
    if (!selectedKey) return
    request({action: "switches", profile: state.profile, slot: selectedKey.slot})
  }
  function loadDevice() { request({action: "device", profile: state.profile}) }
  function accept(data) {
    try {
      var next = JSON.parse(data)
      if (next.error || next.ok === false) { if (!nativeJob && next.connected === false) state = next; message = next.error || "Keyboard operation failed"; return }
      if (!nativeJob) {
        if (!next.connected) { state = next; message = "Keyboard unavailable"; return }
        var oldProfile = state.profile
        var oldDevice = state.deviceId
        state = next
        if (oldProfile !== state.profile || oldDevice !== state.deviceId) { keysData = null; switchData = null; deviceData = null; paintData = null; paintColors = []; paintDirty = false; tabs.currentIndex = 0; hostSelect.currentIndex = 0 }
        message = next.compatibility || (next.modelName + " · firmware " + next.firmware)
        effect.currentIndex = next.modes.findIndex(function(m) { return m.value === next.mode })
        brightness.value = next.brightness === undefined ? 0 : next.brightness
        speed.value = next.speed === undefined ? 0 : next.speed
        hex.text = next.color || ""
        return
      }
      message = next.message || "Settings loaded"
      if (next.kind === "paint") { paintView.currentIndex = 0; paintData = next; paintColors = next.colors.slice(); paintDirty = false }
      if (next.kind === "paint-saved") { paintData = Object.assign({}, paintData, {colors: paintColors.slice()}); paintDirty = false }
      if (next.kind === "keys") { keysData = next; switchData = null }
      if (next.kind === "switches") {
        switchData = next
        actuation.text = next.actuation.toFixed(3)
        releaseTravel.text = next.release.toFixed(3)
        rtPress.text = next.pressStep.toFixed(3)
        rtRelease.text = next.releaseStep.toFixed(3)
        deadzone.text = next.deadzone.toFixed(3)
        rt.checked = next.rapidTrigger
      }
      if (next.kind === "macro") macroData = next
      if (next.kind === "device") {
        deviceData = next
        if (next.sleep) { sleepBT.value = next.sleep[0]; sleepRF.value = next.sleep[1]; deepBT.value = next.sleep[2]; deepRF.value = next.sleep[3] }
        autoOS.checked = next.autoOS === true
        if (next.reportRate !== undefined) rate.currentIndex = [8000,4000,2000,1000,500,250,125].indexOf(next.reportRate)
        if (next.keyboardOptions) {
          wasdSwap.checked = next.keyboardOptions[4] === 1
          antiAccidental.checked = next.keyboardOptions[2] !== 0
          stabilization.currentIndex = next.keyboardOptions[3]
        }
      }
      if (next.kind === "firmware") { firmwareData = next; if (next.downloadMessage) message = next.downloadMessage }
      if (next.path) message += "\n" + next.path
    } catch (e) { message = "Invalid helper response: " + e }
  }
  function paintKey(index, erase) {
    if (!ready || !paintData || !/^#[0-9a-fA-F]{6}$/.test(brush.text)) return
    var colors = paintColors.slice()
    colors[index] = erase ? "#000000" : brush.text.toLowerCase()
    paintColors = colors
    paintDirty = true
  }
  onOpenedChanged: if (opened && !compat.running) run(["status"])
  Process {
    id: worker
    stdout: StdioCollector { onStreamFinished: root.accept(this.text) }
    stderr: StdioCollector { onStreamFinished: if (this.text.length) root.message = this.text.slice(-600) }
  }
  Process {
    id: compat
    command: ["python3", "-B", root.folder + "iot_linux.py"].concat(root.firmwareBridge ? ["--firmware"] : [])
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var result = JSON.parse(line)
          if (result.event === "ready") { root.compatibilityReady = true; root.compatMessage = result.firmware ? "Vendor update bridge ready · connected keyboard USB port only" : "Settings bridge ready · localhost:3838 and :6015" }
          if (result.event === "rpc-error" || result.event === "error") root.compatMessage = result.error
        } catch (e) {}
      }
    }
    stderr: StdioCollector { onStreamFinished: if (this.text.length) root.compatMessage = this.text.slice(-500) }
    onExited: { root.compatibilityReady = false; if (root.compatMessage.indexOf("ready") >= 0) root.compatMessage = "Stopped" }
  }
  FileDialog {
    id: picturePicker
    title: "Choose a keyboard display picture"
    nameFilters: ["Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"]
    onAccepted: root.pictureFile = selectedFile
  }
  ColorDialog {
    id: paintPicker
    title: "Brush colour"
    onAccepted: brush.text = selectedColor.toString().slice(-7)
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰌌"
    tooltipText: (root.state.modelName || "Keydous") + " · keyboard controls"
    onPressed: root.toggle()
  }
  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: popup.fittedContentWidth(640)
    contentHeight: popup.fittedContentHeight(640)
    focusTarget: surface
    Controls.Pane {
      id: surface
      anchors.fill: parent
      padding: 0
      background: null
      palette.window: Commons.Color.background
      palette.base: Commons.Color.background
      palette.button: Qt.lighter(Commons.Color.background, 1.35)
      palette.text: root.fg
      palette.windowText: root.fg
      palette.buttonText: root.fg
      palette.highlight: Commons.Color.accent
      palette.highlightedText: Commons.Color.background
      Keys.onEscapePressed: root.close()
      ColumnLayout {
        anchors.fill: parent
        spacing: 10
        RowLayout {
          Label { text: root.state.modelName || "Keydous Keyboard"; font.pixelSize: 20; font.bold: true }
          Action { text: root.busy ? "Working…" : "Refresh"; onClicked: root.run(["status"]) }
        }
        Label { text: root.message; opacity: 0.8; maximumLineCount: 4; elide: Text.ElideRight }
        Label { text: "Onboard profile"; visible: root.caps.profiles === true }
        RowLayout {
          visible: root.caps.profiles === true
          enabled: root.ready
          Repeater { model: root.state.profileCount || 0; Action { required property int index; text: String(index + 1); highlighted: root.state.profile === index; onClicked: root.run(["profile", "--profile", String(index)]) } }
        }
        Controls.TabBar {
          id: tabs
          Layout.fillWidth: true
          Controls.TabButton { text: "Lighting" }
          Controls.TabButton { text: "Keys"; enabled: root.caps.keymap === true }
          Controls.TabButton { text: "Switches"; enabled: root.caps.advanced === true }
          Controls.TabButton { text: "Device"; enabled: root.caps.advanced === true }
          Controls.TabButton { text: "Firmware"; enabled: root.caps.firmware === true }
          Controls.TabButton { text: "Paint"; enabled: root.caps.paint === true }
        }
        Controls.ScrollView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          contentWidth: availableWidth
          clip: true
          ColumnLayout {
            width: parent.width
            spacing: 12
            ColumnLayout {
              visible: tabs.currentIndex === 0
              enabled: root.ready && root.caps.lighting === true
              Layout.fillWidth: true
              spacing: 12
              Label { text: "Lighting effect" }
              Controls.ComboBox { id: effect; Layout.fillWidth: true; model: root.state.modes || []; textRole: "label"; valueRole: "value" }
              Label { text: "Brightness · " + Math.round(brightness.value * 25) + "%" }
              Controls.Slider { id: brightness; Layout.fillWidth: true; from: 0; to: 4; stepSize: 1; snapMode: Controls.Slider.SnapAlways }
              Label { text: "Animation speed · " + Math.round(speed.value) }
              Controls.Slider { id: speed; Layout.fillWidth: true; from: 0; to: 4; stepSize: 1; snapMode: Controls.Slider.SnapAlways }
              RowLayout {
                Controls.TextField { id: hex; Layout.fillWidth: true; placeholderText: "#RRGGBB"; maximumLength: 7 }
                Rectangle { width: 26; height: 26; radius: 5; color: /^#?[0-9a-fA-F]{6}$/.test(hex.text) ? (hex.text[0] === "#" ? hex.text : "#" + hex.text) : "transparent"; border.color: root.fg }
                Action { text: "Theme accent"; onClicked: hex.text = Commons.Color.accent.toString().slice(-7) }
              }
              RowLayout {
                Action {
                  text: "Apply colour"
                  enabled: root.ready && effect.currentIndex >= 0 && /^#?[0-9a-fA-F]{6}$/.test(hex.text)
                  onClicked: root.run(["light", "--mode", String(effect.currentValue), "--brightness", String(Math.round(brightness.value)), "--speed", String(Math.round(speed.value)), "--color", hex.text])
                }
                Action {
                  text: "Rainbow"
                  enabled: root.ready && effect.currentIndex >= 0
                  onClicked: root.run(["light", "--mode", String(effect.currentValue), "--brightness", String(Math.round(brightness.value)), "--speed", String(Math.round(speed.value)), "--rainbow"])
                }
              }
              Label { text: "Changes save to the keyboard. Brightness 0 turns LEDs off."; opacity: 0.6 }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 1 || tabs.currentIndex === 2
              Layout.fillWidth: true
              spacing: 12
              RowLayout {
                Controls.ComboBox { id: hostSelect; model: ["Windows layer", "Mac layer"]; enabled: root.ready && root.state.family !== "yc500"; onActivated: { root.keysData = null; root.switchData = null } }
                Controls.ComboBox { id: layerSelect; model: ["Base layer", "Fn layer"]; enabled: root.ready; onActivated: { root.keysData = null; root.switchData = null } }
                Action { text: "Load keys"; enabled: root.ready; onClicked: root.loadKeys() }
              }
              Label { text: "Select a slot from the keyboard's live keymap. Slot numbers are hardware positions; Fn is protected."; opacity: 0.7 }
              Controls.ComboBox {
                id: keySelect
                Layout.fillWidth: true
                model: root.keysData ? root.keysData.keys : []
                textRole: "label"
                enabled: root.ready
                onActivated: root.switchData = null
              }
              ColumnLayout {
                visible: tabs.currentIndex === 1
                Layout.fillWidth: true
                enabled: root.ready && root.caps.advanced === true && root.selectedKey !== null
                Label { text: "New assignment" }
                Controls.ComboBox { id: assignment; Layout.fillWidth: true; model: root.keysData ? root.keysData.choices : []; textRole: "label" }
                Action {
                  text: "Save key assignment"
                  onClicked: {
                    var data = root.context("remap")
                    data.slot = root.selectedKey.slot
                    data.expected = root.selectedKey.value
                    data.value = root.keysData.choices[assignment.currentIndex].value
                    root.request(data)
                  }
                }
                Label { text: "A copy of the keymap is saved locally before each change. Host and Fn layers are edited separately."; opacity: 0.6 }
                Label { text: "Text macros"; font.bold: true }
                Label { text: "Macro slots are shared across profiles. Text uses the US keyboard layout."; opacity: 0.7 }
                RowLayout {
                  Controls.SpinBox { id: macroSlot; from: 1; to: 50; value: 1; editable: true; onValueChanged: root.macroData = null }
                  Action { text: "Read macro"; onClicked: root.request({action: "macro", macro: macroSlot.value - 1}) }
                }
                Controls.TextField { id: macroText; Layout.fillWidth: true; placeholderText: "Text to type · up to 40 ASCII characters"; maximumLength: 40 }
                RowLayout {
                  Action { text: "Save text macro"; enabled: root.ready && root.macroData !== null && macroText.text.length > 0; onClicked: root.request({action: "macro-text", macro: macroSlot.value-1, text: macroText.text, expected: root.macroData.digest}) }
                  Action {
                    text: "Assign macro to selected key"
                    enabled: root.ready && root.macroData !== null && root.selectedKey !== null
                    onClicked: {
                      var data = root.context("remap")
                      data.slot = root.selectedKey.slot
                      data.expected = root.selectedKey.value
                      data.value = [9, 0, macroSlot.value-1, 0]
                      root.request(data)
                    }
                  }
                }
              }
              ColumnLayout {
                visible: tabs.currentIndex === 2
                Layout.fillWidth: true
                Action { text: "Read selected switch"; enabled: root.ready && root.selectedKey !== null; onClicked: root.loadSwitches() }
                ColumnLayout {
                  visible: root.switchData !== null
                  enabled: root.ready
                  Layout.fillWidth: true
                  Label { text: "Distances in millimetres · changes apply to this key" }
                  GridLayout {
                    columns: 2
                    Layout.fillWidth: true
                    Label { text: "Actuation" }
                    Controls.TextField { id: actuation; inputMethodHints: Qt.ImhFormattedNumbersOnly; Layout.fillWidth: true }
                    Label { text: "Release point" }
                    Controls.TextField { id: releaseTravel; inputMethodHints: Qt.ImhFormattedNumbersOnly; Layout.fillWidth: true }
                    Label { text: "Rapid trigger press step" }
                    Controls.TextField { id: rtPress; inputMethodHints: Qt.ImhFormattedNumbersOnly; Layout.fillWidth: true }
                    Label { text: "Rapid trigger release step" }
                    Controls.TextField { id: rtRelease; inputMethodHints: Qt.ImhFormattedNumbersOnly; Layout.fillWidth: true }
                    Label { text: "Bottom dead zone" }
                    Controls.TextField { id: deadzone; inputMethodHints: Qt.ImhFormattedNumbersOnly; Layout.fillWidth: true }
                  }
                  Controls.CheckBox { id: rt; text: "Rapid trigger" }
                  Action {
                    text: "Save selected switch"
                    onClicked: root.request({action: "set-switches", profile: root.state.profile, slot: root.switchData.slot,
                      expected: root.switchData.raw, values: {actuation: Number(actuation.text), release: Number(releaseTravel.text),
                      pressStep: Number(rtPress.text), releaseStep: Number(rtRelease.text), deadzone: Number(deadzone.text), keyMode: rt.checked}})
                  }
                  Label { text: "The firmware's distance scale is detected from its version. Other key-mode bits are preserved."; opacity: 0.6 }
                }
              }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 3
              Layout.fillWidth: true
              spacing: 12
              Action { text: "Read device settings"; enabled: root.ready; onClicked: root.loadDevice() }
              ColumnLayout {
                visible: root.deviceData !== null
                Layout.fillWidth: true
                enabled: root.ready
                Label { text: "Polling rate"; font.bold: true }
                RowLayout {
                  Controls.ComboBox { id: rate; model: ["8000 Hz", "4000 Hz", "2000 Hz", "1000 Hz", "500 Hz", "250 Hz", "125 Hz"]; enabled: root.ready && root.deviceData && root.deviceData.reportRate !== undefined }
                  Action { text: "Save polling rate"; enabled: root.ready && root.deviceData && root.deviceData.reportRate !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "reportRate", expected: root.deviceData.reportRate, value: [8000,4000,2000,1000,500,250,125][rate.currentIndex]}) }
                }
                ColumnLayout {
                  visible: root.deviceData && root.deviceData.keyboardOptions !== undefined
                  Layout.fillWidth: true
                  Controls.CheckBox { id: wasdSwap; text: "Swap WASD with arrow keys" }
                  Controls.CheckBox { id: antiAccidental; text: "Prevent accidental triggers" }
                  Label { text: "Rapid trigger stabilization" }
                  Controls.ComboBox { id: stabilization; model: ["Off", "25", "50", "75", "100", "125"] }
                  Action { text: "Save keyboard options"; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "keyboardOptions", expected: root.deviceData.keyboardOptions, value: {wasdSwap: wasdSwap.checked, antiAccidental: antiAccidental.checked, stabilization: stabilization.currentIndex}}) }
                }
                Label { text: "Sleep timers · seconds"; font.bold: true }
                GridLayout {
                  visible: root.deviceData && root.deviceData.sleep !== undefined
                  columns: 2
                  Label { text: "Bluetooth sleep" }
                  Controls.SpinBox { id: sleepBT; from: 0; to: 65535; editable: true }
                  Label { text: "2.4 GHz sleep" }
                  Controls.SpinBox { id: sleepRF; from: 0; to: 65535; editable: true }
                  Label { text: "Bluetooth deep sleep" }
                  Controls.SpinBox { id: deepBT; from: 0; to: 65535; editable: true }
                  Label { text: "2.4 GHz deep sleep" }
                  Controls.SpinBox { id: deepRF; from: 0; to: 65535; editable: true }
                }
                Action { text: "Save sleep timers"; enabled: root.ready && root.deviceData && root.deviceData.sleep !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "sleep", expected: root.deviceData.sleep, value: [sleepBT.value,sleepRF.value,deepBT.value,deepRF.value]}) }
                Controls.CheckBox { id: autoOS; text: "Detect host OS automatically"; enabled: root.ready && root.deviceData && root.deviceData.autoOS !== undefined }
                Action { text: "Save host detection"; enabled: root.ready && root.deviceData && root.deviceData.autoOS !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "autoOS", value: autoOS.checked, expected: root.deviceData.autoOS}) }
                Label { text: root.deviceData && root.deviceData.warnings ? root.deviceData.warnings.join("\n") : ""; opacity: 0.6 }
              }
              Label { text: "Display"; font.bold: true }
              Action { text: "Set display clock to local time"; enabled: root.ready; onClicked: root.request({action: "clock"}) }
              RowLayout {
                Action { text: "Choose picture…"; enabled: root.ready; onClicked: picturePicker.open() }
                Controls.ComboBox { id: pictureSlot; model: ["Picture 1", "Picture 2", "Picture 3", "Picture 4", "Picture 5"]; enabled: root.ready }
                Action { text: "Upload picture"; enabled: root.ready && String(root.pictureFile).length > 0; onClicked: root.request({action: "display-image", slot: pictureSlot.currentIndex, path: decodeURIComponent(String(root.pictureFile).replace(/^file:\/\//,""))}) }
              }
              Image { source: root.pictureFile; visible: String(root.pictureFile).length > 0; Layout.preferredWidth: 160; Layout.preferredHeight: 80; fillMode: Image.PreserveAspectCrop }
              Label { text: "Uploads replace the chosen picture slot. Images are cropped to 160 × 80; animated files use their first frame."; opacity: 0.6 }
              Label { text: "Backup"; font.bold: true }
              Action { text: "Export current profile keymaps and settings"; enabled: root.ready; onClicked: { var data = root.context("export"); root.request(data) } }
              Label { text: "Backups: ~/.local/state/omarchy-keydous/backups"; opacity: 0.6 }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 5
              Layout.fillWidth: true
              spacing: 10
              Label { text: "Per-key lighting · profile " + (root.state.profile + 1); font.bold: true }
              Label { text: "Load your local painting, then click or drag across keys. Right-drag erases. Apply saves to pattern slot 1, shared across onboard profiles." }
              RowLayout {
                Action { text: "Load painting"; enabled: root.ready && !root.paintDirty; onClicked: root.request({action: "paint", profile: root.state.profile}) }
                Controls.TextField { id: brush; text: "#ff6600"; placeholderText: "#RRGGBB"; maximumLength: 7; Layout.preferredWidth: 100 }
                Action { text: "Choose…"; onClicked: paintPicker.open() }
                Rectangle { width: 24; height: 24; color: /^#[0-9a-fA-F]{6}$/.test(brush.text) ? brush.text : "transparent"; border.color: root.fg }
              }
              RowLayout {
                Repeater {
                  model: ["#ff4040", "#ff9900", "#ffff40", "#40ff80", "#40cfff", "#8060ff", "#ff60cf", "#fafafa", "#000000"]
                  Rectangle {
                    required property string modelData
                    width: 25; height: 25; radius: 4; color: modelData; border.color: root.fg
                    MouseArea { anchors.fill: parent; onClicked: brush.text = parent.modelData }
                  }
                }
                Action { text: "Accent"; onClicked: brush.text = Commons.Color.accent.toString().slice(-7) }
              }
              RowLayout {
                Controls.ComboBox { id: paintView; model: root.paintData && root.paintData.layout.keys.length ? ["Keyboard view", "Hardware slots"] : ["Hardware slots"] }
                Label { text: root.paintData ? root.paintData.layout.name : "Load painting to detect layout" }
              }
              Label {
                visible: root.paintData !== null && root.paintData.layout.unresolved > 0
                text: root.paintData ? root.paintData.layout.unresolved + " positions unresolved. Use Hardware slots for remapped or ambiguous keys." : ""
                opacity: 0.7
              }
              Item {
                id: paintGrid
                Layout.fillWidth: true
                Layout.preferredHeight: physical ? width / 16 * 6.4 : Math.ceil(root.paintColors.length / 9) * 37
                property bool physical: root.paintData !== null && root.paintData.layout.keys.length > 0 && paintView.currentIndex === 0
                property real unit: width / 16
                property var cells: {
                  if (!root.paintData) return []
                  if (physical) return root.paintData.layout.keys
                  return root.paintColors.map(function(c, i) { return {slot: i, x: i % 9, y: Math.floor(i / 9), w: 1, h: 1, label: root.paintData.labels[i], assignment: root.paintData.labels[i]} })
                }
                Rectangle {
                  visible: paintGrid.physical && root.paintData !== null
                  x: paintGrid.unit * 14; y: 0
                  width: paintGrid.unit * 2 - 3; height: paintGrid.unit - 3
                  color: "transparent"; radius: 4; border.color: root.fg; opacity: 0.5
                  Text { anchors.centerIn: parent; text: "Display"; color: root.fg; font.pixelSize: 9 }
                }
                Repeater {
                  model: paintGrid.cells
                  Rectangle {
                    required property var modelData
                    x: modelData.x * (paintGrid.physical ? paintGrid.unit : paintGrid.width / 9)
                    y: modelData.y * (paintGrid.physical ? paintGrid.unit : 37)
                    width: modelData.w * (paintGrid.physical ? paintGrid.unit : paintGrid.width / 9) - 3
                    height: modelData.h * (paintGrid.physical ? paintGrid.unit : 37) - 3
                    radius: 4
                    color: modelData.slot >= 0 ? root.paintColors[modelData.slot] : "#262626"
                    border.color: modelData.slot >= 0 ? Qt.rgba(1, 1, 1, 0.4) : "#777777"
                    opacity: modelData.slot >= 0 ? 1 : 0.45
                    Text {
                      anchors.fill: parent; anchors.margins: 2
                      text: parent.modelData.label
                      color: parent.color.r * 0.299 + parent.color.g * 0.587 + parent.color.b * 0.114 > 0.55 ? "#111111" : "#ffffff"
                      font.pixelSize: 9; wrapMode: Text.Wrap; elide: Text.ElideRight
                      horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                  }
                }
                MouseArea {
                  id: paintMouse
                  anchors.fill: parent
                  enabled: root.ready && root.paintData !== null
                  acceptedButtons: Qt.LeftButton | Qt.RightButton
                  hoverEnabled: true
                  property int lastCell: -1
                  property string keyHint: ""
                  function stroke(mouse, draw) {
                    var unitX = paintGrid.physical ? paintGrid.unit : paintGrid.width / 9
                    var unitY = paintGrid.physical ? paintGrid.unit : 37
                    var cell = -1
                    keyHint = ""
                    for (var i = 0; i < paintGrid.cells.length; i++) {
                      var k = paintGrid.cells[i]
                      if (mouse.x >= k.x * unitX && mouse.x < (k.x + k.w) * unitX - 3 && mouse.y >= k.y * unitY && mouse.y < (k.y + k.h) * unitY - 3) {
                        cell = k.slot
                        keyHint = k.label + " · " + k.assignment + (cell >= 0 ? " · slot " + cell : "")
                        break
                      }
                    }
                    if (draw && cell >= 0 && cell !== lastCell) root.paintKey(cell, (mouse.buttons & Qt.RightButton) !== 0)
                    lastCell = cell
                  }
                  onPressed: function(mouse) { lastCell = -1; stroke(mouse, true) }
                  onPositionChanged: function(mouse) { stroke(mouse, pressed) }
                  onReleased: lastCell = -1
                  onExited: keyHint = ""
                  Controls.ToolTip.visible: containsMouse && keyHint.length > 0 && !pressed
                  Controls.ToolTip.text: keyHint
                  Controls.ToolTip.delay: 400
                }
              }
              RowLayout {
                Action {
                  text: "Fill all"; enabled: root.ready && root.paintData !== null && /^#[0-9a-fA-F]{6}$/.test(brush.text)
                  onClicked: { root.paintColors = Array(root.paintColors.length).fill(brush.text.toLowerCase()); root.paintDirty = true }
                }
                Action { text: "Clear"; enabled: root.ready && root.paintData !== null; onClicked: { root.paintColors = Array(root.paintColors.length).fill("#000000"); root.paintDirty = true } }
                Action { text: "Discard edits"; enabled: root.ready && root.paintDirty; onClicked: { root.paintColors = root.paintData.colors.slice(); root.paintDirty = false } }
              }
              Label { text: "Paint brightness" }
              Controls.Slider { id: paintBrightness; Layout.fillWidth: true; from: 0; to: 4; value: 4; stepSize: 1; snapMode: Controls.Slider.SnapAlways }
              Action {
                text: root.paintDirty ? "Apply painting *" : "Apply painting"
                enabled: root.ready && root.paintData !== null
                onClicked: root.request({action: "set-paint", profile: root.paintData.profile, colors: root.paintColors, brightness: Math.round(paintBrightness.value)})
              }
              Label { text: "Strokes are previewed locally. Apply writes flash; wait 10 seconds between uploads. Previous device colours cannot be backed up reliably."; opacity: 0.6 }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 4
              Layout.fillWidth: true
              spacing: 12
              Label { text: "Current firmware: " + (root.state.firmware || "not connected"); font.bold: true }
              Label { text: "Check the vendor's firmware catalogue for the detected keyboard." }
              RowLayout {
                Action { text: "Check updates"; enabled: root.ready; onClicked: root.request({action: "firmware-check"}) }
                Action { text: "Download package"; enabled: root.ready && root.firmwareData && !!root.firmwareData.downloadPath; onClicked: root.request({action: "firmware-download"}) }
              }
              Label { text: root.firmwareData ? "Vendor version: " + root.firmwareData.version : "No update check yet"; opacity: 0.8 }
              Label { text: "The vendor update bridge below lets the official updater use Linux HID. Native package downloads do not flash the keyboard. The update bridge is not yet tested on your hardware." }
              Label { text: "Linux IoT compatibility service · experimental"; font.bold: true }
              Label { text: root.compatMessage; opacity: 0.8 }
              RowLayout {
                Controls.Button {
                  text: compat.running ? "Stop compatibility service" : "Start compatibility service"
                  enabled: !root.busy
                  onClicked: {
                    if (compat.running) compat.signal(15)
                    else { root.firmwareBridge = false; root.compatMessage = "Starting…"; compat.running = true }
                  }
                }
              }
              Label { text: "Native controls pause while the service owns the keyboard. Stop the service when finished. Audio and screen-capture services are not ported."; opacity: 0.7 }
              Controls.Button {
                text: "Start vendor firmware update bridge"
                enabled: !root.busy && !compat.running && root.state.connected === true
                onClicked: { root.firmwareBridge = true; root.compatMessage = "Verifying the keyboard and its USB port…"; compat.running = true }
              }
              Controls.Button {
                text: "Open official updater in Chromium"
                enabled: root.compatibilityReady && root.firmwareBridge
                onClicked: Quickshell.execDetached(["chromium", "--new-window", "https://qmk.top"])
              }
              Label { text: "Use a USB cable. The update bridge follows the verified keyboard through boot mode on the same USB port; the official site selects and sends its firmware. Keep it connected until the vendor reports completion."; opacity: 0.7 }
            }
          }
        }
        Controls.Button { text: "Close"; Layout.alignment: Qt.AlignRight; onClicked: root.close() }
      }
    }
  }
}
