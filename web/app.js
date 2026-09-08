// Giao diện Lyric Sync. Không khung nào cả, không bước dựng — mở là chạy.
// App chạy offline trên máy khách, thêm một chuỗi công cụ dựng chỉ để hiện
// vài ô nhập là thêm một chỗ hỏng khi mang đi máy khác.

const $ = (id) => document.getElementById(id);

let tep = null;        // file nhạc đang chọn
let maViec = null;     // mã việc đang chạy
let cau = [];          // kết quả: từng câu kèm mốc thời gian
let dinh = null;       // đỉnh sóng để vẽ
let am = new Audio();
let dangChon = -1;

// ------------------------------------------------------------------ tiện ích

function gio(t) {
  if (!isFinite(t)) return "0:00";
  const p = Math.floor(t / 60), s = Math.floor(t % 60);
  return p + ":" + String(s).padStart(2, "0");
}

function gioLe(t) {
  return gio(t) + "." + String(Math.floor((t % 1) * 100)).padStart(2, "0");
}

// Chấm màu cho từng câu, dựa trên MỨC BẬT NĂNG LƯỢNG tại mốc mở câu chứ không
// dựa trên điểm tin cậy của model.
//
// Vì sao: model âm vị học từ tiếng NÓI, nên giọng HÁT luôn bị chấm thấp. Đo
// thật trên một bài có lời khớp và mốc đúng, điểm chỉ 0,39-0,68 trong khi cùng
// dây chuyền đó chấm giọng đọc 0,87-0,98. Lấy điểm ấy tô màu là báo đỏ oan cả
// bài, và người dùng mất niềm tin vào một kết quả vốn đúng.
function chamCau(c, truoc) {
  // Câu hát liền mạch với câu trước thì không có khoảng lặng nào để đo mức bật
  // — chấm xám, nghĩa là "không kết luận được", chứ không phải "xấu".
  const khe = truoc ? c.start - truoc.end : c.start;
  if (khe < 0.4) return { mau: "#4a4a54", chu: "continuous — no gap to judge" };
  if (c.mep >= 2.0) return { mau: "var(--tot)", chu: "clear onset (×" + c.mep.toFixed(1) + ")" };
  if (c.mep >= 1.2) return { mau: "var(--vua)", chu: "soft onset (×" + c.mep.toFixed(1) + ")" };
  return { mau: "var(--te)", chu: "no onset here (×" + c.mep.toFixed(1) + ") — listen to this line" };
}

// ------------------------------------------------------------------ chọn file

const DUOI_LOI = ["txt", "srt", "vtt", "lrc", "md", "docx"];

function laDuoiLoi(f) {
  return DUOI_LOI.includes((f.name.split(".").pop() || "").toLowerCase());
}

// Cả hai ô đều nhận CẢ HAI loại file, rồi tự phân theo đuôi.
//
// Vì sao không bắt thả đúng ô: người dùng thường chọn cả hai file rồi kéo một
// lần. Bắt thả đúng chỗ là bắt họ làm hai lượt, và lượt nào thả nhầm ô thì
// chẳng có gì xảy ra — im lặng, không hiểu vì sao.
function nhanNhieu(ds) {
  for (const f of ds) (laDuoiLoi(f) ? nhanFileLoi : nhanFile)(f);
}

function ganTha(vungId, inputId) {
  const v = $(vungId);
  v.onclick = () => $(inputId).click();
  $(inputId).onchange = (e) => nhanNhieu(e.target.files);
  ["dragenter", "dragover"].forEach((s) =>
    v.addEventListener(s, (e) => { e.preventDefault(); v.classList.add("keo"); }));
  ["dragleave", "drop"].forEach((s) =>
    v.addEventListener(s, (e) => { e.preventDefault(); v.classList.remove("keo"); }));
  v.addEventListener("drop", (e) => nhanNhieu(e.dataTransfer.files));
}

ganTha("tha", "chon-file");
ganTha("tha-loi", "chon-loi");

function nhanFile(f) {
  if (!f) return;
  tep = f;
  $("ten-file").textContent = f.name;
  $("thong-tin").textContent = (f.size / 1048576).toFixed(1) + " MB";
  ktChay();
}

