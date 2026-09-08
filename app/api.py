# -*- coding: utf-8 -*-
"""Máy chủ HTTP: nhận file, chạy việc, trả kết quả."""
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import config, danh_gia, doc_loi, jobs, lyrics, srt
from . import align as al
from . import audio as A
from .separate import tach_giong

app = FastAPI(title="Lyric Sync")

# Kết quả giữ trong bộ nhớ theo mã việc: mốc thời gian từng từ để giao diện vẽ,
# và để xuất ra bất kỳ định dạng nào mà không phải căn lại.
_ket: dict = {}


@app.post("/api/align")
async def api_align(
    audio: UploadFile = File(...),
    lyric: str = Form(...),
    tach_nhac: bool = Form(True),
    bo_nhan_doan: bool = Form(True),
):
    if not lyric.strip():
        raise HTTPException(400, "Lyrics are empty.")

    ma = jobs.tao()
    dich = config.UPLOAD / f"{ma}_{Path(audio.filename or 'audio').name}"
    with open(dich, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    def viec(bao):
        cac_dong, cac_tu = lyrics.phan_tich(lyric, bo_nhan_doan=bo_nhan_doan)
        if not cac_tu:
            raise RuntimeError("No singable words found in the lyrics.")

        nguon = dich
        if tach_nhac:
            stem = tach_giong(dich, bao_tien_do=lambda p, m: bao(0.05 + 0.55 * p, m))
            nguon = stem["vocals"]

        moc = al.can_loi(str(nguon), cac_dong, cac_tu,
                         bao=lambda p, m: bao(0.60 + 0.36 * p, m))
        cau = srt.gop_theo_dong(cac_dong, moc)

        bao(0.97, "Checking fit")
        khop = danh_gia.do_do_khop(str(nguon), cau)

        _ket[ma] = {"cau": cau, "audio": str(dich)}
        return {
            "so_cau": len(cau),
            "so_tu": len(moc),
            "thoi_luong": A.thoi_luong(str(dich)),
            "diem_tb": (sum(c["diem"] for c in cau) / len(cau)) if cau else 0.0,
            "khop": round(khop["ti_le"], 1),
            "cau": [
                {"i": c["so"], "text": c["van_ban"], "start": round(c["dau"], 3),
                 "end": round(c["cuoi"], 3), "score": round(c["diem"], 3),
                 "mep": round(m, 2),
                 "words": [{"t": w["goc"], "s": round(w["dau"], 3),
                            "e": round(w["cuoi"], 3)} for w in c["tu"]]}
                for c, m in zip(cau, khop["mep"])
            ],
        }

    jobs.chay(ma, viec)
    return {"id": ma}


@app.post("/api/lyrics")
async def api_lyrics(file: UploadFile = File(...)):
    """Đọc một file lời rồi trả về chữ, để giao diện đổ vào ô nhập.

    Đọc ở máy chủ chứ không đọc bằng JavaScript: trình duyệt chỉ giải mã UTF-8
    cho gọn, gặp file cp1252 hay UTF-16 là ra chữ rác mà không báo gì. Bên
    Python thì đã có sẵn phần đoán bảng mã và bóc mốc thời gian cũ.
    """
    raw = await file.read()
    if len(raw) > 4 * 1024 * 1024:
        raise HTTPException(400, "Lyrics file is too large (max 4 MB).")
    try:
        kq = doc_loi.doc(raw, file.filename or "")
    except Exception as e:
        raise HTTPException(400, f"Could not read the file: {e}")
    if not kq["text"].strip():
        raise HTTPException(400, "That file has no text in it.")
    return kq


@app.get("/api/job/{ma}")
def api_job(ma: str):
    v = jobs.xem(ma)
    if not v:
        raise HTTPException(404, "Unknown job.")
    return v


@app.get("/api/audio/{ma}")
def api_audio(ma: str):
    d = _ket.get(ma)
    if not d:
        raise HTTPException(404, "No audio for this job.")
    return FileResponse(d["audio"])


@app.get("/api/export/{ma}")
def api_export(ma: str, fmt: str = "srt", tai_ve: bool = False):
    d = _ket.get(ma)
    if not d:
        raise HTTPException(404, "No result for this job.")
    cau = d["cau"]

    bang = {
        "srt": (srt.ra_srt(cau), "srt"),
        "vtt": (srt.ra_vtt(cau), "vtt"),
        "lrc": (srt.ra_lrc(cau), "lrc"),
        "lrc_word": (srt.ra_lrc(cau, theo_tung_chu=True), "lrc"),
        "srt_word": (srt.ra_srt_tung_chu(cau), "srt"),
        "json": (json.dumps(
            [{"start": c["dau"], "end": c["cuoi"], "text": c["van_ban"],
              "score": c["diem"],
              "words": [{"text": w["goc"], "start": w["dau"], "end": w["cuoi"]}
                        for w in c["tu"]]} for c in cau],
            ensure_ascii=False, indent=2), "json"),
    }
    if fmt not in bang:
        raise HTTPException(400, f"Unknown format: {fmt}")

    noi_dung, duoi = bang[fmt]
    if not tai_ve:
        return PlainTextResponse(noi_dung)

    f = config.OUT / f"{ma}_{fmt}.{duoi}"
    f.write_text(noi_dung, encoding="utf-8")
    return FileResponse(f, filename=f"lyrics_{fmt}.{duoi}",
                        media_type="application/octet-stream")


@app.post("/api/nudge/{ma}")
def api_nudge(ma: str, du_lieu: dict):
    """Dời một câu đi vài phần trăm giây, khi tai người nghe thấy lệch.

    Căn tự động không bao giờ đúng 100% — có sẵn nút dời tay thì người dùng sửa
    trong ba giây, thay vì phải mở phần mềm khác.
    """
    d = _ket.get(ma)
    if not d:
        raise HTTPException(404, "No result for this job.")
    i = int(du_lieu.get("index", -1))
    lech = float(du_lieu.get("delta", 0.0))
    cau = d["cau"]
    for c in cau:
        if c["so"] == i:
            c["dau"] = max(0.0, c["dau"] + lech)
            c["cuoi"] = max(c["dau"] + 0.2, c["cuoi"] + lech)
            for w in c["tu"]:
                w["dau"] += lech
                w["cuoi"] += lech
            return {"ok": True, "start": c["dau"], "end": c["cuoi"]}
    raise HTTPException(404, "Line not found.")


@app.get("/api/health")
def api_health():
    import torch
    return {"ok": True, "gpu": torch.cuda.is_available(),
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}


# Giao diện là HTML/CSS/JS tĩnh, không có bước dựng. Gắn SAU cùng để các đường
# /api/* không bị lớp file tĩnh nuốt mất.
_web = config.GOC / "web"
if _web.exists():
    app.mount("/", StaticFiles(directory=str(_web), html=True), name="web")
