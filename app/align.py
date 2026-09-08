# -*- coding: utf-8 -*-
"""Căn lời vào tiếng hát (forced alignment).

Đây KHÔNG phải nhận dạng tiếng nói. Ta đã có sẵn lời, việc còn lại chỉ là tìm
xem mỗi chữ rơi vào mili giây nào — bài toán dễ hơn hẳn vì model không phải
đoán chữ, chỉ phải xếp chuỗi chữ đã biết vào dòng âm thanh.

Cách làm: wav2vec2 cho ra xác suất của từng âm ở từng khung 20 ms, rồi thuật
toán Viterbi (torchaudio.functional.forced_align) tìm đường đi khớp nhất giữa
chuỗi chữ và chuỗi khung.
"""
from typing import Callable, List, Optional

import numpy as np
import torch
import torchaudio

from . import config
from . import audio as A
from .lyrics import Dong, Tu

# Bước nhảy của wav2vec2: mỗi khung ứng với 320 mẫu, tức 20 ms ở 16 kHz.
BUOC = 320
TRUONG_NHIN = 400          # số mẫu một khung thực sự "nhìn" thấy

# Cửa sổ nạp vào model, tính bằng khung cho khỏi lệch số lẻ.
KHUNG_CUA_SO = 1500        # 30 s
KHUNG_CHONG = 50           # 1 s chồng lấn giữa hai cửa sổ

_bundle = None
_model = None
_bang_chu = None


def _tai_model(bao=None):
    """Nạp model một lần rồi giữ lại. Lần đầu sẽ tải ~360 MB về data/cache."""
    global _bundle, _model, _bang_chu
    if _model is None:
        if bao:
            bao(0.0, "Loading acoustic model")
        _bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
        _model = _bundle.get_model()
        _model.eval()
        nhan = _bundle.get_labels()          # ('-', '|', 'E', 'T', ...)
        _bang_chu = {c: i for i, c in enumerate(nhan)}
    return _model, _bang_chu


def thiet_bi() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _xac_suat(song: np.ndarray, bao=None) -> torch.Tensor:
    """Tính log-xác suất âm vị cho cả bài, trả về tensor (T, C) trên CPU.

    Phải cắt cửa sổ chứ không nạp cả bài: lớp tự chú ý tốn bộ nhớ theo bình
    phương độ dài, bài 4 phút nạp một lần là tràn VRAM ngay cả trên card lớn.
    """
    model, _ = _tai_model(bao)
    dev = thiet_bi()
    model.to(dev)

    N = song.shape[0]
    tong_khung = max(1, (N - TRUONG_NHIN) // BUOC + 1)
    win = KHUNG_CUA_SO * BUOC
    hop = (KHUNG_CUA_SO - KHUNG_CHONG) * BUOC
    bien = KHUNG_CHONG // 2

    ket_qua: Optional[torch.Tensor] = None
    dau = 0
    while True:
        lat = song[dau:dau + win]
        cuoi_bai = dau + win >= N
        if lat.shape[0] < TRUONG_NHIN:
            break
        x = torch.from_numpy(lat).float()[None].to(dev)
        with torch.no_grad():
            logit, _ = model(x)
            lp = torch.log_softmax(logit[0], dim=-1).cpu()

        if ket_qua is None:
            ket_qua = torch.full((tong_khung, lp.shape[1]), float("nan"))

        k_dau = 0 if dau == 0 else bien
        k_cuoi = lp.shape[0] if cuoi_bai else lp.shape[0] - bien
        g_dau = dau // BUOC + k_dau
        g_cuoi = min(tong_khung, dau // BUOC + k_cuoi)
        if g_cuoi > g_dau:
            ket_qua[g_dau:g_cuoi] = lp[k_dau:k_dau + (g_cuoi - g_dau)]

        if bao:
            bao(min(0.999, (dau + win) / max(N, 1)), "Reading phonemes")
        if cuoi_bai:
            break
        dau += hop

    if ket_qua is None:
        raise RuntimeError("Đoạn âm thanh quá ngắn để căn.")

    # Khung cuối cùng có thể chưa được điền nếu bài không chia chẵn cửa sổ.
    thieu = torch.isnan(ket_qua[:, 0])
    if thieu.any():
        ket_qua[thieu] = ket_qua[~thieu][-1]

    if dev == "cuda":
        torch.cuda.empty_cache()
    return ket_qua


def can_loi(
    duong_dan_vocal: str,
    cac_dong: List[Dong],
    cac_tu: List[Tu],
    bao: Optional[Callable[[float, str], None]] = None,
) -> List[dict]:
    """Trả về danh sách mốc từng từ: {'i', 'goc', 'dong', 'dau', 'cuoi', 'diem'}."""
    _, bang = _tai_model(bao)

    song = A.doc(duong_dan_vocal, config.SR_ALIGN, mono=True)[0]
    lp = _xac_suat(song, bao)

    if bao:
        bao(0.0, "Aligning words")

    # Ghép mọi chữ của mọi từ thành một chuỗi dài. Không chèn dấu ngăn từ:
    # ký tự trống (blank) của CTC tự đóng vai trò đó, chèn thêm chỉ làm model
    # phải "tìm" một khoảng lặng không nhất thiết tồn tại khi hát liền hơi.
    muc_tieu: List[int] = []
    do_dai: List[int] = []
    for t in cac_tu:
        ky_tu = [bang[c] for c in t.chuan if c in bang]
        if not ky_tu:
            ky_tu = [bang["A"]]      # từ lạ hoàn toàn: giữ một chỗ cho khỏi lệch
        muc_tieu.extend(ky_tu)
        do_dai.append(len(ky_tu))

    if not muc_tieu:
        return []

    # Chạy Viterbi trên CPU: bảng quy hoạch động to theo (số khung x số chữ),
    # bài dài mà để trên card 4 GB là tràn, trong khi trên CPU chỉ mất vài giây.
    dau_ra, diem = torchaudio.functional.forced_align(
        lp[None].float(), torch.tensor([muc_tieu], dtype=torch.int32), blank=0
    )
    dau_ra, diem = dau_ra[0], diem[0].exp()

    khoang = torchaudio.functional.merge_tokens(dau_ra, diem, blank=0)

    giay = BUOC / config.SR_ALIGN
    ket: List[dict] = []
    vi_tri = 0
    for i, t in enumerate(cac_tu):
        n = do_dai[i]
        phan = khoang[vi_tri:vi_tri + n]
        vi_tri += n
        if not phan:
            continue
        ket.append({
            "i": i,
            "goc": t.goc,
            "dong": t.dong,
            "dau": phan[0].start * giay,
            "cuoi": phan[-1].end * giay,
            "diem": float(np.mean([p.score for p in phan])),
        })

    if bao:
        bao(1.0, "Alignment done")
    return ket