async function nhanFileLoi(f) {
  if (!f) return;
  $("ten-loi").textContent = f.name;
  $("thong-tin-loi").textContent = "reading…";

  const fd = new FormData();
  fd.append("file", f);
  try {
    const r = await fetch("/api/lyrics", { method: "POST", body: fd });
    const v = await r.json();
    if (!r.ok) throw new Error(v.detail || r.statusText);
    $("loi").value = v.text;
    // Nói rõ đã nhận ra định dạng gì. File .srt/.lrc bị bóc mốc thời gian cũ —
    // người dùng phải biết chuyện đó đã xảy ra, chứ không phải đoán.
    $("thong-tin-loi").textContent = v.dang === "txt"
      ? v.so_dong + " lines"
      : v.so_dong + " lines · old timings stripped from " + v.dang.toUpperCase();
    ktChay();
  } catch (e) {
    $("thong-tin-loi").textContent = String(e.message || e);
  }
}

$("loi").oninput = ktChay;

function ktChay() {
  $("chay").disabled = !(tep && $("loi").value.trim());
}

// ------------------------------------------------------------------ chạy việc

$("chay").onclick = async () => {
  const fd = new FormData();
  fd.append("audio", tep);
  fd.append("lyric", $("loi").value);
  fd.append("tach_nhac", $("tach").checked ? "true" : "false");
  fd.append("bo_nhan_doan", $("bo-nhan").checked ? "true" : "false");

  $("chay").disabled = true;
  datTrangThai("Uploading", false);

  try {
    const r = await fetch("/api/align", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    maViec = (await r.json()).id;
    theoDoi();
  } catch (e) {
    datTrangThai(String(e.message || e), true);
    $("chay").disabled = false;
  }
};

function datTrangThai(s, loi) {
  const el = $("trang-thai");
  el.textContent = s;
  el.classList.toggle("loi", !!loi);
}

async function theoDoi() {
  const r = await fetch("/api/job/" + maViec);
  const v = await r.json();

  $("thanh-tien").style.width = (v.tien_do * 100).toFixed(1) + "%";
  datTrangThai(v.thong_bao, v.trang_thai === "error");

  if (v.trang_thai === "done") {
    $("chay").disabled = false;
    veKetQua(v.ket_qua);
    return;
  }
  if (v.trang_thai === "error") {
    datTrangThai(v.loi || "Failed", true);
    $("chay").disabled = false;
    return;
  }
  setTimeout(theoDoi, 700);
}

// ------------------------------------------------------------------ kết quả

async function veKetQua(kq) {
  cau = kq.cau;
  $("trong").hidden = true;
  $("kq").hidden = false;

  $("sl-cau").textContent = kq.so_cau;
  $("sl-tu").textContent = kq.so_tu;
  $("sl-khop").textContent = "×" + kq.khop;
  $("sl-diem").textContent = Math.round(kq.diem_tb * 100) + "%";
  $("sl-tg").textContent = gio(kq.thoi_luong);

  veBang();
  doThanhDinh();

  // Bài mới thì trả cửa sổ xem về cả bài. Giữ mức phóng của bài trước là
  // người dùng mở bài mới ra thấy một khúc giữa, không hiểu vì sao.
  xemDau = 0;
  xemDai = 0;

  am.src = "/api/audio/" + maViec;
  am.load();
  await docDinh();
  veSong();
}

/** Đo chiều cao thanh dính rồi báo cho CSS, để tiêu đề bảng dính đúng ngay
 *  dưới nó. Phải đo chứ không ghim cứng — thanh cao bao nhiêu còn tuỳ cỡ màn
 *  và tuỳ các nút có xuống dòng hay không. */
function doThanhDinh() {
  const d = $("kq").querySelector(".dau-kq");
  if (!d) return;
  const le = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue("--le")) || 16;
  document.documentElement.style.setProperty(
    "--th-tren", Math.round(d.offsetHeight - le) + "px");
}

