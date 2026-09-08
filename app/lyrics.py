# -*- coding: utf-8 -*-
"""Biến lời bài hát dạng chữ thành thứ model căn được.

Model wav2vec2 tiếng Anh chỉ biết 26 chữ cái và dấu nháy đơn. Mọi thứ khác —
dấu câu, số, ký tự lạ — phải quy về đó, nếu không thì tra bảng chữ cái là văng
lỗi và cả bài không căn được chỉ vì một dấu phẩy.
"""
import re
from dataclasses import dataclass, field
from typing import List

# Nhãn đoạn: [Verse 1], (Chorus), Bridge:. Người chép lời hay để lẫn vào và
# chúng KHÔNG được hát, để lại là mốc thời gian trôi lệch từ đó về sau.
NHAN_DOAN = re.compile(
    r"^\s*[\[\(]?\s*(verse|chorus|hook|bridge|intro|outro|pre[- ]?chorus|refrain|"
    r"solo|instrumental|interlude|breakdown|coda|drop)\b[^\]\)]*[\]\)]?\s*:?\s*$",
    re.IGNORECASE,
)

SO = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


@dataclass
class Tu:
    """Một từ trong lời, kèm dạng đã chuẩn hoá để đưa vào model."""
    goc: str          # nguyên văn, dùng để in ra lại
    chuan: str        # chỉ còn A-Z và ', dùng để căn
    dong: int         # thuộc dòng thứ mấy


@dataclass
class Dong:
    """Một dòng lời — chính là một câu phụ đề sẽ xuất ra."""
    so: int
    goc: str
    tu: List[int] = field(default_factory=list)   # chỉ số các Tu thuộc dòng này


def _chuan_hoa(tu: str) -> str:
    """Đưa một từ về bảng chữ cái của model. Trả về chuỗi rỗng nếu không còn gì."""
    t = tu.strip()
    # Dấu nháy cong của Word -> nháy thẳng, nếu không "don’t" thành "dont" sai âm.
    t = t.replace("’", "'").replace("‘", "'")
    t = "".join(SO.get(c, c) if c.isdigit() else c for c in t)
    t = t.upper()
    t = re.sub(r"[^A-Z']", "", t)
    t = t.strip("'")
    return t


def phan_tich(van_ban: str, bo_nhan_doan: bool = True) -> tuple:
    """Trả về (danh sách Dong, danh sách Tu).

    Dòng trống bị bỏ, nhưng thứ tự dòng còn lại giữ nguyên như người dùng nhập —
    phụ đề xuất ra phải khớp từng dòng với thứ họ nhìn thấy trong ô nhập.
    """
    cac_dong: List[Dong] = []
    cac_tu: List[Tu] = []

    for raw in van_ban.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        goc = raw.strip()
        if not goc:
            continue
        if bo_nhan_doan and NHAN_DOAN.match(goc):
            continue

        d = Dong(so=len(cac_dong), goc=goc)
        # Gạch nối và gạch dài tách thành hai từ; "well-known" hát ra hai từ.
        for mieng in re.split(r"[\s–—/\-]+", goc):
            if not mieng:
                continue
            ch = _chuan_hoa(mieng)
            if not ch:
                continue          # ví dụ "(x2)" hay "..." — không hát thành tiếng
            d.tu.append(len(cac_tu))
            cac_tu.append(Tu(goc=mieng, chuan=ch, dong=d.so))

        # Giữ cả dòng không còn từ nào (ví dụ dòng chỉ có "(x2)"): bỏ đi thì
        # số thứ tự dòng nhảy, và phụ đề lệch so với ô nhập của người dùng.
        cac_dong.append(d)

    return cac_dong, cac_tu
