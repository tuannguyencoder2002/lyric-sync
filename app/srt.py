# -*- coding: utf-8 -*-
"""Gộp mốc từng từ thành mốc từng câu rồi xuất .srt / .vtt / .lrc."""
from typing import List

from .lyrics import Dong

# Vào sớm một chút cho người đọc kịp, ra muộn một chút cho chữ khỏi biến mất
# ngay lúc còn đang ngân. Hai con số này là quy ước làm phụ đề, không phải đo đạc.
DEM_TRUOC = 0.08
DEM_SAU = 0.20
TOI_THIEU = 0.70          # câu ngắn hơn mức này thì mắt chưa kịp bắt


def gop_theo_dong(cac_dong: List[Dong], moc_tu: List[dict]) -> List[dict]:
    """Trả về [{'so','van_ban','dau','cuoi','diem','tu':[...]}] đã sắp xếp."""
    theo_dong = {}
    for m in moc_tu:
        theo_dong.setdefault(m["dong"], []).append(m)

    cau = []
    for d in cac_dong:
        ds = sorted(theo_dong.get(d.so, []), key=lambda m: m["dau"])
        if not ds:
            continue          # dòng không có từ nào hát được -> không thành phụ đề
        cau.append({
            "so": d.so,
            "van_ban": d.goc,
            "dau": ds[0]["dau"],
            "cuoi": ds[-1]["cuoi"],
            "diem": sum(m["diem"] for m in ds) / len(ds),
            "tu": ds,
        })

    cau.sort(key=lambda c: c["dau"])

    # Nới hai đầu nhưng không được giẫm lên câu bên cạnh: hai phụ đề chồng thời
    # gian là trình phát hiện đè lên nhau, xem rất rối.
    for i, c in enumerate(cau):
        truoc_het = cau[i - 1]["cuoi"] if i > 0 else 0.0
        sau_bat_dau = cau[i + 1]["dau"] if i + 1 < len(cau) else c["cuoi"] + 10.0
        c["dau"] = max(truoc_het + 0.01, c["dau"] - DEM_TRUOC, 0.0)
        c["cuoi"] = min(sau_bat_dau - 0.01, c["cuoi"] + DEM_SAU)
        if c["cuoi"] - c["dau"] < TOI_THIEU:
            c["cuoi"] = min(sau_bat_dau - 0.01, c["dau"] + TOI_THIEU)
        if c["cuoi"] <= c["dau"]:
            c["cuoi"] = c["dau"] + 0.30
    return cau


def _gio_srt(t: float) -> str:
    t = max(0.0, t)
    g = int(t // 3600)
    p = int((t % 3600) // 60)
    s = t % 60
    return f"{g:02d}:{p:02d}:{s:06.3f}".replace(".", ",")


def _gio_vtt(t: float) -> str:
    return _gio_srt(t).replace(",", ".")


def _gio_lrc(t: float) -> str:
    t = max(0.0, t)
    p = int(t // 60)
    s = t % 60
    return f"[{p:02d}:{s:05.2f}]"


def ra_srt(cau: List[dict]) -> str:
    khoi = []
    for i, c in enumerate(cau, 1):
        khoi.append(f"{i}\n{_gio_srt(c['dau'])} --> {_gio_srt(c['cuoi'])}\n{c['van_ban']}\n")
    return "\n".join(khoi)


def ra_vtt(cau: List[dict]) -> str:
    khoi = ["WEBVTT\n"]
    for c in cau:
        khoi.append(f"{_gio_vtt(c['dau'])} --> {_gio_vtt(c['cuoi'])}\n{c['van_ban']}\n")
    return "\n".join(khoi)


def ra_lrc(cau: List[dict], theo_tung_chu: bool = False) -> str:
    """LRC thường, hoặc LRC mở rộng có mốc từng chữ để chạy chữ kiểu karaoke."""
    dong = []
    for c in cau:
        if theo_tung_chu:
            phan = "".join(f"<{_gio_lrc(t['dau'])[1:-1]}>{t['goc']} " for t in c["tu"])
            dong.append(f"{_gio_lrc(c['dau'])}{phan.strip()}")
        else:
            dong.append(f"{_gio_lrc(c['dau'])}{c['van_ban']}")
    return "\n".join(dong)


def ra_srt_tung_chu(cau: List[dict]) -> str:
    """Mỗi chữ một khối phụ đề — dùng cho video chạy chữ từng từ."""
    khoi = []
    n = 1
    for c in cau:
        for t in c["tu"]:
            cuoi = max(t["cuoi"], t["dau"] + 0.12)
            khoi.append(f"{n}\n{_gio_srt(t['dau'])} --> {_gio_srt(cuoi)}\n{t['goc']}\n")
            n += 1
    return "\n".join(khoi)
