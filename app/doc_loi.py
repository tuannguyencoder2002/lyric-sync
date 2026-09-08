# -*- coding: utf-8 -*-
"""Đọc lời bài hát từ file, đủ mọi kiểu khách hay gửi tới.

Hai việc phải làm, và cả hai đều là chỗ dễ vỡ:

1. **Đoán bảng mã.** Word, Notepad, và các trang chép lời mỗi nơi đẻ ra một
   kiểu: UTF-8 có BOM, UTF-16, cp1252. Đọc cứng một bảng mã là gặp file thứ hai
   đã văng, hoặc tệ hơn là đọc ra chữ rác mà không báo lỗi gì.

2. **Bóc mốc thời gian cũ.** Khách gửi file .srt hoặc .lrc đã có mốc sẵn là
   chuyện thường — họ muốn căn lại cho khớp một bản thu khác. Không bóc thì
   "00:00:12,340 --> 00:00:15,120" bị coi là lời hát và cả bài lệch từ đó.
"""
import io
import re
from typing import Optional

# Mốc kiểu SRT/VTT nằm trên dòng riêng:  00:00:12,340 --> 00:00:15,120
MOC_SRT = re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*-->")
# Số thứ tự khối phụ đề, đứng một mình trên một dòng
SO_KHOI = re.compile(r"^\s*\d{1,5}\s*$")
# Mốc kiểu LRC ở đầu dòng:  [00:12.34]  — và mốc từng chữ  <00:12.34>
MOC_LRC = re.compile(r"^(\s*\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\])+")
MOC_CHU = re.compile(r"<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")
# Thẻ thông tin của LRC:  [ar:Tên ca sĩ], [ti:Tên bài]
THE_LRC = re.compile(r"^\s*\[[a-zA-Z#]{2,}:[^\]]*\]\s*$")


def _giai_ma(raw: bytes) -> str:
    """Đưa mảng byte về chuỗi, thử lần lượt cho tới khi ra chữ đọc được."""
    # BOM nói thẳng bảng mã là gì, tin nó trước.
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Không phải UTF-8 thì mới đoán. Đoán trước khi thử UTF-8 là sai hướng:
    # bộ đoán chỉ cho xác suất, còn UTF-8 giải mã trót lọt là chắc chắn đúng.
    try:
        import chardet
        doan = chardet.detect(raw)
        if doan and doan.get("encoding") and doan.get("confidence", 0) > 0.7:
            return raw.decode(doan["encoding"], errors="replace")
    except Exception:
        pass

    for ma in ("cp1252", "latin-1"):
        try:
            return raw.decode(ma)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _la_nhi_phan(raw: bytes) -> bool:
    """Đoán xem đây có phải file chữ không, TRƯỚC khi cố giải mã.

    Vì sao cần: giải mã kiểu latin-1 không bao giờ báo lỗi — nó ánh xạ được
    mọi byte. Thả nhầm một file mp3 vào là ra vài nghìn ký tự rác đổ thẳng vào
    ô nhập lời, rồi tool ngoan ngoãn đi căn cái đống rác đó. Thà chặn ở đây.

    Dấu hiệu: byte 0 (chữ thật gần như không bao giờ có), hoặc quá nhiều ký tự
    điều khiển.
    """
    mau = raw[:4096]
    if not mau:
        return False
    if b"\x00" in mau and not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    # Ký tự điều khiển, trừ xuống dòng, về đầu dòng, tab và xoá lùi trang.
    dieu_khien = sum(1 for b in mau if b < 32 and b not in (9, 10, 13, 12))
    return dieu_khien / len(mau) > 0.05


def _doc_docx(raw: bytes) -> Optional[str]:
    try:
        import docx
    except ImportError:
        return None
    tai_lieu = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in tai_lieu.paragraphs)


def _bo_moc(van_ban: str) -> tuple:
    """Bóc mốc thời gian nếu có. Trả về (lời sạch, tên định dạng nhận ra)."""
    cac_dong = van_ban.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    co_srt = any(MOC_SRT.match(d) for d in cac_dong)
    co_lrc = any(MOC_LRC.match(d) for d in cac_dong)

    if co_srt:
        giu = []
        for i, d in enumerate(cac_dong):
            if MOC_SRT.match(d) or d.strip().upper() == "WEBVTT":
                continue
            # Số thứ tự khối chỉ bị bỏ khi dòng NGAY SAU nó là một mốc thời
            # gian. Không kiểm điều đó thì một câu hát chỉ có mỗi chữ số —
            # ví dụ dòng "1993" — cũng bị xoá mất.
            if SO_KHOI.match(d) and i + 1 < len(cac_dong) and MOC_SRT.match(cac_dong[i + 1]):
                continue
            if not d.strip():
                # Dòng trống trong SRT là dấu ngăn giữa hai khối, không phải
                # một dòng lời. Giữ lại thì ô nhập đầy khoảng trắng, và số dòng
                # đếm ra không khớp với số câu người dùng nhìn thấy.
                continue
            giu.append(d)
        return _gon(giu), "srt"

    if co_lrc:
        giu = []
        for d in cac_dong:
            if THE_LRC.match(d):
                continue
            d = MOC_LRC.sub("", d)
            d = MOC_CHU.sub("", d)
            giu.append(d)
        return _gon(giu), "lrc"

    return _gon(cac_dong), "txt"


def _gon(cac_dong) -> str:
    """Bỏ khoảng trắng thừa hai đầu, và gộp nhiều dòng trống liền nhau về một."""
    ra, trong_truoc = [], False
    for d in cac_dong:
        d = d.strip()
        if not d:
            if not trong_truoc and ra:
                ra.append("")
            trong_truoc = True
            continue
        trong_truoc = False
        ra.append(d)
    while ra and not ra[-1]:
        ra.pop()
    return "\n".join(ra)


def doc(raw: bytes, ten_file: str = "") -> dict:
    """Trả về {'text', 'dang', 'so_dong'}."""
    if ten_file.lower().endswith(".docx"):
        van_ban = _doc_docx(raw)
        if van_ban is None:
            raise RuntimeError("python-docx is not installed, cannot read .docx")
        loi, _ = _bo_moc(van_ban)
        return {"text": loi, "dang": "docx",
                "so_dong": len([d for d in loi.split("\n") if d.strip()])}

    if _la_nhi_phan(raw):
        raise RuntimeError("this is not a text file — did you drop the audio here?")

    loi, dang = _bo_moc(_giai_ma(raw))
    return {"text": loi, "dang": dang,
            "so_dong": len([d for d in loi.split("\n") if d.strip()])}
