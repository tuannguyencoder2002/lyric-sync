# Lyric Sync

Đưa vào **file nhạc + lời bài hát dạng chữ**, lấy ra **file .srt có mốc thời gian
từng câu** (và .lrc chạy chữ từng chữ nếu cần).

Chạy: bấm đúp `Run.bat`.

---

## Đây không phải nhận dạng tiếng nói

Chỗ này quan trọng, vì nó quyết định vì sao bài toán khả thi.

Nhận dạng tiếng nói (Whisper và họ hàng) phải **đoán xem người ta hát chữ gì** —
với giọng hát có ngân, có luyến, có nhạc nền chồng lên thì đoán sai rất nhiều.

Ở đây ta **đã có sẵn lời**. Việc còn lại chỉ là tìm xem mỗi chữ rơi vào mili
giây nào. Ngành gọi là *forced alignment*. Model không phải đoán chữ, chỉ phải
xếp một chuỗi chữ đã biết vào một dòng âm thanh — dễ hơn hẳn, và chính xác hơn
hẳn.

## Dây chuyền

```
file nhạc ──► Demucs tách vocal ──► wav2vec2 tính xác suất âm vị
                                          │
              lời bài hát ────────────────┤
                                          ▼
                            Viterbi (forced_align)  ──► mốc từng chữ
                                          │
                                          ▼
                                gộp theo dòng ──► .srt / .lrc / .vtt / .json
```

**Bước tách vocal là bắt buộc, không phải tuỳ chọn.** Model âm vị được huấn
luyện trên tiếng nói sạch; đưa cả bản phối vào thì trống và bass lấn phổ, xác
suất âm vị nhoè ra, mốc thời gian lệch. Đây là nguyên nhân số một làm hỏng căn
lời. (Vẫn có ô tắt, để thử với file đã là vocal thuần.)

## Số đo thật trên máy này

Máy đo: RTX 3050 Laptop 4 GB, Windows 10.

| Việc | Bài 4 phút |
|---|---|
| Tách vocal + căn 56 dòng lời | **17 giây** |
| Riêng phần căn (vocal có sẵn) | ~3 giây |
| VRAM đỉnh | dưới 3 GB |

Đo trên một bài hát thật (28 giây, 4 dòng lời): **12 giây**, chỉ số Fit ×18,9 —
xem mục dưới để hiểu con số đó nghĩa là gì.

Lần chạy đầu tiên tải model về `data/cache`: 360 MB (wav2vec2) + 80 MB (Demucs).
Từ lần sau không tải nữa.

Không có card NVIDIA thì vẫn chạy, chậm hơn khoảng 4-5 lần.

## Giao diện

- Thả file nhạc và file lời vào, bấm **Sync**. Kéo **cả hai file cùng lúc**
  cũng được — thả vào ô nào cũng xong, tool tự phân loại theo đuôi file. Hoặc
  vẫn dán chữ thẳng vào ô nhập như cũ.
- Bảng kết quả có **chấm trạng thái** từng câu: xanh là mốc mở câu rõ ràng,
  vàng là mờ, đỏ là nên nghe lại, xám là câu hát liền mạch với câu trước nên
  không có khoảng lặng nào để đánh giá.
- Bấm vào một dòng là nhảy tới đúng chỗ đó trong bài, và thanh sóng kéo theo.
- Nút `−` `+` dời một câu 0,1 giây. Căn tự động không bao giờ đúng tuyệt đối;
  có nút dời tay thì sửa tại chỗ trong ba giây.
- Nút tải file nằm ở **thanh dính đầu khối kết quả**, luôn nhìn thấy kể cả khi
  đang cuộn tới dòng thứ 60. Trước đó nó nằm dưới bảng và người dùng phải cuộn
  hết bảng mới tới — trong khi tải file mới là việc họ vào đây để làm.

## Thao tác trên thanh sóng

| Thao tác | Việc |
|---|---|
| lăn chuột | thu phóng, **neo vào chỗ con trỏ** đang chỉ |
| kéo thân sóng | dịch ngang |
| bấm thân sóng | tua tới đó |
| kéo trên thước hoặc sát vạch trắng | rê vạch phát |
| bấm đúp | xem lại cả bài |
| `Space` | phát / dừng |
| `←` `→` | lùi/tới 1 giây, giữ `Shift` thành 5 giây |
| `+` `−` | thu phóng |
| `0` | xem lại cả bài |

