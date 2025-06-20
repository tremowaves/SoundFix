import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, sosfilt
from pathlib import Path
import datetime

def get_category(file_name):
    fname = file_name.lower()
    if "footstep" in fname or "step" in fname: return 'Footstep'
    if "impact" in fname or "attack" in fname or "hit" in fname: return 'Attack/Impact'
    if "ui_click" in fname or "ui_sfx" in fname or "ui" in fname or "click" in fname: return 'UI SFX'
    if "voice" in fname or "dialog" in fname or "speech" in fname: return 'Voice/Dialog'
    if "ambient" in fname: return 'Ambient'
    if "env" in fname or "environment" in fname: return 'Environment Tone'
    if "music" in fname: return 'Music Background'
    if "rattle" in fname or "window" in fname or "door" in fname or "creak" in fname: return 'Environment Tone'
    if "rain" in fname or "water" in fname or "drip" in fname: return 'Ambient'
    if "wind" in fname or "air" in fname: return 'Ambient'
    if "metal" in fname or "wood" in fname or "glass" in fname: return 'Attack/Impact'
    return None

# ==============================================================================
# PRESETS ĐÃ CẬP NHẬT VỚI LOGIC MỚI
# 'attenuation_db': Độ suy giảm (bằng dB) cho các tần số bên ngoài dải mong muốn.
# ==============================================================================
PRESETS = {
    'UI SFX':     {'lowcut': 200, 'highcut': 6000,  'volume': 0,   'attenuation_db': -60},
    'Footstep':   {'lowcut': 100, 'highcut': 5000,  'volume': -2,  'attenuation_db': -60},
    'Attack/Impact': {'lowcut': 150, 'highcut': 7000,  'volume': -2,  'attenuation_db': -60},
    'Voice/Dialog':  {'lowcut': 150, 'highcut': 8000, 'volume': 0,   'attenuation_db': -60},
    'Ambient':    {'lowcut': 80,  'highcut': 8000, 'volume': -8,  'attenuation_db': -50},
    'Environment Tone': {'lowcut': 60,  'highcut': 6000, 'volume': -14, 'attenuation_db': -50},
    'Music Background': {'lowcut': 100, 'highcut': 12000, 'volume': -8,  'attenuation_db': -60}
}

# ------------------------------------------------------------------------------
# HÀM LỌC HELPER (GIỮ NGUYÊN)
# ------------------------------------------------------------------------------
def butter_bandpass_filter(data, lowcut, highcut, sr, order=8):
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = highcut / nyq
    sos = butter(order, [low, high], analog=False, btype='band', output='sos')
    
    if len(data.shape) > 1:
        filtered = np.zeros_like(data)
        for ch in range(data.shape[0]):
            filtered[ch] = sosfilt(sos, data[ch])
        return filtered
    else:
        filtered = sosfilt(sos, data)
        return filtered

# ==============================================================================
# HÀM LỌC HYBRID MỚI - TRÁI TIM CỦA LOGIC MỚI
# ==============================================================================
def hybrid_brickwall_filter(data, lowcut, highcut, sr, attenuation_db=-60):
    """
    Tạo hiệu ứng 'brickwall' bằng cách tách tín hiệu thành pass-band và stop-band,
    sau đó giảm gain của stop-band và tái tổ hợp chúng.
    """
    # 1. Tách tín hiệu Pass-band (dải tần muốn giữ lại)
    # Sử dụng order cao hơn (ví dụ: 8) để tách bạch hơn
    y_pass = butter_bandpass_filter(data, lowcut, highcut, sr, order=8)
    
    # 2. Tạo tín hiệu Stop-band (phần còn lại) bằng cách lấy gốc trừ đi pass-band
    y_stop = data - y_pass
    
    # 3. Tính toán hệ số gain để giảm âm cho stop-band
    reduction_gain = 10 ** (attenuation_db / 20.0)
    
    # 4. Giảm âm stop-band
    y_stop_attenuated = y_stop * reduction_gain
    
    # 5. Tái tổ hợp tín hiệu: Pass-band + Stop-band đã giảm âm
    y_hybrid = y_pass + y_stop_attenuated
    
    return y_hybrid

