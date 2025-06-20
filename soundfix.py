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
import csv

# Cố gắng nhập thư viện tkinterdnd2 để có chức năng kéo-thả
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_SUPPORT = True
except ImportError:
    DND_SUPPORT = False

# ==============================================================================
# LOGIC ĐỌC CẤU HÌNH VÀ XỬ LÝ ÂM THANH (KHÔNG THAY ĐỔI)
# ==============================================================================
def load_presets_from_csv(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {csv_path}")
    presets = []
    with open(csv_path, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            try:
                row['priority'] = int(row['priority'])
                row['keywords'] = [k.strip().lower() for k in row['keywords'].split(',')]
                row['lowcut'] = int(row['lowcut'])
                row['highcut'] = int(row['highcut'])
                row['volume'] = float(row['volume'])
                row['attenuation_db'] = float(row['attenuation_db'])
                row['gate_threshold_db'] = float(row['gate_threshold_db'])
                row['expansion_ratio'] = float(row['expansion_ratio'])
                presets.append(row)
            except (ValueError, KeyError) as e:
                raise ValueError(f"Dữ liệu lỗi trong file CSV ở hàng: {row}. Lỗi: {e}")
    presets.sort(key=lambda x: x['priority'])
    return presets

def get_preset_for_file(filename, presets):
    fn_lower = filename.lower()
    for preset in presets:
        for keyword in preset['keywords']:
            if keyword in fn_lower:
                return preset
    return None

def butter_filter(data, lowcut, highcut, sr, order=20, btype='band'):
    nyq = 0.5 * sr
    low = max(0.01, lowcut / nyq)
    high = min(0.99, highcut / nyq)
    sos = butter(order, [low, high], analog=False, btype=btype, output='sos')
    if data.ndim > 1:
        filtered = np.zeros_like(data)
        for ch in range(data.shape[0]): filtered[ch] = sosfilt(sos, data[ch])
        return filtered
    else:
        return sosfilt(sos, data)

def hybrid_brickwall_filter(data, sr, **preset):
    y_pass = butter_filter(data, preset['lowcut'], preset['highcut'], sr, order=24, btype='band')
    y_stop = data - y_pass
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    y_stop_attenuated = y_stop * reduction_gain
    return y_pass + y_stop_attenuated

def dynamic_hybrid_filter(data, sr, **preset):
    y_pass = butter_filter(data, preset['lowcut'], preset['highcut'], sr, order=32, btype='band')
    y_stop = data - y_pass
    threshold_linear = 10 ** (preset['gate_threshold_db'] / 20.0)
    frame_size, hop_size = 512, 256
    
    if data.ndim > 1:
        y_stop_gated = np.zeros_like(y_stop)
        for ch in range(data.shape[0]):
            rms = librosa.feature.rms(y=y_stop[ch], frame_length=frame_size, hop_length=hop_size)[0]
            gain_envelope = np.ones_like(rms)
            gain_envelope[rms < threshold_linear] = preset['expansion_ratio']
            smooth_gain = np.repeat(gain_envelope, hop_size)
            proc_len = min(y_stop_gated.shape[1], len(smooth_gain))
            y_stop_gated[ch, :proc_len] = y_stop[ch, :proc_len] * smooth_gain[:proc_len]
    else:
        y_stop_gated = np.zeros_like(y_stop)
        rms = librosa.feature.rms(y=y_stop, frame_length=frame_size, hop_length=hop_size)[0]
        gain_envelope = np.ones_like(rms)
        gain_envelope[rms < threshold_linear] = preset['expansion_ratio']
        smooth_gain = np.repeat(gain_envelope, hop_size)
        proc_len = min(len(y_stop_gated), len(smooth_gain))
        y_stop_gated[:proc_len] = y_stop[:proc_len] * smooth_gain[:proc_len]

    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    y_stop_final = y_stop_gated * reduction_gain
    final_len = min(y_pass.shape[-1], y_stop_final.shape[-1])
    return y_pass[..., :final_len] + y_stop_final[..., :final_len]

def process_audio_file(audio_path, output_dir, algorithm, preset):
    file_name = os.path.basename(audio_path)
    if preset is None:
        return f"🟡 Bỏ qua file: {file_name} (Không khớp quy tắc)"
    
    try:
        print(f"🎵 Xử lý {file_name} với quy tắc '{preset['category_name']}' bằng Engine '{algorithm}'")
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        if y.ndim == 1: y = y[np.newaxis, :]
        
        if algorithm == "Butterworth Filter":
            y_eq = butter_filter(y, preset['lowcut'], preset['highcut'], sr, order=20, btype='band')
        else:
            engine = dynamic_hybrid_filter if algorithm == "Dynamic Hybrid Brickwall" else hybrid_brickwall_filter
            y_eq = engine(y, sr=sr, **preset)

        total_gain = 10 ** (preset['volume'] / 20.0)
        y_processed = y_eq * total_gain
        
        if np.any(np.isnan(y_processed)) or np.any(np.isinf(y_processed)):
            return f"❌ Dữ liệu lỗi cho file: {file_name}"
        
        output_name = f"processed_{os.path.splitext(file_name)[0]}{os.path.splitext(audio_path)[1]}"
        output_path = os.path.join(output_dir, output_name)
        sf.write(output_path, y_processed.T.astype(np.float32), sr)
        
        return f"✅ {file_name} → {output_name} ({preset['category_name']})"
        
    except Exception as e:
        return f"❌ Lỗi xử lý '{file_name}': {e}"

def batch_process(folder_path, dest_folder, csv_path, log_func, algorithm):
    try:
        presets = load_presets_from_csv(csv_path)
        log_func(f"Tải thành công {len(presets)} quy tắc từ {os.path.basename(csv_path)}")
    except Exception as e:
        log_func(f"❌ Lỗi nghiêm trọng: Không thể tải file cấu hình.\n{e}")
        messagebox.showerror("Lỗi file cấu hình", f"Không thể đọc file CSV:\n{e}")
        return

    audio_files = [os.path.join(r, f) for r, _, fs in os.walk(folder_path) for f in fs if f.lower().endswith(('.wav', '.mp3', '.flac', '.ogg'))]
    if not audio_files:
        log_func("Không tìm thấy file âm thanh nào trong folder!")
        return
    
    output_dir = Path(dest_folder) / f"SoundFix_{Path(folder_path).name}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    log_func(f"Bắt đầu xử lý {len(audio_files)} file...\nThư mục output: {output_dir}")
    
    counts = {'success': 0, 'skipped': 0, 'error': 0}
    for i, file_path in enumerate(audio_files):
        preset = get_preset_for_file(os.path.basename(file_path), presets)
        msg = process_audio_file(file_path, output_dir, algorithm, preset)
        log_func(f"[{i+1}/{len(audio_files)}] {msg}")
        
        if "✅" in msg: counts['success'] += 1
        elif "🟡" in msg: counts['skipped'] += 1
        else: counts['error'] += 1
    
    log_func(f"\n📊 Thống kê:\n✅ Thành công: {counts['success']} file\n🟡 Bỏ qua: {counts['skipped']} file\n❌ Lỗi: {counts['error']} file")
    messagebox.showinfo("Xong!", f"Đã xử lý xong!\n✅ Thành công: {counts['success']}\n🟡 Bỏ qua: {counts['skipped']}\n❌ Lỗi: {counts['error']}\n📁 Output: {output_dir}")

# ==============================================================================
# GIAO DIỆN NGƯỜI DÙNG
# ==============================================================================
def run_app():
    # Sử dụng root của TkinterDnD nếu có, ngược lại dùng tk.Tk bình thường
    root = TkinterDnD.Tk() if DND_SUPPORT else tk.Tk()
    root.title("SoundFix Pro - Cấu hình bằng CSV (Hỗ trợ Kéo-Thả)")
    root.geometry("750x600")

    # --- Các biến lưu trữ ---
    folder_var = tk.StringVar()
    dest_var = tk.StringVar()
    csv_path_var = tk.StringVar()
    algorithm_var = tk.StringVar()
    
    # --- CÁC HÀM TRỢ GIÚP GIAO DIỆN ---
    def show_config_preview(csv_path):
        if not csv_path or not os.path.exists(csv_path):
            return
        
        try:
            presets = load_presets_from_csv(csv_path)
        except Exception as e:
            messagebox.showerror("Lỗi đọc CSV", f"Không thể phân tích file cấu hình:\n{e}")
            return
            
        preview_win = tk.Toplevel(root)
        preview_win.title(f"Xem trước cấu hình - {os.path.basename(csv_path)}")
        preview_win.geometry("800x400")
        
        cols = list(presets[0].keys())
        tree = ttk.Treeview(preview_win, columns=cols, show='headings')
        
        for col in cols:
            tree.heading(col, text=col.replace('_', ' ').title())
            tree.column(col, width=100, anchor='center')
        
        for preset in presets:
            # Chuyển đổi list keywords thành string để hiển thị
            preset_display = preset.copy()
            preset_display['keywords'] = ', '.join(preset_display['keywords'])
            tree.insert("", "end", values=list(preset_display.values()))
            
        vsb = ttk.Scrollbar(preview_win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        preview_win.grab_set() # Giữ focus ở cửa sổ này

    def setup_drag_and_drop(widget, string_var, is_csv=False):
        if not DND_SUPPORT: return

        def on_drop(event):
            # Làm sạch đường dẫn nhận được từ event
            path = event.data.strip()
            if path.startswith('{') and path.endswith('}'):
                path = path[1:-1]
            string_var.set(path)
            if is_csv:
                show_config_preview(path)

        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', on_drop)
        
    def select_csv_and_show():
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            csv_path_var.set(path)
            show_config_preview(path)

    def create_template_csv():
        # (hàm này giữ nguyên như trước)
        save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="sound_presets.csv", title="Lưu file cấu hình mẫu")
        if not save_path: return
        header = "priority,category_name,keywords,lowcut,highcut,volume,attenuation_db,gate_threshold_db,expansion_ratio"
        data = ["10,UI SFX,\"ui_click,ui_sfx,ui,click\",200,6000,0,-80,-50,0.1", "20,Footstep,\"footstep,step\",100,5000,-2,-80,-50,0.1", "30,Attack/Impact,\"impact,attack,hit,metal,wood,glass\",150,7000,-2,-80,-50,0.1", "40,Voice/Dialog,\"voice,dialog,speech\",150,8000,0,-80,-60,0.05", "50,Ambient,\"ambient,rain,water,drip,wind,air\",80,8000,-8,-70,-50,0.1", "60,Environment Tone,\"env,environment,rattle,window,door,creak\",60,6000,-14,-70,-50,0.1", "70,Music Background,music,100,12000,-8,-80,-50,0.1"]
        with open(save_path, 'w', newline='', encoding='utf-8') as f:
            f.write(header + '\n' + '\n'.join(data))
        messagebox.showinfo("Thành công", f"Đã tạo file mẫu tại:\n{save_path}")
        csv_path_var.set(save_path)
        show_config_preview(save_path)

    # --- BỐ CỤC GIAO DIỆN ---
    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill='both', expand=True)

    if not DND_SUPPORT:
        tk.Label(main_frame, text="Lưu ý: Để bật kéo-thả, hãy cài đặt thư viện 'tkinterdnd2' (pip install tkinterdnd2)", fg="orange").pack(anchor='w')

    # Các ô nhập liệu
    tk.Label(main_frame, text="1. Folder âm thanh gốc:").pack(anchor='w')
    frame1 = tk.Frame(main_frame)
    frame1.pack(fill='x', pady=(2, 10))
    entry1 = tk.Entry(frame1, textvariable=folder_var)
    entry1.pack(side='left', expand=True, fill='x')
    tk.Button(frame1, text="Chọn...", command=lambda: folder_var.set(filedialog.askdirectory(title="Chọn folder âm thanh gốc"))).pack(side='left', padx=(5,0))
    setup_drag_and_drop(entry1, folder_var)
    
    tk.Label(main_frame, text="2. Thư mục đích:").pack(anchor='w')
    frame2 = tk.Frame(main_frame)
    frame2.pack(fill='x', pady=(2, 10))
    entry2 = tk.Entry(frame2, textvariable=dest_var)
    entry2.pack(side='left', expand=True, fill='x')
    tk.Button(frame2, text="Chọn...", command=lambda: dest_var.set(filedialog.askdirectory(title="Chọn thư mục đích"))).pack(side='left', padx=(5,0))
    setup_drag_and_drop(entry2, dest_var)

    tk.Label(main_frame, text="3. File cấu hình (.csv):").pack(anchor='w')
    frame3 = tk.Frame(main_frame)
    frame3.pack(fill='x', pady=(2, 0))
    entry3 = tk.Entry(frame3, textvariable=csv_path_var)
    entry3.pack(side='left', expand=True, fill='x')
    tk.Button(frame3, text="Chọn...", command=select_csv_and_show).pack(side='left', padx=(5,0))
    tk.Button(main_frame, text="Tạo file cấu hình mẫu...", command=create_template_csv).pack(anchor='e', pady=(2, 10))
    setup_drag_and_drop(entry3, csv_path_var, is_csv=True)
    
    tk.Label(main_frame, text="4. Engine xử lý:", font=('Arial', 10, 'bold')).pack(anchor='w')
    ttk.Combobox(main_frame, textvariable=algorithm_var, values=["Dynamic Hybrid Brickwall", "Hybrid Brickwall", "Butterworth Filter"], state="readonly").pack(fill='x', pady=(2, 15))
    algorithm_var.set("Dynamic Hybrid Brickwall")
    
    # Nút xử lý
    log_box = None
    def start_process():
        if not all([folder_var.get(), dest_var.get(), csv_path_var.get(), algorithm_var.get()]):
            messagebox.showerror("Lỗi", "Vui lòng điền đầy đủ tất cả các mục!")
            return
        if log_box: log_box.delete(1.0, tk.END)
        threading.Thread(target=batch_process, args=(folder_var.get(), dest_var.get(), csv_path_var.get(), log, algorithm_var.get()), daemon=True).start()
    tk.Button(main_frame, text="5. BẮT ĐẦU XỬ LÝ", command=start_process, bg='#007acc', fg='white', font=('Arial', 12, 'bold'), height=2).pack(fill='x', pady=10)
    
    # Log box
    log_box = scrolledtext.ScrolledText(main_frame, height=10, font=('Consolas', 10), bg="#2d2d2d", fg="#dcdcdc", wrap=tk.WORD)
    log_box.pack(fill='both', expand=True)
    
    def log(msg):
        if root.winfo_exists() and log_box:
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)

    root.mainloop()

if __name__ == "__main__":
    run_app()