# -*- coding: utf-8 -*-
"""Cấu hình dùng chung. Mọi hằng số ở một chỗ để đổi một lần là cả app đổi theo."""
import os
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
DATA = GOC / "data"
UPLOAD = DATA / "upload"      # file nhạc người dùng tải lên
WORK = DATA / "work"          # vocal tách ra, cache theo mã băm của file
OUT = DATA / "out"            # .srt/.lrc/.vtt xuất ra
CACHE = DATA / "cache"        # trọng số model tải về (không đụng ổ C)

for _p in (UPLOAD, WORK, OUT, CACHE):
    _p.mkdir(parents=True, exist_ok=True)

# Trọng số model để trong dự án, không rải vào %USERPROFILE% — đóng gói mang đi
# máy khách thì bê cả thư mục là chạy được.
os.environ.setdefault("TORCH_HOME", str(CACHE))
os.environ.setdefault("HF_HOME", str(CACHE / "hf"))

# Tần số lấy mẫu của model nhận âm vị. wav2vec2 chỉ ăn đúng 16 kHz.
SR_ALIGN = 16000
# Demucs được huấn luyện ở 44.1 kHz stereo, đưa khác đi là chất lượng tách tụt.
SR_SEP = 44100

# Card 4 GB: cắt nhỏ đoạn đưa vào Demucs cho khỏi tràn VRAM. Đơn vị là giây.
DEMUCS_SEGMENT = float(os.environ.get("DEMUCS_SEGMENT", "7.8"))

# Cho Demucs chạy chế độ tính hỗn hợp trên GPU: nhanh gấp 2,27 lần, sai lệch
# -62 dB dưới tín hiệu (không nghe ra). Đặt biến môi trường DEMUCS_FP32=1 nếu
# cần kết quả trùng khớp từng bit với bản đầy đủ.
NUA_DO_CHINH_XAC = os.environ.get("DEMUCS_FP32", "") == ""
# Cửa sổ tính xác suất âm vị, cũng để chặn VRAM. Có chồng lấn để không hụt
# ngữ cảnh ở mép cửa sổ.
EMIT_WINDOW = 30.0
EMIT_OVERLAP = 1.0

PORT = int(os.environ.get("PORT", "8770"))