Ba chi tiết nhỏ nhưng thiếu là hỏng:

- Lăn chuột phải gắn bằng `addEventListener(..., {passive: false})`. Dùng
  thuộc tính `onwheel` thì `preventDefault` không có tác dụng và **mỗi lần lăn
  là cả trang cuộn theo**.
- Nấc thu phóng **nhân/chia** chứ không cộng/trừ, và nấc cho chuột (1,22) nhẹ
  hơn nấc cho phím (1,45) — một cú lăn phát ra nhiều sự kiện liền nhau.
- Mọi phím tắt đi qua một cửa chặn `dangGo()`. Người dùng gõ lời vào ô nhập mà
  dấu cách là phím phát/dừng: thiếu cửa chặn thì gõ một khoảng trắng là nhạc chạy.

Vạch phát có vùng bắt rộng 7px chứ không phải đúng 1,5px của nét vẽ — bấm trúng
một vạch một điểm rưỡi bằng chuột là việc không ai làm được.

## Hai con số ở đầu bảng kết quả, đọc thế nào

**Fit** là thước đo chính, và nó là thước đo khách quan: năng lượng giọng hát
BÊN TRONG các khoảng thời gian đã gán, chia cho năng lượng BÊN NGOÀI chúng.
Không hỏi model, chỉ hỏi thẳng âm thanh. Đo trên một bài hát thật được ×18,9 —
tức là chỗ nào tool bảo "đang hát" thì đúng là đang hát to gấp gần 19 lần chỗ
nó bảo "không hát".

**Phoneme** là điểm tin cậy của model âm vị, và **đừng hoảng khi thấy nó thấp**.
Model này học từ tiếng NÓI, nên giọng HÁT luôn bị chấm thấp. Số đo thật:

| Chất liệu | Phoneme | Fit | Mốc thời gian thực tế |
|---|---|---|---|
| Giọng đọc (TTS) | 0,87–0,98 | — | đúng |
| Giọng hát thật | 0,39–0,68 | ×18,9 | **cũng đúng** |

Cùng một dây chuyền, cùng độ chính xác, mà điểm chênh nhau hơn hai lần. Nên
Phoneme chỉ dùng để so các câu TRONG CÙNG một bài với nhau, không dùng để kết
luận bài đó căn đúng hay sai. Muốn biết đúng sai thì nhìn Fit và nghe thử mấy
câu có chấm vàng/đỏ.

## Chạy hàng loạt, không cần giao diện

    data/Test/Input/     bỏ file nhạc + file lời vào đây
    data/Test/Output/    .srt và .lrc hiện ra ở đây

Ghép cặp theo **tên file**, không theo thứ tự bỏ vào: `my-song.mp3` đi với
`my-song.txt`. Ghép theo thứ tự thì đổi tên một file là cả mẻ lệch cặp mà không
ai biết.

Rồi bấm `Run-Batch.bat`. Mỗi bài in ra một dòng tổng kết kèm chỉ số Fit và số
câu nên nghe lại. File nhạc không có file lời cùng tên thì được liệt kê ra chứ
không bị bỏ qua im lặng.

## Định dạng lời nhận vào

| Đuôi | Xử lý |
|---|---|
| `.txt` `.md` | đọc thẳng |
| `.srt` `.vtt` | **bóc mốc thời gian cũ**, chỉ giữ lời |
| `.lrc` | bóc mốc từng câu, mốc từng chữ, và thẻ `[ar:]` `[ti:]` |
| `.docx` | đọc từng đoạn văn trong file Word |

Bảng mã tự đoán: UTF-8, UTF-8 có BOM, UTF-16, cp1252. Word và Notepad mỗi cái
đẻ ra một kiểu, đọc cứng một bảng mã là gặp file thứ hai đã ra chữ rác.

Việc bóc mốc cũ để làm gì: khách gửi một file `.srt` đã có mốc và muốn căn lại
cho khớp một bản thu khác — chuyện rất thường. Không bóc thì dòng
`00:00:12,340 --> 00:00:15,120` bị coi là lời hát và cả bài lệch từ đó. Tool
báo rõ ngay dưới ô thả file là nó đã bóc mốc từ định dạng nào.

Thả nhầm file nhạc vào ô lời thì bị chặn kèm thông báo, chứ không im lặng đổ
mấy nghìn ký tự rác vào ô nhập.

