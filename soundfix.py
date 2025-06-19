import os
import gradio as gr
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, lfilter
import zipfile
import tempfile
import shutil
from pathlib import Path
import glob
from pydub import AudioSegment

# Định nghĩa preset cho từng loại âm thanh
PRESETS = {
    'UI SFX':     {'lowcut': 100, 'highcut': 8000,  'volume': 0},
    'Footstep':   {'lowcut': 60,  'highcut': 7000,  'volume': -2},
    'Attack/Impact': {'lowcut': 80,  'highcut': 9000,  'volume': -2},
    'Voice/Dialog':  {'lowcut': 80,  'highcut': 12000, 'volume': 0},
    'Ambient':    {'lowcut': 60,  'highcut': 10000, 'volume': -8},
    'Environment Tone': {'lowcut': 50,  'highcut': 10000, 'volume': -14},
    'Music Background': {'lowcut': 40,  'highcut': 16000, 'volume': -8}
}

def get_category(file_name):
    fname = file_name.lower()
    if fname.startswith('footstep'):
        return 'Footstep'
    elif fname.startswith('impact') or fname.startswith('attack'):
        return 'Attack/Impact'
    elif fname.startswith('ui_click') or fname.startswith('ui_sfx'):
        return 'UI SFX'
    elif fname.startswith('voice') or fname.startswith('dialog'):
        return 'Voice/Dialog'
    elif fname.startswith('ambient'):
        return 'Ambient'
    elif fname.startswith('env'):
        return 'Environment Tone'
    elif fname.startswith('music'):
        return 'Music Background'
    else:
        return None

def butter_filter(data, sr, lowcut, highcut):
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(2, [low, high], btype='band')
    return lfilter(b, a, data)

def process_audio_file(audio_path, output_dir):
    file_name = os.path.basename(audio_path)
    category = get_category(file_name)
    if category is None:
        return f"❌ Không xác định loại âm thanh cho file: {file_name}"
    try:
        preset = PRESETS[category]
        audio = AudioSegment.from_file(audio_path)
        # Điều chỉnh volume (dB)
        audio = audio + preset['volume']
        # Lưu file
        name, ext = os.path.splitext(file_name)
        output_name = f"processed_{name}.wav"
        output_path = os.path.join(output_dir, output_name)
        audio.export(output_path, format="wav")
        return f"✅ {file_name} → {output_name} ({category})"
    except Exception as e:
        return f"❌ Lỗi xử lý '{file_name}': {str(e)}"

def get_audio_files_from_folder(folder_path):
    """Lấy tất cả file âm thanh từ folder"""
    audio_extensions = ['*.wav', '*.mp3', '*.flac', '*.ogg', '*.m4a', '*.aac']
    audio_files = []
    
    for ext in audio_extensions:
        pattern = os.path.join(folder_path, '**', ext)
        audio_files.extend(glob.glob(pattern, recursive=True))
    
    return audio_files

def process_folder(folder_path, output_folder=None):
    """Xử lý toàn bộ folder âm thanh"""
    if not folder_path:
        return "Chưa chọn folder nào!", "", None, ""
    
    # Lấy tất cả file âm thanh trong folder
    audio_files = get_audio_files_from_folder(folder_path)
    
    if not audio_files:
        return "Không tìm thấy file âm thanh nào trong folder!", "", None, ""
    
    # Tạo thư mục SoundFix
    soundfix_dir = Path("SoundFix")
    soundfix_dir.mkdir(exist_ok=True)
    
    # Tạo thư mục con với tên folder gốc + timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = os.path.basename(folder_path)
    output_dir = soundfix_dir / f"{folder_name}_processed_{timestamp}"
    output_dir.mkdir(exist_ok=True)
    
    results = []
    total_files = len(audio_files)
    
    for i, file_path in enumerate(audio_files):
        # Cập nhật progress
        progress = (i + 1) / total_files * 100
        result = process_audio_file(file_path, output_dir)
        results.append(f"[{i+1}/{total_files}] {result}")
        
        # Yield để cập nhật UI real-time
        yield f"Đang xử lý... {progress:.1f}% ({i+1}/{total_files})", "\n".join(results), None, ""
    
    # Tạo file ZIP chứa tất cả kết quả
    zip_name = f"SoundFix_{folder_name}_{timestamp}.zip"
    zip_path = output_dir.parent / zip_name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.name)
    
    # Copy file ZIP vào thư mục đích nếu được chọn
    final_message = f"✅ Hoàn thành! Đã xử lý {total_files} file từ folder '{folder_name}'.\n📁 Kết quả được lưu tại: {output_dir}\n📦 File ZIP: {zip_path}"
    
    if output_folder:
        try:
            dest_zip_path = Path(output_folder) / zip_name
            shutil.copy2(zip_path, dest_zip_path)
            final_message += f"\n📂 Đã copy file ZIP vào: {dest_zip_path}"
        except Exception as e:
            final_message += f"\n⚠️ Không thể copy file ZIP: {str(e)}"
    
    yield f"Hoàn thành 100% ({total_files}/{total_files})", "\n".join(results), str(zip_path), final_message

