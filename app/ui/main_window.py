import logging
import math
import os
from functools import partial

import numpy as np
import pyvista as pv
from PyQt5 import QtCore, QtGui, QtWidgets
from pyvistaqt import QtInteractor

from app.services import (
    MeshOperationError,
    create_custom_colormap as build_colormap,
    load_mesh,
    save_colored_mesh,
    save_mesh,
)
from app.ui.workers import DistanceComputationWorker

logger = logging.getLogger(__name__)

_CREATE_LIGHTS = (
    {"position": (0, 7, 14), "intensity": 0.26},
    {"position": (0, -7, -14), "intensity": 0.18},
    {"position": (9, 0, 10), "intensity": 0.24},
    {"position": (-9, 0, -10), "intensity": 0.2},
    {"position": (6, 6, 12), "intensity": 0.18},
    {"position": (-6, -6, -12), "intensity": 0.16},
)

_COMPARE_LIGHTS = (
    {"position": (0, 8, 16), "intensity": 0.24},
    {"position": (0, -8, -16), "intensity": 0.18},
    {"position": (10, 0, 12), "intensity": 0.22},
    {"position": (-10, 0, -12), "intensity": 0.2},
    {"position": (7, 7, 14), "intensity": 0.18},
    {"position": (-7, -7, -14), "intensity": 0.16},
)



class _DummyCamera:
    def Zoom(self, factor):
        pass


class _DummyProperty:
    def __init__(self):
        self.opacity = 1.0

    def SetOpacity(self, opacity):
        self.opacity = opacity


class _DummyActor:
    def __init__(self):
        self.visible = True
        self._property = _DummyProperty()

    def SetVisibility(self, visible):
        self.visible = visible

    def GetProperty(self):
        return self._property


class HeadlessPlotter:
    def __init__(self, parent=None):
        self.interactor = QtWidgets.QLabel("Headless Plotter", parent)
        self.interactor.setAlignment(QtCore.Qt.AlignCenter)
        self.actors = {}
        self.camera = _DummyCamera()

    def add_axes(self):
        pass

    def add_text(self, text, **kwargs):
        self.interactor.setText(text)

    def add_mesh(self, mesh, name=None, **kwargs):
        actor_name = name or kwargs.get('name')
        if actor_name:
            self.actors[actor_name] = _DummyActor()

    def remove_actor(self, name, render=True):
        self.actors.pop(name, None)

    def remove_scalar_bar(self):
        pass

    def reset_camera(self):
        pass

    def screenshot(self, **kwargs):
        import numpy as np
        return np.zeros((120, 160, 3), dtype=np.uint8)

    def clear(self):
        self.actors.clear()
        self.interactor.setText("Headless Plotter")

    def render(self):
        pass

    def link_views(self, *args, **kwargs):
        pass
class _ViewportEventFilter(QtCore.QObject):
    def __init__(self, plotter):
        super().__init__()
        self._plotters = [plotter]
        self._dragging = False
        self._drag_mode = None
        self._last_pos = None

    def set_linked_plotters(self, plotters):
        if plotters:
            self._plotters = list(plotters)

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.LeftButton:
                self._dragging = True
                self._drag_mode = 'orbit'
                self._last_pos = event.pos()
                return True
            if event.button() == QtCore.Qt.RightButton:
                self._dragging = True
                self._drag_mode = 'pan'
                self._last_pos = event.pos()
                return True
        if etype == QtCore.QEvent.MouseMove:
            if self._dragging:
                current = event.pos()
                if self._last_pos is not None:
                    dx = current.x() - self._last_pos.x()
                    dy = current.y() - self._last_pos.y()
                    if dx or dy:
                        if self._drag_mode == 'orbit':
                            self._apply_orbit(dx, dy)
                        elif self._drag_mode == 'pan':
                            self._apply_pan(dx, dy)
                self._last_pos = current
            return True
        if etype == QtCore.QEvent.MouseButtonRelease:
            if event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
                self._dragging = False
                self._drag_mode = None
                self._last_pos = None
                return True
        if etype == QtCore.QEvent.Wheel:
            delta = event.angleDelta().y()
            if delta != 0:
                step = max(abs(delta) / 240.0, 0.1)
                factor = 1.0 + step
                if delta > 0:
                    self._apply_zoom(factor)
                else:
                    self._apply_zoom(1.0 / factor)
                return True
        return False

    def _apply_zoom(self, factor):
        if not self._plotters:
            return
        if not isinstance(factor, (int, float)):
            return
        if not math.isfinite(factor) or factor <= 0:
            return
        max_step = 1.4
        min_step = 1.0 / max_step
        if factor > 1.0:
            factor = min(factor, max_step)
        else:
            factor = max(factor, min_step)
        primary = self._plotters[0]
        camera = getattr(primary, 'camera', None)
        renderer = getattr(primary, 'renderer', None)
        if camera is None or renderer is None:
            return
        try:
            camera.Dolly(factor)
            renderer.ResetCameraClippingRange()
            primary.render()
        except Exception:
            return
        for plotter in self._plotters[1:]:
            try:
                plotter.renderer.ResetCameraClippingRange()
                plotter.render()
            except Exception:
                pass

    def _apply_orbit(self, dx, dy):
        if not self._plotters or (dx == 0 and dy == 0):
            return
        primary = self._plotters[0]
        camera = getattr(primary, 'camera', None)
        renderer = getattr(primary, 'renderer', None)
        if camera is None or renderer is None:
            return
        azimuth = -dx * 0.4
        elevation = dy * 0.4
        try:
            camera.Azimuth(azimuth)
            camera.Elevation(elevation)
            camera.OrthogonalizeViewUp()
            renderer.ResetCameraClippingRange()
            primary.render()
        except Exception:
            return
        for plotter in self._plotters[1:]:
            try:
                plotter.renderer.ResetCameraClippingRange()
                plotter.render()
            except Exception:
                pass

    def _apply_pan(self, dx, dy):
        if not self._plotters or (dx == 0 and dy == 0):
            return
        primary = self._plotters[0]
        camera = getattr(primary, 'camera', None)
        renderer = getattr(primary, 'renderer', None)
        if camera is None or renderer is None:
            return
        try:
            focal = np.array(camera.focal_point)
            position = np.array(camera.position)
            direction = np.array(camera.direction)
            if np.linalg.norm(direction) == 0:
                return
            direction = direction / np.linalg.norm(direction)
            up = np.array(camera.up)
            if np.linalg.norm(up) == 0:
                return
            up = up / np.linalg.norm(up)
            right = np.cross(direction, up)
            if np.linalg.norm(right) == 0:
                return
            right = right / np.linalg.norm(right)
            distance = np.linalg.norm(position - focal)
            gain = distance * 0.002
            translation = (-dx * gain) * right + (dy * gain) * up
            new_focal = focal + translation
            new_position = position + translation
            camera.focal_point = new_focal.tolist()
            camera.position = new_position.tolist()
            renderer.ResetCameraClippingRange()
            primary.render()
        except Exception:
            return
        for plotter in self._plotters[1:]:
            try:
                plotter.renderer.ResetCameraClippingRange()
                plotter.render()
            except Exception:
                pass

class JointSpaceVisualizerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JointSpaceVisualizer ver.2")
        self.setGeometry(100, 100, 1200, 800)

        # セッション（タブ）ごとの状態を保持（作成タブ内）
        self.sessions = []  # list of dicts: { 'plotter': QtInteractor, 'models': {} }
        self._distance_thread = None
        self._distance_worker = None
        self._is_busy = False
        self._event_filters = []
        self._plotter_brightness = {}
        self._plotter_is_compare = {}
        self._pending_cancel = False
        self._log_path = self._resolve_log_path()
        self._cancel_watchdog = None
        self.headless_mode = bool(os.environ.get("JSV_HEADLESS"))
        self.setup_ui()
        self.connect_signals()
        self._update_disclaimer_state()
        self.main_tabs.currentChanged.connect(self._on_tab_change)
        logger.info("JointSpaceVisualizerApp initialized")

    def setup_ui(self):
        self.status_bar = self.statusBar()
        # --- 上位タブ（作成 / 比較） ---
        self.main_tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.main_tabs)

        # 重要タブ
        self.disclaimer_root = QtWidgets.QWidget()
        disclaimer_layout = QtWidgets.QVBoxLayout(self.disclaimer_root)
        disclaimer_layout.setContentsMargins(16, 16, 16, 16)
        disclaimer_layout.setSpacing(12)

        disclaimer_text = QtWidgets.QTextBrowser()
        disclaimer_text.setReadOnly(True)
        disclaimer_text.setStyleSheet("font-size: 13px;")
        disclaimer_text.setPlainText(
            "重要：本ソフトウェアの利用制限について\n\n"
            "この度は、本ソフトウェアをご利用いただき、誠にありがとうございます。" \
            "ご利用を開始される前に、以下の重要な事項を必ずお読みください。\n\n"
            "医療機器としての未承認\n"
            "本ソフトウェアは、薬機法（医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律）"
            "に定められる医療機器ではなく、いかなる診断、治療、予防を目的とした使用も想定しておりません。"
            "また、関連する規制当局からの承認・認証等も一切受けておりません。\n\n"
            "研究用途への限定\n"
            "本ソフトウェアの機能は、すべて研究用途での利用に限定されます。本ソフトウェアから出力される"
            "いかなる情報も、臨床現場における診断や治療方針の決定など、医学的判断の根拠として使用することは"
            "固く禁じます。\n\n"
            "免責事項\n"
            "利用者が本ソフトウェアを使用したこと、あるいは使用できなかったことによって生じる一切の"
            "直接的・間接的損害（データの損失、業務の中断、健康上の問題等を含む）に対し、当方は何らの保証も"
            "行わず、一切の責任を負いません。"
        )
        disclaimer_layout.addWidget(disclaimer_text)

        self.disclaimer_checkbox = QtWidgets.QCheckBox("この内容に同意します。")
        disclaimer_layout.addWidget(self.disclaimer_checkbox)
        disclaimer_layout.addStretch(1)

        self.main_tabs.addTab(self.disclaimer_root, "重要事項")

        # 作成タブ
        self.create_root = QtWidgets.QWidget()
        create_layout = QtWidgets.QHBoxLayout(self.create_root)
        self.main_tabs.addTab(self.create_root, "作成")

        # 比較タブ
        self.compare_root = QtWidgets.QWidget()
        compare_layout = QtWidgets.QHBoxLayout(self.compare_root)
        self.main_tabs.addTab(self.compare_root, "比較")

        # デバッグタブ
        self.debug_root = QtWidgets.QWidget()
        debug_layout = QtWidgets.QVBoxLayout(self.debug_root)
        debug_layout.setContentsMargins(12, 12, 12, 12)
        debug_layout.setSpacing(8)

        debug_header = QtWidgets.QLabel("デバッグログコンソール")
        debug_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        debug_layout.addWidget(debug_header)

        log_hint = QtWidgets.QLabel("最新のアプリケーションログを表示します。必要に応じて更新してください。")
        log_hint.setStyleSheet("color: #555; font-size: 11px;")
        log_hint.setWordWrap(True)
        debug_layout.addWidget(log_hint)

        controls_row = QtWidgets.QHBoxLayout()
        self.debug_refresh_button = QtWidgets.QPushButton("ログを更新")
        self.debug_clear_button = QtWidgets.QPushButton("クリア")
        controls_row.addWidget(self.debug_refresh_button)
        controls_row.addWidget(self.debug_clear_button)
        controls_row.addStretch(1)
        debug_layout.addLayout(controls_row)

        self.debug_console = QtWidgets.QPlainTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.debug_console.setStyleSheet("font-family: Menlo, Consolas, monospace; font-size: 12px;")
        debug_layout.addWidget(self.debug_console, 1)

        self.debug_status_label = QtWidgets.QLabel()
        self.debug_status_label.setStyleSheet("color: #777; font-size: 11px;")
        debug_layout.addWidget(self.debug_status_label)

        self.main_tabs.addTab(self.debug_root, "デバッグ")

        # === 作成タブのUI ===
        # 左パネル（コントロール）
        self.control_panel = QtWidgets.QGroupBox("Controls")
        self.control_panel.setFixedWidth(350)
        self.control_layout = QtWidgets.QVBoxLayout(self.control_panel)
        create_layout.addWidget(self.control_panel)

        # 右ビュー（単一ビュー + セッションタブ）
        self.view_container = QtWidgets.QWidget()
        self.view_layout = QtWidgets.QVBoxLayout(self.view_container)
        create_layout.addWidget(self.view_container)

        # セッションタブ（各タブが独立したビュー = 過去状態の比較用）
        self.session_tabs = QtWidgets.QTabWidget()
        self.session_tabs.setTabsClosable(True)
        self.view_layout.addWidget(self.session_tabs)

        # 初期セッションはUI要素（コンボ等）作成後に追加する

        # --- UIコントロールの構築 ---
        # Inputs Group
        inputs_group = QtWidgets.QGroupBox("Inputs")
        inputs_layout = QtWidgets.QFormLayout(inputs_group)
        self.target_combo = QtWidgets.QComboBox()
        self.target_load_button = QtWidgets.QPushButton("Load...")
        target_layout = QtWidgets.QHBoxLayout()
        target_layout.addWidget(self.target_combo)
        target_layout.addWidget(self.target_load_button)
        inputs_layout.addRow("上顎骨モデル:", target_layout)
        self.source_combo = QtWidgets.QComboBox()
        self.source_load_button = QtWidgets.QPushButton("Load...")
        source_layout = QtWidgets.QHBoxLayout()
        source_layout.addWidget(self.source_combo)
        source_layout.addWidget(self.source_load_button)
        inputs_layout.addRow("下顎骨モデル:", source_layout)
        self.control_layout.addWidget(inputs_group)

        # Apply Button
        apply_row = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setStyleSheet("font-weight: bold; padding: 5px;")
        self.cancel_button = QtWidgets.QPushButton("中止")
        self.cancel_button.setEnabled(False)
        apply_row.addWidget(self.apply_button)
        apply_row.addWidget(self.cancel_button)
        apply_row.addStretch(1)
        self.control_layout.addLayout(apply_row)
        apply_note = QtWidgets.QLabel("処理には時間がかかります。処理時間はPCのスペックに依存します。")
        apply_note.setWordWrap(True)
        apply_note.setStyleSheet("color: #555; font-size: 11px;")
        self.control_layout.addWidget(apply_note)

        # Decimation Group
        self.decimation_group = QtWidgets.QGroupBox("Decimation Options")
        self.decimation_group.setCheckable(True)
        self.decimation_group.setChecked(False)
        decimation_layout = QtWidgets.QFormLayout(self.decimation_group)
        self.decimation_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.decimation_slider.setRange(0, 99)
        self.decimation_slider.setValue(90)
        decimation_layout.addRow("Target Reduction (%):", self.decimation_slider)
        decimation_note = QtWidgets.QLabel("値（％）を下げるほど頂点数が減り、荒くなりますが処理時間は短くなる傾向があります。")
        decimation_note.setWordWrap(True)
        decimation_note.setStyleSheet("color: #555; font-size: 11px;")
        decimation_layout.addRow(decimation_note)
        self.control_layout.addWidget(self.decimation_group)

        # Display Group
        display_group = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QFormLayout(display_group)
        self.min_distance_label = QtWidgets.QLabel("-")
        display_layout.addRow("Min Distance (mm):", self.min_distance_label)
        # Result controls
        self.result_visibility_checkbox = QtWidgets.QCheckBox("Show")
        self.result_visibility_checkbox.setChecked(True)
        self.result_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.result_opacity_slider.setRange(0, 100)
        self.result_opacity_slider.setValue(100)
        self.save_result_button = QtWidgets.QPushButton("Save Result...")
        self.save_colored_result_button = QtWidgets.QPushButton("Save Colored...")
        result_controls_layout = QtWidgets.QHBoxLayout()
        result_controls_layout.addWidget(self.result_visibility_checkbox)
        result_controls_layout.addWidget(self.result_opacity_slider)
        display_layout.addRow("Result:", result_controls_layout)
        display_layout.addRow(self.save_result_button)
        display_layout.addRow(self.save_colored_result_button)
        # Target controls
        self.target_visibility_checkbox = QtWidgets.QCheckBox("Show")
        self.target_visibility_checkbox.setChecked(True)
        self.target_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.target_opacity_slider.setRange(0, 100)
        self.target_opacity_slider.setValue(100)
        target_controls_layout = QtWidgets.QHBoxLayout()
        target_controls_layout.addWidget(self.target_visibility_checkbox)
        target_controls_layout.addWidget(self.target_opacity_slider)
        display_layout.addRow("上顎骨:", target_controls_layout)
        # Source controls
        self.source_visibility_checkbox = QtWidgets.QCheckBox("Show")
        self.source_visibility_checkbox.setChecked(True)
        self.source_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.source_opacity_slider.setRange(0, 100)
        self.source_opacity_slider.setValue(40)
        source_controls_layout = QtWidgets.QHBoxLayout()
        source_controls_layout.addWidget(self.source_visibility_checkbox)
        source_controls_layout.addWidget(self.source_opacity_slider)
        display_layout.addRow("下顎骨:", source_controls_layout)
        self.control_layout.addWidget(display_group)

        # Snapshot/Session Group（作成タブ内）
        snapshot_group = QtWidgets.QGroupBox("Snapshot / Compare")
        snapshot_layout = QtWidgets.QVBoxLayout(snapshot_group)
        self.save_screenshot_button = QtWidgets.QPushButton("Save Screenshot (Current View)...")
        snapshot_layout.addWidget(self.save_screenshot_button)
        self.new_snapshot_button = QtWidgets.QPushButton("New Snapshot Tab")
        snapshot_layout.addWidget(self.new_snapshot_button)
        self.control_layout.addWidget(snapshot_group)

        view_group = QtWidgets.QGroupBox("View Controls")
        view_layout = QtWidgets.QHBoxLayout(view_group)
        self.zoom_in_button = QtWidgets.QPushButton("Zoom In")
        self.zoom_out_button = QtWidgets.QPushButton("Zoom Out")
        self.zoom_reset_button = QtWidgets.QPushButton("Reset")
        view_layout.addWidget(self.zoom_in_button)
        view_layout.addWidget(self.zoom_out_button)
        view_layout.addWidget(self.zoom_reset_button)
        self.control_layout.addWidget(view_group)

        # Compare Controls は比較タブ内に配置するため、ここでは作成しない

        # === 比較タブのUI（コントロール + 2画面ビュー） ===
        # 左：コントロールパネル
        self.compare_panel = QtWidgets.QGroupBox("Compare Controls")
        self.compare_panel.setFixedWidth(350)
        self.compare_layout_panel = QtWidgets.QVBoxLayout(self.compare_panel)
        compare_layout.addWidget(self.compare_panel)

        # ビューリンクの切り替え
        link_row = QtWidgets.QHBoxLayout()
        self.link_views_checkbox = QtWidgets.QCheckBox("リンクビュー")
        self.link_views_checkbox.setChecked(True)
        self.link_views_checkbox.stateChanged.connect(lambda *_: self._link_compare_views())
        link_row.addWidget(self.link_views_checkbox)
        link_row.addStretch(1)
        self.compare_layout_panel.addLayout(link_row)

        # セッション選択（左/右）
        # ファイルから読み込み（左/右）
        self.left_load_button = QtWidgets.QPushButton("Load Left From File...")
        self.right_load_button = QtWidgets.QPushButton("Load Right From File...")
        self.compare_layout_panel.addWidget(self.left_load_button)
        self.compare_layout_panel.addWidget(self.right_load_button)
        # クリアボタン（左右）
        self.clear_left_button = QtWidgets.QPushButton("Clear Left")
        self.clear_right_button = QtWidgets.QPushButton("Clear Right")
        self.compare_layout_panel.addWidget(self.clear_left_button)
        self.compare_layout_panel.addWidget(self.clear_right_button)
        # スクリーンショット
        self.compare_screenshot_button = QtWidgets.QPushButton("Save Compare Screenshot...")
        self.compare_layout_panel.addWidget(self.compare_screenshot_button)

        zoom_row = QtWidgets.QHBoxLayout()
        self.compare_zoom_in_button = QtWidgets.QPushButton("Zoom In")
        self.compare_zoom_out_button = QtWidgets.QPushButton("Zoom Out")
        self.compare_zoom_reset_button = QtWidgets.QPushButton("Reset")
        zoom_row.addWidget(self.compare_zoom_in_button)
        zoom_row.addWidget(self.compare_zoom_out_button)
        zoom_row.addWidget(self.compare_zoom_reset_button)
        self.compare_layout_panel.addLayout(zoom_row)

        # 右：2画面ビュー
        self.compare_view_container = QtWidgets.QWidget()
        self.compare_view_layout = QtWidgets.QHBoxLayout(self.compare_view_container)
        compare_layout.addWidget(self.compare_view_container)

        self.compare_plotter_left = self.create_plotter(self.compare_view_container, for_compare=True)
        self.compare_left_panel = QtWidgets.QWidget()
        self.compare_left_layout = QtWidgets.QVBoxLayout(self.compare_left_panel)
        self.compare_left_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_left_layout.setSpacing(6)
        self.compare_left_layout.addWidget(self.compare_plotter_left.interactor)
        self._add_brightness_control(self.compare_left_layout, self.compare_plotter_left)
        self.compare_left_layout.addWidget(self._create_color_scale_widget())
        self.compare_view_layout.addWidget(self.compare_left_panel)
        self.compare_plotter_left.add_axes()
        self.compare_plotter_left.add_text("Left", position='upper_left', font_size=12)

        self.compare_plotter_right = self.create_plotter(self.compare_view_container, for_compare=True)
        self.compare_right_panel = QtWidgets.QWidget()
        self.compare_right_layout = QtWidgets.QVBoxLayout(self.compare_right_panel)
        self.compare_right_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_right_layout.setSpacing(6)
        self.compare_right_layout.addWidget(self.compare_plotter_right.interactor)
        self._add_brightness_control(self.compare_right_layout, self.compare_plotter_right)
        self.compare_right_layout.addWidget(self._create_color_scale_widget())
        self.compare_view_layout.addWidget(self.compare_right_panel)
        self.compare_plotter_right.add_axes()
        self.compare_plotter_right.add_text("Right", position='upper_left', font_size=12)

        # カメラ連動
        self._link_compare_views()

        self.control_layout.addStretch(1)

        # ここで初期セッションを追加（コンボボックスが準備できた後）
        self.add_new_session()


    def create_plotter(self, parent, for_compare=False):
        if self.headless_mode:
            return HeadlessPlotter(parent)
        plotter = QtInteractor(parent)
        self._plotter_brightness[plotter] = 1.0
        self._plotter_is_compare[plotter] = for_compare
        self._configure_plotter_lighting(plotter, compare=for_compare)
        interactor = plotter.interactor
        event_filter = _ViewportEventFilter(plotter)
        interactor.installEventFilter(event_filter)
        setattr(plotter, "_viewport_event_filter", event_filter)
        self._event_filters.append(event_filter)
        return plotter

    def _add_brightness_control(self, layout, plotter):
        if self.headless_mode:
            return None
        row = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("明るさ")
        label.setFixedWidth(70)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(20, 200)
        slider.setSingleStep(5)
        slider.setToolTip("ビュー全体の照明強度を調整します")
        default = int(self._plotter_brightness.get(plotter, 1.0) * 100)
        slider.setValue(default)
        slider.valueChanged.connect(partial(self._set_plotter_brightness, plotter))
        row.addWidget(label)
        row.addWidget(slider)
        layout.addLayout(row)
        return slider

    def _create_color_scale_widget(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QtWidgets.QLabel("カラースケール (距離)")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        segments = [
            ("0.0–1.0 mm", "#ff0000"),
            ("1.6 mm", "#ffff00"),
            ("2.5 mm", "#00ff00"),
            ("3.3 mm", "#00ffff"),
            ("4.0–5.0 mm", "#0000ff"),
        ]

        for label_text, color in segments:
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedHeight(24)
            text_color = "#000000"
            if color.lower() == "#0000ff":
                text_color = "#ffffff"
            label.setStyleSheet(
                "border: 1px solid #444; padding: 2px; font-size: 10px; "
                f"background-color: {color}; color: {text_color};"
            )
            layout.addWidget(label)

        layout.addStretch(1)
        return widget

    def _link_compare_views(self, force=False):
        if self.headless_mode:
            return
        plotters = [self.compare_plotter_left, self.compare_plotter_right]
        enabled = force or self.link_views_checkbox.isChecked()
        if enabled:
            try:
                self.compare_plotter_left.link_views_across_plotters(plotters)
            except Exception:
                try:
                    camera = self.compare_plotter_left.camera
                    self.compare_plotter_right.camera = camera
                except Exception:
                    pass
        else:
            try:
                self.compare_plotter_left.unlink_views()
            except Exception:
                pass
            try:
                self.compare_plotter_right.unlink_views()
            except Exception:
                pass
        for plotter in plotters:
            event_filter = getattr(plotter, "_viewport_event_filter", None)
            if event_filter is not None:
                event_filter.set_linked_plotters(plotters if enabled else [plotter])

    def connect_signals(self):
        """シグナルとスロットを接続する"""
        # ターゲット/ソースは現在の（作成タブの）セッションビューに表示する
        self.target_load_button.clicked.connect(lambda: self.load_model(self.target_combo, "target"))
        self.source_load_button.clicked.connect(lambda: self.load_model(self.source_combo, "source"))
        self.apply_button.clicked.connect(self.on_apply)

        # Display controls
        self.result_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility("result", checked))
        self.target_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility(self.target_combo.currentData(), checked))
        self.source_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility(self.source_combo.currentData(), checked))

        self.result_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity("result", value / 100.0))
        self.target_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity(self.target_combo.currentData(), value / 100.0))
        self.source_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity(self.source_combo.currentData(), value / 100.0))

        # Save buttons
        self.save_result_button.clicked.connect(self.save_result)
        self.save_colored_result_button.clicked.connect(self.save_colored_result)
        self.save_screenshot_button.clicked.connect(self.save_screenshot)
        self.new_snapshot_button.clicked.connect(lambda: self.add_new_session(copy_from=self.current_session()))
        self.cancel_button.clicked.connect(self.cancel_distance)

        # 作成タブ内のセッションタブ操作
        self.session_tabs.currentChanged.connect(self.on_tab_changed)
        self.session_tabs.tabCloseRequested.connect(self.close_session)

        # 比較タブ操作（操作UIは作成タブへ集約）
        self.left_load_button.clicked.connect(lambda: self.compare_load_from_file('left'))
        self.right_load_button.clicked.connect(lambda: self.compare_load_from_file('right'))
        self.compare_screenshot_button.clicked.connect(self.save_compare_screenshot)
        self.clear_left_button.clicked.connect(lambda: self.clear_compare_side('left'))
        self.clear_right_button.clicked.connect(lambda: self.clear_compare_side('right'))
        self.zoom_in_button.clicked.connect(lambda: self.adjust_zoom(1.2))
        self.zoom_out_button.clicked.connect(lambda: self.adjust_zoom(0.8))
        self.zoom_reset_button.clicked.connect(self.reset_camera_view)
        self.compare_zoom_in_button.clicked.connect(lambda: self.adjust_zoom(1.2))
        self.compare_zoom_out_button.clicked.connect(lambda: self.adjust_zoom(0.8))
        self.compare_zoom_reset_button.clicked.connect(self.reset_camera_view)
        self.disclaimer_checkbox.toggled.connect(self._update_disclaimer_state)
        self.debug_refresh_button.clicked.connect(self._refresh_debug_console)
        self.debug_clear_button.clicked.connect(self._clear_debug_console)

    def set_busy_state(self, busy, message=None):
        if busy == self._is_busy:
            if busy and message:
                self.status_bar.showMessage(message)
            return

        self._is_busy = busy
        self._refresh_controls_enabled()

        if busy:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            if message:
                self.status_bar.showMessage(message)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.status_bar.clearMessage()

    def adjust_zoom(self, factor):
        if self.headless_mode:
            return
        try:
            if self.main_tabs.currentWidget() is self.compare_root:
                plotters = [self.compare_plotter_left, self.compare_plotter_right]
            else:
                session = self.current_session()
                if session is None:
                    return
                plotters = [session['plotter']]

            for plotter in plotters:
                plotter.camera.Zoom(factor)
                plotter.render()
        except Exception as exc:
            logger.exception("Failed to adjust zoom")
            QtWidgets.QMessageBox.warning(self, "Warning", f"ズームの適用に失敗しました: {exc}")

    def reset_camera_view(self):
        if self.headless_mode:
            return
        try:
            if self.main_tabs.currentWidget() is self.compare_root:
                self.compare_plotter_left.reset_camera()
                self.compare_plotter_right.reset_camera()
            else:
                session = self.current_session()
                if session is None:
                    return
                session['plotter'].reset_camera()
        except Exception as exc:
            logger.exception("Failed to reset camera")
            QtWidgets.QMessageBox.warning(self, "Warning", f"ビューのリセットに失敗しました: {exc}")

    def save_screenshot(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            "view.png",
            "PNG Image (*.png)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return

        try:
            session = self.current_session()
            if session is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Warning",
                    "アクティブなセッションが見つからないためスクリーンショットを保存できません。",
                )
                return

            if not file_path.lower().endswith(".png"):
                file_path = f"{file_path}.png"

            logger.info("Saving screenshot to %s", file_path)
            session['plotter'].screenshot(
                filename=file_path, transparent_background=True
            )
            logger.info("Screenshot saved to %s", file_path)
        except Exception as e:
            logger.exception("Failed to save screenshot to %s", file_path)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save screenshot: {e}")

    def _configure_plotter_lighting(self, plotter, compare=False):
        try:
            renderer = plotter.renderer
        except Exception:
            return

        def _clear(renderer):
            try:
                existing = list(renderer.lights)
                for light in existing:
                    renderer.remove_light(light)
            except Exception:
                try:
                    vtk_lights = renderer.GetLights()
                    vtk_lights.InitTraversal()
                    items = []
                    for _ in range(vtk_lights.GetNumberOfItems()):
                        items.append(vtk_lights.GetNextItem())
                    for light in items:
                        renderer.RemoveLight(light)
                except Exception:
                    return

        _clear(renderer)

        try:
            renderer.SetUseImageBasedLighting(False)
        except Exception:
            pass

        brightness = self._plotter_brightness.get(plotter, 1.0)
        light_defs = _COMPARE_LIGHTS if compare else _CREATE_LIGHTS
        for light_def in light_defs:
            try:
                intensity = light_def.get("intensity", 0.4) * brightness
                light = pv.Light(
                    position=light_def.get("position", (0, 0, 0)),
                    focal_point=light_def.get("focal_point", (0, 0, 0)),
                    color=light_def.get("color", "white"),
                    intensity=intensity,
                )
                try:
                    light.set_light_type_to_scene_light()
                except AttributeError:
                    try:
                        light.light_type = pv.Light.SCENE_LIGHT
                    except Exception:
                        pass
                renderer.add_light(light)
            except Exception:
                continue

        # 視線方向に追従するヘッドライトを追加（弱めに設定）
        try:
            headlight = pv.Light(color='white', intensity=0.16 * brightness)
            try:
                headlight.set_light_type_to_headlight()
            except AttributeError:
                try:
                    headlight.light_type = pv.Light.HEADLIGHT
                except Exception:
                    headlight.light_type = pv.Light.LIGHT_TYPE_HEADLIGHT
            renderer.add_light(headlight)
        except Exception:
            pass

    def _reapply_plotter_lighting(self, plotter):
        if self.headless_mode:
            return
        try:
            compare = self._plotter_is_compare.get(plotter, False)
            self._configure_plotter_lighting(plotter, compare=compare)
        except Exception:
            logger.debug("Failed to reapply lighting", exc_info=True)

    def _set_plotter_brightness(self, plotter, value):
        if self.headless_mode:
            return
        if plotter not in self._plotter_brightness:
            return
        factor = max(value, 1) / 100.0
        self._plotter_brightness[plotter] = factor
        compare = self._plotter_is_compare.get(plotter, False)
        self._configure_plotter_lighting(plotter, compare=compare)
        try:
            plotter.renderer.ResetCameraClippingRange()
            plotter.render()
        except Exception:
            pass


    def _distance_scalars(self, mesh):
        if 'Distance' in mesh.point_data:
            return mesh.point_data['Distance'], 'point'
        if 'Distance' in mesh.cell_data:
            return mesh.cell_data['Distance'], 'cell'
        return None, None

    def _apply_surface_properties(self, actor):
        try:
            prop = actor.GetProperty()
            prop.SetAmbient(0.22)
            prop.SetDiffuse(0.68)
            prop.SetSpecular(0.08)
            prop.SetSpecularPower(18)
        except Exception:
            pass

    def _add_result_mesh(self, plotter, mesh, name="result"):
        distances, assoc = self._distance_scalars(mesh)
        common_kwargs = {'lighting': True, 'smooth_shading': True}
        if distances is None:
            actor = plotter.add_mesh(mesh, name=name, **common_kwargs)
            self._apply_surface_properties(actor)
            plotter.renderer.ResetCameraClippingRange()
            plotter.render()
            return
        lut = self.create_custom_colormap()
        kwargs = {
            'name': name,
            'scalars': distances,
            'cmap': lut.cmap,
            'clim': lut.scalar_range,
            'scalar_bar_args': {'title': 'Distance (mm)'},
        }
        if assoc == 'cell':
            kwargs['preference'] = 'cell'
        kwargs.update(common_kwargs)
        actor = plotter.add_mesh(mesh, **kwargs)
        self._apply_surface_properties(actor)
        plotter.renderer.ResetCameraClippingRange()
        plotter.render()

    def save_result(self):
        session = self.current_session()
        if "result" not in session['models']:
            QtWidgets.QMessageBox.warning(self, "Warning", "No result to save. Please run Apply first.")
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Result Model",
            "result.vtp",
            "VTK PolyData (*.vtp);;PLY (*.ply);;STL (*.stl)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return
        
        try:
            save_mesh(session['models']["result"], file_path)
            print(f"Result saved to {file_path}")
        except MeshOperationError as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save result: {exc}")

    def save_colored_result(self):
        session = self.current_session()
        if "result" not in session['models']:
            QtWidgets.QMessageBox.warning(self, "Warning", "No result to save. Please run Apply first.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Colored Result Model",
            "colored_result.ply",
            "PLY (*.ply);;VTK PolyData (*.vtp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return

        try:
            result_mesh = session['models']["result"]
            lut = self.create_custom_colormap()
            save_colored_mesh(result_mesh, lut, file_path)
            print(f"Colored result saved to {file_path}")
        except MeshOperationError as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save colored result: {exc}")

    def load_model(self, combo_box, name_prefix):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Model",
            "",
            "Model Files (*.stl *.ply *.vtk *.vtp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return
        try:
            mesh = load_mesh(file_path)
        except MeshOperationError as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load model: {exc}")
            return

        file_name = os.path.basename(file_path)
        actor_name = f"{name_prefix}_{file_name}"

        session = self.current_session()
        plotter = session['plotter']

        if combo_box.currentData():
            plotter.remove_actor(combo_box.currentData())

        session['models'][actor_name] = mesh
        combo_box.addItem(file_name, actor_name)
        combo_box.setCurrentIndex(combo_box.count() - 1)
        actor = plotter.add_mesh(mesh, name=actor_name, lighting=True, smooth_shading=True)
        self._apply_surface_properties(actor)
        plotter.reset_camera()
        logger.info("Loaded model %s as actor %s", file_name, actor_name)

    def on_apply(self):
        if self._distance_thread is not None:
            QtWidgets.QMessageBox.information(self, "Busy", "距離計算を実行中です。完了までお待ちください。")
            return

        session = self.current_session()
        target_actor_name = self.target_combo.currentData()
        source_actor_name = self.source_combo.currentData()

        if not target_actor_name or not source_actor_name:
            logger.warning("Apply requested without both models selected")
            QtWidgets.QMessageBox.warning(self, "Warning", "ターゲットとソースを両方選択してください。")
            return

        source_mesh = session['models'][source_actor_name]
        target_mesh = session['models'][target_actor_name]

        reduction = None
        if self.decimation_group.isChecked():
            reduction = self.decimation_slider.value() / 100.0

        self.set_busy_state(True, "距離計算中...")
        self._pending_cancel = False
        if self._cancel_watchdog is not None:
            self._cancel_watchdog.stop()
            self._cancel_watchdog.deleteLater()
            self._cancel_watchdog = None

        self._distance_thread = QtCore.QThread(self)
        self._distance_worker = DistanceComputationWorker(source_mesh, target_mesh, reduction=reduction)
        self._distance_worker.moveToThread(self._distance_thread)
        self._distance_thread.started.connect(self._distance_worker.run)
        self._distance_worker.finished.connect(self.on_distance_finished)
        self._distance_worker.error.connect(self.on_distance_error)
        self._distance_worker.cancelled.connect(self.on_distance_cancelled)
        self._distance_worker.finished.connect(self.cleanup_distance_worker)
        self._distance_worker.error.connect(self.cleanup_distance_worker)
        self._distance_worker.cancelled.connect(self.cleanup_distance_worker)
        self._distance_thread.finished.connect(self._distance_thread.deleteLater)
        self._distance_thread.start()
        self._refresh_controls_enabled()

    def cancel_distance(self):
        if self._distance_worker is None:
            return
        logger.info("Cancelling distance computation on user request")
        self._pending_cancel = True
        self.status_bar.showMessage("距離計算の中止を要求しました...", 3000)
        try:
            self._distance_worker.cancel()
        except AttributeError:
            logger.debug("Distance worker does not support cancel()")
        self.cancel_button.setEnabled(False)
        self._refresh_controls_enabled()
        if self._cancel_watchdog is not None:
            self._cancel_watchdog.stop()
            self._cancel_watchdog.deleteLater()
        self._cancel_watchdog = QtCore.QTimer(self)
        self._cancel_watchdog.setSingleShot(True)
        self._cancel_watchdog.timeout.connect(self._handle_cancel_timeout)
        self._cancel_watchdog.start(2000)

    def on_distance_finished(self, result_mesh, min_dist):
        if self._pending_cancel:
            logger.info("Distance computation finished but cancellation was requested; discarding results")
            return
        logger.info("Distance computation finished")
        session = self.current_session()
        if session is None:
            return
        session['models']["result"] = result_mesh
        if min_dist is not None:
            self.min_distance_label.setText(f"{min_dist:.4f}")
        else:
            self.min_distance_label.setText("-")

        plotter = session['plotter']
        plotter.remove_actor("result", render=False)
        try:
            plotter.remove_scalar_bar()
        except Exception:
            logger.debug("No scalar bar to remove during apply")

        self._add_result_mesh(plotter, result_mesh)
        self.status_bar.showMessage("距離計算が完了しました", 3000)

    def on_distance_error(self, message):
        logger.error("Distance computation failed: %s", message)
        QtWidgets.QMessageBox.critical(self, "Error", f"距離計算に失敗しました: {message}")

    def on_distance_cancelled(self):
        logger.info("Distance computation cancelled")
        QtCore.QTimer.singleShot(0, lambda: self.status_bar.showMessage("距離計算を中止しました", 3000))

    def cleanup_distance_worker(self, *args):
        thread = self._distance_thread
        if thread is not None:
            try:
                thread.requestInterruption()
                thread.quit()
                thread.wait(200)
            except RuntimeError:
                pass
        if self._distance_worker is not None:
            try:
                self._distance_worker.deleteLater()
            except Exception:
                pass
        self._distance_thread = None
        self._distance_worker = None
        self.set_busy_state(False)
        self._pending_cancel = False
        if self._cancel_watchdog is not None:
            self._cancel_watchdog.stop()
            self._cancel_watchdog.deleteLater()
            self._cancel_watchdog = None
        self._refresh_controls_enabled()

    def _handle_cancel_timeout(self):
        logger.warning("Cancel watchdog triggered; forcing cleanup")
        QtCore.QTimer.singleShot(0, lambda: self.status_bar.showMessage("距離計算を中止しました", 3000))
        self.cleanup_distance_worker()

    def create_custom_colormap(self):
        return build_colormap()

    def set_actor_visibility(self, name, visible):
        session = self.current_session()
        plotter = session['plotter']
        if name and name in plotter.actors:
            plotter.actors[name].SetVisibility(visible)

    def set_actor_opacity(self, name, opacity):
        session = self.current_session()
        plotter = session['plotter']
        if name and name in plotter.actors:
            plotter.actors[name].GetProperty().SetOpacity(opacity)

    # --- セッション/タブ管理 ---
    def add_new_session(self, copy_from=None):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        plotter = self.create_plotter(page)
        layout.addWidget(plotter.interactor)
        slider = self._add_brightness_control(layout, plotter)
        plotter.add_axes()
        plotter.add_text("Source / Target / Result", position='upper_left', font_size=12)
        layout.addWidget(self._create_color_scale_widget())

        session = { 'plotter': plotter, 'models': {}, 'brightness_slider': slider }

        # 既存セッションからスナップショット
        if copy_from is not None:
            for name, mesh in copy_from['models'].items():
                try:
                    mcopy = mesh.copy()
                    session['models'][name] = mcopy
                    actor = plotter.add_mesh(mcopy, name=name, lighting=True, smooth_shading=True)
                    self._apply_surface_properties(actor)
                except Exception:
                    pass
            plotter.reset_camera()
            if slider is not None:
                prev = int(self._plotter_brightness.get(copy_from['plotter'], 1.0) * 100)
                slider.blockSignals(True)
                slider.setValue(prev)
                slider.blockSignals(False)
                self._set_plotter_brightness(plotter, prev)
        idx = self.session_tabs.addTab(page, f"Session {self.session_tabs.count()+1}")
        self.sessions.append(session)
        self.session_tabs.setCurrentIndex(idx)
        logger.info("Added new session %d", idx + 1)
        self.rebuild_combos_for_session(session)
        self.rebuild_compare_session_combos()

    def current_session(self):
        idx = self.session_tabs.currentIndex()
        if idx < 0:
            return None
        return self.sessions[idx]

    def on_tab_changed(self, index):
        if index < 0 or index >= len(self.sessions):
            return
        session = self.sessions[index]
        self.rebuild_combos_for_session(session)
        # 比較タブのセッション選択も更新
        self.rebuild_compare_session_combos()

    def close_session(self, index):
        if len(self.sessions) <= 1:
            # 少なくとも1タブは残す
            return
        plotter = self.sessions[index]['plotter']
        self.session_tabs.removeTab(index)
        del self.sessions[index]
        self._plotter_brightness.pop(plotter, None)
        self._plotter_is_compare.pop(plotter, None)
        # タブ変更イベントでコンボ再構築される
        self.rebuild_compare_session_combos()

    def rebuild_combos_for_session(self, session):
        # 現在のセッションのモデルからコンボを再構築
        def populate_combo(combo, prefix):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for name in session['models'].keys():
                if name.startswith(prefix + "_"):
                    file_name = name[len(prefix)+1:]
                    combo.addItem(file_name, name)
            # 可能なら以前の選択を維持
            if current:
                idx = combo.findData(current)
                if idx != -1:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        populate_combo(self.target_combo, 'target')
        populate_combo(self.source_combo, 'source')

    # === 比較タブの処理 ===
    def rebuild_compare_session_combos(self):
        pass

    def compare_load_from_file(self, side):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Model",
            "",
            "Model Files (*.stl *.ply *.vtk *.vtp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return
        plotter = self.compare_plotter_left if side == 'left' else self.compare_plotter_right
        try:
            # 既存表示をクリアして単一モデルを表示
            try:
                plotter.clear()
            except Exception:
                for name in list(plotter.actors.keys()):
                    plotter.remove_actor(name)
            self._reapply_plotter_lighting(plotter)
            plotter.add_axes()
            label = 'Left' if side == 'left' else 'Right'
            plotter.add_text(label, position='upper_left', font_size=12)

            mesh = load_mesh(file_path)
            name = os.path.basename(file_path)
            distances, _ = self._distance_scalars(mesh)
            if distances is not None:
                self._add_result_mesh(plotter, mesh, name=name)
            else:
                actor = plotter.add_mesh(mesh, name=name, lighting=True, smooth_shading=True)
                self._apply_surface_properties(actor)
            plotter.reset_camera()
            logger.info("Loaded comparison model %s onto %s panel", name, side)
            # カメラ連動を再適用
            self._link_compare_views()
        except MeshOperationError as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load model: {exc}")

    def save_compare_screenshot(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Compare Screenshot",
            "compare.png",
            "PNG Image (*.png)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not file_path:
            return
        try:
            logger.info("Saving compare screenshot to %s", file_path)
            img_left = self.compare_plotter_left.screenshot(transparent_background=True)
            img_right = self.compare_plotter_right.screenshot(transparent_background=True)

            # 高さを合わせる
            h_left, w_left, _ = img_left.shape
            h_right, w_right, _ = img_right.shape
            if h_left != h_right:
                if h_left < h_right:
                    new_w = int(w_left * (h_right / h_left))
                    img_left_resized = pv.wrap(img_left).resize([new_w, h_right])
                    img_left = img_left_resized.to_array()
                else:
                    new_w = int(w_right * (h_left / h_right))
                    img_right_resized = pv.wrap(img_right).resize([new_w, h_left])
                    img_right = img_right_resized.to_array()

            combined_img = pv.numpy_to_texture(img_left).hstack(pv.numpy_to_texture(img_right))
            combined_img.save(file_path)
            print(f"Compare screenshot saved to {file_path}")
            logger.info("Compare screenshot saved to %s", file_path)
        except Exception as e:
            logger.exception("Failed to save compare screenshot to %s", file_path)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save compare screenshot: {e}")

    def clear_compare_side(self, side):
        plotter = self.compare_plotter_left if side == 'left' else self.compare_plotter_right
        logger.info("Clearing compare view on %s side", side)
        try:
            plotter.clear()
        except Exception:
            for name in list(plotter.actors.keys()):
                plotter.remove_actor(name)
        self._reapply_plotter_lighting(plotter)
        plotter.add_axes()
        label = 'Left' if side == 'left' else 'Right'
        plotter.add_text(label, position='upper_left', font_size=12)
        self._link_compare_views()

    def _interaction_allowed(self):
        try:
            return self.disclaimer_checkbox.isChecked()
        except Exception:
            return False

    def _refresh_controls_enabled(self):
        allowed = self._interaction_allowed()
        busy = self._is_busy
        try:
            self.create_root.setEnabled(allowed)
            self.compare_root.setEnabled(allowed)
            self.debug_root.setEnabled(allowed)
        except Exception:
            pass
        general_controls = [
            getattr(self, 'apply_button', None),
            getattr(self, 'target_load_button', None),
            getattr(self, 'source_load_button', None),
            getattr(self, 'target_combo', None),
            getattr(self, 'source_combo', None),
            getattr(self, 'decimation_group', None),
            getattr(self, 'decimation_slider', None),
            getattr(self, 'result_visibility_checkbox', None),
            getattr(self, 'result_opacity_slider', None),
            getattr(self, 'target_visibility_checkbox', None),
            getattr(self, 'target_opacity_slider', None),
            getattr(self, 'source_visibility_checkbox', None),
            getattr(self, 'source_opacity_slider', None),
            getattr(self, 'new_snapshot_button', None),
            getattr(self, 'save_result_button', None),
            getattr(self, 'save_colored_result_button', None),
            getattr(self, 'save_screenshot_button', None),
            getattr(self, 'left_load_button', None),
            getattr(self, 'right_load_button', None),
            getattr(self, 'clear_left_button', None),
            getattr(self, 'clear_right_button', None),
            getattr(self, 'compare_screenshot_button', None),
            getattr(self, 'zoom_in_button', None),
            getattr(self, 'zoom_out_button', None),
            getattr(self, 'zoom_reset_button', None),
            getattr(self, 'compare_zoom_in_button', None),
            getattr(self, 'compare_zoom_out_button', None),
            getattr(self, 'compare_zoom_reset_button', None),
        ]
        for widget in general_controls:
            if widget is not None:
                try:
                    widget.setEnabled(allowed and not busy)
                except Exception:
                    continue

        for widget in (getattr(self, 'debug_refresh_button', None), getattr(self, 'debug_clear_button', None)):
            if widget is not None:
                try:
                    widget.setEnabled(allowed)
                except Exception:
                    continue

        if getattr(self, 'cancel_button', None) is not None:
            try:
                self.cancel_button.setEnabled(allowed and self._distance_worker is not None and busy)
            except Exception:
                pass

    def _update_disclaimer_state(self):
        accepted = self.disclaimer_checkbox.isChecked()
        disclaimer_idx = self.main_tabs.indexOf(self.disclaimer_root)
        for idx in range(self.main_tabs.count()):
            if idx == disclaimer_idx:
                continue
            try:
                self.main_tabs.setTabEnabled(idx, accepted)
            except Exception:
                continue
        self._refresh_controls_enabled()

    def _on_tab_change(self, index):
        if self.disclaimer_checkbox.isChecked():
            if index == self.main_tabs.indexOf(self.debug_root):
                QtCore.QTimer.singleShot(0, self._refresh_debug_console)
            return
        disclaimer_idx = self.main_tabs.indexOf(self.disclaimer_root)
        if index != disclaimer_idx:
            QtCore.QTimer.singleShot(0, lambda: self.main_tabs.setCurrentIndex(disclaimer_idx))

    def _resolve_log_path(self):
        try:
            root = logging.getLogger()
            for handler in root.handlers:
                path = getattr(handler, 'baseFilename', None)
                if path:
                    return path
        except Exception:
            pass
        default_dir = os.path.join(os.path.expanduser("~"), ".joint_space_visualizer")
        default_path = os.path.join(default_dir, "app.log")
        return default_path

    def _refresh_debug_console(self):
        path = self._log_path
        if not path or not os.path.exists(path):
            self.debug_console.setPlainText("ログファイルが見つかりませんでした。")
            self.debug_status_label.setText("ログパス: 未検出")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as exc:
            self.debug_console.setPlainText(f"ログの読み込みに失敗しました: {exc}")
            self.debug_status_label.setText(f"ログパス: {path}")
            return
        self.debug_console.setPlainText(content)
        self.debug_console.verticalScrollBar().setValue(self.debug_console.verticalScrollBar().maximum())
        self.debug_status_label.setText(f"ログパス: {path}")

    def _clear_debug_console(self):
        self.debug_console.clear()
        self.debug_status_label.setText("コンソールをクリアしました。ログ自体は削除されていません。")
