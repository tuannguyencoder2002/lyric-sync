# -*- coding: utf-8 -*-
"""Chạy hàng loạt theo thư mục, không cần mở giao diện.

    data/Test/Input/    <- bỏ file nhạc + file lời vào đây
    data/Test/Output/   <- .srt và .lrc hiện ra ở đây

Ghép cặp theo TÊN FILE: `bai-hat.mp3` đi với `bai-hat.txt`. Không ghép theo thứ
tự bỏ vào, vì đổi tên một file là cả mẻ lệch cặp mà không ai biết.
"""
import json
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent
if str(GOC) not in sys.path:
    sys.path.insert(0, str(GOC))


def _sua_console():
    """Ép console về UTF-8 TRƯỚC khi in bất cứ thứ gì.

    Console Windows mặc định là cp1252; in một chữ có dấu là UnicodeEncodeError
    làm sập cả tiến trình — và nó sập ở dòng thông báo, tức là đúng lúc người
    dùng cần đọc thông báo nhất.
    """
    for luong in (sys.stdout, sys.stderr):
        try:
            luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_sua_console()

from app import config, danh_gia, doc_loi, lyrics, srt  # noqa: E402
from app import align as al                            # noqa: E402
from app import audio as A                             # noqa: E402
from app.separate import tach_giong                    # noqa: E402

VAO = config.DATA / "Test" / "Input"
RA = config.DATA / "Test" / "Output"

DUOI_NHAC = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".mp4"}
DUOI_LOI = [".txt", ".lrc", ".srt", ".vtt", ".md", ".docx"]


def doc_file_loi(f: Path) -> str:
    """Đọc file lời. Dùng chung một bộ đọc với giao diện, khỏi hai nơi hai kiểu."""
    return doc_loi.doc(f.read_bytes(), f.name)["text"]


def tim_cap():
    """Trả về [(file nhạc, file lời)] đã ghép, và danh sách file nhạc thiếu lời."""
    cap, thieu = [], []
    for nhac in sorted(VAO.iterdir()):
        if not nhac.is_file() or nhac.suffix.lower() not in DUOI_NHAC:
            continue
        loi = None
        for d in DUOI_LOI:
            ung = nhac.with_suffix(d)
            if ung.exists():
                loi = ung
                break
        (cap if loi else thieu).append((nhac, loi) if loi else nhac)
    return cap, thieu


def xu_ly_mot(nhac: Path, loi_f: Path) -> dict:
    van_ban = doc_file_loi(loi_f)
    cac_dong, cac_tu = lyrics.phan_tich(van_ban)
    if not cac_tu:
        raise RuntimeError("file lời không có chữ nào hát được")

    stem = tach_giong(nhac, bao_tien_do=lambda p, m: _tien_do(m, p))
    moc = al.can_loi(str(stem["vocals"]), cac_dong, cac_tu,
                     bao=lambda p, m: _tien_do(m, p))
    cau = srt.gop_theo_dong(cac_dong, moc)
    khop = danh_gia.do_do_khop(str(stem["vocals"]), cau)

    ten = nhac.stem
    (RA / f"{ten}.srt").write_text(srt.ra_srt(cau), encoding="utf-8")
    (RA / f"{ten}.lrc").write_text(srt.ra_lrc(cau, theo_tung_chu=True), encoding="utf-8")
    # JSON kèm mốc từng chữ: chạy thư mục cũng phải xuất đủ như giao diện, để
    # còn nối vào công cụ khác hoặc kiểm lại bằng máy.
    (RA / f"{ten}.json").write_text(json.dumps(
        [{"start": c["dau"], "end": c["cuoi"], "text": c["van_ban"],
          "score": c["diem"],
          "words": [{"text": w["goc"], "start": w["dau"], "end": w["cuoi"]}
                    for w in c["tu"]]} for c in cau],
        ensure_ascii=False, indent=2), encoding="utf-8")

    return {"cau": cau, "khop": khop, "so_tu": len(moc),
            "dai": A.thoi_luong(str(nhac))}


def _tien_do(thong_bao: str, p: float):
    print(f"\r      {thong_bao:<28} {p * 100:5.1f}%", end="", flush=True)


def _phut(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def main():
    VAO.mkdir(parents=True, exist_ok=True)
    RA.mkdir(parents=True, exist_ok=True)

    cap, thieu = tim_cap()

    if thieu:
        print("Bỏ qua (không tìm thấy file lời cùng tên):")
        for f in thieu:
            print(f"  - {f.name}  ->  cần {f.stem}.txt")
        print()

    if not cap:
        print(f"Không có cặp nào để chạy.\n")
        print(f"Bỏ vào  {VAO}")
        print("hai file cùng tên, ví dụ:  bai-hat.mp3  và  bai-hat.txt")
        return

    print(f"Có {len(cap)} bài. Kết quả sẽ nằm ở {RA}\n")

    tong = 0.0
    for i, (nhac, loi_f) in enumerate(cap, 1):
        print(f"[{i}/{len(cap)}] {nhac.name}")
        t0 = time.time()
        try:
            kq = xu_ly_mot(nhac, loi_f)
        except Exception as e:
            print(f"\r      LỖI: {e}" + " " * 30)
            continue

        giay = time.time() - t0
        tong += giay
        cau = kq["cau"]

        # Đếm số câu đáng ngờ: có khoảng lặng trước nó mà năng lượng không bật
        # lên tại mốc -> nhiều khả năng mốc rơi sai chỗ.
        dang_ngo = 0
        truoc = None
        for c, m in zip(cau, kq["khop"]["mep"]):
            if truoc is not None and c["dau"] - truoc["cuoi"] >= 0.4 and m < 1.2:
                dang_ngo += 1
            truoc = c

        print(f"\r      {len(cau)} câu · {kq['so_tu']} từ · dài {_phut(kq['dai'])}"
              f" · Fit ×{kq['khop']['ti_le']:.1f}"
              f" · {dang_ngo} câu nên nghe lại"
              f" · {giay:.0f}s" + " " * 12)

    print(f"\nXong {len(cap)} bài trong {tong:.0f} giây.")
    print("Fit càng cao càng khớp — dưới ×5 là nên mở giao diện xem lại bằng tai.")


if __name__ == "__main__":
    main()
