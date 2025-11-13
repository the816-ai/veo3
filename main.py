import os
import sys
import subprocess
import datetime
from typing import List, Optional, Tuple

from PyQt5 import QtWidgets, QtCore

from processing import FFmpegPipelineBuilder, run_ffmpeg_with_progress
from delogo import DelogoPreset


class LogTextEdit(QtWidgets.QPlainTextEdit):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setReadOnly(True)
		self.setMaximumBlockCount(1000)

	def append_line(self, text: str) -> None:
		self.appendPlainText(text)
		self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class VideoToolUI(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Trình ghép & nâng cấp video 9:16 (TikTok) - Tiếng Việt")
		self.resize(1200, 900)
		self.setMinimumSize(1000, 700)

		# State
		self.input_files: List[str] = []
		self.output_path: Optional[str] = None
		self.lut_path: Optional[str] = None

		# Widgets
		self.btn_select_files = QtWidgets.QPushButton("Chọn video...")
		self.btn_select_folder = QtWidgets.QPushButton("Chọn thư mục...")
		self.list_inputs = QtWidgets.QListWidget()
		self.list_inputs.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		self.btn_remove_selected = QtWidgets.QPushButton("Xóa mục đã chọn")
		self.btn_clear = QtWidgets.QPushButton("Xóa tất cả")

		self.chk_loop_if_single = QtWidgets.QCheckBox("Nếu chỉ 1 video → tự động lặp lại để đủ thời lượng")
		self.chk_loop_if_single.setChecked(True)

		self.grp_transition = QtWidgets.QGroupBox("Transition giữa 2 clip")
		self.cmb_transition = QtWidgets.QComboBox()
		self.cmb_transition.addItems([
			"Không", 
			"Fade", 
			"Crossfade",
			"Wipe (quét ngang)",
			"Slide (trượt)",
			"Zoom (phóng to)",
			"Blur (mờ nét)",
		])
		self.cmb_transition.setCurrentText("Crossfade")
		self.spin_trans_duration = QtWidgets.QDoubleSpinBox()
		self.spin_trans_duration.setSuffix(" s")
		self.spin_trans_duration.setDecimals(1)
		self.spin_trans_duration.setRange(0.2, 3.0)
		self.spin_trans_duration.setValue(0.8)
		self.chk_smooth_transition = QtWidgets.QCheckBox("⚠️ Transition mượt mà (có thể gây lỗi - tắt nếu lỗi)")
		self.chk_smooth_transition.setChecked(False)  # Tắt mặc định để tránh lỗi
		trans_layout = QtWidgets.QFormLayout()
		trans_layout.addRow("Loại:", self.cmb_transition)
		trans_layout.addRow("Thời gian:", self.spin_trans_duration)
		trans_layout.addRow(self.chk_smooth_transition)
		self.grp_transition.setLayout(trans_layout)

		self.grp_quality = QtWidgets.QGroupBox("Chuẩn hóa & chất lượng")
		self.chk_auto_mode = QtWidgets.QCheckBox("🎯 CHẾ ĐỘ AUTO - Tự động áp dụng tất cả settings tối ưu")
		self.chk_auto_mode.setChecked(True)
		self.chk_auto_mode.setStyleSheet("font-weight: bold; color: #2E8B57;")
		self.chk_force_9_16 = QtWidgets.QCheckBox("Ép về 9:16 (2160x3840 dọc), crop/fit tự động")
		self.chk_force_9_16.setChecked(True)
		self.chk_60fps = QtWidgets.QCheckBox("Ép về 60fps mượt")
		self.chk_60fps.setChecked(True)
		self.chk_sharpen = QtWidgets.QCheckBox("Làm nét (unsharp)")
		self.chk_sharpen.setChecked(True)
		self.chk_color = QtWidgets.QCheckBox("Tự động chỉnh màu (sáng/độ tương phản/màu)")
		self.chk_color.setChecked(True)
		self.chk_max_speed = QtWidgets.QCheckBox("Tăng tốc tối đa (giảm filter, scale nhanh)")
		self.chk_max_speed.setChecked(False)
		quality_layout = QtWidgets.QVBoxLayout()
		quality_layout.addWidget(self.chk_auto_mode)
		quality_layout.addWidget(QtWidgets.QLabel(""))  # Spacer
		quality_layout.addWidget(self.chk_force_9_16)
		quality_layout.addWidget(self.chk_60fps)
		quality_layout.addWidget(self.chk_sharpen)
		quality_layout.addWidget(self.chk_color)
		quality_layout.addWidget(self.chk_max_speed)
		self.grp_quality.setLayout(quality_layout)

		self.grp_cinematic = QtWidgets.QGroupBox("Hiệu ứng Cinematic (giống quay thật)")
		self.chk_film_grain = QtWidgets.QCheckBox("Film Grain (nhiễu phim)")
		self.chk_film_grain.setChecked(False)
		self.spin_grain_strength = QtWidgets.QDoubleSpinBox()
		self.spin_grain_strength.setRange(0.1, 2.0)
		self.spin_grain_strength.setDecimals(1)
		self.spin_grain_strength.setValue(0.5)
		self.spin_grain_strength.setSuffix("x")
		
		self.chk_vignette = QtWidgets.QCheckBox("Vignette (tối góc)")
		self.chk_vignette.setChecked(False)
		self.spin_vignette_strength = QtWidgets.QDoubleSpinBox()
		self.spin_vignette_strength.setRange(0.1, 1.0)
		self.spin_vignette_strength.setDecimals(1)
		self.spin_vignette_strength.setValue(0.3)
		self.spin_vignette_strength.setSuffix("x")
		
		self.chk_chromatic = QtWidgets.QCheckBox("Chromatic Aberration (lệch màu)")
		self.chk_chromatic.setChecked(False)
		self.spin_chromatic_strength = QtWidgets.QDoubleSpinBox()
		self.spin_chromatic_strength.setRange(0.1, 1.0)
		self.spin_chromatic_strength.setDecimals(1)
		self.spin_chromatic_strength.setValue(0.2)
		self.spin_chromatic_strength.setSuffix("x")
		
		self.chk_digital_noise = QtWidgets.QCheckBox("Digital Noise (nhiễu số)")
		self.chk_digital_noise.setChecked(False)
		self.spin_noise_strength = QtWidgets.QDoubleSpinBox()
		self.spin_noise_strength.setRange(0.1, 1.0)
		self.spin_noise_strength.setDecimals(1)
		self.spin_noise_strength.setValue(0.3)
		self.spin_noise_strength.setSuffix("x")
		
		cinematic_layout = QtWidgets.QFormLayout()
		cinematic_layout.addRow(self.chk_film_grain)
		cinematic_layout.addRow("Cường độ Grain:", self.spin_grain_strength)
		cinematic_layout.addRow(self.chk_vignette)
		cinematic_layout.addRow("Cường độ Vignette:", self.spin_vignette_strength)
		cinematic_layout.addRow(self.chk_chromatic)
		cinematic_layout.addRow("Cường độ Chromatic:", self.spin_chromatic_strength)
		cinematic_layout.addRow(self.chk_digital_noise)
		cinematic_layout.addRow("Cường độ Noise:", self.spin_noise_strength)
		
		# LUT (Look-Up Table) support
		self.chk_use_lut = QtWidgets.QCheckBox("Sử dụng LUT (Color Grading)")
		self.chk_use_lut.setChecked(False)
		self.btn_select_lut = QtWidgets.QPushButton("Chọn file LUT (.cube)")
		self.lut_path_label = QtWidgets.QLabel("Chưa chọn LUT")
		self.lut_path_label.setStyleSheet("color: gray; font-style: italic;")
		
		cinematic_layout.addRow(self.chk_use_lut)
		cinematic_layout.addRow("File LUT:", self.btn_select_lut)
		cinematic_layout.addRow("", self.lut_path_label)
		self.grp_cinematic.setLayout(cinematic_layout)

		self.grp_delogo = QtWidgets.QGroupBox("Xóa logo/Watermark")
		self.chk_delogo = QtWidgets.QCheckBox("Bật xóa logo")
		self.chk_delogo.setChecked(False)  # Tắt mặc định
		self.cmb_delogo_preset = QtWidgets.QComboBox()
		self.cmb_delogo_preset.addItems([
			"Tự suy đoán góc",
			"Góc phải trên",
			"Góc trái trên", 
			"Góc phải dưới",
			"Góc trái dưới",
		])
		self.cmb_delogo_preset.setCurrentText("Tự suy đoán góc")
		self.spin_delogo_w = QtWidgets.QSpinBox(); self.spin_delogo_w.setRange(10, 1000); self.spin_delogo_w.setValue(260)
		self.spin_delogo_h = QtWidgets.QSpinBox(); self.spin_delogo_h.setRange(10, 1000); self.spin_delogo_h.setValue(110)
		self.spin_delogo_margin = QtWidgets.QSpinBox(); self.spin_delogo_margin.setRange(0, 200); self.spin_delogo_margin.setValue(30)
		self.chk_zoom_logo = QtWidgets.QCheckBox("Zoom nhẹ để loại bỏ logo (1-8%)")
		self.chk_zoom_logo.setChecked(False)
		self.chk_zoom_auto = QtWidgets.QCheckBox("Tự tính hệ số theo kích thước logo")
		self.chk_zoom_auto.setChecked(False)
		self.spin_zoom = QtWidgets.QDoubleSpinBox(); self.spin_zoom.setRange(1.01, 1.20); self.spin_zoom.setDecimals(2); self.spin_zoom.setValue(1.05)
		delogo_form = QtWidgets.QFormLayout()
		delogo_form.addRow(self.chk_delogo)
		delogo_form.addRow("Preset:", self.cmb_delogo_preset)
		delogo_form.addRow("Rộng (px):", self.spin_delogo_w)
		delogo_form.addRow("Cao (px):", self.spin_delogo_h)
		delogo_form.addRow("Lề từ góc (px):", self.spin_delogo_margin)
		delogo_form.addRow(self.chk_zoom_logo)
		delogo_form.addRow(self.chk_zoom_auto)
		delogo_form.addRow("Hệ số zoom:", self.spin_zoom)
		self.grp_delogo.setLayout(delogo_form)

		self.grp_export = QtWidgets.QGroupBox("Xuất file")
		self.cmb_codec = QtWidgets.QComboBox(); self.cmb_codec.addItems(["H.264", "H.265"]) 
		self.spin_bitrate = QtWidgets.QSpinBox(); self.spin_bitrate.setRange(2, 50); self.spin_bitrate.setValue(12); self.spin_bitrate.setSuffix(" Mbps")
		self.chk_keep_audio = QtWidgets.QCheckBox("Giữ âm thanh gốc (nếu có)")
		self.chk_keep_audio.setChecked(True)
		self.chk_mute_all = QtWidgets.QCheckBox("Tắt tất cả âm thanh")
		self.chk_mute_all.setChecked(True)
		self.chk_reencode_metadata = QtWidgets.QCheckBox("Re-encode xóa metadata")
		self.chk_reencode_metadata.setChecked(True)
		self.chk_hide_qr = QtWidgets.QCheckBox("Ẩn QR code (blur vùng góc)")
		self.chk_hide_qr.setChecked(False)
		self.btn_save_as = QtWidgets.QPushButton("Chọn nơi lưu (Save As)...")
		export_form = QtWidgets.QFormLayout()
		export_form.addRow("Codec:", self.cmb_codec)
		export_form.addRow("Bitrate:", self.spin_bitrate)
		export_form.addRow(self.chk_keep_audio)
		export_form.addRow(self.chk_mute_all)
		export_form.addRow(self.chk_reencode_metadata)
		export_form.addRow(self.chk_hide_qr)
		export_form.addRow(self.btn_save_as)
		self.grp_export.setLayout(export_form)

		self.grp_perf = QtWidgets.QGroupBox("Tối ưu tốc độ")
		# Xóa NVENC/CUDA hoàn toàn để tránh lỗi
		# self.chk_use_nvenc = QtWidgets.QCheckBox("⚠️ Dùng GPU NVENC (có thể gây lỗi - tắt nếu lỗi)")
		# self.chk_use_nvenc.setChecked(False)  # Tắt mặc định để tránh lỗi
		# self.chk_hwaccel = QtWidgets.QCheckBox("⚠️ Giải mã GPU (CUDA) - có thể gây lỗi")
		# self.chk_hwaccel.setChecked(False)  # Tắt mặc định để tránh lỗi
		self.cmb_preset = QtWidgets.QComboBox(); self.cmb_preset.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"]) 
		self.cmb_preset.setCurrentText("fast")
		self.spin_threads = QtWidgets.QSpinBox(); self.spin_threads.setRange(0, 32); self.spin_threads.setValue(0)
		self.spin_threads.setToolTip("0 = auto theo FFmpeg")
		self.spin_filter_threads = QtWidgets.QSpinBox(); self.spin_filter_threads.setRange(0, 32); self.spin_filter_threads.setValue(0)
		self.spin_filter_threads.setToolTip("Luồng filter; 0 = để FFmpeg tự chọn")
		self.chk_faststart = QtWidgets.QCheckBox("-movflags +faststart (tối ưu phát trực tuyến)")
		self.chk_faststart.setChecked(True)
		perf_form = QtWidgets.QFormLayout()
		# perf_form.addRow(self.chk_use_nvenc)
		# perf_form.addRow(self.chk_hwaccel)
		perf_form.addRow("Encoder preset:", self.cmb_preset)
		perf_form.addRow("Threads:", self.spin_threads)
		perf_form.addRow("Filter threads:", self.spin_filter_threads)
		perf_form.addRow(self.chk_faststart)
		self.grp_perf.setLayout(perf_form)

		self.progress = QtWidgets.QProgressBar()
		self.progress.setRange(0, 100)
		self.txt_log = LogTextEdit()

		self.btn_start = QtWidgets.QPushButton("Bắt đầu xử lý")
		self.btn_start.setStyleSheet("font-weight: bold")

		# Layout
		left_col = QtWidgets.QVBoxLayout()
		file_btns = QtWidgets.QHBoxLayout()
		file_btns.addWidget(self.btn_select_files)
		file_btns.addWidget(self.btn_select_folder)
		left_col.addLayout(file_btns)
		left_col.addWidget(self.list_inputs, 1)
		rm_btns = QtWidgets.QHBoxLayout()
		rm_btns.addWidget(self.btn_remove_selected)
		rm_btns.addWidget(self.btn_clear)
		left_col.addLayout(rm_btns)

		# Right column with scroll area
		right_scroll = QtWidgets.QScrollArea()
		right_scroll.setWidgetResizable(True)
		right_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		right_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		
		right_widget = QtWidgets.QWidget()
		right_col = QtWidgets.QVBoxLayout(right_widget)
		right_col.addWidget(self.grp_transition)
		right_col.addWidget(self.grp_quality)
		right_col.addWidget(self.grp_cinematic)
		right_col.addWidget(self.grp_delogo)  # Khôi phục delogo
		right_col.addWidget(self.grp_export)
		right_col.addWidget(self.grp_perf)
		right_col.addStretch(1)
		
		right_scroll.setWidget(right_widget)

		top = QtWidgets.QHBoxLayout()
		top.addLayout(left_col, 2)
		top.addWidget(right_scroll, 3)

		bottom = QtWidgets.QVBoxLayout()
		bottom.addWidget(self.progress)
		bottom.addWidget(self.txt_log, 1)
		bottom.addWidget(self.btn_start)

		root = QtWidgets.QVBoxLayout(self)
		root.addLayout(top, 3)
		root.addLayout(bottom, 2)

		# Signals
		self.btn_select_files.clicked.connect(self.on_select_files)
		self.btn_select_folder.clicked.connect(self.on_select_folder)
		self.btn_remove_selected.clicked.connect(self.on_remove_selected)
		self.btn_clear.clicked.connect(self.on_clear)
		self.btn_save_as.clicked.connect(self.on_save_as)
		self.btn_select_lut.clicked.connect(self.on_select_lut)
		self.btn_start.clicked.connect(self.on_start)
		self.chk_auto_mode.toggled.connect(self.on_auto_mode_toggled)

	def log(self, msg: str) -> None:
		self.txt_log.append_line(msg)

	def on_auto_mode_toggled(self, checked: bool):
		"""Tự động bật/tắt tất cả settings khi chọn chế độ auto"""
		if checked:
			# Chế độ AUTO - Bật settings an toàn (không gây lỗi)
			self.chk_force_9_16.setChecked(True)
			self.chk_60fps.setChecked(True)
			self.chk_sharpen.setChecked(True)
			self.chk_color.setChecked(True)
			self.chk_delogo.setChecked(True)  # Bật delogo trong auto mode
			# Tắt các tính năng có thể gây lỗi
			# NVENC/CUDA đã bị xóa hoàn toàn
			self.chk_smooth_transition.setChecked(False)  # Tắt transition mượt để tránh lỗi
			self.chk_faststart.setChecked(True)
			self.cmb_transition.setCurrentText("Crossfade")
			self.spin_trans_duration.setValue(0.8)
			self.cmb_delogo_preset.setCurrentText("Tự suy đoán góc")
			self.cmb_preset.setCurrentText("fast")
			self.cmb_codec.setCurrentText("H.264")
			self.spin_bitrate.setValue(12)
			self.chk_mute_all.setChecked(True)
			self.chk_reencode_metadata.setChecked(True)  # Bật re-encode metadata
			self.chk_hide_qr.setChecked(False)  # Tắt QR blur mặc định
			self.log("🎯 Đã bật CHẾ ĐỘ AUTO - Settings an toàn (không gây lỗi)!")
		else:
			self.log("⚠️ Đã tắt chế độ auto - Bạn có thể tự điều chỉnh settings")

	def on_select_files(self):
		files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Chọn video", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)")
		if files:
			for f in files:
				if f not in self.input_files:
					self.input_files.append(f)
					self.list_inputs.addItem(f)

	def on_select_folder(self):
		folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa video")
		if folder:
			exts = (".mp4", ".mov", ".mkv", ".avi", ".webm")
			items = sorted([os.path.join(folder, x) for x in os.listdir(folder) if x.lower().endswith(exts)])
			for f in items:
				if f not in self.input_files:
					self.input_files.append(f)
					self.list_inputs.addItem(f)

	def on_remove_selected(self):
		for item in self.list_inputs.selectedItems():
			row = self.list_inputs.row(item)
			self.list_inputs.takeItem(row)
		self.input_files = [self.list_inputs.item(i).text() for i in range(self.list_inputs.count())]

	def on_clear(self):
		self.list_inputs.clear()
		self.input_files = []

	def on_save_as(self):
		now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
		suggested = f"output_{now}.mp4"
		path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Chọn nơi lưu", suggested, "MP4 (*.mp4)")
		if path:
			if not path.lower().endswith(".mp4"):
				path += ".mp4"
			self.output_path = path
			self.log(f"Sẽ lưu file: {self.output_path}")

	def on_select_lut(self):
		path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn file LUT", "", "LUT files (*.cube *.3dl *.dat)")
		if path:
			self.lut_path = path
			filename = os.path.basename(path)
			self.lut_path_label.setText(filename)
			self.lut_path_label.setStyleSheet("color: green; font-weight: bold;")
			self.log(f"Đã chọn LUT: {filename}")

	def build_pipeline(self) -> Tuple[List[str], Optional[float]]:
		if not self.input_files:
			raise RuntimeError("Vui lòng chọn ít nhất 1 video")

		inputs = list(self.input_files)
		if len(inputs) == 1 and self.chk_loop_if_single.isChecked():
			inputs.append(inputs[0])

		# Export options
		use_h265 = (self.cmb_codec.currentText() == "H.265")
		bitrate_mbps = self.spin_bitrate.value()
		keep_audio = self.chk_keep_audio.isChecked()
		mute_all = self.chk_mute_all.isChecked()
		reencode_metadata = self.chk_reencode_metadata.isChecked()
		hide_qr = self.chk_hide_qr.isChecked()

		# Processing options
		auto_mode = self.chk_auto_mode.isChecked()
		transition = self.cmb_transition.currentText()
		trans_dur = float(self.spin_trans_duration.value())
		smooth_transition = self.chk_smooth_transition.isChecked()
		force_9_16 = self.chk_force_9_16.isChecked()
		force_60 = self.chk_60fps.isChecked()
		use_sharpen = self.chk_sharpen.isChecked() and not self.chk_max_speed.isChecked()
		use_color = self.chk_color.isChecked() and not self.chk_max_speed.isChecked()
		fast_mode = self.chk_max_speed.isChecked()

		# Cinematic effects
		use_film_grain = self.chk_film_grain.isChecked()
		grain_strength = float(self.spin_grain_strength.value())
		use_vignette = self.chk_vignette.isChecked()
		vignette_strength = float(self.spin_vignette_strength.value())
		use_chromatic = self.chk_chromatic.isChecked()
		chromatic_strength = float(self.spin_chromatic_strength.value())
		use_digital_noise = self.chk_digital_noise.isChecked()
		noise_strength = float(self.spin_noise_strength.value())
		use_lut = self.chk_use_lut.isChecked()

		use_delogo = self.chk_delogo.isChecked()
		delogo_preset = self.cmb_delogo_preset.currentText()
		delogo_w = int(self.spin_delogo_w.value())
		delogo_h = int(self.spin_delogo_h.value())
		delogo_margin = int(self.spin_delogo_margin.value())
		zoom_logo = self.chk_zoom_logo.isChecked()
		zoom_auto = self.chk_zoom_auto.isChecked()
		zoom_factor = float(self.spin_zoom.value())

		# Performance options (NVENC/CUDA đã bị xóa)
		# use_nvenc = self.chk_use_nvenc.isChecked()
		# use_hwaccel = self.chk_hwaccel.isChecked()
		preset = self.cmb_preset.currentText()
		threads = int(self.spin_threads.value())
		filter_threads = int(self.spin_filter_threads.value())
		faststart = self.chk_faststart.isChecked()

		# Build
		if auto_mode:
			self.log("🎯 Đang sử dụng CHẾ ĐỘ AUTO - Tất cả settings đã được tối ưu!")
		
		builder = FFmpegPipelineBuilder(inputs)
		builder.set_target_vertical_4k(force_9_16)
		builder.set_fps60(force_60)
		builder.set_quality_filters(use_sharpen=use_sharpen, use_color=use_color)
		builder.set_speed_options(fast_mode=fast_mode, hwaccel_decode=False, filter_threads=filter_threads)  # Tắt hwaccel
		builder.set_zoom_options(enable=zoom_logo, factor=zoom_factor, auto=zoom_auto)
		builder.set_cinematic_effects(
			film_grain=use_film_grain, grain_strength=grain_strength,
			vignette=use_vignette, vignette_strength=vignette_strength,
			chromatic=use_chromatic, chromatic_strength=chromatic_strength,
			digital_noise=use_digital_noise, noise_strength=noise_strength,
			use_lut=use_lut, lut_path=self.lut_path
		)

		if use_delogo:
			preset_dl = DelogoPreset.from_vn_name(delogo_preset)
			builder.set_delogo(preset=preset_dl, box_size=(delogo_w, delogo_h), margin=delogo_margin)

		if transition != "Không" and len(inputs) == 2:
			builder.set_transition(transition, trans_dur, smooth_transition)

		builder.set_export(hevc=use_h265, bitrate_mbps=bitrate_mbps, keep_audio=(False if mute_all else keep_audio), reencode_metadata=reencode_metadata, hide_qr=hide_qr)
		builder.set_performance(use_nvenc=False, preset=preset, threads=threads, faststart=faststart)  # Tắt NVENC

		cmd = builder.build()
		# append output
		if self.output_path:
			cmd = cmd + [self.output_path]
		else:
			now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
			cmd = cmd + [os.path.join(os.getcwd(), f"output_{now}.mp4")]
		return cmd, None

	def on_start(self):
		try:
			cmd, total_secs = self.build_pipeline()

			self.progress.setValue(0)
			self.txt_log.clear()
			self.btn_start.setEnabled(False)

			def on_progress(pct: Optional[float], line: str):
				if pct is not None:
					self.progress.setValue(int(max(0, min(100, pct))))
				if line:
					self.log(line)

			QtCore.QTimer.singleShot(50, lambda: self._run_cmd(cmd, total_secs, on_progress))
		except Exception as e:
			QtWidgets.QMessageBox.critical(self, "Lỗi", str(e))

	def _run_cmd(self, cmd: List[str], total_secs: Optional[float], cb):
		try:
			run_ffmpeg_with_progress(cmd, total_duration_hint=total_secs, on_progress=cb)
			self.progress.setValue(100)
			out_path = cmd[-1] if cmd and not cmd[-1].startswith("-") else ""
			self.log(f"Hoàn tất! Đã lưu: {out_path}")
			# Auto clear input list to chọn 2 video mới dễ hơn
			self.list_inputs.clear()
			self.input_files = []
			self.output_path = None
			# Reset LUT
			self.lut_path = None
			self.lut_path_label.setText("Chưa chọn LUT")
			self.lut_path_label.setStyleSheet("color: gray; font-style: italic;")
		except FileNotFoundError:
			QtWidgets.QMessageBox.critical(self, "Thiếu FFmpeg", "Không tìm thấy ffmpeg trong PATH. Vui lòng cài ffmpeg và mở lại ứng dụng.")
		except subprocess.CalledProcessError as e:
			self.log(str(e))
			QtWidgets.QMessageBox.critical(self, "Lỗi xử lý", "FFmpeg báo lỗi. Xem log để biết thêm chi tiết.")
		finally:
			self.btn_start.setEnabled(True)


def main():
	app = QtWidgets.QApplication(sys.argv)
	ui = VideoToolUI()
	ui.show()
	sys.exit(app.exec_())


if __name__ == "__main__":
	main()
