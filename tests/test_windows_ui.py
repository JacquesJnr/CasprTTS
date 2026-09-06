"""Offscreen interaction coverage; no Windows/audio dependencies or user data writes."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from quick_tts_mic.windows_ui import Controller
from quick_tts_mic.windows_runtime import WindowsConfig
from quick_tts_mic.windows_audio import Endpoint


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def controller(app, monkeypatch, tmp_path):
    monkeypatch.setattr(WindowsConfig, 'save', lambda self: None)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    result = Controller(app, WindowsConfig(), start_services=False)
    yield result
    result.close()
    result.settings.deleteLater()
    result.overlay.deleteLater()
    app.processEvents()


def inventory():
    return {'devices': [Endpoint('msg', 'Cable Input', 2), Endpoint('preview', 'Headphones', 2)],
            'voices': [dict(id='james', name='James (fixture)', language='en-GB')]}


def test_settings_and_overlay_render(controller, app):
    controller.settings.show()
    controller.overlay.open()
    app.processEvents()
    assert not controller.settings.grab().isNull()
    assert not controller.overlay.grab().isNull()


def test_voice_switches_keep_other_selection(controller):
    controller.config.model_path = 'saved-model.onnx'
    controller.config.microsoft_voice_id = 'missing-voice'
    controller.on_discovered(inventory())
    assert controller.settings.microsoft.currentData() == 'missing-voice'
    assert 'unavailable' in controller.settings.microsoft.currentText()
    controller.settings.provider.setCurrentIndex(1)
    controller.settings.microsoft.setCurrentIndex(1)
    assert controller.config.microsoft_voice_id == 'james'
    assert controller.config.model_path == 'saved-model.onnx'
    controller.settings.provider.setCurrentIndex(0)
    assert controller.config.microsoft_voice_id == 'james'
    assert controller.config.speech_provider == 'piper'


def test_preview_verification_resets_on_device_or_selection_change(controller):
    controller.config.message_endpoint_id = 'msg'
    controller.config.preview_endpoint_id = 'preview'
    controller.on_discovered(inventory())
    assert not controller.settings.sample.isEnabled()
    controller.settings.verified.setChecked(True)
    assert controller.settings.sample.isEnabled()
    changed = inventory()
    changed['devices'].append(Endpoint('usb', 'USB', 2))
    controller.on_discovered(changed)
    assert not controller.settings.sample.isEnabled()
    assert not controller.settings.verified.isChecked()
    controller.settings.verified.setChecked(True)
    controller.update('message_endpoint_id', 'preview')
    assert not controller.settings.sample.isEnabled()


def test_enter_escape_history_and_no_disk_history(controller):
    submitted = []
    controller.worker = SimpleNamespace(submit=lambda *args, **kwargs: submitted.append((args, kwargs)), stop=lambda: None)
    overlay = controller.overlay
    overlay.open()
    overlay.entry.setText('Hello')
    QTest.keyClick(overlay.entry, Qt.Key.Key_Return)
    assert submitted[0][0][0] == 'Hello'
    assert overlay.history.items == ('Hello',)
    assert not overlay.isVisible() and not overlay.entry.text()
    overlay.open()
    QTest.keyClick(overlay.entry, Qt.Key.Key_Up)
    assert overlay.entry.text() == 'Hello'
    QTest.keyClick(overlay.entry, Qt.Key.Key_Escape)
    assert not overlay.entry.text() and not overlay.isVisible()
    assert len(submitted) == 1
