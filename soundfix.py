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

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_SUPPORT = True
except ImportError:
    DND_SUPPORT = False

# ==============================================================================
# LOGIC ĐỌC CẤU HÌNH VÀ XỬ LÝ ÂM THANH (KHÔNG THAY ĐỔI)
# ==============================================================================
def load_presets_from_csv(csv_path):
    if not os.path.exists(csv_path): raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")
    presets = []
    with open(csv_path, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            try:
                presets.append({
                    'priority': int(row['priority']),
                    'keywords': [k.strip().lower() for k in row['keywords'].split(',')],
                    'category_name': row['category_name'],
                    'lowcut': int(row['lowcut']), 'highcut': int(row['highcut']),
                    'volume': float(row['volume']), 'attenuation_db': float(row['attenuation_db']),
                    'gate_threshold_db': float(row['gate_threshold_db']),
                    'expansion_ratio': float(row['expansion_ratio'])
                })
            except (ValueError, KeyError) as e:
                raise ValueError(f"Lỗi dữ liệu CSV ở hàng: {row}. Chi tiết: {e}")
    presets.sort(key=lambda x: x['priority'])
    return presets

def get_preset_for_file(filename, presets):
    fn_lower = filename.lower()
    for preset in presets:
        if any(keyword in fn_lower for keyword in preset['keywords']): return preset
    return None

def butter_filter(data, lowcut, highcut, sr, order=20, btype='band'):
    nyq = 0.5 * sr
    low, high = max(0.01, lowcut / nyq), min(0.99, highcut / nyq)
    sos = butter(order, [low, high], analog=False, btype=btype, output='sos')
    if data.ndim > 1:
        for ch in range(data.shape[0]): data[ch] = sosfilt(sos, data[ch])
        return data
    return sosfilt(sos, data)

def hybrid_brickwall_filter(data, sr, **preset):
    y_pass = butter_filter(data.copy(), preset['lowcut'], preset['highcut'], sr, order=24, btype='band')
    y_stop = data - y_pass
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    return y_pass + (y_stop * reduction_gain)

def dynamic_hybrid_filter(data, sr, **preset):
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
        # Code cho mono (nếu cần)
        pass
        
    reduction_gain = 10 ** (preset['attenuation_db'] / 20.0)
    y_stop_final = y_stop_gated * reduction_gain
    final_len = min(y_pass.shape[-1], y_stop_final.shape[-1])
    return y_pass[..., :final_len] + y_stop_final[..., :final_len]

def process_audio_file(audio_path, output_dir, algorithm, preset):
    # (Hàm này gần như không đổi)
    file_name = os.path.basename(audio_path)
    if preset is None: return f"🟡 Bỏ qua: {file_name} (Không khớp quy tắc)"
    try:
        print(f"🎵 Xử lý {file_name} với '{preset['category_name']}' bằng '{algorithm}'")
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        if y.ndim == 1: y = y[np.newaxis, :]
        engine = {'Butterworth Filter': lambda d, s, p: butter_filter(d, p['lowcut'], p['highcut'], s),
                  'Hybrid Brickwall': hybrid_brickwall_filter,
                  'Dynamic Hybrid Brickwall': dynamic_hybrid_filter}.get(algorithm)
        y_eq = engine(y, sr=sr, **preset)
        y_processed = y_eq * (10 ** (preset['volume'] / 20.0))
        if np.any(np.isnan(y_processed)): return f"❌ Dữ liệu lỗi cho file: {file_name}"
        output_name = f"processed_{os.path.splitext(file_name)[0]}{os.path.splitext(audio_path)[1]}"
        sf.write(Path(output_dir) / output_name, y_processed.T.astype(np.float32), sr)
        return f"✅ {file_name} → {output_name} ({preset['category_name']})"
    except Exception as e: return f"❌ Lỗi xử lý '{file_name}': {e}"

def batch_process(folder_path, dest_folder, csv_path, log_func, algorithm):
    # (Hàm này không đổi)
    try:
        presets = load_presets_from_csv(csv_path)
        log_func(f"Tải thành công {len(presets)} quy tắc từ {os.path.basename(csv_path)}")
    except Exception as e:
        log_func(f"❌ Lỗi: Không thể tải file cấu hình.\n{e}")
        return
    audio_files = [os.path.join(r, f) for r, _, fs in os.walk(folder_path) for f in fs if f.lower().endswith(('.wav', '.mp3', '.flac', '.ogg'))]
    if not audio_files: log_func("Không tìm thấy file âm thanh."); return
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
# GIAO DIỆN NGƯỜI DÙNG (ĐÃ TÁI CẤU TRÚC)
# ==============================================================================
def run_app():
    root = TkinterDnD.Tk() if DND_SUPPORT else tk.Tk()
    root.title("SoundFix Pro - Giao diện Tích hợp")
    root.geometry("850x700")

    # --- Các biến lưu trữ ---
    folder_var, dest_var, csv_path_var, algorithm_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()

    # --- Bố cục chính với PanedWindow ---
    main_paned_window = ttk.PanedWindow(root, orient=tk.VERTICAL)
    main_paned_window.pack(fill='both', expand=True, padx=10, pady=10)

    # --- Pane trên: Các điều khiển ---
    controls_frame = ttk.Frame(main_paned_window, padding=10)
    main_paned_window.add(controls_frame, weight=0) # weight 0 để không co giãn

    # --- Pane dưới: Dữ liệu (Xem trước và Log) ---
    data_frame = ttk.Frame(main_paned_window)
    main_paned_window.add(data_frame, weight=1) # weight 1 để co giãn

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
    combo = ttk.Combobox(controls_frame, textvariable=algorithm_var, values=["Dynamic Hybrid Brickwall", "Hybrid Brickwall", "Butterworth Filter"], state="readonly")
    combo.grid(row=9, column=0, columnspan=3, sticky='ew', pady=(2, 10))
    algorithm_var.set("Dynamic Hybrid Brickwall")
    
    ttk.Button(controls_frame, text="5. BẮT ĐẦU XỬ LÝ", command=lambda: start_process(), style="Accent.TButton", padding=10).grid(row=10, column=0, columnspan=3, sticky='ew')
    controls_frame.columnconfigure(0, weight=1)

    # --- TẠO NỘI DUNG CHO PANE DỮ LIỆU ---
    # Pane này lại được chia thành 2 phần: xem trước ở trên, log ở dưới
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
        if not DND_SUPPORT: return
        def on_drop(event):
            path = event.data.strip('{}')
            var.set(path)
            if is_csv: show_config_preview(path, preview_frame)
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', on_drop)
    
    setup_dnd(entry1, folder_var)
    setup_dnd(entry2, dest_var)
    setup_dnd(entry3, csv_path_var, is_csv=True, preview_frame=preview_container)
    
    def show_config_preview(csv_path, parent_frame):
        for widget in parent_frame.winfo_children(): widget.destroy() # Xóa nội dung cũ
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

    def select_csv_and_show(preview_frame):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            csv_path_var.set(path)
            show_config_preview(path, preview_frame)
            
    def create_template_csv(preview_frame):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="sound_presets.csv")
        if not path: return
        # (Nội dung file mẫu không đổi)
        header = "priority,category_name,keywords,lowcut,highcut,volume,attenuation_db,gate_threshold_db,expansion_ratio"
        data = ["10,UI SFX,\"ui_click,ui_sfx,ui,click\",200,6000,0,-80,-50,0.1", "20,Footstep,\"footstep,step\",100,5000,-2,-80,-50,0.1", "30,Attack/Impact,\"impact,attack,hit,metal,wood,glass\",150,7000,-2,-80,-50,0.1", "40,Voice/Dialog,\"voice,dialog,speech\",150,8000,0,-80,-60,0.05", "50,Ambient,\"ambient,rain,water,drip,wind,air\",80,8000,-8,-70,-50,0.1", "60,Environment Tone,\"env,environment,rattle,window,door,creak\",60,6000,-14,-70,-50,0.1", "70,Music Background,music,100,12000,-8,-80,-50,0.1"]
        with open(path, 'w', newline='', encoding='utf-8') as f: f.write(header + '\n' + '\n'.join(data))
        messagebox.showinfo("Thành công", f"Đã tạo file mẫu tại:\n{path}")
        csv_path_var.set(path)
        show_config_preview(path, preview_frame)

    def log(msg):
        if root.winfo_exists(): log_box.insert(tk.END, msg + "\n"); log_box.see(tk.END)

    def start_process():
        if not all([folder_var.get(), dest_var.get(), csv_path_var.get(), algorithm_var.get()]):
            messagebox.showerror("Lỗi", "Vui lòng điền đầy đủ tất cả các mục!")
            return
        log_box.delete(1.0, tk.END)
        threading.Thread(target=batch_process, args=(folder_var.get(), dest_var.get(), csv_path_var.get(), log, algorithm_var.get()), daemon=True).start()
    
    root.mainloop()

if __name__ == "__main__":
    run_app()