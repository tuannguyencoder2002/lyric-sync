// Vỏ .exe cho ứng dụng. Nó KHÔNG nhét Python vào trong như PyInstaller — chỉ
// làm đúng một việc: gọi runtime\python\pythonw.exe chạy launcher.py.
//
// Vì sao làm thế thay vì PyInstaller: gói này mang theo hơn 3 GB thư viện CUDA.
// PyInstaller phải giải nén toàn bộ ra thư mục tạm mỗi lần khởi động, mất hàng
// chục giây và tốn thêm chừng ấy dung lượng. Cách này khởi động tức thì, và
// khi có trục trặc thì mọi thứ vẫn nằm nguyên ở dạng file thường để lần ra.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

static class Launcher
{
    [STAThread]
    static int Main(string[] args)
    {
        string goc = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string py = Path.Combine(goc, @"runtime\python\pythonw.exe");
        string kich_ban = Path.Combine(goc, "launcher.py");

        if (!File.Exists(py) || !File.Exists(kich_ban))
        {
            // Thiếu file thì nói rõ THIẾU CÁI GÌ. Người dùng hay chỉ copy mỗi
            // file .exe sang máy khác rồi không hiểu vì sao nó không chạy.
            MessageBox.Show(
                "Thiếu file trong thư mục cài đặt:\n\n" +
                (File.Exists(py) ? "" : py + "\n") +
                (File.Exists(kich_ban) ? "" : kich_ban + "\n") +
                "\nHãy chép NGUYÊN CẢ THƯ MỤC sang máy này, không chép riêng file .exe.",
                "Lyric Sync", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        var kh = new ProcessStartInfo
        {
            FileName = py,
            Arguments = "\"" + kich_ban + "\"",
            WorkingDirectory = goc,
            UseShellExecute = false,
        };
        foreach (string a in args) kh.Arguments += " \"" + a + "\"";

        try
        {
            Process.Start(kh);
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show("Không chạy được:\n\n" + e.Message,
                            "Lyric Sync", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
