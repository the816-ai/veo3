## Trình ghép & nâng cấp video 9:16 (TikTok) - Tiếng Việt

### Tính năng
- Chọn nhiều video hoặc cả thư mục, tự nối theo thứ tự tên file
- Nếu chỉ 1 video: tự động nhân đôi để đủ thời lượng (ghép 2 lần)
- Mặc định chuẩn 9:16 dọc 4K (2160x3840), scale Lanczos + pad
- Mặc định 60fps mượt, sharpen + auto color
- Transition mặc định Crossfade 0.8s giữa 2 clip
- Xóa logo mặc định bật (auto góc), có thể chỉnh preset/kích thước/lề
- Tắt tất cả âm thanh (mặc định BẬT); hoặc giữ âm thanh gốc nếu bỏ chọn
- Tùy chọn tăng tốc: NVENC GPU (nếu có), preset encoder, threads, faststart
- Xuất MP4 H.264/H.265, yuv420p, bitrate tùy chọn
- Thanh tiến trình + log

### Yêu cầu

#### Chạy từ source code:
- Python 3.9+
- FFmpeg (tải từ [ffmpeg.org](https://ffmpeg.org/download.html) hoặc để build script tự tải)

#### Chạy từ EXE đã build:
- Windows 10/11 (64-bit)
- Không cần cài Python hay FFmpeg

### Cài đặt & Chạy

#### Từ source code:
```bash
pip install -r requirements.txt
python main.py
```

#### Build portable EXE (1 file):
```bash
.\build.bat
```
Sau khi build xong, file `dist\Veo3App.exe` có thể chạy trực tiếp trên máy khác (không cần Python/FFmpeg).

#### Build installer (cần Inno Setup):
Sau khi build EXE, chạy:
```bash
iscc installer.iss
```
File `dist\Veo3Setup.exe` sẽ được tạo để cài đặt chuẩn.

#### Ký số (tùy chọn):
Nếu có chứng thư số, set biến môi trường và chạy:
```bash
set CERT_PATH=path\to\cert.pfx
set CERT_PASSWORD=your_password
.\sign.bat
```

### Phân phối

**Để gửi cho người khác sử dụng:**
- Chỉ cần gửi file `dist\Veo3App.exe` (portable, chạy ngay)
- Hoặc file `dist\Veo3Setup.exe` (installer, cài đặt chuẩn)

**Lưu ý SmartScreen:**
- Lần đầu chạy có thể bị cảnh báo "Unknown publisher"
- Chọn "More info" → "Run anyway"
- Ký số (code signing) sẽ giảm cảnh báo này

### Ghi chú
- Crossfade: `xfade` (video) + `acrossfade` (audio), tự tính offset theo độ dài clip 1.
- NVENC cần GPU NVIDIA + driver hỗ trợ; nếu không có, tắt NVENC trong phần Tối ưu tốc độ.
- FFmpeg được tự động bundle vào EXE, không cần cài riêng khi chạy từ EXE.