function veBang() {
  const tb = $("dong-loi");
  tb.innerHTML = "";
  cau.forEach((c, i) => {
    const tr = document.createElement("tr");
    const ch = chamCau(c, i > 0 ? cau[i - 1] : null);
    // Chấm trạng thái đứng NGAY SAU mốc thời gian, không đẩy sang tận mép phải:
    // nó nói về cái mốc ấy, để xa thì mắt phải bắc cầu qua cả dòng chữ.
    tr.innerHTML =
      '<td class="tg">' + gioLe(c.start) + " → " + gioLe(c.end) + "</td>" +
      '<td><span class="cham-cau" style="background:' + ch.mau + '" title="' + ch.chu + '"></span></td>' +
      "<td>" + c.text.replace(/[<>&]/g, (m) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[m])) + "</td>" +
      '<td class="doi-moc"><button class="nho" data-dich="-0.1" data-i="' + i + '">−</button>' +
      '<button class="nho" data-dich="0.1" data-i="' + i + '">+</button></td>';
    tr.onclick = (e) => {
      if (e.target.dataset.dich) return;
      am.currentTime = c.start;
      keoToi(c.start);      // kéo cửa sổ sóng tới câu vừa bấm
      am.play();
    };
    tb.appendChild(tr);
  });

  // Dời tay: căn tự động không bao giờ đúng tuyệt đối, có nút dời thì người
  // dùng sửa tại chỗ thay vì phải mở phần mềm khác.
  tb.onclick = async (e) => {
    const d = e.target.dataset.dich;
    if (!d) return;
    e.stopPropagation();
    const i = +e.target.dataset.i;
    const r = await fetch("/api/nudge/" + maViec, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: cau[i].i, delta: +d }),
    });
    if (!r.ok) return;
    const v = await r.json();
    cau[i].start = v.start;
    cau[i].end = v.end;
    veBang();
    veSong();
  };
}

// ------------------------------------------------------------------ sóng

// Cửa sổ đang xem, tính bằng giây. Bằng cả bài lúc mới mở.
let xemDau = 0;
let xemDai = 0;
// Đỉnh sóng ở độ phân giải CAO, không phải theo bề rộng màn hình.
//
// Bản trước rút gọn thẳng về 1200 cột — vừa đủ khi xem cả bài, nhưng phóng to
// vào 10 giây thì mỗi cột trải ra hơn một trăm điểm ảnh và sóng thành bậc
// thang. Giữ ở ~10 ms một cột rồi mới gộp lúc vẽ: bài 3 phút hết 76 KB, đổi
// lại phóng tới đâu cũng còn chi tiết.
const MS_MOI_COT = 10;

async function docDinh() {
  try {
    const r = await fetch("/api/audio/" + maViec);
    const buf = await r.arrayBuffer();
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const dl = await ctx.decodeAudioData(buf);
    const x = dl.getChannelData(0);
    const buoc = Math.max(1, Math.round(dl.sampleRate * MS_MOI_COT / 1000));
    const cot = Math.floor(x.length / buoc);
    dinh = new Float32Array(cot);
    for (let i = 0; i < cot; i++) {
      let m = 0;
      const a = i * buoc, b = a + buoc;
      // Nhảy 4 mẫu một: đỉnh trong 10 ms gần như không đổi, mà đọc đủ thì
      // bài 3 phút phải duyệt 8 triệu mẫu ngay trên luồng giao diện.
      for (let j = a; j < b; j += 4) {
        const v = Math.abs(x[j]);
        if (v > m) m = v;
      }
      dinh[i] = m;
    }
    ctx.close();
  } catch (e) {
    dinh = null;
  }
}

function tongDai() {
  return am.duration || (cau.length ? cau[cau.length - 1].end : 1);
}

/** Kẹp cửa sổ xem trong bài, và không cho thu nhỏ quá 1 giây. */
function chuanCuaSo() {
  const tong = tongDai();
  xemDai = Math.max(1, Math.min(xemDai || tong, tong));
  xemDau = Math.max(0, Math.min(tong - xemDai, xemDau));
}

/** Đổi mức thu phóng, GIỮ NGUYÊN mốc thời gian đang nằm dưới con trỏ.
 *
 *  Neo vào con trỏ chứ không vào tâm cửa sổ: người dùng lăn chuột ở chỗ nào là
 *  đang quan tâm chỗ đó. Neo vào tâm thì chỗ họ nhìn trôi đi mất, và phải kéo
 *  lại — thành hai thao tác cho một ý định. */
