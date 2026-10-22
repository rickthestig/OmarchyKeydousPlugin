#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated Quickshell lifecycle regression check; no desktop IPC or HID access.

Uses installed native Omarchy UI components. Only the Wayland popup host is
replaced with an Item so this runs offscreen. Python helpers are replaced with
mock processes in a temporary plugin copy. Does not validate layer-shell itself.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
HOST = '''import QtQuick
Item {
  property Item anchorItem
  property QtObject bar
  property var owner
  property bool open: false
  property Item focusTarget
  property int contentWidth: 760
  property int contentHeight: 800
  width: contentWidth; height: contentHeight
  function fittedContentWidth(value) { return value }
  function fittedContentHeight(value) { return value }
}
'''
MOCK = '''import json, os, time
print(json.dumps({'pid': os.getpid()}), flush=True)
time.sleep(0.4)
print(json.dumps({'ok': False, 'connected': False, 'error': 'Mock helper response'}), flush=True)
'''
# The stdout has one valid settings JSON response, while the bridge uses lines.
WORKER = '''import json, time
time.sleep(0.4)
print(json.dumps({'ok': False, 'connected': False, 'error': 'Mock helper response'}), flush=True)
'''
QML = '''import QtQuick
import Quickshell
import "Plugin" as Plugin
ShellRoot {
  id: test
  property var panel: null
  property int iteration: 0
  property int phase: 0
  property var helperPids: []
  property int selected: -1
  property int painted: -1
  property bool erased: false
  Item { id: holder; width: 800; height: 840 }
  Component { id: factory; Plugin.Panel { manageIpc: false } }
  Plugin.KeyboardMap {
    id: keyboard
    width: 660
    layout: ({width:16, height:6.4, keys:[{slot:7,x:1.75,y:3.4,w:1,h:1,label:"A",assignment:"A"}]})
    slots: [{slot:7,label:"007 · A"}]
    colors: Array(126).fill("#123456")
    onChosen: function(slot) { test.selected = slot }
    onPainted: function(slot, erase) { test.painted = slot; test.erased = erase }
  }
  function require(condition, message) { if (!condition) { console.error(message); Qt.exit(1); throw new Error(message) } }
  function namedData(item, name) {
    for (var i = 0; i < item.data.length; i++) if (item.data[i].objectName === name) return item.data[i]
    return null
  }
  Component.onCompleted: {
    var pointer = namedData(keyboard, "keydousKeyPointer")
    var mouse = {x: 2.25 * keyboard.unit, y: 3.9 * keyboard.rowHeight, buttons: Qt.LeftButton}
    pointer.hit(mouse, true)
    require(selected === 7, "Physical key hit selected the wrong slot")
    keyboard.painting = true; pointer.lastSlot = -1; mouse.buttons = Qt.RightButton
    pointer.hit(mouse, true)
    require(painted === 7 && erased, "Erase hit selected the wrong slot")
    painted = -1
    keyboard.layout = {width:16, height:6.4, keys:[{slot:127,x:1.75,y:3.4,w:1,h:1,label:"Unmapped",assignment:"Unmapped"}]}
    pointer.lastSlot = -1
    pointer.hit(mouse, true)
    require(painted === -1, "Out-of-range paint slot was accepted")
    keyboard.visible = false
  }
  Timer {
    interval: 60
    running: true
    repeat: true
    onTriggered: {
      if (test.phase === 0) {
        test.panel = factory.createObject(holder)
        test.require(test.panel !== null, "Panel failed to instantiate")
        test.require(!test.panel.busy, "Panel started a helper before being opened")
        var worker = test.namedData(test.panel, "keydousWorker")
        var compat = test.namedData(test.panel, "keydousCompat")
        test.require(!worker.running && !compat.running, "Idle panel started a background process")
        if (test.iteration % 3 === 0) test.panel.run(["status"])
        else if (test.iteration % 3 === 1) test.panel.request({action:"keys",profile:0})
        else test.panel.startBridge(false)
        var before = worker.command.join(" ")
        test.panel.request({action:"must-not-run"})
        test.panel.run(["must-not-run"])
        test.require(worker.command.join(" ") === before, "A busy helper accepted another request")
        test.phase = 1
      } else {
        var helper = test.namedData(test.panel, test.iteration % 3 === 2 ? "keydousCompat" : "keydousWorker")
        if (test.iteration % 4 === 0 && test.iteration % 3 !== 2) {
          if (helper.running) return
          test.require(test.panel.message === "Mock helper response", "Completed helper response was lost")
        }
        if (helper.processId) test.helperPids.push(Number(helper.processId))
        test.panel.destroy()
        test.panel = null
        test.iteration++
        test.phase = 0
        if (test.iteration >= CYCLES) {
          stop()
          finish.start()
        }
      }
    }
  }
  Timer {
    id: finish
    interval: 700
    onTriggered: {
      console.log("KEYDOUS_LIFECYCLE_PASS " + JSON.stringify({cycles:test.iteration, pids:test.helperPids}))
      Qt.quit()
    }
  }
}
'''