def process_batch_files(files, output_folder=None):
    """Xử lý hàng loạt nhiều file âm thanh (giữ lại cho tương thích)"""
    if not files:
        return "Chưa chọn file nào!", "", None, ""
    
    # Tạo thư mục SoundFix
    soundfix_dir = Path("SoundFix")
    soundfix_dir.mkdir(exist_ok=True)
    
    # Tạo thư mục con với timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = soundfix_dir / f"processed_{timestamp}"
    output_dir.mkdir(exist_ok=True)
    
    results = []
    total_files = len(files)
    
    for i, file_path in enumerate(files):
        # Cập nhật progress
        progress = (i + 1) / total_files * 100
        result = process_audio_file(file_path, output_dir)
        results.append(f"[{i+1}/{total_files}] {result}")
        
        # Yield để cập nhật UI real-time
        yield f"Đang xử lý... {progress:.1f}% ({i+1}/{total_files})", "\n".join(results), None, ""
    
    # Tạo file ZIP chứa tất cả kết quả
    zip_path = output_dir.parent / f"SoundFix_Results_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.name)
    
    final_message = f"✅ Hoàn thành! Đã xử lý {total_files} file.\n📁 Kết quả được lưu tại: {output_dir}\n📦 File ZIP: {zip_path}"
    
    if output_folder:
        try:
            dest_zip_path = Path(output_folder) / f"SoundFix_Results_{timestamp}.zip"
            shutil.copy2(zip_path, dest_zip_path)
            final_message += f"\n📂 Đã copy file ZIP vào: {dest_zip_path}"
        except Exception as e:
            final_message += f"\n⚠️ Không thể copy file ZIP: {str(e)}"
    
    yield f"Hoàn thành 100% ({total_files}/{total_files})", "\n".join(results), str(zip_path), final_message

