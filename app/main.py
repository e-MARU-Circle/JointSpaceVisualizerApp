import sys
import os
import vtk
import pyvista as pv
from PyQt5 import QtWidgets, QtCore
from pyvistaqt import QtInteractor

class JointSpaceVisualizerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Joint Space Visualizer (Standalone)")
        self.setGeometry(100, 100, 1200, 800)

        # セッション（タブ）ごとの状態を保持（作成タブ内）
        self.sessions = []  # list of dicts: { 'plotter': QtInteractor, 'models': {} }
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        # --- 上位タブ（作成 / 比較） ---
        self.main_tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.main_tabs)

        # 作成タブ
        self.create_root = QtWidgets.QWidget()
        create_layout = QtWidgets.QHBoxLayout(self.create_root)
        self.main_tabs.addTab(self.create_root, "作成")

        # 比較タブ
        self.compare_root = QtWidgets.QWidget()
        compare_layout = QtWidgets.QHBoxLayout(self.compare_root)
        self.main_tabs.addTab(self.compare_root, "比較")

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
        inputs_layout.addRow("Target Model:", target_layout)
        self.source_combo = QtWidgets.QComboBox()
        self.source_load_button = QtWidgets.QPushButton("Load...")
        source_layout = QtWidgets.QHBoxLayout()
        source_layout.addWidget(self.source_combo)
        source_layout.addWidget(self.source_load_button)
        inputs_layout.addRow("Source Model:", source_layout)
        self.control_layout.addWidget(inputs_group)

        # Apply Button
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setStyleSheet("font-weight: bold; padding: 5px;")
        self.control_layout.addWidget(self.apply_button)

        # Decimation Group
        self.decimation_group = QtWidgets.QGroupBox("Decimation Options")
        self.decimation_group.setCheckable(True)
        self.decimation_group.setChecked(False)
        decimation_layout = QtWidgets.QFormLayout(self.decimation_group)
        self.decimation_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.decimation_slider.setRange(0, 99)
        self.decimation_slider.setValue(90)
        decimation_layout.addRow("Target Reduction (%):", self.decimation_slider)
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
        display_layout.addRow("Target:", target_controls_layout)
        # Source controls
        self.source_visibility_checkbox = QtWidgets.QCheckBox("Show")
        self.source_visibility_checkbox.setChecked(True)
        self.source_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.source_opacity_slider.setRange(0, 100)
        self.source_opacity_slider.setValue(40)
        source_controls_layout = QtWidgets.QHBoxLayout()
        source_controls_layout.addWidget(self.source_visibility_checkbox)
        source_controls_layout.addWidget(self.source_opacity_slider)
        display_layout.addRow("Source:", source_controls_layout)
        self.control_layout.addWidget(display_group)

        # Snapshot/Session Group（作成タブ内）
        snapshot_group = QtWidgets.QGroupBox("Snapshot / Compare")
        snapshot_layout = QtWidgets.QVBoxLayout(snapshot_group)
        self.save_screenshot_button = QtWidgets.QPushButton("Save Screenshot (Current View)...")
        snapshot_layout.addWidget(self.save_screenshot_button)
        self.new_snapshot_button = QtWidgets.QPushButton("New Snapshot Tab")
        snapshot_layout.addWidget(self.new_snapshot_button)
        self.control_layout.addWidget(snapshot_group)

        # Compare Controls は比較タブ内に配置するため、ここでは作成しない

        # === 比較タブのUI（コントロール + 2画面ビュー） ===
        # 左：コントロールパネル
        self.compare_panel = QtWidgets.QGroupBox("Compare Controls")
        self.compare_panel.setFixedWidth(350)
        self.compare_layout_panel = QtWidgets.QFormLayout(self.compare_panel)
        compare_layout.addWidget(self.compare_panel)

        # セッション選択（左/右）
        self.left_session_combo = QtWidgets.QComboBox()
        self.right_session_combo = QtWidgets.QComboBox()
        self.compare_layout_panel.addRow("Left Session:", self.left_session_combo)
        self.compare_layout_panel.addRow("Right Session:", self.right_session_combo)
        # ファイルから読み込み（左/右）
        self.left_load_button = QtWidgets.QPushButton("Load Left From File...")
        self.right_load_button = QtWidgets.QPushButton("Load Right From File...")
        self.compare_layout_panel.addRow(self.left_load_button)
        self.compare_layout_panel.addRow(self.right_load_button)
        # クリアボタン（左右）
        self.clear_left_button = QtWidgets.QPushButton("Clear Left")
        self.clear_right_button = QtWidgets.QPushButton("Clear Right")
        self.compare_layout_panel.addRow(self.clear_left_button)
        self.compare_layout_panel.addRow(self.clear_right_button)
        # スクリーンショット
        self.compare_screenshot_button = QtWidgets.QPushButton("Save Compare Screenshot...")
        self.compare_layout_panel.addRow(self.compare_screenshot_button)

        # 右：2画面ビュー
        self.compare_view_container = QtWidgets.QWidget()
        self.compare_view_layout = QtWidgets.QHBoxLayout(self.compare_view_container)
        compare_layout.addWidget(self.compare_view_container)

        self.compare_plotter_left = QtInteractor(self.compare_view_container)
        self.compare_view_layout.addWidget(self.compare_plotter_left.interactor)
        self.compare_plotter_left.add_axes()
        self.compare_plotter_left.add_text("Left", position='upper_left', font_size=12)

        self.compare_plotter_right = QtInteractor(self.compare_view_container)
        self.compare_view_layout.addWidget(self.compare_plotter_right.interactor)
        self.compare_plotter_right.add_axes()
        self.compare_plotter_right.add_text("Right", position='upper_left', font_size=12)

        # カメラ連動
        try:
            self.compare_plotter_left.link_views(self.compare_plotter_right)
        except Exception:
            try:
                self.compare_plotter_left.link_views([self.compare_plotter_right])
            except Exception:
                pass

        self.control_layout.addStretch(1)

        # ここで初期セッションを追加（コンボボックスが準備できた後）
        self.add_new_session()

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

        # 作成タブ内のセッションタブ操作
        self.session_tabs.currentChanged.connect(self.on_tab_changed)
        self.session_tabs.tabCloseRequested.connect(self.close_session)

        # 比較タブ操作（操作UIは作成タブへ集約）
        self.left_session_combo.currentIndexChanged.connect(lambda _: self.load_compare_from_session('left'))
        self.right_session_combo.currentIndexChanged.connect(lambda _: self.load_compare_from_session('right'))
        self.left_load_button.clicked.connect(lambda: self.compare_load_from_file('left'))
        self.right_load_button.clicked.connect(lambda: self.compare_load_from_file('right'))
        self.compare_screenshot_button.clicked.connect(self.save_compare_screenshot)
        self.clear_left_button.clicked.connect(lambda: self.clear_compare_side('left'))
        self.clear_right_button.clicked.connect(lambda: self.clear_compare_side('right'))

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
            img = session['plotter'].screenshot(transparent_background=True)
            tex = pv.numpy_to_texture(img)
            tex.save(file_path)
            print(f"Screenshot saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save screenshot: {e}")

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
            session['models']["result"].save(file_path)
            print(f"Result saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save result: {e}")

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
            # Bake colors
            colored_mesh = result_mesh.copy()
            rgba = lut.map_scalars(result_mesh.get_array('Distance'), rgba=True)
            colored_mesh.point_data['RGB'] = rgba[:, :3]
            colored_mesh.save(file_path, binary=True)
            print(f"Colored result saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save colored result: {e}")

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
            mesh = pv.read(file_path)
            file_name = os.path.basename(file_path)
            actor_name = f"{name_prefix}_{file_name}"

            session = self.current_session()
            plotter = session['plotter']

            if combo_box.currentData():
                plotter.remove_actor(combo_box.currentData())

            session['models'][actor_name] = mesh
            combo_box.addItem(file_name, actor_name)
            combo_box.setCurrentIndex(combo_box.count() - 1)
            plotter.add_mesh(mesh, name=actor_name)
            plotter.reset_camera()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

    def on_apply(self):
        session = self.current_session()
        target_actor_name = self.target_combo.currentData()
        source_actor_name = self.source_combo.currentData()

        if not target_actor_name or not source_actor_name:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select both Target and Source models.")
            return

        target_mesh = session['models'][target_actor_name]
        source_mesh = session['models'][source_actor_name]

        if self.decimation_group.isChecked():
            reduction = self.decimation_slider.value() / 100.0
            source_mesh = source_mesh.decimate(reduction)
            target_mesh = target_mesh.decimate(reduction)

        dist_filter = vtk.vtkDistancePolyDataFilter()
        dist_filter.SetInputData(0, source_mesh)
        dist_filter.SetInputData(1, target_mesh)
        dist_filter.SignedDistanceOff()
        dist_filter.Update()

        result_mesh = pv.wrap(dist_filter.GetOutput())
        session['models']["result"] = result_mesh
        min_dist = result_mesh.get_array('Distance').min()
        self.min_distance_label.setText(f"{min_dist:.4f}")

        plotter = session['plotter']
        plotter.remove_actor("result", render=False)
        try:
            plotter.remove_scalar_bar()
        except Exception:
            # No scalar bar to remove or backend mismatch
            pass

        custom_lut = self.create_custom_colormap()
        plotter.add_mesh(result_mesh, name="result", scalars='Distance', lut=custom_lut, scalar_bar_args={'title': 'Distance (mm)'})

    def create_custom_colormap(self):
        lut = pv.LookupTable()
        lut.add_point(0.0, (1.0, 0.0, 0.0))
        lut.add_point(1.0, (1.0, 0.0, 0.0))
        lut.add_point(1.6, (1.0, 1.0, 0.0))
        lut.add_point(2.5, (0.0, 1.0, 0.0))
        lut.add_point(3.3, (0.0, 1.0, 1.0))
        lut.add_point(4.0, (0.0, 0.0, 1.0))
        lut.add_point(5.0, (0.0, 0.0, 1.0))
        lut.scalar_range = (0.0, 5.0)
        return lut

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
        plotter = QtInteractor(page)
        layout.addWidget(plotter.interactor)
        plotter.add_axes()
        plotter.add_text("Source / Target / Result", position='upper_left', font_size=12)

        session = { 'plotter': plotter, 'models': {} }

        # 既存セッションからスナップショット
        if copy_from is not None:
            for name, mesh in copy_from['models'].items():
                try:
                    mcopy = mesh.copy()
                    session['models'][name] = mcopy
                    plotter.add_mesh(mcopy, name=name)
                except Exception:
                    pass
            plotter.reset_camera()
        idx = self.session_tabs.addTab(page, f"Session {self.session_tabs.count()+1}")
        self.sessions.append(session)
        self.session_tabs.setCurrentIndex(idx)
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
        self.session_tabs.removeTab(index)
        del self.sessions[index]
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
        def set_items(combo):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            for i in range(len(self.sessions)):
                combo.addItem(f"Session {i+1}", i)
            # 可能なら以前の選択を維持
            if current:
                idx = combo.findText(current)
                if idx != -1:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        set_items(self.left_session_combo)
        set_items(self.right_session_combo)

    def load_compare_from_session(self, side):
        if not self.sessions:
            return
        plotter = self.compare_plotter_left if side == 'left' else self.compare_plotter_right
        combo = self.left_session_combo if side == 'left' else self.right_session_combo
        idx = combo.currentData()
        if idx is None or idx < 0 or idx >= len(self.sessions):
            return
        session = self.sessions[idx]
        # クリア
        try:
            plotter.clear()
        except Exception:
            # 互換API: actorsを一つずつ削除
            for name in list(plotter.actors.keys()):
                plotter.remove_actor(name)
        plotter.add_axes()
        label = 'Left' if side == 'left' else 'Right'
        plotter.add_text(label, position='upper_left', font_size=12)
        # 追加
        for name, mesh in session['models'].items():
            try:
                mcopy = mesh.copy()
                if name == 'result':
                    lut = self.create_custom_colormap()
                    plotter.add_mesh(mcopy, name=name, scalars='Distance', lut=lut, scalar_bar_args={'title': 'Distance (mm)'})
                else:
                    plotter.add_mesh(mcopy, name=name)
            except Exception:
                pass
        plotter.reset_camera()

        # カメラ連動（念のため毎回）
        try:
            self.compare_plotter_left.link_views(self.compare_plotter_right)
        except Exception:
            try:
                self.compare_plotter_left.link_views([self.compare_plotter_right])
            except Exception:
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
            plotter.add_axes()
            label = 'Left' if side == 'left' else 'Right'
            plotter.add_text(label, position='upper_left', font_size=12)

            mesh = pv.read(file_path)
            name = os.path.basename(file_path)
            plotter.add_mesh(mesh, name=name)
            plotter.reset_camera()
            # カメラ連動を再適用
            try:
                self.compare_plotter_left.link_views(self.compare_plotter_right)
            except Exception:
                try:
                    self.compare_plotter_left.link_views([self.compare_plotter_right])
                except Exception:
                    pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

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
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save compare screenshot: {e}")

    def clear_compare_side(self, side):
        plotter = self.compare_plotter_left if side == 'left' else self.compare_plotter_right
        try:
            plotter.clear()
        except Exception:
            for name in list(plotter.actors.keys()):
                plotter.remove_actor(name)
        plotter.add_axes()
        label = 'Left' if side == 'left' else 'Right'
        plotter.add_text(label, position='upper_left', font_size=12)
        try:
            self.compare_plotter_left.link_views(self.compare_plotter_right)
        except Exception:
            try:
                self.compare_plotter_left.link_views([self.compare_plotter_right])
            except Exception:
                pass

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = JointSpaceVisualizerApp()
    window.show()
    sys.exit(app.exec_())
