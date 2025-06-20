import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import numpy as np
from numpy.typing import NDArray
import librosa
import soundfile as sf
from scipy.signal import butter, sosfilt
from pathlib import Path
import datetime
import csv
from typing import Dict, List, Optional, Union, Any, Tuple

# Xử lý import tkinterdnd2 một cách an toàn
DND_SUPPORT = False
try:
    print("DEBUG: Attempting to import tkinterdnd2...")
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_SUPPORT = True
    print("DEBUG: tkinterdnd2 imported successfully.")
except Exception as e:
    print(f"DEBUG: Failed to import tkinterdnd2. Error type: {type(e).__name__}, Message: {e}")
    # Tạo dummy classes để tránh lỗi type checking
    class DND_FILES:
        pass
    
    class TkinterDnD:
        class Tk(tk.Tk):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            
            def drop_target_register(self, *args, **kwargs):
                pass
            
            def dnd_bind(self, *args, **kwargs):
                pass

# ==============================================================================
# LOGIC ĐỌC CẤU HÌNH VÀ XỬ LÝ ÂM THANH
# ==============================================================================
def load_presets_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(csv_path): 
        raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")
    presets = []
    with open(csv_path, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            try:
                presets.append({
                    'priority': int(row['priority']),
                    'keywords': [k.strip().lower() for k in row['keywords'].split(',')],
                    'category_name': row['category_name'],
                    'lowcut': int(row['lowcut']), 
                    'highcut': int(row['highcut']),
                    'volume': float(row['volume']), 
                    'attenuation_db': float(row['attenuation_db']),
                    'gate_threshold_db': float(row['gate_threshold_db']),
                    'expansion_ratio': float(row['expansion_ratio']),
                    'mb_low_thresh': float(row.get('mb_low_thresh', -6.0)),
                    'mb_low_ratio': float(row.get('mb_low_ratio', 4.0)),
                    'mb_mid_thresh': float(row.get('mb_mid_thresh', -4.0)),
                    'mb_mid_ratio': float(row.get('mb_mid_ratio', 3.0)),
                    'mb_high_thresh': float(row.get('mb_high_thresh', -2.0)),
                    'mb_high_ratio': float(row.get('mb_high_ratio', 2.0)),
                })
            except (ValueError, KeyError) as e:
                raise ValueError(f"Lỗi dữ liệu CSV ở hàng: {row}. Chi tiết: {e}")
    presets.sort(key=lambda x: x['priority'])
    return presets

def get_preset_for_file(filename: str, presets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    fn_lower = filename.lower()
    for preset in presets:
        if any(keyword in fn_lower for keyword in preset['keywords']): 
            return preset
    return None

def butter_filter(data: NDArray, lowcut: int, highcut: int, sr: int, order: int = 20, btype: str = 'band') -> NDArray:
    nyq = 0.5 * sr
    low, high = max(0.01, lowcut / nyq), min(0.99, highcut / nyq)
    sos = butter(order, [low, high], analog=False, btype=btype, output='sos')
    if data.ndim > 1:
        result = data.copy()
        for ch in range(data.shape[0]): 
            result[ch] = sosfilt(sos, data[ch])
        return result
    return sosfilt(sos, data)

def multiband_limiting_filter(data: NDArray, sr: int, **preset) -> NDArray:
    """
    Multiband Limiting Filter với 3 dải tần số:
    - Low band: 20Hz - 250Hz
    - Mid band: 250Hz - 4000Hz  
    - High band: 4000Hz - 20000Hz
    """
    # Định nghĩa các dải tần số
    bands = [
        {'low': 20, 'high': 250, 'name': 'Low'},
        {'low': 250, 'high': 4000, 'name': 'Mid'},
        {'low': 4000, 'high': 20000, 'name': 'High'}
    ]
    
    # Các tham số limiting cho từng dải
    limiting_params = {
        'Low': {'threshold': preset.get('mb_low_thresh', -6.0), 'ratio': preset.get('mb_low_ratio', 4.0), 'attack': 0.001, 'release': 0.1},
        'Mid': {'threshold': preset.get('mb_mid_thresh', -4.0), 'ratio': preset.get('mb_mid_ratio', 3.0), 'attack': 0.005, 'release': 0.05},
        'High': {'threshold': preset.get('mb_high_thresh', -2.0), 'ratio': preset.get('mb_high_ratio', 2.0), 'attack': 0.01, 'release': 0.02}
    }
    
    processed_bands = []
    
    for band in bands:
        # Lọc dải tần số
        band_data = butter_filter(data.copy(), band['low'], band['high'], sr, order=24, btype='band')
        
        # Áp dụng limiting cho dải này
        params = limiting_params[band['name']]
        limited_band = apply_limiter(band_data, sr, **params)
        
        processed_bands.append(limited_band)
    
    # Kết hợp các dải đã xử lý
    result = np.zeros_like(data)
    for band_data in processed_bands:
        result += band_data
    
    # Áp dụng EQ chính từ preset
    y_pass = butter_filter(result, preset['lowcut'], preset['highcut'], sr, order=24, btype='band')
    y_stop = result - y_pass
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    
    return y_pass + (y_stop * reduction_gain)

def apply_limiter(data: NDArray, sr: int, threshold: float, ratio: float, attack: float, release: float) -> NDArray:
    """
    Áp dụng limiter cho một dải tần số
    """
    # Chuyển đổi thời gian attack/release thành số mẫu
    attack_samples = int(attack * sr)
    release_samples = int(release * sr)
    
    # Chuyển đổi threshold từ dB sang linear
    threshold_linear = 10 ** (threshold / 20.0)
    
    if data.ndim > 1:
        # Stereo
        result = np.zeros_like(data)
        for ch in range(data.shape[0]):
            result[ch] = apply_limiter_mono(data[ch], threshold_linear, ratio, attack_samples, release_samples)
        return result
    else:
        # Mono
        return apply_limiter_mono(data, threshold_linear, ratio, attack_samples, release_samples)

def apply_limiter_mono(data: NDArray, threshold: float, ratio: float, attack_samples: int, release_samples: int) -> NDArray:
    """
    Áp dụng limiter cho mono channel
    """
    # Đảm bảo data là numpy array
    data = np.asarray(data)
    
    # Tính RMS của tín hiệu
    frame_size = 512
    hop_size = 256
    rms = librosa.feature.rms(y=data, frame_length=frame_size, hop_length=hop_size)[0]
    
    # Tính gain reduction
    gain_reduction = np.ones_like(rms)
    for i, rms_val in enumerate(rms):
        if rms_val > threshold:
            # Tính gain reduction dựa trên ratio
            excess = rms_val - threshold
            reduction = excess * (1 - 1/ratio)
            gain_reduction[i] = (rms_val - reduction) / rms_val
    
    # Smooth gain reduction với attack/release
    smoothed_gain = np.ones_like(gain_reduction)
    for i in range(1, len(gain_reduction)):
        if gain_reduction[i] < smoothed_gain[i-1]:
            # Attack phase
            alpha = 1.0 / attack_samples
        else:
            # Release phase
            alpha = 1.0 / release_samples
        
        smoothed_gain[i] = smoothed_gain[i-1] + alpha * (gain_reduction[i] - smoothed_gain[i-1])
    
    # Áp dụng gain reduction
    gain_signal = np.repeat(smoothed_gain, hop_size)
    proc_len = min(len(data), len(gain_signal))
    
    # Đảm bảo kết quả có cùng độ dài với input
    result = np.zeros_like(data)
    result[:proc_len] = data[:proc_len] * gain_signal[:proc_len]
    
    return result

def hybrid_brickwall_filter(data: NDArray, sr: int, **preset) -> NDArray:
    y_pass = butter_filter(data.copy(), preset['lowcut'], preset['highcut'], sr, order=24, btype='band')
    y_stop = data - y_pass
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    return y_pass + (y_stop * reduction_gain)

def dynamic_hybrid_filter(data: NDArray, sr: int, **preset) -> NDArray:
    y_pass = butter_filter(data.copy(), preset['lowcut'], preset['highcut'], sr, order=32, btype='band')
    y_stop = data - y_pass
    threshold = 10 ** (preset['gate_threshold_db'] / 20.0)
    frame_size, hop_size = 512, 256
    
    y_stop_gated = np.zeros_like(y_stop)
    if data.ndim > 1:
        for ch in range(data.shape[0]):
            rms = librosa.feature.rms(y=y_stop[ch], frame_length=frame_size, hop_length=hop_size)[0]
            gain = np.where(rms < threshold, preset['expansion_ratio'], 1.0)
            smooth_gain = np.repeat(gain, hop_size)
            proc_len = min(y_stop.shape[1], len(smooth_gain))
            y_stop_gated[ch, :proc_len] = y_stop[ch, :proc_len] * smooth_gain[:proc_len]
    else:
        # Code cho mono
        rms = librosa.feature.rms(y=y_stop, frame_length=frame_size, hop_length=hop_size)[0]
        gain = np.where(rms < threshold, preset['expansion_ratio'], 1.0)
        smooth_gain = np.repeat(gain, hop_size)
        proc_len = min(len(y_stop), len(smooth_gain))
        y_stop_gated[:proc_len] = y_stop[:proc_len] * smooth_gain[:proc_len]
        
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    y_stop_final = y_stop_gated * reduction_gain
    
    # Xử lý kết quả cuối cùng một cách an toàn
    if data.ndim > 1:
        final_len = min(y_pass.shape[1], y_stop_final.shape[1])
        result = np.zeros_like(y_pass)
        result[:, :final_len] = y_pass[:, :final_len] + y_stop_final[:, :final_len]
        return result
    else:
        final_len = min(len(y_pass), len(y_stop_final))
        result = np.zeros_like(y_pass)
        result[:final_len] = y_pass[:final_len] + y_stop_final[:final_len]
        return result

def process_audio_file(audio_path: str, output_dir: str, algorithm: str, preset: Optional[Dict[str, Any]]) -> str:
    file_name = os.path.basename(audio_path)
    if preset is None: 
        return f"🟡 Bỏ qua: {file_name} (Không khớp quy tắc)"
    try:
        print(f"🎵 Xử lý {file_name} với '{preset['category_name']}' bằng '{algorithm}'")
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        if y.ndim == 1: 
            y = y[np.newaxis, :]
        
        # Định nghĩa engine functions
        engine_functions = {
            'Butterworth Filter': lambda d, s, p: butter_filter(d, p['lowcut'], p['highcut'], s),
            'Hybrid Brickwall': hybrid_brickwall_filter,
            'Dynamic Hybrid Brickwall': dynamic_hybrid_filter,
            'Multiband Limiting': multiband_limiting_filter
        }
        
        engine = engine_functions.get(algorithm)
        if engine is None:
            return f"❌ Không tìm thấy engine: {algorithm}"
            
        y_eq = engine(y, sr=sr, **preset)
        y_processed = y_eq * (10 ** (preset['volume'] / 20.0))
        if np.any(np.isnan(y_processed)): 
            return f"❌ Dữ liệu lỗi cho file: {file_name}"
        output_name = f"processed_{os.path.splitext(file_name)[0]}{os.path.splitext(audio_path)[1]}"
        sf.write(Path(output_dir) / output_name, y_processed.T.astype(np.float32), sr)
        return f"✅ {file_name} → {output_name} ({preset['category_name']})"
    except Exception as e: 
        return f"❌ Lỗi xử lý '{file_name}': {e}"

def batch_process(folder_path: str, dest_folder: str, csv_path: str, log_func, algorithm: str) -> None:
    try:
        presets = load_presets_from_csv(csv_path)
        log_func(f"Tải thành công {len(presets)} quy tắc từ {os.path.basename(csv_path)}")
    except Exception as e:
        log_func(f"❌ Lỗi: Không thể tải file cấu hình.\n{e}")
        return
    audio_files = [os.path.join(r, f) for r, _, fs in os.walk(folder_path) for f in fs if f.lower().endswith(('.wav', '.mp3', '.flac', '.ogg'))]
    if not audio_files: 
        log_func("Không tìm thấy file âm thanh.")
        return
    output_dir = Path(dest_folder) / f"SoundFix_{Path(folder_path).name}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_func(f"Bắt đầu xử lý {len(audio_files)} file...\nThư mục output: {output_dir}")
    counts = {'success': 0, 'skipped': 0, 'error': 0}
    for i, file_path in enumerate(audio_files):
        preset = get_preset_for_file(os.path.basename(file_path), presets)
        msg = process_audio_file(file_path, output_dir, algorithm, preset)
        log_func(f"[{i+1}/{len(audio_files)}] {msg}")
        if "✅" in msg: 
            counts['success'] += 1
        elif "🟡" in msg: 
            counts['skipped'] += 1
        else: 
            counts['error'] += 1
    log_func(f"\n📊 Thống kê:\n✅ Thành công: {counts['success']} file\n🟡 Bỏ qua: {counts['skipped']} file\n❌ Lỗi: {counts['error']} file")
    messagebox.showinfo("Xong!", f"Đã xử lý xong!\n✅ Thành công: {counts['success']}\n🟡 Bỏ qua: {counts['skipped']}\n❌ Lỗi: {counts['error']}\n📁 Output: {output_dir}")

# ==============================================================================
# GIAO DIỆN NGƯỜI DÙNG
# ==============================================================================
def run_app() -> None:
    root = TkinterDnD.Tk() if DND_SUPPORT else tk.Tk()
    root.title("SoundFix Pro - Giao diện Tích hợp")
    root.geometry("850x700")

    # --- Các biến lưu trữ ---
    folder_var = tk.StringVar()
    dest_var = tk.StringVar()
    csv_path_var = tk.StringVar()
    algorithm_var = tk.StringVar()

    # --- Bố cục chính với PanedWindow ---
    main_paned_window = ttk.PanedWindow(root, orient=tk.VERTICAL)
    main_paned_window.pack(fill='both', expand=True, padx=10, pady=10)

    # --- Pane trên: Các điều khiển ---
    controls_frame = ttk.Frame(main_paned_window, padding=10)
    main_paned_window.add(controls_frame, weight=0)

    # --- Pane dưới: Dữ liệu (Xem trước và Log) ---
    data_frame = ttk.Frame(main_paned_window)
    main_paned_window.add(data_frame, weight=1)

    # --- TẠO NỘI DUNG CHO PANE ĐIỀU KHIỂN ---
    if not DND_SUPPORT:
        ttk.Label(controls_frame, text="Cài đặt 'tkinterdnd2' để bật kéo-thả.", foreground="orange").grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 5))
    
    ttk.Label(controls_frame, text="1. Folder Âm thanh:").grid(row=1, column=0, sticky='w')
    entry1 = ttk.Entry(controls_frame, textvariable=folder_var)
    entry1.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 5))
    ttk.Button(controls_frame, text="Chọn...", command=lambda: folder_var.set(filedialog.askdirectory())).grid(row=2, column=2, padx=(5,0))
    
    ttk.Label(controls_frame, text="2. Thư mục đích:").grid(row=3, column=0, sticky='w')
    entry2 = ttk.Entry(controls_frame, textvariable=dest_var)
    entry2.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(0, 5))
    ttk.Button(controls_frame, text="Chọn...", command=lambda: dest_var.set(filedialog.askdirectory())).grid(row=4, column=2, padx=(5,0))

    ttk.Label(controls_frame, text="3. File cấu hình (.csv):").grid(row=5, column=0, sticky='w')
    entry3 = ttk.Entry(controls_frame, textvariable=csv_path_var)
    entry3.grid(row=6, column=0, columnspan=2, sticky='ew')
    ttk.Button(controls_frame, text="Chọn...", command=lambda: select_csv_and_show(preview_container)).grid(row=6, column=2, padx=(5,0))
    
    ttk.Button(controls_frame, text="Tạo file mẫu...", command=lambda: create_template_csv(preview_container)).grid(row=7, column=0, columnspan=3, sticky='e', pady=(2, 10))
    
    ttk.Label(controls_frame, text="4. Engine xử lý:", font=('Arial', 10, 'bold')).grid(row=8, column=0, sticky='w')
    combo = ttk.Combobox(controls_frame, textvariable=algorithm_var, values=["Dynamic Hybrid Brickwall", "Hybrid Brickwall", "Butterworth Filter", "Multiband Limiting"], state="readonly")
    combo.grid(row=9, column=0, columnspan=3, sticky='ew', pady=(2, 10))
    algorithm_var.set("Dynamic Hybrid Brickwall")
    
    ttk.Button(controls_frame, text="5. BẮT ĐẦU XỬ LÝ", command=lambda: start_process(), padding=10).grid(row=10, column=0, columnspan=3, sticky='ew')
    controls_frame.columnconfigure(0, weight=1)

    # --- TẠO NỘI DUNG CHO PANE DỮ LIỆU ---
    data_paned_window = ttk.PanedWindow(data_frame, orient=tk.VERTICAL)
    data_paned_window.pack(fill='both', expand=True)
    
    preview_container = ttk.Frame(data_paned_window, padding=5)
    data_paned_window.add(preview_container, weight=1)
    
    log_container = ttk.Frame(data_paned_window, padding=(5,0,5,5))
    data_paned_log_label = ttk.Label(log_container, text="Log tiến trình:", font=('Arial', 10, 'bold'))
    data_paned_log_label.pack(anchor='w')
    log_box = scrolledtext.ScrolledText(log_container, height=8, font=('Consolas', 10), bg="#2d2d2d", fg="#dcdcdc", wrap=tk.WORD, relief='flat')
    log_box.pack(fill='both', expand=True)
    data_paned_window.add(log_container, weight=1)
    ttk.Label(preview_container, text="Kéo file .csv vào ô trên hoặc nhấn 'Chọn...' để xem trước cấu hình tại đây.").pack(pady=20)

    # --- CÁC HÀM TRỢ GIÚP GIAO DIỆN ---
    def setup_dnd(widget, var, is_csv=False, preview_frame=None):
        if not DND_SUPPORT: 
            return
        def on_drop(event):
            path = event.data.strip('{}')
            var.set(path)
            if is_csv: 
                show_config_preview(path, preview_frame)
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', on_drop)
    
    setup_dnd(entry1, folder_var)
    setup_dnd(entry2, dest_var)
    setup_dnd(entry3, csv_path_var, is_csv=True, preview_frame=preview_container)
    
    def show_config_preview(csv_path: str, parent_frame) -> None:
        for widget in parent_frame.winfo_children(): 
            widget.destroy()
        if not csv_path or not os.path.exists(csv_path):
            ttk.Label(parent_frame, text="Không thể tải file cấu hình.").pack()
            return
        try:
            presets = load_presets_from_csv(csv_path)
            ttk.Label(parent_frame, text=f"Cấu hình từ: {os.path.basename(csv_path)}", font=('Arial', 10, 'bold')).pack(anchor='w')
            cols = list(presets[0].keys())
            tree = ttk.Treeview(parent_frame, columns=cols, show='headings')
            for col in cols:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=80, anchor='w')
            for p in presets:
                p_display = {k: ', '.join(v) if isinstance(v, list) else v for k, v in p.items()}
                tree.insert("", "end", values=list(p_display.values()))
            vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            vsb.pack(side='right', fill='y')
            tree.pack(fill='both', expand=True)
        except Exception as e:
            ttk.Label(parent_frame, text=f"Lỗi đọc file CSV:\n{e}", foreground="red").pack()

    def select_csv_and_show(preview_frame) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            csv_path_var.set(path)
            show_config_preview(path, preview_frame)
            
    def create_template_csv(preview_frame) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="sound_presets.csv")
        if not path: 
            return
        header = "priority,category_name,keywords,lowcut,highcut,volume,attenuation_db,gate_threshold_db,expansion_ratio,mb_low_thresh,mb_low_ratio,mb_mid_thresh,mb_mid_ratio,mb_high_thresh,mb_high_ratio"
        data = [
            "10,UI SFX,\"ui_click,ui_sfx,ui,click\",200,6000,0,-80,-50,0.1,-6,4,-4,3,-2,2",
            "20,Footstep,\"footstep,step\",100,5000,-2,-80,-50,0.1,-8,4,-6,3,-4,2",
            "30,Attack/Impact,\"impact,attack,hit,metal,wood,glass\",150,7000,-2,-80,-50,0.1,-4,4,-3,3,-2,2",
            "35,Weapon,\"weapon,gun,rifle,shot,fire\",150,7000,-2,-80,-50,0.1,-4,4,-2,4,-1,3",
            "40,Voice/Dialog,\"voice,dialog,speech\",150,8000,0,-80,-60,0.05,-6,3,-4,3,-3,2",
            "50,Ambient,\"ambient,rain,water,drip,wind,air\",80,8000,-8,-70,-50,0.1,-10,2,-8,2,-6,2",
            "60,Environment Tone,\"env,environment,rattle,window,door,creak\",60,6000,-14,-70,-50,0.1,-12,2,-10,2,-8,2",
            "70,Music Background,music,100,12000,-8,-80,-50,0.1,-8,3,-4,3,-2,2"
        ]
        with open(path, 'w', newline='', encoding='utf-8') as f: 
            f.write(header + '\n' + '\n'.join(data))
        messagebox.showinfo("Thành công", f"Đã tạo file mẫu tại:\n{path}")
        csv_path_var.set(path)
        show_config_preview(path, preview_frame)

    def log(msg: str) -> None:
        if root.winfo_exists(): 
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)

    def start_process() -> None:
        if not all([folder_var.get(), dest_var.get(), csv_path_var.get(), algorithm_var.get()]):
            messagebox.showerror("Lỗi", "Vui lòng điền đầy đủ tất cả các mục!")
            return
        log_box.delete(1.0, tk.END)
        threading.Thread(target=batch_process, args=(folder_var.get(), dest_var.get(), csv_path_var.get(), log, algorithm_var.get()), daemon=True).start()
    
    root.mainloop()

if __name__ == "__main__":
    run_app() 