## Định dạng xuất

| Nút | Ra cái gì | Dùng ở đâu |
|---|---|---|
| SRT | phụ đề từng câu | YouTube, Premiere, mọi trình phát |
| VTT | như SRT | web, thẻ `<video>` |
| LRC | lời có mốc từng câu | trình nghe nhạc |
| LRC word | mốc **từng chữ** | karaoke chạy chữ |
| SRT word | mỗi chữ một khối | video chạy chữ từng từ |
| JSON | toàn bộ số liệu | nối vào công cụ khác |

## Giới hạn cần biết trước

- **Hiện chỉ tiếng Anh.** Model đang dùng là `WAV2VEC2_ASR_BASE_960H`. Muốn thêm
  tiếng Việt thì đổi model trong `app/align.py` sang một model wav2vec2 tiếng
  Việt — chỗ nạp model đã tách riêng sẵn cho việc này.
- **Lời phải khớp bài hát.** Thiếu một đoạn điệp khúc lặp lại, hoặc thừa một
  dòng không hát, thì phần từ đó về sau lệch dồn. Nhãn `[Verse]`, `(Chorus)` thì
  app tự bỏ (có ô tắt).
- **Đoạn ngân dài, luyến láy** là chỗ dễ lệch nhất. Xem chấm trạng thái.
- Nốt hát trên nền nhạc rất dày (metal, EDM nén mạnh) thì tách vocal kém hơn,
  kéo theo căn kém hơn.

## Cỡ màn hình

Đã thử thật bằng trình duyệt ở bốn cỡ: laptop 1366×768, laptop 1536×864,
màn rời 24" 1920×1080, màn rời 27" 2560×1440. Không cỡ nào bị tràn ngang.

| Bề ngang | Cột trái | Khối kết quả |
|---|---|---|
| < 1080 | xếp dọc, cuộn cả trang | tràn hết bề ngang |
| 1366 | 320px | 960px |
| 1536 | 340px | 1080px |
| 1920 | 384px | 1380px |
| 2560 | 420px | 1560px |

Hai cột giãn **khác nhau**, và đó là chủ ý:

- Cột trái nới vừa phải. Nó chứa các ô nhập bề ngang cố định; nới quá thì chữ
  với ô nhập trôi xa nhau, mắt phải nhảy qua lại.
- Khối kết quả **phải có trần**. Không chặn thì trên màn 27" một dòng chữ dàn
  ngang hơn hai nghìn điểm ảnh: đọc hết dòng rồi phải quét ngược cả màn hình
  để tìm đầu dòng sau. Chặn lại rồi căn giữa.

Nút chạy dính đáy cột trái. Màn laptop cao 768 điểm ảnh không đủ chỗ cho cả
cột điều khiển nên cột đó phải cuộn; không dính đáy thì mỗi lần chỉnh một thanh
kéo lại phải cuộn xuống mới bấm được.

## Cấu trúc mã nguồn

```
app/config.py     hằng số dùng chung, đường dẫn, cổng
app/audio.py      đọc/ghi audio bằng ffmpeg
app/separate.py   tách vocal bằng Demucs, có cache theo mã băm file
app/lyrics.py     chuẩn hoá lời: bỏ dấu câu, số thành chữ, bỏ nhãn đoạn
app/align.py      wav2vec2 + forced_align  ← lõi của tool
app/doc_loi.py    đọc lời từ txt/srt/vtt/lrc/docx, đoán bảng mã, bóc mốc cũ
app/srt.py        gộp mốc từng chữ thành từng câu rồi xuất file
app/danh_gia.py   chấm Fit: mốc có rơi vào chỗ thật sự có tiếng hát không
app/jobs.py       hàng đợi việc chạy nền
app/api.py        máy chủ HTTP
web/              giao diện: HTML/CSS/JS thuần, không có bước dựng
launcher.py       bật máy chủ rồi mở cửa sổ ứng dụng
batch.py          chạy hàng loạt theo thư mục Test/Input -> Test/Output
```

## Cài trên máy mới

Xem đầu file `requirements.txt`. Có một cái bẫy: bản `demucs==4.0.1` trên PyPI
ghi chặn `torchaudio<2.1`, cài kiểu thường là pip hạ torchaudio xuống và torch
gãy theo — phải cài `--no-deps` rồi tự cài các gói phụ.
