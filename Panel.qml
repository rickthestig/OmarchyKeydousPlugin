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
  property var switchAnnotations: ({})
  property var deviceData: null
  property var firmwareData: null
  property var macroData: null
  property string message: "Open to read keyboard settings"
  property string compatMessage: "Stopped"
  property bool busy: jobPending || worker.running
  property bool jobPending: false
  property bool bridgePending: false
  property bool nativeJob: false
  property bool shuttingDown: false
  property bool compatibilityReady: false
  property bool firmwareBridge: false
  property url pictureFile
  readonly property var caps: state.capabilities || ({})
  readonly property bool ready: state.connected === true && !busy && !compat.running && !bridgePending && !shuttingDown
  readonly property var selectedKey: keysData && keysData.keys[keySelect.currentIndex] ? keysData.keys[keySelect.currentIndex] : null
  readonly property string folder: Qt.resolvedUrl(".").toString().replace(/^file:\/\//, "")
  readonly property color fg: Commons.Color.foreground

  component Label: Text {
    color: root.fg
    wrapMode: Text.Wrap
    Layout.fillWidth: true
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
    textFormat: Text.PlainText
  }
  component Action: Button {
    property bool highlighted: false
    selected: highlighted
    focusable: true
    bordered: true
    enabled: !root.busy && !compat.running && !root.bridgePending
    opacity: enabled ? 1 : 0.4
  }
  component Choice: Dropdown {
    id: choice
    property var model: []
    property string textRole: ""
    property string valueRole: ""
    property int currentIndex: 0
    readonly property var currentValue: model[currentIndex] && valueRole ? model[currentIndex][valueRole] : model[currentIndex]
    signal activated(int index)
    implicitWidth: Commons.Style.space(170)
    options: model.map(function(item, i) { return {value: String(i), label: choice.textRole ? item[choice.textRole] : String(item)} })
    value: String(currentIndex)
    onChanged: function(value) { currentIndex = Number(value); activated(currentIndex) }
  }
  component Check: Toggle {
    property alias text: toggle.label
    id: toggle
    Layout.fillWidth: true
    onClicked: checked = !checked
  }
  component Count: NumberField {
    id: count
    onModified: function(value) { count.value = value }
  }
  component Level: PanelSlider {
    property alias from: level.minimum
    property alias to: level.maximum
    property alias stepSize: level.step
    id: level
    fillColor: Commons.Color.accent
    trackColor: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.15)
    onMoved: function(value) { level.value = Math.round(value / step) * step }
  }
  function selectKey(slot, readSwitch) {
    if (!ready || !keysData) return
    var index = keysData.keys.findIndex(function(key) { return key.slot === slot })
    if (index < 0) return
    keySelect.currentIndex = index
    switchData = null
    if (readSwitch && caps.advanced) request({action: "switches", profile: state.profile, slot: slot})
  }

  function run(args) {
    if (shuttingDown || busy || compat.running || bridgePending) return
    jobPending = true
    nativeJob = false
    message = "Reading keyboard…"
    worker.command = ["python3", "-B", folder + "bridge.py"].concat(args)
    worker.running = true
  }
  function request(data) {
    if (shuttingDown || busy || compat.running || bridgePending) return
    jobPending = true
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
    if (shuttingDown) return
    try {
      var next = JSON.parse(data)
      if (next.error || next.ok === false) { if (!nativeJob && next.connected === false) state = next; message = next.error || "Keyboard operation failed"; return }
      if (!nativeJob) {
        if (!next.connected) { state = next; message = "Keyboard unavailable"; return }
        var oldProfile = state.profile
        var oldDevice = state.deviceId
        state = next
        if (oldProfile !== state.profile || oldDevice !== state.deviceId) { keysData = null; switchData = null; switchAnnotations = ({}); deviceData = null; paintData = null; paintColors = []; paintDirty = false; tabs.currentIndex = 0; hostSelect.currentIndex = 0 }
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
        var annotations = Object.assign({}, switchAnnotations)
        annotations[next.slot] = next.actuation.toFixed(2)
        switchAnnotations = annotations
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
    if (!ready || !paintData || !Number.isInteger(index) || index < 0 || index >= paintColors.length) return
    if (!erase && !/^#[0-9a-fA-F]{6}$/.test(brush.text)) return
    var colors = paintColors.slice()
    colors[index] = erase ? "#000000" : brush.text.toLowerCase()
    paintColors = colors
    paintDirty = true
  }
  onOpenedChanged: if (opened && !shuttingDown && !compat.running) run(["status"])
  function startBridge(firmware) {
    if (shuttingDown || busy || compat.running || bridgePending) return
    bridgePending = true
    firmwareBridge = firmware
    compatMessage = "Starting…"
    compat.running = true
  }
  Timer {
    interval: 5000
    running: root.jobPending && !worker.running && !root.shuttingDown
    onTriggered: { root.jobPending = false; root.message = "Keyboard helper could not start. Refresh to retry." }
  }
  Timer {
    interval: 5000
    running: root.bridgePending && !compat.running && !root.shuttingDown
    onTriggered: { root.bridgePending = false; root.compatMessage = "Compatibility helper could not start." }
  }
  // Drop parsers before terminating helpers so teardown cannot deliver a late
  // stdout callback into controls which have already been destroyed.
  function shutdown() {
    if (shuttingDown) return
    shuttingDown = true
    jobPending = false
    bridgePending = false
    worker.stdout = null
    worker.stderr = null
    compat.stdout = null
    compat.stderr = null
    if (worker.running) worker.running = false
    if (compat.running) compat.running = false
  }
  Component.onDestruction: shutdown()
  Process {
    id: worker
    objectName: "keydousWorker"
    stdout: StdioCollector { id: workerOutput; waitForEnd: true }
    stderr: StdioCollector { id: workerError; waitForEnd: true }
    onExited: function(exitCode, exitStatus) {
      if (root.shuttingDown) return
      root.jobPending = false
      if (workerOutput.text.trim().length) root.accept(workerOutput.text)
      else root.message = "Keyboard helper exited without a response. Refresh to retry."
      if (workerError.text.trim().length) root.message = workerError.text.slice(-600)
    }
  }
  Process {
    id: compat
    onRunningChanged: if (running) root.bridgePending = false
    objectName: "keydousCompat"
    command: ["python3", "-B", root.folder + "iot_linux.py"].concat(root.firmwareBridge ? ["--firmware"] : [])
    stdout: SplitParser {
      onRead: function(line) {
        if (root.shuttingDown) return
        try {
          var result = JSON.parse(line)
          if (result.event === "ready") { root.compatibilityReady = true; root.compatMessage = result.firmware ? "Vendor update bridge ready · connected keyboard USB port only" : "Settings bridge ready · localhost:3838 and :6015" }
          if (result.event === "rpc-error" || result.event === "error") root.compatMessage = result.error
        } catch (e) {}
      }
    }
    stderr: StdioCollector { id: compatError; waitForEnd: true }
    onExited: {
      if (root.shuttingDown) return
      root.bridgePending = false
      root.compatibilityReady = false
      if (compatError.text.trim().length) root.compatMessage = compatError.text.slice(-500)
      else if (root.compatMessage.indexOf("ready") >= 0) root.compatMessage = "Stopped"
    }
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
    contentWidth: popup.fittedContentWidth(Commons.Style.space(760))
    contentHeight: popup.fittedContentHeight(Commons.Style.space(800))
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
        spacing: Commons.Style.spacing.md
        PanelHero {
          Layout.fillWidth: true
          title: root.state.modelName || "Keydous Keyboard"
          meta: root.state.connected ? "USB · Firmware " + root.state.firmware : "Connect your keyboard by USB"
          detail: root.busy ? "Working" : root.state.connected ? "Connected" : "Offline"
          iconComponent: Component { Text { text: "󰌌"; color: root.fg; font.family: Commons.Style.font.family; font.pixelSize: Commons.Style.font.display } }
          trailingControl: Component { Action { text: "󰑐"; tooltipText: "Refresh keyboard"; onClicked: root.run(["status"]) } }
        }
        PanelSeparator { Layout.fillWidth: true }
        PanelSectionHeader { text: "ONBOARD PROFILE"; visible: root.caps.profiles === true }
        RowLayout {
          visible: root.caps.profiles === true
          enabled: root.ready
          Repeater { model: root.state.profileCount || 0; Action { required property int index; text: String(index + 1); highlighted: root.state.profile === index; onClicked: root.run(["profile", "--profile", String(index)]) } }
        }
        RowLayout {
          id: tabs
          objectName: "keydousTabs"
          property int currentIndex: 0
          Layout.fillWidth: true
          spacing: Commons.Style.spacing.xs
          Repeater {
            model: ["Lighting", "Keys", "Travel", "Device", "Firmware", "Paint"]
            Action {
              required property int index
              required property string modelData
              Layout.fillWidth: true
              text: modelData
              selected: tabs.currentIndex === index
              bordered: false
              enabled: !root.busy && [true, root.caps.keymap, root.caps.advanced, root.caps.advanced, root.caps.firmware, root.caps.paint][index] === true
              onClicked: tabs.currentIndex = index
            }
          }
        }
        PanelSeparator { Layout.fillWidth: true }
        Controls.ScrollView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          contentWidth: availableWidth
          clip: true
          ColumnLayout {
            width: parent.width
            spacing: Commons.Style.spacing.lg
            ColumnLayout {
              visible: tabs.currentIndex === 0
              enabled: root.ready && root.caps.lighting === true
              Layout.fillWidth: true
              spacing: Commons.Style.spacing.lg
              Label { text: "Lighting effect" }
              Choice { id: effect; Layout.fillWidth: true; model: root.state.modes || []; textRole: "label"; valueRole: "value" }
              Label { text: "Brightness · " + Math.round(brightness.value * 25) + "%" }
              Level { id: brightness; Layout.fillWidth: true; from: 0; to: 4; stepSize: 1 }
              Label { text: "Animation speed · " + Math.round(speed.value) }
              Level { id: speed; Layout.fillWidth: true; from: 0; to: 4; stepSize: 1 }
              RowLayout {
                TextField { id: hex; Layout.fillWidth: true; placeholderText: "#RRGGBB"; maximumLength: 7 }
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
              spacing: Commons.Style.spacing.lg
              RowLayout {
                visible: tabs.currentIndex === 1
                Choice { id: hostSelect; model: ["Windows layer", "Mac layer"]; enabled: root.ready && root.state.family !== "yc500"; onActivated: { root.keysData = null; root.switchData = null } }
                Choice { id: layerSelect; model: ["Base layer", "Fn layer"]; enabled: root.ready; onActivated: { root.keysData = null; root.switchData = null } }
                Action { text: "Load keys"; enabled: root.ready; onClicked: root.loadKeys() }
              }
              RowLayout {
                PanelSectionHeader { Layout.fillWidth: true; text: tabs.currentIndex === 2 ? "SELECT A KEY TO EDIT TRAVEL" : "SELECT A KEY TO REMAP" }
                Choice { id: keyView; model: root.keysData && root.keysData.layout.keys.length ? ["Keyboard", "Slots"] : ["Slots"] }
              }
              KeyboardMap {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                Layout.maximumWidth: Commons.Style.space(660)
                Layout.alignment: Qt.AlignHCenter
                layout: root.keysData ? root.keysData.layout : null
                slots: root.keysData ? root.keysData.keys : []
                hardwareView: keyView.currentIndex === 1
                selectedSlot: root.selectedKey ? root.selectedKey.slot : -1
                annotations: tabs.currentIndex === 2 ? root.switchAnnotations : ({})
                enabled: root.ready
                onChosen: function(slot) { root.selectKey(slot, tabs.currentIndex === 2) }
              }
              Action { visible: !root.keysData && tabs.currentIndex === 2; text: "Load keyboard"; enabled: root.ready; onClicked: { hostSelect.currentIndex = 0; layerSelect.currentIndex = 0; root.loadKeys() } }
              Choice {
                id: keySelect
                visible: !root.keysData || !root.keysData.layout.keys.length || keyView.currentIndex === 1
                Layout.fillWidth: true
                model: root.keysData ? root.keysData.keys : []
                textRole: "label"
                enabled: root.ready
                onActivated: root.selectKey(root.keysData.keys[currentIndex].slot, tabs.currentIndex === 2)
              }
              ColumnLayout {
                visible: tabs.currentIndex === 1
                Layout.fillWidth: true
                enabled: root.ready && root.caps.advanced === true && root.selectedKey !== null
                Label { text: "New assignment" }
                Choice { id: assignment; Layout.fillWidth: true; model: root.keysData ? root.keysData.choices : []; textRole: "label" }
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
                PanelSectionHeader { text: "Text macros"; Layout.fillWidth: true }
                Label { text: "Macro slots are shared across profiles. Text uses the US keyboard layout."; opacity: 0.7 }
                RowLayout {
                  Count { id: macroSlot; from: 1; to: 50; value: 1; onValueChanged: root.macroData = null }
                  Action { text: "Read macro"; onClicked: root.request({action: "macro", macro: macroSlot.value - 1}) }
                }
                TextField { id: macroText; Layout.fillWidth: true; placeholderText: "Text to type · up to 40 ASCII characters"; maximumLength: 40 }
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
                Action { text: "Read selected key"; visible: !root.switchData; enabled: root.ready && root.selectedKey !== null; onClicked: root.loadSwitches() }
                ColumnLayout {
                  visible: root.switchData !== null
                  enabled: root.ready
                  Layout.fillWidth: true
                  PanelSectionHeader { text: root.selectedKey ? "TRAVEL · " + root.selectedKey.label : "TRAVEL" }
                  Label { text: "Adjust this key, then apply. Labels on the keyboard show the last read actuation distance."; opacity: 0.6 }
                  TravelField { id: actuation; label: "Actuation"; Layout.fillWidth: true; step: root.switchData ? 1 / root.switchData.scale : 0.01 }
                  TravelField { id: releaseTravel; label: "Release point"; Layout.fillWidth: true; step: actuation.step }
                  PanelSeparator { Layout.fillWidth: true }
                  PanelSectionHeader { text: "RAPID TRIGGER" }
                  TravelField { id: rtPress; label: "Press sensitivity"; Layout.fillWidth: true; step: actuation.step }
                  TravelField { id: rtRelease; label: "Release sensitivity"; Layout.fillWidth: true; step: actuation.step }
                  TravelField { id: deadzone; label: "Bottom dead zone"; minimum: 0; maximum: 1; Layout.fillWidth: true; step: actuation.step }
                  Check { id: rt; text: "Rapid trigger" }
                  Label { text: "The firmware's distance scale is detected from its version. Other key-mode bits are preserved."; opacity: 0.6 }
                }
              }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 3
              Layout.fillWidth: true
              spacing: Commons.Style.spacing.lg
              Action { text: "Read device settings"; enabled: root.ready; onClicked: root.loadDevice() }
              ColumnLayout {
                visible: root.deviceData !== null
                Layout.fillWidth: true
                enabled: root.ready
                PanelSectionHeader { text: "Polling rate"; Layout.fillWidth: true }
                RowLayout {
                  Choice { id: rate; model: ["8000 Hz", "4000 Hz", "2000 Hz", "1000 Hz", "500 Hz", "250 Hz", "125 Hz"]; enabled: root.ready && root.deviceData && root.deviceData.reportRate !== undefined }
                  Action { text: "Save polling rate"; enabled: root.ready && root.deviceData && root.deviceData.reportRate !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "reportRate", expected: root.deviceData.reportRate, value: [8000,4000,2000,1000,500,250,125][rate.currentIndex]}) }
                }
                ColumnLayout {
                  visible: root.deviceData && root.deviceData.keyboardOptions !== undefined
                  Layout.fillWidth: true
                  Check { id: wasdSwap; text: "Swap WASD with arrow keys" }
                  Check { id: antiAccidental; text: "Prevent accidental triggers" }
                  Label { text: "Rapid trigger stabilization" }
                  Choice { id: stabilization; model: ["Off", "25", "50", "75", "100", "125"] }
                  Action { text: "Save keyboard options"; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "keyboardOptions", expected: root.deviceData.keyboardOptions, value: {wasdSwap: wasdSwap.checked, antiAccidental: antiAccidental.checked, stabilization: stabilization.currentIndex}}) }
                }
                PanelSectionHeader { text: "Sleep timers · seconds"; Layout.fillWidth: true }
                GridLayout {
                  visible: root.deviceData && root.deviceData.sleep !== undefined
                  columns: 2
                  Label { text: "Bluetooth sleep" }
                  Count { id: sleepBT; from: 0; to: 65535 }
                  Label { text: "2.4 GHz sleep" }
                  Count { id: sleepRF; from: 0; to: 65535 }
                  Label { text: "Bluetooth deep sleep" }
                  Count { id: deepBT; from: 0; to: 65535 }
                  Label { text: "2.4 GHz deep sleep" }
                  Count { id: deepRF; from: 0; to: 65535 }
                }
                Action { text: "Save sleep timers"; enabled: root.ready && root.deviceData && root.deviceData.sleep !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "sleep", expected: root.deviceData.sleep, value: [sleepBT.value,sleepRF.value,deepBT.value,deepRF.value]}) }
                Check { id: autoOS; text: "Detect host OS automatically"; enabled: root.ready && root.deviceData && root.deviceData.autoOS !== undefined }
                Action { text: "Save host detection"; enabled: root.ready && root.deviceData && root.deviceData.autoOS !== undefined; onClicked: root.request({action: "set-device", profile: root.state.profile, setting: "autoOS", value: autoOS.checked, expected: root.deviceData.autoOS}) }
                Label { text: root.deviceData && root.deviceData.warnings ? root.deviceData.warnings.join("\n") : ""; opacity: 0.6 }
              }
              PanelSectionHeader { text: "Display"; Layout.fillWidth: true }
              Action { text: "Set display clock to local time"; enabled: root.ready; onClicked: root.request({action: "clock"}) }
              RowLayout {
                Action { text: "Choose picture…"; enabled: root.ready; onClicked: picturePicker.open() }
                Choice { id: pictureSlot; model: ["Picture 1", "Picture 2", "Picture 3", "Picture 4", "Picture 5"]; enabled: root.ready }
                Action { text: "Upload picture"; enabled: root.ready && String(root.pictureFile).length > 0; onClicked: root.request({action: "display-image", slot: pictureSlot.currentIndex, path: decodeURIComponent(String(root.pictureFile).replace(/^file:\/\//,""))}) }
              }
              Image { source: root.pictureFile; visible: String(root.pictureFile).length > 0; Layout.preferredWidth: 160; Layout.preferredHeight: 80; fillMode: Image.PreserveAspectCrop }
              Label { text: "Uploads replace the chosen picture slot. Images are cropped to 160 × 80; animated files use their first frame."; opacity: 0.6 }
              PanelSectionHeader { text: "Backup"; Layout.fillWidth: true }
              Action { text: "Export current profile keymaps and settings"; enabled: root.ready; onClicked: { var data = root.context("export"); root.request(data) } }
              Label { text: "Backups: ~/.local/state/omarchy-keydous/backups"; opacity: 0.6 }
            }
            ColumnLayout {
              visible: tabs.currentIndex === 5
              Layout.fillWidth: true
              spacing: Commons.Style.spacing.md
              Label { text: "Per-key lighting · profile " + (root.state.profile + 1); font.bold: true }
              Label { text: "Load your local painting, then click or drag across keys. Right-drag erases. Apply saves to pattern slot 1, shared across onboard profiles." }
              RowLayout {
                Action { text: "Load painting"; enabled: root.ready && !root.paintDirty; onClicked: root.request({action: "paint", profile: root.state.profile}) }
                TextField { id: brush; text: "#ff6600"; placeholderText: "#RRGGBB"; maximumLength: 7; Layout.preferredWidth: 100 }
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
                Choice { id: paintView; model: root.paintData && root.paintData.layout.keys.length ? ["Keyboard view", "Hardware slots"] : ["Hardware slots"] }
                Label { text: root.paintData ? root.paintData.layout.name : "Load painting to detect layout" }
              }
              Label {
                visible: root.paintData !== null && root.paintData.layout.unresolved > 0
                text: root.paintData ? root.paintData.layout.unresolved + " positions unresolved. Use Hardware slots for remapped or ambiguous keys." : ""
                opacity: 0.7
              }
              KeyboardMap {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                Layout.maximumWidth: Commons.Style.space(660)
                Layout.alignment: Qt.AlignHCenter
                layout: root.paintData ? root.paintData.layout : null
                slots: root.paintData ? root.paintData.labels.map(function(label, slot) { return {slot: slot, label: label} }) : []
                colors: root.paintColors
                painting: true
                hardwareView: paintView.currentIndex === 1
                enabled: root.ready
                onPainted: function(slot, erase) { root.paintKey(slot, erase) }
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
              Level { id: paintBrightness; Layout.fillWidth: true; from: 0; to: 4; value: 4; stepSize: 1 }
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
              spacing: Commons.Style.spacing.lg
              Label { text: "Current firmware: " + (root.state.firmware || "not connected"); font.bold: true }
              Label { text: "Check the vendor's firmware catalogue for the detected keyboard." }
              RowLayout {
                Action { text: "Check updates"; enabled: root.ready; onClicked: root.request({action: "firmware-check"}) }
                Action { text: "Download package"; enabled: root.ready && root.firmwareData && !!root.firmwareData.downloadPath; onClicked: root.request({action: "firmware-download"}) }
              }
              Label { text: root.firmwareData ? "Vendor version: " + root.firmwareData.version : "No update check yet"; opacity: 0.8 }
              Label { text: "The vendor update bridge below lets the official updater use Linux HID. Native package downloads do not flash the keyboard. The update bridge is not yet tested on your hardware." }
              PanelSectionHeader { text: "Linux IoT compatibility service · experimental"; Layout.fillWidth: true }
              Label { text: root.compatMessage; opacity: 0.8 }
              RowLayout {
                Action {
                  text: compat.running ? "Stop compatibility service" : "Start compatibility service"
                  enabled: !root.busy
                  onClicked: {
                    if (compat.running) compat.signal(15)
                    else root.startBridge(false)
                  }
                }
              }
              Label { text: "Native controls pause while the service owns the keyboard. Stop the service when finished. Audio and screen-capture services are not ported."; opacity: 0.7 }
              Action {
                text: "Start vendor firmware update bridge"
                enabled: !root.busy && !compat.running && !root.bridgePending && root.state.connected === true
                onClicked: root.startBridge(true)
              }
              Action {
                text: "Open official updater in Chromium"
                enabled: root.compatibilityReady && root.firmwareBridge
                onClicked: Quickshell.execDetached(["chromium", "--new-window", "https://qmk.top"])
              }
              Label { text: "Use a USB cable. The update bridge follows the verified keyboard through boot mode on the same USB port; the official site selects and sends its firmware. Keep it connected until the vendor reports completion."; opacity: 0.7 }
            }
          }
        }
        PanelSeparator { Layout.fillWidth: true }
        RowLayout {
          Label { text: root.message; font.pixelSize: Commons.Style.font.caption; opacity: 0.65; maximumLineCount: 2; elide: Text.ElideRight }
                  Action {
                    visible: tabs.currentIndex === 2 && root.switchData !== null
                    text: "Apply to key"
                    selected: true
                    enabled: root.ready && root.switchData !== null && root.selectedKey !== null && root.switchData.slot === root.selectedKey.slot && actuation.acceptable && releaseTravel.acceptable && rtPress.acceptable && rtRelease.acceptable && deadzone.acceptable
                    onClicked: root.request({action: "set-switches", profile: root.state.profile, slot: root.switchData.slot,
                      expected: root.switchData.raw, values: {actuation: Number(actuation.text), release: Number(releaseTravel.text),
                      pressStep: Number(rtPress.text), releaseStep: Number(rtRelease.text), deadzone: Number(deadzone.text), keyMode: rt.checked}})
                  }
          Action { text: "Close"; bordered: false; onClicked: root.close() }
        }
      }
    }
  }
}
