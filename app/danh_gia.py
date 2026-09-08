# -*- coding: utf-8 -*-
"""Chấm xem mốc thời gian có thật sự rơi vào chỗ có tiếng hát không.

Vì sao cần cái này bên cạnh điểm tin cậy của model: model âm vị được huấn
luyện trên tiếng NÓI. Đưa giọng HÁT vào thì nó luôn chấm thấp — đo thật trên
một bài có lời khớp và mốc đúng, điểm chỉ 0,39-0,68 trong khi cùng dây chuyền
đó chấm giọng đọc 0,87-0,98. Lấy điểm ấy tô màu cảnh báo là báo đỏ oan cả bài.

Thước đo ở đây không hỏi model, nó hỏi thẳng âm thanh: trong khoảng thời gian
ta gán cho một câu, có tiếng hát không, và ngay tại mốc mở câu năng lượng có
bật lên không. Thước này không phụ thuộc model, không phụ thuộc ngôn ngữ.
"""
import numpy as np

from . import audio as A
from . import config

KHOI = 320                 # 20 ms một điểm đo, bằng đúng bước của model âm vị
NUA_GIAY = 25              # 25 điểm = 0,5 giây


def do_do_khop(duong_dan_vocal: str, cau: list) -> dict:
    """Trả về {'ti_le', 'phu', 'mep': [...]} — 'mep' cùng thứ tự với `cau`."""
    if not cau:
        return {"ti_le": 0.0, "phu": 0.0, "mep": []}

    v = A.doc(duong_dan_vocal, config.SR_ALIGN, mono=True)[0]
    n = len(v) // KHOI
    if n < 2:
        return {"ti_le": 0.0, "phu": 0.0, "mep": [0.0] * len(cau)}

    # Đường bao năng lượng, mỗi điểm là mức hiệu dụng của 20 ms.
    nang = np.sqrt((v[:n * KHOI].reshape(n, KHOI) ** 2).mean(axis=1))
    t = np.arange(n) * KHOI / config.SR_ALIGN

    trong = np.zeros(n, dtype=bool)
    for c in cau:
        trong |= (t >= c["dau"]) & (t <= c["cuoi"])

    tb_trong = float(nang[trong].mean()) if trong.any() else 0.0
    tb_ngoai = float(nang[~trong].mean()) if (~trong).any() else 0.0

    mep = []
    for c in cau:
        i = int(c["dau"] * config.SR_ALIGN / KHOI)
        truoc = float(nang[max(0, i - NUA_GIAY):i].mean()) if i > 0 else 0.0
        sau = float(nang[i:i + NUA_GIAY].mean()) if i < n else 0.0
        # Bao nhiêu lần to lên ngay tại mốc mở câu. Mốc đúng thì con số này lớn,
        # mốc rơi vào giữa một câu đang hát thì nó quanh 1.
        mep.append(sau / max(truoc, 1e-6))

    return {
        "ti_le": tb_trong / max(tb_ngoai, 1e-9),
        "phu": float(trong.mean()),
        "mep": mep,
    }
