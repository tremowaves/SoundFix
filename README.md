# SoundFix - Bộ xử lý âm thanh tự động cho Game

## 📖 Mô tả
SoundFix là ứng dụng desktop tự động xử lý âm thanh cho game sound effects. Ứng dụng sử dụng AI để nhận diện loại âm thanh dựa trên tên file và áp dụng các preset EQ phù hợp.

## ✨ Tính năng chính
- 🎯 **Tự động nhận diện loại âm thanh** dựa trên tên file
- 🎛️ **7 preset EQ chuyên nghiệp** cho từng loại âm thanh
- 🔊 **Xử lý âm thanh nâng cao** với bandpass filter
- 📦 **Xuất file ZIP** tự động với timestamp
- 🖥️ **Giao diện desktop** dễ sử dụng với Tkinter
- 📊 **Thống kê chi tiết** quá trình xử lý

## 🎵 Các preset âm thanh

| Loại âm thanh | Tần số thấp | Tần số cao | Âm lượng | Mô tả |
|---------------|-------------|------------|----------|-------|
| **UI SFX** | 200 Hz | 6000 Hz | 0 dB | Tối ưu cho âm thanh giao diện |
| **Footstep** | 100 Hz | 5000 Hz | -2 dB | Giảm bass và treble cho bước chân |
| **Attack/Impact** | 150 Hz | 7000 Hz | -2 dB | Tập trung vào âm thanh va chạm |
| **Voice/Dialog** | 150 Hz | 8000 Hz | 0 dB | Tối ưu cho giọng nói |
| **Ambient** | 80 Hz | 8000 Hz | -8 dB | Âm thanh môi trường |
| **Environment Tone** | 60 Hz | 6000 Hz | -14 dB | Âm thanh môi trường nhẹ |
| **Music Background** | 100 Hz | 12000 Hz | -8 dB | Nhạc nền |

## 🚀 Cài đặt

### Yêu cầu hệ thống
- Python 3.8+
- FFmpeg (đã cài đặt)
- Windows 10/11

### Cài đặt dependencies
```bash
pip install numpy scipy librosa soundfile tkinter
```

### Cài đặt FFmpeg
1. Tải FFmpeg từ: https://ffmpeg.org/download.html
2. Thêm FFmpeg vào PATH của Windows
3. Kiểm tra cài đặt: `ffmpeg -version`

## 📁 Cấu trúc thư mục
```
Sound Fix/
├── soundfix_desktop.py    # Ứng dụng chính
├── test_filter.py         # Script test filter
├── README.md             # Hướng dẫn này
└── requirements.txt      # Dependencies
```

## 🎮 Cách sử dụng

### 1. Chạy ứng dụng
```bash
python soundfix_desktop.py
```

### 2. Chọn folder âm thanh gốc
- Click "Chọn..." để chọn thư mục chứa file âm thanh
- Hỗ trợ: WAV, MP3, FLAC, OGG, M4A, AAC

### 3. Chọn thư mục đích
- Click "Chọn..." để chọn nơi lưu file ZIP kết quả

### 4. Xử lý và xuất ZIP
- Click "Xử lý và xuất ZIP" để bắt đầu
- Theo dõi tiến trình trong log
- File ZIP sẽ được tạo tự động với timestamp

## 🎯 Quy tắc đặt tên file

Ứng dụng tự động nhận diện loại âm thanh dựa trên từ khóa trong tên file:

### Từ khóa được hỗ trợ:
- **Footstep**: `footstep`, `step`
- **Attack/Impact**: `impact`, `attack`, `hit`
- **UI SFX**: `ui_click`, `ui_sfx`, `ui`, `click`
- **Voice/Dialog**: `voice`, `dialog`, `speech`
- **Ambient**: `ambient`, `rain`, `water`, `drip`, `wind`, `air`
- **Environment Tone**: `env`, `environment`, `rattle`, `window`, `door`, `creak`
- **Music Background**: `music`

### Ví dụ tên file:
```
✅ Ambient_Rain_Night_var7_(No Noise).wav    → Ambient preset
✅ Window_Rattle_var9_(No Noise).wav         → Environment Tone preset
✅ Player_Footstep_Wood_01.wav               → Footstep preset
✅ UI_Click_Button_01.wav                    → UI SFX preset
❌ Unknown_Sound_01.wav                      → Không nhận diện được
```

## 🔧 Tùy chỉnh

### Thêm preset mới
Chỉnh sửa `PRESETS` trong `soundfix_desktop.py`:
```python
PRESETS = {
    'Tên Preset': {'lowcut': 100, 'highcut': 8000, 'volume': -2},
    # Thêm preset mới ở đây
}
```

### Thêm từ khóa nhận diện
Chỉnh sửa hàm `get_category()` trong `soundfix_desktop.py`:
```python
elif "từ_khóa_mới" in fname:
    return 'Tên Preset'
```

## 🧪 Test và Debug

### Chạy test filter
```bash
python test_filter.py
```
Script này sẽ:
- Tạo tín hiệu test với nhiều tần số
- Áp dụng filter bandpass
- Hiển thị đồ thị đáp ứng tần số
- Tạo file test để nghe thử

### Debug logging
Ứng dụng hiển thị thông tin chi tiết trong console:
```
🎵 Xử lý file.wav với preset Ambient:
   - Lowcut: 80Hz
   - Highcut: 8000Hz
   - Volume: -8dB
   - Sample rate: 44100Hz
   - Channels: 2
```

## 📊 Thống kê kết quả
Sau khi xử lý, ứng dụng hiển thị:
- ✅ Số file thành công
- ❌ Số file lỗi
- 📦 Đường dẫn file ZIP

## 🐛 Xử lý lỗi thường gặp

### Lỗi "Format not recognised"
- Kiểm tra file âm thanh có bị hỏng không
- Thử chuyển đổi sang WAV bằng FFmpeg

### Lỗi "Không xác định loại âm thanh"
- Đổi tên file theo quy tắc đặt tên
- Thêm từ khóa vào hàm `get_category()`

### Lỗi thiếu dependencies
```bash
pip install -r requirements.txt
```

## 📝 Changelog

### Version 1.1
- ✅ Cải thiện nhận diện preset
- ✅ Thêm debug logging
- ✅ Cải thiện error handling
- ✅ Thêm thống kê chi tiết

### Version 1.0
- ✅ Ứng dụng desktop với Tkinter
- ✅ 7 preset EQ chuyên nghiệp
- ✅ Xuất file ZIP tự động

## 🤝 Đóng góp
1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

## 📄 License
MIT License - Xem file LICENSE để biết thêm chi tiết

## 📞 Hỗ trợ
Nếu gặp vấn đề, vui lòng tạo issue trên GitHub hoặc liên hệ qua email.

---
**SoundFix** - Làm cho âm thanh game trở nên chuyên nghiệp hơn! 🎮🎵 