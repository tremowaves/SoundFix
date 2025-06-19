# SoundFix - Automatic Audio Processor for Game Sound Effects

## 📖 Description
SoundFix is a desktop application that automatically processes audio files for game sound effects. The app uses AI to detect the type of sound based on the filename and applies the appropriate EQ preset.

## ✨ Main Features
- 🎯 **Automatic sound type detection** based on filename keywords
- 🎛️ **7 professional EQ presets** for different sound categories
- 🔊 **Advanced audio processing** with brickwall bandpass filter (FFT/STFT)
- 📦 **Automatic ZIP export** with timestamp
- 🖥️ **User-friendly desktop interface** (Tkinter)
- 📊 **Detailed processing log and statistics**

## 🎵 Preset Table

| Sound Type         | Lowcut | Highcut | Volume | Description                      |
|--------------------|--------|---------|--------|----------------------------------|
| **UI SFX**         | 200 Hz | 6000 Hz | 0 dB   | Optimized for UI sounds          |
| **Footstep**       | 100 Hz | 5000 Hz | -2 dB  | Reduces bass/treble for steps    |
| **Attack/Impact**  | 150 Hz | 7000 Hz | -2 dB  | Focused on impact sounds         |
| **Voice/Dialog**   | 150 Hz | 8000 Hz | 0 dB   | Optimized for voice/dialogue     |
| **Ambient**        | 80 Hz  | 8000 Hz | -8 dB  | For environmental/ambient sounds |
| **Environment Tone** | 60 Hz | 6000 Hz | -14 dB | Subtle environmental tones       |
| **Music Background** | 100 Hz | 12000 Hz | -8 dB | Background music                 |

## 🚀 Installation

### System Requirements
- Python 3.8+
- FFmpeg (installed and in PATH)
- Windows 10/11

### Install dependencies
```bash
pip install -r requirements.txt
```

### FFmpeg Installation
1. Download FFmpeg: https://ffmpeg.org/download.html
2. Add FFmpeg to your Windows PATH
3. Check installation: `ffmpeg -version`

## 📁 Project Structure
```
Sound Fix/
├── soundfix_desktop.py    # Main application
├── test_filter.py         # Filter test script
├── README.md              # This guide
└── requirements.txt       # Dependencies
```

## 🎮 Usage

### 1. Run the application
```bash
python soundfix_desktop.py
```

### 2. Select the source audio folder
- Click "Browse..." to select the folder containing your audio files
- Supported formats: WAV, MP3, FLAC, OGG, M4A, AAC

### 3. Select the output folder
- Click "Browse..." to select where the ZIP file will be saved

### 4. Process and export ZIP
- Click "Process and Export ZIP" to start
- Monitor progress in the log
- The ZIP file will be created automatically with a timestamp

## 🎯 Filename Keyword Rules

The app automatically detects sound type based on keywords in the filename:

| Sound Type         | Keywords (case-insensitive)                |
|--------------------|--------------------------------------------|
| Footstep           | footstep, step                             |
| Attack/Impact      | impact, attack, hit                        |
| UI SFX             | ui_click, ui_sfx, ui, click                |
| Voice/Dialog       | voice, dialog, speech                      |
| Ambient            | ambient, rain, water, drip, wind, air      |
| Environment Tone   | env, environment, rattle, window, door, creak |
| Music Background   | music                                      |

**Example filenames:**
```
Ambient_Rain_Night_var7_(No Noise).wav    → Ambient preset
Window_Rattle_var9_(No Noise).wav         → Environment Tone preset
Player_Footstep_Wood_01.wav               → Footstep preset
UI_Click_Button_01.wav                    → UI SFX preset
Unknown_Sound_01.wav                      → Not recognized
```

## 🔧 Customization

### Add a new preset
Edit the `PRESETS` dictionary in `soundfix_desktop.py`:
```python
PRESETS = {
    'New Preset': {'lowcut': 100, 'highcut': 8000, 'volume': -2},
    # Add more presets here
}
```

### Add new detection keywords
Edit the `get_category()` function in `soundfix_desktop.py`:
```python
elif "new_keyword" in fname:
    return 'New Preset'
```

## 🧪 Testing & Debugging

### Run the filter test script
```bash
python test_filter.py
```
This script will:
- Generate a test signal with multiple frequencies
- Apply the brickwall bandpass filter
- Show filter response plots
- Save test audio files for listening

### Debug logging
The app prints detailed info in the console:
```
🎵 Processing file.wav with preset Ambient:
   - Lowcut: 80Hz
   - Highcut: 8000Hz
   - Volume: -8dB
   - Sample rate: 44100Hz
   - Channels: 2
```

## 📊 Processing Statistics
After processing, the app shows:
- ✅ Number of successful files
- ❌ Number of errors
- 📦 ZIP file path

## 🐛 Troubleshooting

### "Format not recognised" error
- Check if the audio file is corrupted
- Try converting to WAV using FFmpeg

### "Sound type not recognized" error
- Rename the file according to the keyword rules
- Add new keywords in `get_category()`

### Missing dependencies
```bash
pip install -r requirements.txt
```

## 📝 Changelog

### Version 1.1
- Improved preset detection
- Added debug logging
- Enhanced error handling
- Added detailed statistics

### Version 1.0
- Desktop app with Tkinter
- 7 professional EQ presets
- Automatic ZIP export

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## 📄 License
MIT License - See LICENSE for details

## 📞 Support
If you have issues, please open an issue on GitHub or contact via email.

---
**SoundFix** - Make your game audio more professional! 🎮🎵 