def create_demo():
    with gr.Blocks(title="SoundFix - Bộ xử lý âm thanh tự động") as demo:
        gr.Markdown("""
        # 🎵 SoundFix - Bộ xử lý âm thanh tự động cho Game
        
        ### 🚀 Cách sử dụng đơn giản:
        1. **Chọn folder chứa âm thanh** (bước duy nhất cần làm thủ công)
        2. **Chọn thư mục đích** để lưu file ZIP (tùy chọn)
        3. **Nhấn "Xử lý folder"** - ứng dụng sẽ tự động:
           - Tìm tất cả file âm thanh trong folder
           - Phân loại và xử lý theo preset
           - Tạo file ZIP kết quả
           - Copy file ZIP vào thư mục đích (nếu chọn)
        4. **Tải file ZIP** chứa tất cả kết quả đã xử lý
        
        ### 📁 Hỗ trợ định dạng:
        - WAV, MP3, FLAC, OGG, M4A, AAC
        
        ### 🎛️ Preset tự động:
        - `Footstep_*` → Preset Footstep
        - `Impact_*`, `Attack_*` → Preset Attack/Impact  
        - `UI_Click_*`, `UI_SFX_*` → Preset UI SFX
        - `Voice_*`, `Dialog_*` → Preset Voice/Dialog
        - `Ambient_*` → Preset Ambient
        - `Env_*` → Preset Environment Tone
        - `Music_*` → Preset Music Background
        """)
        
        with gr.Tab("📁 Xử lý Folder (Khuyến nghị)"):
            with gr.Row():
                with gr.Column(scale=2):
                    folder_input = gr.File(
                        label="📁 Chọn folder chứa âm thanh (kéo thả hoặc click để chọn)",
                        file_count="directory",
                        file_types=["audio"]
                    )
                    
                    output_folder_input = gr.File(
                        label="📂 Chọn thư mục đích để lưu file ZIP (tùy chọn)",
                        file_count="directory"
                    )
                    
                    process_folder_btn = gr.Button(
                        "🚀 Xử lý toàn bộ folder", 
                        variant="primary",
                        size="lg"
                    )
                    
                    progress_text = gr.Textbox(
                        label="📊 Tiến trình",
                        value="Sẵn sàng xử lý...",
                        interactive=False
                    )
                
                with gr.Column(scale=1):
                    download_btn = gr.File(
                        label="📦 Tải file ZIP kết quả",
                        visible=False
                    )
            
            output_text = gr.Textbox(
                label="📋 Kết quả xử lý",
                lines=15,
                max_lines=20,
                interactive=False
            )
            
            final_message_text = gr.Textbox(
                label="📢 Thông báo cuối",
                lines=3,
                interactive=False
            )
            
            # Xử lý sự kiện folder
            def on_process_folder(folder, output_folder):
                if not folder:
                    return "Chưa chọn folder nào!", "", None, ""
                return process_folder(folder, output_folder)
            
            process_folder_btn.click(
                on_process_folder,
                inputs=[folder_input, output_folder_input],
                outputs=[progress_text, output_text, download_btn, final_message_text],
                show_progress=True
            )
        
        with gr.Tab("📄 Xử lý File riêng lẻ"):
            with gr.Row():
                with gr.Column(scale=2):
                    file_input = gr.File(
                        label="📄 Chọn file âm thanh (có thể chọn nhiều file)",
                        file_count="multiple",
                        file_types=["audio"]
                    )
                    
                    output_folder_input_2 = gr.File(
                        label="📂 Chọn thư mục đích để lưu file ZIP (tùy chọn)",
                        file_count="directory"
                    )
                    
                    process_btn = gr.Button(
                        "🚀 Xử lý file", 
                        variant="secondary",
                        size="lg"
                    )
                    
                    progress_text_2 = gr.Textbox(
                        label="📊 Tiến trình",
                        value="Sẵn sàng xử lý...",
                        interactive=False
                    )
                
                with gr.Column(scale=1):
                    download_btn_2 = gr.File(
                        label="📦 Tải file ZIP kết quả",
                        visible=False
                    )
            
            output_text_2 = gr.Textbox(
                label="📋 Kết quả xử lý",
                lines=15,
                max_lines=20,
                interactive=False
            )
            
            final_message_text_2 = gr.Textbox(
                label="📢 Thông báo cuối",
                lines=3,
                interactive=False
            )
            
            # Xử lý sự kiện file
            def on_process_files(files, output_folder):
                if not files:
                    return "Chưa chọn file nào!", "", None, ""
                return process_batch_files(files, output_folder)
            
            process_btn.click(
                on_process_files,
                inputs=[file_input, output_folder_input_2],
                outputs=[progress_text_2, output_text_2, download_btn_2, final_message_text_2],
                show_progress=True
            )
        
        # Thêm footer
        gr.Markdown("""
        ---
        **💡 Lưu ý:** 
        - File output sẽ có prefix `processed_`
        - Kết quả được lưu trong folder `SoundFix/[tên_folder]_processed_[timestamp]/`
        - Hỗ trợ file âm thanh stereo và mono
        - Tự động tạo file ZIP để dễ dàng tải về
        - **Nếu chọn thư mục đích, file ZIP sẽ được copy tự động vào đó**
        - **Khuyến nghị sử dụng tab "Xử lý Folder" để tự động hóa hoàn toàn**
        """)
    
    return demo

if __name__ == "__main__":
    demo = create_demo()
    demo.launch(
        server_name="127.0.0.1",
        share=False,
        show_error=True
    )
