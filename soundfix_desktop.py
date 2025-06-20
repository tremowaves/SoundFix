import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, sosfilt
from pathlib import Path
import datetime

def get_category(file_name):
    # (Hàm này giữ nguyên)
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
# PRESETS ĐÃ CẬP NHẬT VỚI CÁC THAM SỐ CHO BỘ LỌC DYNAMIC
# ==============================================================================
PRESETS = {
    'UI SFX':     {'lowcut': 200, 'highcut': 6000, 'volume': 0,   'attenuation_db': -80, 'gate_threshold_db': -50, 'expansion_ratio': 0.1},
    'Footstep':   {'lowcut': 100, 'highcut': 5000, 'volume': -2,  'attenuation_db': -80, 'gate_threshold_db': -50, 'expansion_ratio': 0.1},
    'Attack/Impact':{'lowcut': 150, 'highcut': 7000, 'volume': -2,  'attenuation_db': -80, 'gate_threshold_db': -50, 'expansion_ratio': 0.1},
    'Voice/Dialog': {'lowcut': 150, 'highcut': 8000, 'volume': 0,   'attenuation_db': -80, 'gate_threshold_db': -60, 'expansion_ratio': 0.05},
    'Ambient':    {'lowcut': 80,  'highcut': 8000, 'volume': -8,  'attenuation_db': -70, 'gate_threshold_db': -50, 'expansion_ratio': 0.1},
    'Environment Tone':{'lowcut': 60, 'highcut': 6000, 'volume': -14, 'attenuation_db': -70, 'gate_threshold_db': -50, 'expansion_ratio': 0.1},
    'Music Background':{'lowcut': 100, 'highcut': 12000,'volume': -8,  'attenuation_db': -80, 'gate_threshold_db': -50, 'expansion_ratio': 0.1}
}

# ==============================================================================
# CÁC ENGINE LỌC ÂM THANH
# ==============================================================================

def butter_filter(data, lowcut, highcut, sr, order=20, btype='band'):
    """Hàm lọc Butterworth cơ bản cho cả band-pass và band-stop."""
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = highcut / nyq
    if btype == 'band':
        sos = butter(order, [low, high], analog=False, btype='band', output='sos')
    elif btype == 'bandstop':
        sos = butter(order, [low, high], analog=False, btype='bandstop', output='sos')
    
    if len(data.shape) > 1:
        filtered = np.zeros_like(data)
        for ch in range(data.shape[0]):
            filtered[ch] = sosfilt(sos, data[ch])
        return filtered
    else:
        return sosfilt(sos, data)

def hybrid_brickwall_filter(data, lowcut, highcut, sr, attenuation_db, **kwargs):
    """Engine 2: Multi-band gain với bộ lọc bậc cao."""
    y_pass = butter_filter(data, lowcut, highcut, sr, order=24, btype='band')
    y_stop = data - y_pass
    reduction_gain = 10 ** (attenuation_db / 20.0)
    y_stop_attenuated = y_stop * reduction_gain
    return y_pass + y_stop_attenuated

def dynamic_hybrid_filter(data, lowcut, highcut, sr, attenuation_db, gate_threshold_db, expansion_ratio, **kwargs):
    """Engine 3: Tối ưu - Multi-band gain kết hợp Dynamic Processor (Gate)."""
    # 1. Tách pass-band với bộ lọc bậc siêu cao (32) để có sự tách bạch tối đa
    y_pass = butter_filter(data, lowcut, highcut, sr, order=32, btype='band')
    
    # 2. Tạo stop-band
    y_stop = data - y_pass

    # 3. Áp dụng Dynamic Processor (Gate/Expander) lên y_stop
    # Chuyển ngưỡng từ dB sang biên độ tuyến tính
    threshold_linear = 10 ** (gate_threshold_db / 20.0)
    
    # Tính toán năng lượng (RMS) theo từng khối để quyết định gain
    frame_size = 512
    hop_size = 256
    
    # Xử lý từng kênh
    if len(data.shape) > 1:
        y_stop_gated = np.zeros_like(y_stop)
        for ch in range(data.shape[0]):
            rms = librosa.feature.rms(y=y_stop[ch], frame_length=frame_size, hop_length=hop_size)[0]
            gain_envelope = np.ones_like(rms)
            gain_envelope[rms < threshold_linear] = expansion_ratio
            # Tạo một gain mượt mà cho toàn bộ tín hiệu
            smooth_gain = np.repeat(gain_envelope, hop_size)
            # Cắt bớt phần thừa để khớp độ dài
            y_stop_gated[ch] = y_stop[ch, :len(smooth_gain)] * smooth_gain
    else: # Mono
        rms = librosa.feature.rms(y=y_stop, frame_length=frame_size, hop_length=hop_size)[0]
        gain_envelope = np.ones_like(rms)
        gain_envelope[rms < threshold_linear] = expansion_ratio
        smooth_gain = np.repeat(gain_envelope, hop_size)
        y_stop_gated = y_stop[:len(smooth_gain)] * smooth_gain
        
    # 4. Áp dụng thêm suy giảm tĩnh
    reduction_gain = 10 ** (attenuation_db / 20.0)
    y_stop_final = y_stop_gated * reduction_gain
    
    # 5. Tái tổ hợp
    # Đảm bảo y_pass có cùng độ dài với y_stop_final
    min_len = min(len(y_pass.T), len(y_stop_final.T))
    return y_pass[:,:min_len] + y_stop_final[:,:min_len]


