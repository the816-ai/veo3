from dataclasses import dataclass
from typing import Tuple
import cv2
import numpy as np


@dataclass
class DelogoPreset:
	name: str  # internal key: top_right, top_left, bottom_right, bottom_left, auto

	@staticmethod
	def from_vn_name(vn: str) -> "DelogoPreset":
		mapping = {
			"Tự suy đoán góc": "auto",
			"Góc phải trên": "top_right",
			"Góc trái trên": "top_left",
			"Góc phải dưới": "bottom_right",
			"Góc trái dưới": "bottom_left",
		}
		key = mapping.get(vn, "auto")
		return DelogoPreset(name=key)


def compute_delogo_coords(preset: DelogoPreset, w: int, h: int, margin: int) -> Tuple[int, int]:
	"""Trả về (x, y) tương đối theo preset góc, giả định khung 2160x3840."""
	canvas_w, canvas_h = 2160, 3840
	if preset.name == "top_left":
		return margin, margin
	if preset.name == "top_right":
		return max(0, canvas_w - w - margin), margin
	if preset.name == "bottom_left":
		return margin, max(0, canvas_h - h - margin)
	if preset.name == "bottom_right":
		return max(0, canvas_w - w - margin), max(0, canvas_h - h - margin)
	# auto: tạm coi như top_right
	return max(0, canvas_w - w - margin), margin


def _compose_to_canvas_2160x3840(frame_bgr: np.ndarray) -> np.ndarray:
	"""Resize giữ tỉ lệ vào khung 2160x3840 và pad đen giống logic FFmpeg."""
	canvas_w, canvas_h = 2160, 3840
	h, w = frame_bgr.shape[:2]
	scale = min(canvas_w / w, canvas_h / h)
	new_w, new_h = int(w * scale), int(h * scale)
	resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
	canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
	off_x = (canvas_w - new_w) // 2
	off_y = (canvas_h - new_h) // 2
	canvas[off_y:off_y+new_h, off_x:off_x+new_w] = resized
	return canvas


def infer_delogo_region_auto(frame_bgr, default_size: Tuple[int, int], default_margin: int) -> Tuple[int, int, int, int]:
	"""Suy đoán góc watermark bằng cách đo độ tương phản/biên tại bốn góc.
	Trả về (x, y, w, h) trên canvas 2160x3840.
	"""
	w_box, h_box = default_size
	canvas = _compose_to_canvas_2160x3840(frame_bgr)
	gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)

	candidates = {
		"top_left": (default_margin, default_margin),
		"top_right": (2160 - w_box - default_margin, default_margin),
		"bottom_left": (default_margin, 3840 - h_box - default_margin),
		"bottom_right": (2160 - w_box - default_margin, 3840 - h_box - default_margin),
	}

	best_key = None
	best_score = -1.0
	best_xy = (default_margin, default_margin)
	for key, (x, y) in candidates.items():
		roi = gray[y:y+h_box, x:x+w_box]
		if roi.size == 0:
			continue
		# Score: mix of edge strength and brightness (typical watermark sáng)
		edges = cv2.Laplacian(roi, cv2.CV_32F)
		edge_var = float(edges.var())
		mean_val = float(roi.mean())
		score = edge_var * 0.7 + mean_val * 0.3
		if score > best_score:
			best_score = score
			best_xy = (x, y)
			best_key = key

	x, y = best_xy
	return x, y, w_box, h_box


def infer_delogo_region(frame_bgr, default_size: Tuple[int, int], default_margin: int) -> Tuple[int, int, int, int]:
	return infer_delogo_region_auto(frame_bgr, default_size, default_margin)
