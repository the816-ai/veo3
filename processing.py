import os
import subprocess
from typing import List, Optional, Tuple

from delogo import DelogoPreset, compute_delogo_coords, infer_delogo_region
import cv2
import sys

# Resolve ffmpeg/ffprobe paths for portable builds (PyInstaller bundle or PATH)
def _resolve_ffmpeg_paths() -> Tuple[str, str]:
	# 1) Env overrides
	ffmpeg_env = os.environ.get("FFMPEG_PATH")
	ffprobe_env = os.environ.get("FFPROBE_PATH")
	if ffmpeg_env and ffprobe_env and os.path.exists(ffmpeg_env) and os.path.exists(ffprobe_env):
		return ffmpeg_env, ffprobe_env

	# 2) PyInstaller bundle (sys._MEIPASS)
	meipass = getattr(sys, "_MEIPASS", None)
	if meipass and os.path.isdir(meipass):
		ffmpeg_bundled = os.path.join(meipass, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
		ffprobe_bundled = os.path.join(meipass, "ffprobe.exe" if os.name == "nt" else "ffprobe")
		if os.path.exists(ffmpeg_bundled) and os.path.exists(ffprobe_bundled):
			return ffmpeg_bundled, ffprobe_bundled

	# 3) Local vendor folder next to app
	app_dir = os.path.dirname(os.path.abspath(getattr(sys, 'executable', sys.argv[0])))
	vendor_bin = os.path.join(app_dir, "ffmpeg", "bin")
	ffmpeg_local = os.path.join(vendor_bin, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
	ffprobe_local = os.path.join(vendor_bin, "ffprobe.exe" if os.name == "nt" else "ffprobe")
	if os.path.exists(ffmpeg_local) and os.path.exists(ffprobe_local):
		return ffmpeg_local, ffprobe_local

	# 4) Fallback to system PATH
	return "ffmpeg", "ffprobe"

_FFMPEG_BIN, _FFPROBE_BIN = _resolve_ffmpeg_paths()


class FFmpegPipelineBuilder:
	"""Xây dựng câu lệnh ffmpeg theo tùy chọn."""

	def __init__(self, input_files: List[str]):
		if not input_files:
			raise ValueError("input_files rỗng")
		self.input_files = input_files

		# Options
		self.force_vertical_4k = True
		self.force_fps60 = True
		self.use_sharpen = True
		self.use_color = True
		self.fast_mode = False
		self.hwaccel_decode = True
		self.filter_threads = 0
		self.transition: Optional[Tuple[str, float]] = None
		self.delogo_preset: Optional[DelogoPreset] = None
		self.delogo_box_size: Optional[Tuple[int, int]] = None
		self.delogo_margin: int = 30
		self.zoom_remove_logo = False
		self.zoom_factor = 1.05
		self.zoom_auto = False

		self.use_hevc = False
		self.bitrate_mbps = 12
		self.keep_audio = True
		self.reencode_metadata = True
		self.hide_qr = False

		# Performance
		self.use_nvenc = True
		self.encoder_preset = "fast"
		self.threads = 0  # 0 = auto
		self.faststart = True

		self.expected_total_duration_seconds: Optional[float] = None

		# Cinematic effects
		self.use_film_grain = False
		self.grain_strength = 0.5
		self.use_vignette = False
		self.vignette_strength = 0.3
		self.use_chromatic = False
		self.chromatic_strength = 0.2
		self.use_digital_noise = False
		self.noise_strength = 0.3
		self.use_lut = False
		self.lut_path: Optional[str] = None

	def set_speed_options(self, fast_mode: bool, hwaccel_decode: bool, filter_threads: int):
		self.fast_mode = fast_mode
		self.hwaccel_decode = hwaccel_decode
		self.filter_threads = filter_threads

	def set_zoom_options(self, enable: bool, factor: float, auto: bool):
		self.zoom_remove_logo = enable
		self.zoom_factor = max(1.01, min(1.20, factor))
		self.zoom_auto = auto

	def set_cinematic_effects(self, film_grain: bool = False, grain_strength: float = 0.5,
							  vignette: bool = False, vignette_strength: float = 0.3,
							  chromatic: bool = False, chromatic_strength: float = 0.2,
							  digital_noise: bool = False, noise_strength: float = 0.3,
							  use_lut: bool = False, lut_path: Optional[str] = None):
		"""Thiết lập các hiệu ứng cinematic để video trông giống quay thật"""
		self.use_film_grain = film_grain
		self.grain_strength = max(0.1, min(2.0, grain_strength))
		self.use_vignette = vignette
		self.vignette_strength = max(0.1, min(1.0, vignette_strength))
		self.use_chromatic = chromatic
		self.chromatic_strength = max(0.1, min(1.0, chromatic_strength))
		self.use_digital_noise = digital_noise
		self.noise_strength = max(0.1, min(1.0, noise_strength))
		self.use_lut = use_lut
		self.lut_path = lut_path

	# Configuration setters
	def set_target_vertical_4k(self, enable: bool):
		self.force_vertical_4k = enable

	def set_fps60(self, enable: bool):
		self.force_fps60 = enable

	def set_quality_filters(self, use_sharpen: bool, use_color: bool):
		self.use_sharpen = use_sharpen
		self.use_color = use_color

	def set_transition(self, type_name: str, duration_sec: float, smooth: bool = True):
		self.transition = (type_name, max(0.2, min(3.0, duration_sec)), smooth)

	def set_delogo(self, preset: DelogoPreset, box_size: Tuple[int, int], margin: int):
		self.delogo_preset = preset
		self.delogo_box_size = box_size
		self.delogo_margin = max(0, margin)

	def set_export(self, hevc: bool, bitrate_mbps: int, keep_audio: bool, reencode_metadata: bool = True, hide_qr: bool = False):
		self.use_hevc = hevc
		self.bitrate_mbps = bitrate_mbps
		self.keep_audio = keep_audio
		self.reencode_metadata = reencode_metadata
		self.hide_qr = hide_qr

	def set_performance(self, use_nvenc: bool, preset: str, threads: int, faststart: bool):
		self.use_nvenc = use_nvenc
		self.encoder_preset = preset
		self.threads = threads
		self.faststart = faststart

	# Helpers
	def _base_video_filter(self, force_vertical_4k: bool, use_sharpen: bool, use_color: bool, fast_mode: bool) -> str:
		filters = []
		if force_vertical_4k:
			if fast_mode:
				filters.append("scale=2160:3840:flags=bicubic:force_original_aspect_ratio=decrease")
			else:
				filters.append("scale=2160:3840:flags=lanczos:force_original_aspect_ratio=decrease")
			filters.append("pad=2160:3840:(ow-iw)/2:(oh-ih)/2:color=black")
		if (not fast_mode) and use_sharpen:
			filters.append("unsharp=5:5:1.0:5:5:0.0")
		if (not fast_mode) and use_color:
			filters.append("eq=contrast=1.05:brightness=0.02:saturation=1.03")
		
		# Thêm các hiệu ứng cinematic
		cinematic_filters = self._get_cinematic_filters()
		if cinematic_filters:
			filters.extend(cinematic_filters)
		
		vf = ",".join(filters) if filters else "null"
		return vf

	def _zoom_crop_filter(self, corner: str) -> str:
		# scale up then crop to 2160x3840, pushing crop window away from the corner containing the logo
		z = self.zoom_factor
		scale = f"scale=round(2160*{z}):round(3840*{z}):flags=bicubic"
		# choose crop anchor
		if corner == "top_right":
			crop = "crop=2160:3840:0:ih-3840"
		elif corner == "top_left":
			crop = "crop=2160:3840:iw-2160:ih-3840"
		elif corner == "bottom_right":
			crop = "crop=2160:3840:0:0"
		else:  # bottom_left
			crop = "crop=2160:3840:iw-2160:0"
		return f"{scale},{crop}"

	@staticmethod
	def _probe_duration(path: str) -> Optional[float]:
		try:
			res = subprocess.run([
				_FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
				"-of", "default=nw=1:nk=1", path
			], capture_output=True, text=True, check=True)
			val = float(res.stdout.strip())
			return val if val > 0 else None
		except Exception:
			return None

	@staticmethod
	def _probe_has_audio(path: str) -> bool:
		try:
			res = subprocess.run([
				_FFPROBE_BIN, "-v", "error", "-select_streams", "a:0",
				"-show_entries", "stream=index", "-of", "csv=p=0", path
			], capture_output=True, text=True, check=True)
			return res.stdout.strip() != ""
		except Exception:
			return False

	@staticmethod
	def _blur_overlay_expression(w: int, h: int, x: int, y: int) -> str:
		# Sử dụng giá trị boxblur trong giới hạn cho phép (tối đa 27)
		return f"split[base][crop];[crop]crop={w}:{h}:{x}:{y},boxblur=20:2[bl];[base][bl]overlay={x}:{y}"

	@staticmethod
	def _grab_first_frame(path: str):
		try:
			cap = cv2.VideoCapture(path)
			ok, frame = cap.read()
			cap.release()
			return frame if ok else None
		except Exception:
			return None

	def _auto_delogo_xy(self, default_size: Tuple[int, int]) -> Tuple[int, int, str]:
		w, h = default_size
		frame = self._grab_first_frame(self.input_files[0])
		if frame is None:
			# default to top_right
			x, y = compute_delogo_coords(DelogoPreset("top_right"), w, h, self.delogo_margin)
			return x, y, "top_right"
		x, y, _, _ = infer_delogo_region(frame, default_size, self.delogo_margin)
		# infer corner label by position
		corner = "top_right" if x > 1080 else "top_left"
		corner = "bottom_" + ("right" if corner.endswith("right") else "left") if y > 1920 else corner
		return x, y, corner

	def _compute_auto_zoom(self) -> float:
		if not self.delogo_box_size:
			return self.zoom_factor
		w, h = self.delogo_box_size
		m = max(0, self.delogo_margin)
		z = 1.0 + max((w + m) / 2160.0, (h + m) / 3840.0)
		return float(max(1.01, min(1.20, z)))

	def _build_concat_simple(self) -> Tuple[List[str], Optional[str]]:
		list_file = os.path.join(os.getcwd(), "_ffconcat.txt")
		with open(list_file, "w", encoding="utf-8") as f:
			for p in self.input_files:
				p_escaped = p.replace("'", "'\\''")
				f.write(f"file '{p_escaped}'\n")
		vf = self._base_video_filter(self.force_vertical_4k, self.use_sharpen, self.use_color, self.fast_mode)
		return ["-f", "concat", "-safe", "0", "-i", list_file, "-vf", vf], list_file

	def _build_two_inputs_with_transition(self) -> List[str]:
		tran_name = (self.transition[0] if self.transition else "Crossfade")
		tran_dur = (self.transition[1] if self.transition else 0.6)
		smooth_mode = (self.transition[2] if self.transition and len(self.transition) > 2 else True)

		# decide per-clip preprocessing chain
		corner_for_zoom = None
		# Disable zoom path when NVENC is used to tránh xung đột phần cứng
		if (not self.use_nvenc) and self.zoom_remove_logo and self.delogo_box_size and self.delogo_preset:
			w, h = self.delogo_box_size
			if self.delogo_preset.name == "auto":
				_, _, corner_for_zoom = self._auto_delogo_xy((w, h))
			else:
				corner_for_zoom = self.delogo_preset.name

		if corner_for_zoom:
			z = self._compute_auto_zoom() if self.zoom_auto else self.zoom_factor
			# patch zoom factor for filter string
			old = self.zoom_factor
			self.zoom_factor = z
			pre_base = self._zoom_crop_filter(corner_for_zoom)
			self.zoom_factor = old
		else:
			pre_base = self._base_video_filter(self.force_vertical_4k, self.use_sharpen, self.use_color, self.fast_mode)

		dur0 = self._probe_duration(self.input_files[0]) or 0.0
		dur1 = self._probe_duration(self.input_files[1]) or 0.0
		self.expected_total_duration_seconds = max(0.0, dur0 + dur1 - tran_dur)
		offset = max(0.0, dur0 - tran_dur)

		filters = []
		pre_v0 = f"[0:v]{pre_base}"
		pre_v1 = f"[1:v]{pre_base}"
		if self.force_fps60:
			pre_v0 += ",fps=60"
			pre_v1 += ",fps=60"
		filters.append(pre_v0 + "[v0]")
		filters.append(pre_v1 + "[v1]")
		# Cải thiện transition để mượt mà hơn, tránh nhiễu sóng
		xfade_params = self._get_smooth_xfade_params(tran_name, tran_dur, offset, smooth_mode)
		filters.append(f"[v0][v1]{xfade_params},format=yuv420p[vx]")

		# if not zooming, apply blur-overlay delogo
		if (not corner_for_zoom) and self.delogo_preset and self.delogo_box_size:
			w, h = self.delogo_box_size
			if self.delogo_preset.name == "auto":
				x, y, _ = self._auto_delogo_xy((w, h))
			else:
				x, y = compute_delogo_coords(self.delogo_preset, w, h, self.delogo_margin)
			filters.append(f"[vx]{self._blur_overlay_expression(w, h, x, y)}[vf]")
		else:
			filters.append("[vx]null[vf]")

		has_a0 = self._probe_has_audio(self.input_files[0])
		has_a1 = self._probe_has_audio(self.input_files[1])
		map_args: List[str] = []
		if self.keep_audio and (has_a0 or has_a1):
			# Cải thiện audio processing để mượt mà hơn
			filters.append("[0:a]aresample=async=1:first_pts=0,apad[a0]")
			filters.append("[1:a]aresample=async=1:first_pts=0,apad[a1]")
			# Audio transition với curve mượt mà hơn và anti-aliasing
			if smooth_mode:
				filters.append(f"[a0][a1]acrossfade=d={tran_dur}:c1=cos:c2=cos:o1=0:o2=0:curve1=cos:curve2=cos[af]")
			else:
				filters.append(f"[a0][a1]acrossfade=d={tran_dur}:c1=tri:c2=tri:o1=0:o2=0[af]")
			map_args = ["-map", "[vf]", "-map", "[af]"]
		else:
			map_args = ["-map", "[vf]", "-an"]

		filtergraph = ";".join(filters)
		return ["-i", self.input_files[0], "-i", self.input_files[1], "-filter_complex", filtergraph] + map_args

	def _append_delogo(self, cmd: List[str], already_has_filtergraph: bool) -> List[str]:
		if not self.delogo_preset or not self.delogo_box_size or self.zoom_remove_logo:
			return cmd
		if already_has_filtergraph:
			return cmd
		w, h = self.delogo_box_size
		x, y = compute_delogo_coords(self.delogo_preset, w, h, self.delogo_margin)
		blur_expr = self._blur_overlay_expression(w, h, x, y)
		if "-vf" in cmd:
			idx = cmd.index("-vf")
			current = cmd[idx + 1]
			cmd[idx + 1] = f"{current},{blur_expr}"
		else:
			cmd.extend(["-vf", blur_expr])
		return cmd

	def build(self) -> List[str]:
		cmd: List[str] = [_FFMPEG_BIN, "-y"]

		# HW decode flags
		if self.hwaccel_decode:
			cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])  # will fallback if not available

		has_complex = False
		if len(self.input_files) == 2 and self.transition is not None:
			cmd.extend(self._build_two_inputs_with_transition())
			has_complex = True
		else:
			concat_part, _ = self._build_concat_simple()
			cmd.extend(concat_part)

		if self.force_fps60 and not has_complex:
			if "-vf" in cmd:
				i = cmd.index("-vf")
				cmd[i + 1] = cmd[i + 1] + ",fps=60"
			else:
				cmd.extend(["-vf", "fps=60"])

		cmd = self._append_delogo(cmd, already_has_filtergraph=has_complex)

		# Select encoder
		video_encoder_args: List[str]
		if self.use_nvenc:
			video_encoder_args = ["-c:v", ("hevc_nvenc" if self.use_hevc else "h264_nvenc"), "-preset", self.encoder_preset, "-b:v", f"{self.bitrate_mbps}M", "-pix_fmt", "yuv420p"]
		else:
			if self.use_hevc:
				video_encoder_args = ["-c:v", "libx265", "-preset", self.encoder_preset, "-crf", "20", "-b:v", f"{self.bitrate_mbps}M", "-pix_fmt", "yuv420p"]
			else:
				video_encoder_args = ["-c:v", "libx264", "-preset", self.encoder_preset, "-crf", "18", "-tune", "film", "-b:v", f"{self.bitrate_mbps}M", "-pix_fmt", "yuv420p"]
		cmd.extend(video_encoder_args)

		# Audio
		if self.keep_audio and "-map" not in cmd:
			cmd.extend(["-c:a", "aac", "-b:a", "192k"])
		elif not self.keep_audio and "-map" not in cmd:
			cmd.extend(["-an"])
		if "-map" in cmd and "[af]" in cmd:
			cmd.extend(["-c:a", "aac", "-b:a", "192k"])

		# Threads
		if self.threads and self.threads > 0:
			cmd.extend(["-threads", str(self.threads)])
		if self.filter_threads and self.filter_threads > 0:
			cmd.extend(["-filter_threads", str(self.filter_threads)])

		# Faststart
		if self.faststart:
			cmd.extend(["-movflags", "+faststart"])

		if self.expected_total_duration_seconds and self.expected_total_duration_seconds > 0:
			cmd.extend(["-t", f"{self.expected_total_duration_seconds:.3f}", "-shortest"])
		else:
			cmd.extend(["-shortest"])  # safeguard

		# Metadata removal
		if self.reencode_metadata:
			cmd.extend(["-map_metadata", "-1"])  # Xóa tất cả metadata

		# QR code hiding (blur corners)
		if self.hide_qr:
			cmd = self._append_qr_blur(cmd, already_has_filtergraph=has_complex)

		return cmd

	def _append_qr_blur(self, cmd: List[str], already_has_filtergraph: bool = False) -> List[str]:
		"""Thêm blur cho các góc để ẩn QR code"""
		# Blur các góc của video để ẩn QR code
		qr_blur_filter = "split[base][qr1][qr2][qr3][qr4];[qr1]crop=200:200:0:0,boxblur=10:2[blur1];[qr2]crop=200:200:iw-200:0,boxblur=10:2[blur2];[qr3]crop=200:200:0:ih-200,boxblur=10:2[blur3];[qr4]crop=200:200:iw-200:ih-200,boxblur=10:2[blur4];[base][blur1]overlay=0:0[tmp1];[tmp1][blur2]overlay=iw-200:0[tmp2];[tmp2][blur3]overlay=0:ih-200[tmp3];[tmp3][blur4]overlay=iw-200:ih-200[final]"
		
		if already_has_filtergraph:
			# Nếu đã có filter graph, thêm vào cuối
			if "-filter_complex" in cmd:
				idx = cmd.index("-filter_complex")
				cmd[idx + 1] = cmd[idx + 1] + ";" + qr_blur_filter
			else:
				cmd.extend(["-filter_complex", qr_blur_filter])
			# Cập nhật map để sử dụng output cuối cùng
			if "-map" in cmd:
				map_idx = cmd.index("-map")
				cmd[map_idx + 1] = "[final]"
		else:
			# Tạo filter graph mới
			cmd.extend(["-vf", qr_blur_filter])
		
		return cmd

	def _get_smooth_xfade_params(self, transition: str, duration: float, offset: float, smooth: bool = True) -> str:
		"""Tạo tham số xfade mượt mà, tránh nhiễu sóng"""
		transition_map = {
			"Không": "xfade=transition=none:duration=0:offset=0",
			"Fade": "xfade=transition=fade:duration={duration}:offset={offset}",
			"Crossfade": "xfade=transition=dissolve:duration={duration}:offset={offset}",
			"Wipe (quét ngang)": "xfade=transition=wipeleft:duration={duration}:offset={offset}",
			"Slide (trượt)": "xfade=transition=slideleft:duration={duration}:offset={offset}",
			"Zoom (phóng to)": "xfade=transition=zoomin:duration={duration}:offset={offset}",
			"Blur (mờ nét)": "xfade=transition=fadegrays:duration={duration}:offset={offset}",
		}
		
		base_params = transition_map.get(transition, transition_map["Crossfade"])
		result = base_params.format(duration=duration, offset=offset)
		
		# Tạm thời tắt smooth mode để tránh lỗi eval=frame
		# if smooth and transition != "Không":
		# 	# Thêm anti-aliasing và interpolation mượt mà hơn
		# 	result += ":eval=frame"
		
		return result

	def _get_cinematic_filters(self) -> List[str]:
		"""Tạo các filter cinematic để video trông giống quay thật"""
		filters = []
		
		# Film Grain - nhiễu phim cổ điển (sử dụng noise đơn giản)
		if self.use_film_grain:
			strength = int(self.grain_strength * 20)  # 0.1-2.0 -> 2-40
			filters.append(f"noise=alls={strength}")
		
		# Vignette - tối góc để tập trung vào giữa (đơn giản hóa)
		if self.use_vignette:
			strength = int(self.vignette_strength * 100)  # 0.1-1.0 -> 10-100
			filters.append(f"vignette=PI/4:{strength}")
		
		# Chromatic Aberration - tạm thời tắt để tránh lỗi filter phức tạp
		# if self.use_chromatic:
		# 	strength = self.chromatic_strength * 0.1  # 0.1-1.0 -> 0.01-0.1
		# 	# Sử dụng filter đơn giản hơn để tránh lỗi
		# 	filters.append(f"split[base][red];[red]extractplanes=r[red_plane];[base]extractplanes=g+b[gb];[gb]blend=all_mode=addition:all_opacity={strength}")
		
		# Digital Noise - nhiễu số hiện đại (sử dụng noise đơn giản)
		if self.use_digital_noise:
			strength = int(self.noise_strength * 10)  # 0.1-1.0 -> 1-10
			filters.append(f"noise=alls={strength}")
		
		# LUT (Look-Up Table) - Color Grading
		if self.use_lut and self.lut_path and os.path.exists(self.lut_path):
			# FFmpeg hỗ trợ LUT với filter lut3d
			try:
				# Kiểm tra xem file LUT có tồn tại và có thể đọc được không
				with open(self.lut_path, 'r') as f:
					pass  # Chỉ kiểm tra file có thể mở được
				filters.append(f"lut3d={self.lut_path}")
			except Exception:
				# Nếu không thể đọc LUT, bỏ qua
				pass
		
		return filters