# ==============================================================================
# HÀM XỬ LÝ ÂM THANH CHÍNH (ĐÃ CẬP NHẬT ĐỂ CHỌN ENGINE)
# ==============================================================================
def process_audio_file(audio_path, output_dir, algorithm):
    file_name = os.path.basename(audio_path)
    category = get_category(file_name)
    if category is None:
        return f"❌ Không xác định loại âm thanh cho file: {file_name}"
    
    try:
        preset = PRESETS[category]
        print(f"🎵 Xử lý {file_name} với preset {category} bằng Engine '{algorithm}'")
        
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        
        # --- LỰA CHỌN ENGINE DỰA TRÊN LỰA CHỌN CỦA NGƯỜI DÙNG ---
        if algorithm == "Butterworth Filter":
            y_eq = butter_filter(y, preset['lowcut'], preset['highcut'], sr, order=20, btype='band')
        elif algorithm == "Hybrid Brickwall":
            y_eq = hybrid_brickwall_filter(y, **preset, sr=sr)
        elif algorithm == "Dynamic Hybrid Brickwall":
            y_eq = dynamic_hybrid_filter(y, **preset, sr=sr)
        else: # Mặc định
            y_eq = hybrid_brickwall_filter(y, **preset, sr=sr)
        # -------------------------------------------------------------

        total_gain = 10 ** (preset['volume'] / 20)
        y_processed = y_eq * total_gain
        
        if np.any(np.isnan(y_processed)) or np.any(np.isinf(y_processed)):
            return f"❌ Dữ liệu lỗi cho file: {file_name}"
        
        output_name = f"processed_{file_name}"
        output_path = os.path.join(output_dir, output_name)
        sf.write(output_path, y_processed.T.astype(np.float32), sr)
        
        return f"✅ {file_name} → {output_name} ({category})"
        
    except Exception as e:
        return f"❌ Lỗi xử lý '{file_name}': {e}"

# ==============================================================================
# GIAO DIỆN VÀ LOGIC HÀNG LOẠT (ĐÃ CẬP NHẬT)
# ==============================================================================
def batch_process(folder_path, dest_folder, log_func, algorithm):
    # ... (Hàm này giữ nguyên, chỉ truyền thêm 'algorithm')
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
        msg = process_audio_file(file_path, output_dir, algorithm)
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

def get_audio_files_from_folder(folder_path):
    audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
    audio_files = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in audio_extensions):
                audio_files.append(os.path.join(root, f))
    return audio_files

def run_app():
    root = tk.Tk()
    root.title("SoundFix Pro - Bộ xử lý âm thanh đa Engine")
    root.geometry("700x550")

    folder_var = tk.StringVar()
    dest_var = tk.StringVar()
    algorithm_var = tk.StringVar()

    # --- UI CẬP NHẬT ---
    # Frame cho lựa chọn
    tk.Label(root, text="1. Chọn folder chứa âm thanh gốc:").pack(anchor='w', padx=10, pady=(10,0))
    frame1 = tk.Frame(root)
    frame1.pack(fill='x', padx=10)
    tk.Entry(frame1, textvariable=folder_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame1, text="Chọn...", command=lambda: folder_var.set(filedialog.askdirectory(title="Chọn folder âm thanh gốc"))).pack(side='left', padx=5)

    tk.Label(root, text="2. Chọn thư mục đích để lưu file đã xử lý:").pack(anchor='w', padx=10, pady=(10,0))
    frame2 = tk.Frame(root)
    frame2.pack(fill='x', padx=10)
    tk.Entry(frame2, textvariable=dest_var, width=60).pack(side='left', expand=True, fill='x')
    tk.Button(frame2, text="Chọn...", command=lambda: dest_var.set(filedialog.askdirectory(title="Chọn thư mục đích"))).pack(side='left', padx=5)

    # --- MENU LỰA CHỌN ENGINE MỚI ---
    tk.Label(root, text="3. Chọn Engine xử lý:", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(15,0))
    algorithms = ["Dynamic Hybrid Brickwall", "Hybrid Brickwall", "Butterworth Filter"]
    algorithm_var.set(algorithms[0]) # Mặc định chọn engine tốt nhất
    
    # Sử dụng ttk.Combobox để đẹp hơn
    combo = ttk.Combobox(root, textvariable=algorithm_var, values=algorithms, state="readonly")
    combo.pack(fill='x', padx=10, pady=5)
    
    def start_process():
        folder = folder_var.get()
        dest = dest_var.get()
        algorithm = algorithm_var.get()
        log_box.delete(1.0, tk.END)
        if not all([folder, dest, algorithm]):
            messagebox.showerror("Lỗi", "Vui lòng điền đầy đủ thông tin!")
            return
        threading.Thread(target=batch_process, args=(folder, dest, log, algorithm), daemon=True).start()

    tk.Button(root, text="4. Bắt đầu xử lý", command=start_process, bg='#007acc', fg='white', font=('Arial', 12, 'bold')).pack(pady=20)

    log_box = scrolledtext.ScrolledText(root, height=15, font=('Consolas', 10), bg="#2d2d2d", fg="#dcdcdc")
    log_box.pack(fill='both', expand=True, padx=10, pady=(0,10))
    
    def log(msg):
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)

    root.mainloop()

if __name__ == "__main__":
    run_app()