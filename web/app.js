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

  am.src = "/api/audio/" + maViec;
  am.load();
  await docDinh();
  veSong();
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

async function docDinh() {
  // Đọc file một lần, rút gọn thành 1200 cột đỉnh rồi vẽ. Vẽ thẳng hàng triệu
  // mẫu lên canvas là treo trình duyệt.
  try {
    const r = await fetch("/api/audio/" + maViec);
    const buf = await r.arrayBuffer();
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const dl = await ctx.decodeAudioData(buf);
    const x = dl.getChannelData(0);
    const cot = 1200, buoc = Math.floor(x.length / cot);
    dinh = new Float32Array(cot);
    for (let i = 0; i < cot; i++) {
      let m = 0;
      for (let j = 0; j < buoc; j += 8) {
        const v = Math.abs(x[i * buoc + j]);
        if (v > m) m = v;
      }
      dinh[i] = m;
    }
    ctx.close();
  } catch (e) {
    dinh = null;
  }
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

  const dai = am.duration || (cau.length ? cau[cau.length - 1].end : 1);

  // Vùng có lời tô sáng hơn: nhìn một cái là thấy chỗ nào hát, chỗ nào nhạc dạo.
  cau.forEach((cc) => {
    const x1 = (cc.start / dai) * r.width;
    const x2 = (cc.end / dai) * r.width;
    g.fillStyle = "rgba(110,99,242,.16)";
    g.fillRect(x1, 0, Math.max(1, x2 - x1), r.height);
  });

  if (dinh) {
    g.fillStyle = "#4a4a58";
    const w = r.width / dinh.length;
    for (let i = 0; i < dinh.length; i++) {
      const h = dinh[i] * (r.height * 0.9);
      g.fillRect(i * w, (r.height - h) / 2, Math.max(0.6, w - 0.3), h);
    }
  }

  const t = am.currentTime || 0;
  g.fillStyle = "#887ff4";
  g.fillRect((t / dai) * r.width, 0, 1.5, r.height);
}

$("song").onclick = (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  const dai = am.duration || 1;
  am.currentTime = ((e.clientX - r.left) / r.width) * dai;
  am.play();
};

$("phat").onclick = () => (am.paused ? am.play() : am.pause());
am.onplay = () => ($("phat").textContent = "Pause");
am.onpause = () => ($("phat").textContent = "Play");

am.ontimeupdate = () => {
  $("gio").textContent = gio(am.currentTime) + " / " + gio(am.duration || 0);
  veSong();
  const i = cau.findIndex((c) => am.currentTime >= c.start && am.currentTime <= c.end);
  if (i !== dangChon) {
    dangChon = i;
    const hang = $("dong-loi").children;
    for (let k = 0; k < hang.length; k++) hang[k].classList.toggle("dang", k === i);
  }
};

window.addEventListener("resize", () => { if (!$("kq").hidden) veSong(); });

// ------------------------------------------------------------------ xuất file

document.querySelector(".xuat").onclick = (e) => {
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