function thuPhong(vao, he, xNeo) {
  const c = $("song");
  const r = c.getBoundingClientRect();
  const p = xNeo == null ? 0.5 : Math.max(0, Math.min(1, (xNeo - r.left) / r.width));
  const moc = xemDau + p * xemDai;
  const tong = tongDai();
  // Nhân/chia chứ không cộng/trừ: ở mức 5 giây thì cộng 5 giây là nhảy vọt,
  // còn ở mức cả bài thì 5 giây chẳng nhúc nhích.
  xemDai = Math.max(1, Math.min(tong, vao ? xemDai / he : xemDai * he));
  xemDau = moc - p * xemDai;
  chuanCuaSo();
  veSong();
}

/** Đưa một mốc thời gian vào giữa cửa sổ. Dùng khi bấm vào một câu trong bảng. */
function keoToi(t) {
  if (xemDai >= tongDai() - 0.01) return;   // đang xem cả bài thì khỏi dời
  xemDau = t - xemDai / 2;
  chuanCuaSo();
  veSong();
}

function veSong() {
  const c = $("song");
  const r = c.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  c.width = r.width * dpr;
  c.height = r.height * dpr;
  const g = c.getContext("2d");
  g.scale(dpr, dpr);
  g.clearRect(0, 0, r.width, r.height);

  const tong = tongDai();
  if (!xemDai) xemDai = tong;
  chuanCuaSo();

  const CAO_THUOC = 16;
  const caoSong = r.height - CAO_THUOC;
  const x = (t) => ((t - xemDau) / xemDai) * r.width;

  // Vùng có lời tô sáng: nhìn một cái là thấy chỗ nào hát, chỗ nào nhạc dạo.
  cau.forEach((cc) => {
    if (cc.end < xemDau || cc.start > xemDau + xemDai) return;
    const x1 = x(cc.start), x2 = x(cc.end);
    g.fillStyle = "rgba(110,99,242,.16)";
    g.fillRect(x1, CAO_THUOC, Math.max(1, x2 - x1), caoSong);
  });

  // Sóng. Gộp nhiều cột đỉnh vào một điểm ảnh khi đang xem rộng.
  if (dinh) {
    g.fillStyle = "#4a4a58";
    const giay_moi_cot = MS_MOI_COT / 1000;
    const i0 = Math.max(0, Math.floor(xemDau / giay_moi_cot));
    const i1 = Math.min(dinh.length, Math.ceil((xemDau + xemDai) / giay_moi_cot));
    const cot_moi_px = (i1 - i0) / r.width;

    if (cot_moi_px >= 1) {
      for (let px = 0; px < r.width; px++) {
        let m = 0;
        const a = i0 + Math.floor(px * cot_moi_px);
        const b = i0 + Math.floor((px + 1) * cot_moi_px);
        for (let i = a; i < b; i++) if (dinh[i] > m) m = dinh[i];
        const h = m * (caoSong * 0.9);
        g.fillRect(px, CAO_THUOC + (caoSong - h) / 2, 1, h);
      }
    } else {
      // Phóng to tới mức một cột đỉnh rộng hơn một điểm ảnh: vẽ thành thanh.
      const w = r.width / (i1 - i0);
      for (let i = i0; i < i1; i++) {
        const h = dinh[i] * (caoSong * 0.9);
        g.fillRect((i - i0) * w, CAO_THUOC + (caoSong - h) / 2,
                   Math.max(0.8, w - 0.3), h);
      }
    }
  }

  // Thước thời gian. Bước chia chọn theo CHỖ THẬT SỰ CÓ trên màn, không theo
  // một con số định sẵn: đòi tối thiểu 56 điểm ảnh cho mỗi nhãn, rồi lấy bước
  // nhỏ nhất còn vừa.
  const buoc = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300]
    .find((b) => (b / xemDai) * r.width >= 56) || 600;
  g.fillStyle = "#0f0f13";
  g.fillRect(0, 0, r.width, CAO_THUOC);
  g.strokeStyle = "#26262e";
  g.beginPath(); g.moveTo(0, CAO_THUOC + .5); g.lineTo(r.width, CAO_THUOC + .5); g.stroke();
  g.fillStyle = "#6b6b74";
  g.font = "10px Inter, system-ui, sans-serif";
  g.textBaseline = "middle";
  for (let t = Math.ceil(xemDau / buoc) * buoc; t < xemDau + xemDai; t += buoc) {
    const px = x(t);
    g.fillRect(px, CAO_THUOC - 4, 1, 4);
    g.fillText(buoc < 1 ? gioLe(t) : gio(t), px + 3, CAO_THUOC / 2);
  }

  // Vạch phát, kèm tay nắm hình thang ở đỉnh cho thấy nó cầm được.
  const t = am.currentTime || 0;
  if (t >= xemDau - 1 && t <= xemDau + xemDai + 1) {
    const px = x(t);
    g.fillStyle = "#ffffff";
    g.fillRect(px - 0.75, 0, 1.5, r.height);
    g.beginPath();
    g.moveTo(px - 5, 0); g.lineTo(px + 5, 0);
    g.lineTo(px + 5, 7); g.lineTo(px, 11); g.lineTo(px - 5, 7);
    g.closePath();
    g.fill();
  }

  // Bản đồ thu nhỏ: khi đang phóng to, vẽ một dải mảnh ở đáy cho biết đang
  // đứng ở đâu trong cả bài. Không có nó thì phóng to xong là mất phương hướng.
  if (xemDai < tong - 0.01) {
    const h = 3;
    g.fillStyle = "#1c1c22";
    g.fillRect(0, r.height - h, r.width, h);
    g.fillStyle = "#6e63f2";
    g.fillRect((xemDau / tong) * r.width, r.height - h,
               Math.max(3, (xemDai / tong) * r.width), h);
  }
}