# ==============================================================================
# HÀM XỬ LÝ ÂM THANH ĐÃ ĐƯỢC CẬP NHẬT
# ==============================================================================
def process_audio_file(audio_path, output_dir):
    file_name = os.path.basename(audio_path)
    category = get_category(file_name)
    if category is None:
        return f"❌ Không xác định loại âm thanh cho file: {file_name}"
    
    try:
        preset = PRESETS[category]
        
        print(f"🎵 Xử lý {file_name} với preset {category}:")
        print(f"   - Dải tần: {preset['lowcut']}Hz - {preset['highcut']}Hz")
        print(f"   - Suy giảm ngoài dải: {preset['attenuation_db']}dB")
        print(f"   - Volume tổng: {preset['volume']}dB")
        
        try:
            y, sr = librosa.load(audio_path, sr=None, mono=False)
        except Exception:
            try:
                data, sr = sf.read(audio_path)
                y = data.T
                if len(y.shape) == 1:
                    y = y.reshape(1, -1)
            except Exception as sf_error:
                return f"❌ Không thể đọc file âm thanh '{file_name}': {str(sf_error)}"
        
        print(f"   - Sample rate: {sr}Hz, Channels: {y.shape[0] if len(y.shape) > 1 else 1}")
        
        # --- THAY ĐỔI QUAN TRỌNG Ở ĐÂY ---
        # Áp dụng bộ lọc Hybrid mới
        y_eq = hybrid_brickwall_filter(y, preset['lowcut'], preset['highcut'], sr, preset['attenuation_db'])

        # Áp dụng gain tổng thể
        total_gain = 10 ** (preset['volume'] / 20)
        y_processed = y_eq * total_gain
        # ---------------------------------
        
        if np.any(np.isnan(y_processed)) or np.any(np.isinf(y_processed)):
            return f"❌ Dữ liệu âm thanh lỗi (NaN/Inf) cho file: {file_name}"
        
        name, ext = os.path.splitext(file_name)
        output_name = f"processed_{name}{ext}"
        output_path = os.path.join(output_dir, output_name)
        
        try:
            sf.write(output_path, y_processed.T.astype(np.float32), sr)
        except Exception as write_error:
            return f"❌ Lỗi ghi file '{file_name}': {str(write_error)}"
        
        return f"✅ {file_name} → {output_name} ({category})"
        
    except Exception as e:
        return f"❌ Lỗi xử lý '{file_name}': {str(e)}"

# ==============================================================================
# CÁC HÀM GIAO DIỆN VÀ XỬ LÝ HÀNG LOẠT (GIỮ NGUYÊN)
# ==============================================================================
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
    
    success_count = 0
    error_count = 0
    
    for i, file_path in enumerate(audio_files):
        msg = process_audio_file(file_path, output_dir)
        log_func(f"[{i+1}/{len(audio_files)}] {msg}")
        
        if "✅" in msg:
            success_count += 1
        else:
            error_count += 1
    
    log_func(f"\n📊 Thống kê:")
    log_func(f"✅ Thành công: {success_count} file")
    log_func(f"❌ Lỗi: {error_count} file")
    log_func(f"📁 Thư mục output: {output_dir}")
    
    messagebox.showinfo("Xong!", f"Đã xử lý xong!\n✅ Thành công: {success_count} file\n❌ Lỗi: {error_count} file\n📁 Thư mục output: {output_dir}")

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
        path = filedialog.askdirectory(title="Chọn thư mục đích để lưu file đã xử lý")
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

    tk.Label(root, text="1. Chọn folder chứa âm thanh gốc:").pack(anchor='w', padx=10, pady=(10,0))
    frame1 = tk.Frame(root)
    frame1.pack(fill='x', padx=10)
    tk.Entry(frame1, textvariable=folder_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame1, text="Chọn...", command=choose_folder).pack(side='left', padx=5)

    tk.Label(root, text="2. Chọn thư mục đích để lưu file đã xử lý:").pack(anchor='w', padx=10, pady=(10,0))
    frame2 = tk.Frame(root)
    frame2.pack(fill='x', padx=10)
    tk.Entry(frame2, textvariable=dest_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame2, text="Chọn...", command=choose_dest).pack(side='left', padx=5)

    tk.Button(root, text="3. Xử lý và xuất file", command=start_process, bg='#ff8800', fg='white', font=('Arial', 12, 'bold')).pack(pady=15)

    tk.Label(root, text="Log tiến trình:").pack(anchor='w', padx=10)
    log_box = scrolledtext.ScrolledText(root, height=15, font=('Consolas', 10))
    log_box.pack(fill='both', expand=True, padx=10, pady=(0,10))

    root.mainloop()

if __name__ == "__main__":
    run_app()