def run(shell_root, cycles):
    qs = shutil.which('qs')
    if not qs:
        raise ValueError('Quickshell (qs) is required')
    if not (shell_root/'Ui/KeyboardPanel.qml').is_file():
        raise ValueError('Native Omarchy shell UI was not found; set --shell-root')
    with tempfile.TemporaryDirectory(prefix='keydous-lifecycle-') as folder:
        sandbox = Path(folder)
        runtime = sandbox/'runtime'
        runtime.mkdir(mode=0o700)
        shutil.copytree(shell_root/'Ui', sandbox/'Ui')
        shutil.copytree(shell_root/'Commons', sandbox/'Commons')
        (sandbox/'Ui/KeyboardPanel.qml').write_text(HOST)
        plugin = sandbox/'Plugin'
        plugin.mkdir()
        for name in ('Panel.qml', 'KeyboardMap.qml', 'TravelField.qml'):
            shutil.copy2(ROOT/name, plugin/name)
        for name in ('bridge.py', 'native.py'):
            (plugin/name).write_text(WORKER)
        (plugin/'iot_linux.py').write_text(MOCK)
        (sandbox/'shell.qml').write_text(QML.replace('CYCLES', str(cycles)))
        env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM='offscreen',
                   QT_QPA_PLATFORMTHEME='basic', QT_QUICK_CONTROLS_STYLE='Basic',
                   QS_DISABLE_FILE_WATCHER='1', QS_NO_RELOAD_POPUP='1')
        for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS'):
            env.pop(key, None)
        result = subprocess.run([qs, '-p', str(sandbox/'shell.qml')], env=env,
                                capture_output=True, text=True, timeout=max(20, cycles))
        output = result.stdout + result.stderr
        match = re.search(r'KEYDOUS_LIFECYCLE_PASS (\{[^\n]+\})', output)
        if result.returncode or not match or re.search(
                r'TypeError|ReferenceError|Failed to load configuration|Cannot assign|Error:|binding loop', output, re.I):
            raise RuntimeError('Quickshell lifecycle check failed:\n' + output[-8000:])
        report = json.loads(match[1])
        lingering = []
        for pid in set(report['pids']):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            lingering.append(pid)
        if lingering:
            raise RuntimeError(f'Helpers survived plugin destruction: {lingering}')
        print(f"Passed {report['cycles']} create/run/destroy cycles; helpers exited; keyboard hit checks passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell-root', type=Path, default=Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))/'shell')
    parser.add_argument('--cycles', type=int, default=60)
    args = parser.parse_args()
    if not 3 <= args.cycles <= 120:
        parser.error('--cycles must be in 3..120')
    run(args.shell_root, args.cycles)


if __name__ == '__main__':
    main()
