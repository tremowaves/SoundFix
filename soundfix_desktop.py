import os
import shutil
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, lfilter
from pathlib import Path
import datetime

def get_category(file_name):
    fname = file_name.lower()
    
    # Kiểm tra các từ khóa trong toàn bộ tên file
    if "footstep" in fname or "step" in fname:
        return 'Footstep'
    elif "impact" in fname or "attack" in fname or "hit" in fname:
        return 'Attack/Impact'
    elif "ui_click" in fname or "ui_sfx" in fname or "ui" in fname or "click" in fname:
        return 'UI SFX'
    elif "voice" in fname or "dialog" in fname or "speech" in fname:
        return 'Voice/Dialog'
    elif "ambient" in fname:
        return 'Ambient'
    elif "env" in fname or "environment" in fname:
        return 'Environment Tone'
    elif "music" in fname:
        return 'Music Background'
    elif "rattle" in fname or "window" in fname or "door" in fname or "creak" in fname:
        return 'Environment Tone'  # Các âm thanh môi trường
    elif "rain" in fname or "water" in fname or "drip" in fname:
        return 'Ambient'  # Âm thanh môi trường như mưa
    elif "wind" in fname or "air" in fname:
        return 'Ambient'
    elif "metal" in fname or "wood" in fname or "glass" in fname:
        return 'Attack/Impact'  # Âm thanh va chạm vật liệu
    else:
        return None

PRESETS = {
    'UI SFX':     {'lowcut': 200, 'highcut': 6000,  'volume': 0},    # Tập trung vào mid-range
    'Footstep':   {'lowcut': 100, 'highcut': 5000,  'volume': -2},   # Giảm bass và treble
    'Attack/Impact': {'lowcut': 150, 'highcut': 7000,  'volume': -2}, # Tập trung vào impact
    'Voice/Dialog':  {'lowcut': 150, 'highcut': 8000, 'volume': 0},   # Tối ưu cho giọng nói
    'Ambient':    {'lowcut': 80,  'highcut': 8000, 'volume': -8},     # Giảm bass và treble
    'Environment Tone': {'lowcut': 60,  'highcut': 6000, 'volume': -14}, # Giảm nhiều bass và treble
    'Music Background': {'lowcut': 100, 'highcut': 12000, 'volume': -8}  # Giữ mid-range
}

def butter_filter(data, sr, lowcut, highcut):
    """
    Áp dụng bandpass filter với Butterworth
    """
    # Đảm bảo tần số cắt hợp lệ
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = highcut / nyq
    
    # Kiểm tra tần số cắt có hợp lệ không
    if low >= 1.0 or high >= 1.0:
        print(f"Warning: Tần số cắt quá cao! low={lowcut}Hz, high={highcut}Hz, nyq={nyq}Hz")
        return data
    
    if low >= high:
        print(f"Warning: Tần số thấp >= tần số cao! low={lowcut}Hz, high={highcut}Hz")
        return data
    
    # Tạo filter với order cao hơn để có hiệu ứng rõ ràng hơn
    b, a = butter(4, [low, high], btype='band')
    
    # Áp dụng filter
    filtered_data = lfilter(b, a, data)
    
    return filtered_data

def process_audio_file(audio_path, output_dir):
    file_name = os.path.basename(audio_path)
    category = get_category(file_name)
    if category is None:
        return f"❌ Không xác định loại âm thanh cho file: {file_name}"
    
    try:
        preset = PRESETS[category]
        
        # Debug: Hiển thị thông số được áp dụng
        print(f"🎵 Xử lý {file_name} với preset {category}:")
        print(f"   - Lowcut: {preset['lowcut']}Hz")
        print(f"   - Highcut: {preset['highcut']}Hz") 
        print(f"   - Volume: {preset['volume']}dB")
        
        # Thử đọc file với librosa trước
        try:
            y, sr = librosa.load(audio_path, sr=None, mono=False)
        except Exception as librosa_error:
            # Fallback: thử với soundfile
            try:
                y, sr = sf.read(audio_path)
                if len(y.shape) == 1:
                    y = y.reshape(1, -1)  # Chuyển thành stereo format
                else:
                    y = y.T  # Transpose để phù hợp với format của librosa
            except Exception as sf_error:
                return f"❌ Không thể đọc file âm thanh '{file_name}': {str(librosa_error)} | {str(sf_error)}"
        
        print(f"   - Sample rate: {sr}Hz")
        print(f"   - Channels: {y.shape[0] if len(y.shape) > 1 else 1}")
        
        # Xử lý âm thanh
        if len(y.shape) > 1:
            y_processed = np.zeros_like(y)
            for channel in range(y.shape[0]):
                y_eq = butter_filter(y[channel], sr, preset['lowcut'], preset['highcut'])
                gain = 10 ** (preset['volume'] / 20)
                y_processed[channel] = y_eq * gain
        else:
            y_eq = butter_filter(y, sr, preset['lowcut'], preset['highcut'])
            gain = 10 ** (preset['volume'] / 20)
            y_processed = y_eq * gain
        
        # Kiểm tra NaN/Inf
        if np.any(np.isnan(y_processed)) or np.any(np.isinf(y_processed)):
            return f"❌ Dữ liệu âm thanh lỗi (NaN/Inf) cho file: {file_name}"
        
        # Tạo tên file output
        name, ext = os.path.splitext(file_name)
        output_name = f"processed_{name}{ext}"
        output_path = os.path.join(output_dir, output_name)
        
        # Lưu file với soundfile
        try:
            if len(y_processed.shape) > 1:
                y_processed = y_processed.T  # Transpose lại để phù hợp với soundfile
            sf.write(output_path, y_processed.astype(np.float32), sr)
        except Exception as write_error:
            return f"❌ Lỗi ghi file '{file_name}': {str(write_error)}"
        
        return f"✅ {file_name} → {output_name} ({category})"
        
    except Exception as e:
        return f"❌ Lỗi xử lý '{file_name}': {str(e)}"

