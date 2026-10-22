import QtQuick
import QtQuick.Layouts
import qs.Ui
import qs.Commons as Commons

RowLayout {
  id: root
  property string label: ""
  property alias text: input.text
  property real minimum: 0.1
  property real maximum: 3.3
  property real step: 0.01
  readonly property bool acceptable: input.acceptableInput && isFinite(Number(text)) && Number(text) >= minimum && Number(text) <= maximum
  spacing: Commons.Style.spacing.md
  Text {
    text: root.label; color: Commons.Color.foreground
    font.family: Commons.Style.font.family; font.pixelSize: Commons.Style.font.body
    Layout.preferredWidth: Commons.Style.space(175)
  }
  PanelSlider {
    Layout.fillWidth: true
    minimum: root.minimum; maximum: root.maximum; step: root.step
    value: isFinite(Number(root.text)) ? Number(root.text) : root.minimum
    fillColor: Commons.Color.accent
    trackColor: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.15)
    onMoved: function(value) { root.text = (Math.round(value / root.step) * root.step).toFixed(3) }
  }
  TextField {
    id: input
    Layout.preferredWidth: Commons.Style.space(85)
    inputMethodHints: Qt.ImhFormattedNumbersOnly
    horizontalAlignment: TextInput.AlignRight
    validator: DoubleValidator { bottom: root.minimum; top: root.maximum; decimals: 3; locale: "C"; notation: DoubleValidator.StandardNotation }
  }
  Text { text: "mm"; color: Commons.Color.foreground; opacity: 0.5; font.family: Commons.Style.font.family; font.pixelSize: Commons.Style.font.caption }
}