def _retry_with_cpu_encoder(cmd: List[str]) -> Optional[List[str]]:
	# Replace NVENC with CPU encoders
	new = list(cmd)
	if "h264_nvenc" in new:
		idx = new.index("h264_nvenc")
		new[idx] = "libx264"
		# remove NVENC-only options if any (keep preset)
		return new
	if "hevc_nvenc" in new:
		idx = new.index("hevc_nvenc")
		new[idx] = "libx265"
		return new
	return None


def _strip_hwaccel_flags(cmd: List[str]) -> List[str]:
	new = []
	i = 0
	while i < len(cmd):
		if cmd[i] == "-hwaccel":
			i += 2
			continue
		if cmd[i] == "-hwaccel_output_format":
			i += 2
			continue
		new.append(cmd[i])
		i += 1
	return new


def run_ffmpeg_with_progress(cmd: List[str], total_duration_hint: Optional[float], on_progress):
	if not (len(cmd) >= 2 and not cmd[-1].startswith("-")):
		from datetime import datetime
		out = f"output_{datetime.now().strftime('%Y%m%d_%H%M')}.mp4"
		cmd = list(cmd) + [out]

	def exec_once(c: List[str]) -> Tuple[int, str]:
		proc = subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		total = total_duration_hint
		stderr_acc = []
		while True:
			line = proc.stderr.readline()
			if not line:
				break
			stderr_acc.append(line)
			line_strip = line.strip()
			if on_progress:
				pct = None
				if "time=" in line_strip and total:
					try:
						tpart = line_strip.split("time=")[-1].split(" ")[0]
						h, m, s = tpart.split(":")
						cur = float(h) * 3600 + float(m) * 60 + float(s)
						if total and cur is not None and total > 0:
							pct = min(100.0, max(0.0, cur / total * 100.0))
					except Exception:
						pct = None
				on_progress(pct, line_strip)
		proc.wait()
		return proc.returncode, ''.join(stderr_acc)

	ret, err = exec_once(cmd)
	# Fallback for missing CUDA hwaccel
	cuda_err_markers = ["Cannot load nvcuda.dll", "Could not dynamically load CUDA", "device type cuda", "Hardware device setup failed"]
	if ret != 0 and any(m in err for m in cuda_err_markers):
		fallback_no_hw = _strip_hwaccel_flags(cmd)
		if on_progress:
			on_progress(None, "CUDA hwaccel không khả dụng. Đang thử lại với giải mã CPU...")
		ret, err = exec_once(fallback_no_hw)
		if ret == 0:
			return
		else:
			raise subprocess.CalledProcessError(ret, fallback_no_hw)

	# Fallback encoder if NVENC fails
	if ret != 0 and ("h264_nvenc" in cmd or "hevc_nvenc" in cmd):
		fallback = _retry_with_cpu_encoder(cmd)
		if fallback is not None:
			if on_progress:
				on_progress(None, "NVENC thất bại, đang thử lại với CPU encoder...")
			ret, err = exec_once(fallback)
			if ret == 0:
				return
			else:
				raise subprocess.CalledProcessError(ret, fallback)
	else:
		if ret != 0:
			raise subprocess.CalledProcessError(ret, cmd)