def get_audio_files_from_folder(folder_path):
    audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
    audio_files = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in audio_extensions):
                audio_files.append(os.path.join(root, f))
    return audio_files

def batch_process(folder_path, dest_folder, log_func):
    audio_files = get_audio_files_from_folder(folder_path)
    if not audio_files:
        log_func("Không tìm thấy file âm thanh nào trong folder!")
        return
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = os.path.basename(folder_path)
    output_dir = Path(dest_folder) / f"SoundFix_{folder_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    log_func(f"Bắt đầu xử lý {len(audio_files)} file...")
    log_func(f"Thư mục output: {output_dir}")
    
    results = []
    success_count = 0
    error_count = 0
    
    for i, file_path in enumerate(audio_files):
        msg = process_audio_file(file_path, output_dir)
        log_func(f"[{i+1}/{len(audio_files)}] {msg}")
        results.append(msg)
        
        if "✅" in msg:
            success_count += 1
        else:
            error_count += 1
    
    # Tạo file ZIP
    zip_path = Path(dest_folder) / f"SoundFix_{folder_name}_{timestamp}.zip"
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(output_dir.parent))
        
        log_func(f"\n📊 Thống kê:")
        log_func(f"✅ Thành công: {success_count} file")
        log_func(f"❌ Lỗi: {error_count} file")
        log_func(f"📦 File ZIP: {zip_path}")
        
        messagebox.showinfo("Xong!", f"Đã xử lý xong!\n✅ Thành công: {success_count} file\n❌ Lỗi: {error_count} file\n📦 File ZIP: {zip_path}")
        
    except Exception as e:
        log_func(f"❌ Lỗi tạo file ZIP: {str(e)}")
        messagebox.showerror("Lỗi", f"Không thể tạo file ZIP: {str(e)}")

def run_app():
    root = tk.Tk()
    root.title("SoundFix - Bộ xử lý âm thanh tự động cho Game")
    root.geometry("700x500")

    folder_var = tk.StringVar()
    dest_var = tk.StringVar()

    def choose_folder():
        path = filedialog.askdirectory(title="Chọn folder âm thanh gốc")
        if path:
            folder_var.set(path)

    def choose_dest():
        path = filedialog.askdirectory(title="Chọn thư mục đích để lưu file ZIP")
        if path:
            dest_var.set(path)

    def log(msg):
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        root.update()

    def start_process():
        folder = folder_var.get()
        dest = dest_var.get()
        log_box.delete(1.0, tk.END)
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Lỗi", "Chưa chọn folder âm thanh hợp lệ!")
            return
        if not dest or not os.path.isdir(dest):
            messagebox.showerror("Lỗi", "Chưa chọn thư mục đích hợp lệ!")
            return
        threading.Thread(target=batch_process, args=(folder, dest, log), daemon=True).start()

    # UI
    tk.Label(root, text="1. Chọn folder chứa âm thanh gốc:").pack(anchor='w', padx=10, pady=(10,0))
    frame1 = tk.Frame(root)
    frame1.pack(fill='x', padx=10)
    tk.Entry(frame1, textvariable=folder_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame1, text="Chọn...", command=choose_folder).pack(side='left', padx=5)

    tk.Label(root, text="2. Chọn thư mục đích để lưu file ZIP:").pack(anchor='w', padx=10, pady=(10,0))
    frame2 = tk.Frame(root)
    frame2.pack(fill='x', padx=10)
    tk.Entry(frame2, textvariable=dest_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame2, text="Chọn...", command=choose_dest).pack(side='left', padx=5)

    tk.Button(root, text="3. Xử lý và xuất ZIP", command=start_process, bg='#ff8800', fg='white', font=('Arial', 12, 'bold')).pack(pady=15)

    tk.Label(root, text="Log tiến trình:").pack(anchor='w', padx=10)
    log_box = scrolledtext.ScrolledText(root, height=15, font=('Consolas', 10))
    log_box.pack(fill='both', expand=True, padx=10, pady=(0,10))

    root.mainloop()

if __name__ == "__main__":
    run_app() 