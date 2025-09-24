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

        self.models = {}
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        # --- メインレイアウト ---
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QHBoxLayout(self.central_widget)

        # --- 左側のコントロールパネル ---
        self.control_panel = QtWidgets.QGroupBox("Controls")
        self.control_panel.setFixedWidth(350)
        self.control_layout = QtWidgets.QVBoxLayout(self.control_panel)
        self.main_layout.addWidget(self.control_panel)

        # --- 右側の3Dビューエリア ---
        self.view_container = QtWidgets.QWidget()
        self.view_layout = QtWidgets.QHBoxLayout(self.view_container)
        self.main_layout.addWidget(self.view_container)

        # --- 3Dビューのセットアップ ---
        self.plotter_left = QtInteractor(self.view_container)
        self.view_layout.addWidget(self.plotter_left.interactor)
        self.plotter_left.add_axes()
        self.plotter_left.add_text("Source / Result", position='upper_left', font_size=12)

        self.plotter_right = QtInteractor(self.view_container)
        self.view_layout.addWidget(self.plotter_right.interactor)
        self.plotter_right.add_axes()
        self.plotter_right.add_text("Target", position='upper_left', font_size=12)
        
        # Link cameras between left and right views (robust across PyVista versions)
        try:
            # Prefer direct plotter-to-plotter linking when supported
            self.plotter_left.link_views(self.plotter_right)
        except Exception:
            try:
                # Fallback: older API may expect an iterable; try single-item list
                self.plotter_left.link_views([self.plotter_right])
            except Exception:
                # If linking is unsupported, continue without it
                pass

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

        # Compare Group (Simplified for this stage)
        compare_group = QtWidgets.QGroupBox("Compare")
        compare_layout = QtWidgets.QVBoxLayout(compare_group)
        self.save_screenshot_button = QtWidgets.QPushButton("Save Side-by-Side Screenshot...")
        compare_layout.addWidget(self.save_screenshot_button)
        self.control_layout.addWidget(compare_group)

        self.control_layout.addStretch(1)

    def connect_signals(self):
        """シグナルとスロットを接続する"""
        self.target_load_button.clicked.connect(lambda: self.load_model(self.target_combo, self.plotter_right, "target"))
        self.source_load_button.clicked.connect(lambda: self.load_model(self.source_combo, self.plotter_left, "source"))
        self.apply_button.clicked.connect(self.on_apply)

        # Display controls
        self.result_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility("result", checked, self.plotter_left))
        self.target_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility(self.target_combo.currentData(), checked, self.plotter_right))
        self.source_visibility_checkbox.toggled.connect(lambda checked: self.set_actor_visibility(self.source_combo.currentData(), checked, self.plotter_left))

        self.result_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity("result", value / 100.0, self.plotter_left))
        self.target_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity(self.target_combo.currentData(), value / 100.0, self.plotter_right))
        self.source_opacity_slider.valueChanged.connect(lambda value: self.set_actor_opacity(self.source_combo.currentData(), value / 100.0, self.plotter_left))

        # Save buttons
        self.save_result_button.clicked.connect(self.save_result)
        self.save_colored_result_button.clicked.connect(self.save_colored_result)
        self.save_screenshot_button.clicked.connect(self.save_screenshot)

    def save_screenshot(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Screenshot", "joint_space_comparison.png", "PNG Image (*.png)")
        if not file_path:
            return

        try:
            # スクリーンショットをNumPy配列として取得
            img_left = self.plotter_left.screenshot(transparent_background=True)
            img_right = self.plotter_right.screenshot(transparent_background=True)

            # 高さを合わせる
            h_left, w_left, _ = img_left.shape
            h_right, w_right, _ = img_right.shape
            if h_left != h_right:
                # 小さい方を大きい方の高さにリサイズ（アスペクト比は崩れる可能性）
                if h_left < h_right:
                    new_w = int(w_left * (h_right / h_left))
                    img_left_resized = pv.wrap(img_left).resize([new_w, h_right])
                    img_left = img_left_resized.to_array()
                else:
                    new_w = int(w_right * (h_left / h_right))
                    img_right_resized = pv.wrap(img_right).resize([new_w, h_left])
                    img_right = img_right_resized.to_array()

            # 画像を水平に結合
            combined_img_array = pv.numpy_to_texture(img_left).hstack(pv.numpy_to_texture(img_right))

            # 保存
            combined_img_array.save(file_path)
            print(f"Screenshot saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save screenshot: {e}")

    def save_result(self):
        if "result" not in self.models:
            QtWidgets.QMessageBox.warning(self, "Warning", "No result to save. Please run Apply first.")
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Result Model", "result.vtp", "VTK PolyData (*.vtp);;PLY (*.ply);;STL (*.stl)")
        if not file_path:
            return
        
        try:
            self.models["result"].save(file_path)
            print(f"Result saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save result: {e}")

    def save_colored_result(self):
        if "result" not in self.models:
            QtWidgets.QMessageBox.warning(self, "Warning", "No result to save. Please run Apply first.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Colored Result Model", "colored_result.ply", "PLY (*.ply);;VTK PolyData (*.vtp)")
        if not file_path:
            return

        try:
            result_mesh = self.models["result"]
            lut = self.create_custom_colormap()
            # Bake colors
            colored_mesh = result_mesh.copy()
            rgba = lut.map_scalars(result_mesh.get_array('Distance'), rgba=True)
            colored_mesh.point_data['RGB'] = rgba[:, :3]
            colored_mesh.save(file_path, binary=True)
            print(f"Colored result saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save colored result: {e}")

    def load_model(self, combo_box, plotter, name_prefix):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Model", "", "Model Files (*.stl *.ply *.vtk *.vtp)")
        if not file_path:
            return
        try:
            mesh = pv.read(file_path)
            file_name = os.path.basename(file_path)
            actor_name = f"{name_prefix}_{file_name}"

            if combo_box.currentData():
                plotter.remove_actor(combo_box.currentData())

            self.models[actor_name] = mesh
            combo_box.addItem(file_name, actor_name)
            combo_box.setCurrentIndex(combo_box.count() - 1)
            plotter.add_mesh(mesh, name=actor_name)
            plotter.reset_camera()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

    def on_apply(self):
        target_actor_name = self.target_combo.currentData()
        source_actor_name = self.source_combo.currentData()

        if not target_actor_name or not source_actor_name:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select both Target and Source models.")
            return

        target_mesh = self.models[target_actor_name]
        source_mesh = self.models[source_actor_name]

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
        self.models["result"] = result_mesh
        min_dist = result_mesh.get_array('Distance').min()
        self.min_distance_label.setText(f"{min_dist:.4f}")

        self.plotter_left.remove_actor("result", render=False)
        self.plotter_left.remove_scalar_bar()

        custom_lut = self.create_custom_colormap()
        self.plotter_left.add_mesh(result_mesh, name="result", scalars='Distance', lut=custom_lut, scalar_bar_args={'title': 'Distance (mm)'})

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

    def set_actor_visibility(self, name, visible, plotter):
        if name and name in plotter.actors:
            plotter.actors[name].SetVisibility(visible)

    def set_actor_opacity(self, name, opacity, plotter):
        if name and name in plotter.actors:
            plotter.actors[name].GetProperty().SetOpacity(opacity)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = JointSpaceVisualizerApp()
    window.show()
    sys.exit(app.exec_())