// ------------------------------------------------------- chuột trên sóng

(function ganChuot() {
  const c = $("song");

  // Lăn chuột = thu phóng.
  //
  // Gắn bằng addEventListener với passive:false chứ không dùng thuộc tính
  // onwheel: trình duyệt coi wheel là thụ động ở nhiều ngữ cảnh, và khi ấy
  // preventDefault không có tác dụng — mỗi lần lăn là cả trang cuộn theo.
  //
  // Nấc 1,22 cho chuột, nhẹ hơn nấc 1,45 của phím: một cú lăn phát ra nhiều
  // sự kiện liền nhau, để nấc lớn thì lăn nhẹ một cái đã nhảy hết cỡ.
  c.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) return;    // nhường cho phóng to của trình duyệt
    if (!e.deltaY || $("kq").hidden) return;
    e.preventDefault();
    thuPhong(e.deltaY < 0, 1.22, e.clientX);
  }, { passive: false });

  let keo = null;

  c.addEventListener("pointerdown", (e) => {
    if ($("kq").hidden) return;
    const r = c.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    const t = xemDau + (px / r.width) * xemDai;
    const px_vach = ((am.currentTime - xemDau) / xemDai) * r.width;

    // Ba tầng, phân theo chỗ bấm — không có chế độ nào phải bật tắt:
    //   thước ở trên   -> tua
    //   sát vạch phát  -> tua (vùng bắt rộng 7px, chứ vạch chỉ 1,5px thì
    //                     không ai bấm trúng bằng chuột)
    //   thân sóng      -> kéo để dịch ngang, bấm nhả tại chỗ thì tua
    const tren_thuoc = py < 16;
    const trung_vach = Math.abs(px - px_vach) <= 7;
    keo = {
      x0: e.clientX, dau0: xemDau, da_di: false,
      tua: tren_thuoc || trung_vach,
    };
    c.setPointerCapture(e.pointerId);
    if (keo.tua) am.currentTime = Math.max(0, Math.min(tongDai(), t));
  });

  c.addEventListener("pointermove", (e) => {
    if (!keo) return;
    const r = c.getBoundingClientRect();
    if (keo.tua) {
      const t = xemDau + ((e.clientX - r.left) / r.width) * xemDai;
      am.currentTime = Math.max(0, Math.min(tongDai(), t));
      veSong();
      return;
    }
    const lech = e.clientX - keo.x0;
    // Ngưỡng 4px: dưới mức đó coi là bấm chứ không phải kéo. Không có ngưỡng
    // thì tay run một chút là mất luôn thao tác bấm-để-tua.
    if (!keo.da_di && Math.abs(lech) < 4) return;
    keo.da_di = true;
    xemDau = keo.dau0 - (lech / r.width) * xemDai;
    chuanCuaSo();
    veSong();
  });

  const thoi = (e) => {
    if (!keo) return;
    if (!keo.tua && !keo.da_di) {
      const r = c.getBoundingClientRect();
      am.currentTime = xemDau + ((e.clientX - r.left) / r.width) * xemDai;
      am.play();
    }
    keo = null;
  };
  c.addEventListener("pointerup", thoi);
  c.addEventListener("pointercancel", () => (keo = null));

  // Bấm đúp = xem lại cả bài. Lối thoát khi phóng to lạc mất phương hướng.
  c.addEventListener("dblclick", () => {
    xemDai = tongDai();
    xemDau = 0;
    veSong();
  });
})();

