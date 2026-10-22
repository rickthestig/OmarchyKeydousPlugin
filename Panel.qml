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
        state = next
        if (oldProfile !== state.profile) { keysData = null; switchData = null; deviceData = null }
        message = "Connected · firmware " + next.firmware
        effect.currentIndex = next.modes.findIndex(function(m) { return m.value === next.mode })
        brightness.value = next.brightness
        speed.value = next.speed
        hex.text = next.color
        return
      }
      message = next.message || "Settings loaded"
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
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰌌"
    tooltipText: "Keydous NJ81 MAX-CP · keyboard controls"
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
          Label { text: "Keydous NJ81 MAX-CP"; font.pixelSize: 20; font.bold: true }
          Action { text: root.busy ? "Working…" : "Refresh"; onClicked: root.run(["status"]) }
        }
        Label { text: root.message; opacity: 0.8; maximumLineCount: 4; elide: Text.ElideRight }
        Controls.TabBar {
          id: tabs
          Layout.fillWidth: true
          Controls.TabButton { text: "Lighting" }
          Controls.TabButton { text: "Keys" }
          Controls.TabButton { text: "Switches" }
          Controls.TabButton { text: "Device" }
          Controls.TabButton { text: "Firmware" }
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
              enabled: root.ready
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
              Label { text: "Onboard profile" }
              RowLayout {
                Repeater { model: 4; Action { required property int index; text: String(index + 1); highlighted: root.state.profile === index; onClicked: root.run(["profile", "--profile", String(index)]) } }
              }
              Label { text: "Changes save to the keyboard. Brightness 0 turns LEDs off."; opacity: 0.6 }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 1 || tabs.currentIndex === 2
              Layout.fillWidth: true
              spacing: 12
              RowLayout {
                Controls.ComboBox { id: hostSelect; model: ["Windows layer", "Mac layer"]; enabled: root.ready; onActivated: { root.keysData = null; root.switchData = null } }
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
                enabled: root.ready && root.selectedKey !== null
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
              visible: tabs.currentIndex === 4
              Layout.fillWidth: true
              spacing: 12
              Label { text: "Current firmware: " + (root.state.firmware || "not connected"); font.bold: true }
              Label { text: "Check the vendor's firmware catalogue for this exact keyboard (device 4207)." }
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