// ------------------------------------------------------------- phím tắt

function dangGo(e) {
  const t = e.target;
  if (!t) return false;
  return t.tagName === "INPUT" || t.tagName === "TEXTAREA"
      || t.tagName === "SELECT" || t.isContentEditable;
}

window.addEventListener("keydown", (e) => {
  // Cửa chặn này QUAN TRỌNG hơn ở đây so với mọi app khác: người dùng gõ lời
  // vào ô nhập, mà dấu cách là phím phát/dừng — thiếu cửa chặn thì mỗi lần gõ
  // một khoảng trắng là nhạc chạy.
  if (dangGo(e) || e.ctrlKey || e.altKey || e.metaKey) return;
  if ($("kq").hidden) return;

  const buoc = e.shiftKey ? 5 : 1;
  switch (e.key) {
    case " ":
      e.preventDefault();          // dấu cách vốn cuộn trang xuống một màn
      am.paused ? am.play() : am.pause();
      break;
    case "ArrowLeft":
      e.preventDefault();
      am.currentTime = Math.max(0, am.currentTime - buoc);
      break;
    case "ArrowRight":
      e.preventDefault();
      am.currentTime = Math.min(tongDai(), am.currentTime + buoc);
      break;
    case "+": case "=":
      e.preventDefault();
      thuPhong(true, 1.45);
      break;
    case "-": case "_":
      e.preventDefault();
      thuPhong(false, 1.45);
      break;
    case "0":
      e.preventDefault();
      xemDai = tongDai(); xemDau = 0; veSong();
      break;
  }
});

$("phat").onclick = () => (am.paused ? am.play() : am.pause());
am.onplay = () => ($("phat").textContent = "Pause");
am.onpause = () => ($("phat").textContent = "Play");

am.ontimeupdate = () => {
  $("gio").textContent = gio(am.currentTime) + " / " + gio(am.duration || 0);

  // Đang phóng to mà vạch phát chạy ra khỏi cửa sổ thì kéo cửa sổ theo. Không
  // có chỗ này thì phóng to xong bấm phát là sóng đứng im, nhìn như treo.
  const tong = tongDai();
  if (xemDai < tong - 0.01) {
    const t = am.currentTime;
    if (t < xemDau || t > xemDau + xemDai * 0.92) {
      xemDau = t - xemDai * 0.35;
      chuanCuaSo();
    }
  }
  veSong();

  const i = cau.findIndex((c) => am.currentTime >= c.start && am.currentTime <= c.end);
  if (i !== dangChon) {
    dangChon = i;
    const hang = $("dong-loi").children;
    for (let k = 0; k < hang.length; k++) hang[k].classList.toggle("dang", k === i);
  }
};

window.addEventListener("resize", () => {
  if ($("kq").hidden) return;
  doThanhDinh();
  veSong();
});

// ------------------------------------------------------------------ xuất file

$("kq").querySelector(".xuat").onclick = (e) => {
  const f = e.target.dataset.fmt;
  if (!f || !maViec) return;
  window.location.href = "/api/export/" + maViec + "?fmt=" + f + "&tai_ve=true";
};

// ------------------------------------------------------------------ khởi động

fetch("/api/health").then((r) => r.json()).then((v) => {
  const el = $("the-gpu");
  el.textContent = v.gpu ? v.device.replace("NVIDIA GeForce ", "") : "CPU";
  el.classList.toggle("on", v.gpu);
}).catch(() => ($("the-gpu").textContent = "offline"));
