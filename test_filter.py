import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, lfilter, freqz
import librosa
import soundfile as sf

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
    
    return filtered_data, b, a

def plot_filter_response(b, a, sr, lowcut, highcut):
    """Vẽ đáp ứng tần số của filter"""
    w, h = freqz(b, a, worN=8000)
    plt.figure(figsize=(12, 8))
    
    # Đáp ứng tần số
    plt.subplot(2, 2, 1)
    plt.plot(0.5 * sr * w / np.pi, np.abs(h), 'b')
    plt.plot([lowcut, lowcut], [0, 1], 'r--', label=f'Lowcut: {lowcut}Hz')
    plt.plot([highcut, highcut], [0, 1], 'r--', label=f'Highcut: {highcut}Hz')
    plt.xlabel('Tần số [Hz]')
    plt.ylabel('Độ lớn')
    plt.title('Đáp ứng tần số của Bandpass Filter')
    plt.legend()
    plt.grid(True)
    
    # Phase response
    plt.subplot(2, 2, 2)
    plt.plot(0.5 * sr * w / np.pi, np.unwrap(np.angle(h)) * 180 / np.pi, 'b')
    plt.xlabel('Tần số [Hz]')
    plt.ylabel('Phase [degrees]')
    plt.title('Phase Response')
    plt.grid(True)
    
    # Log scale
    plt.subplot(2, 2, 3)
    plt.semilogx(0.5 * sr * w / np.pi, 20 * np.log10(np.abs(h)), 'b')
    plt.axvline(lowcut, color='r', linestyle='--', label=f'Lowcut: {lowcut}Hz')
    plt.axvline(highcut, color='r', linestyle='--', label=f'Highcut: {highcut}Hz')
    plt.xlabel('Tần số [Hz]')
    plt.ylabel('Magnitude [dB]')
    plt.title('Đáp ứng tần số (dB scale)')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.show()

def test_filter():
    """Test filter với tín hiệu tổng hợp"""
    sr = 44100  # Sample rate
    duration = 2.0  # Thời gian
    t = np.linspace(0, duration, int(sr * duration), False)
    
    # Tạo tín hiệu tổng hợp với nhiều tần số
    signal = (np.sin(2 * np.pi * 50 * t) +      # 50 Hz (bass)
              np.sin(2 * np.pi * 500 * t) +     # 500 Hz (mid)
              np.sin(2 * np.pi * 5000 * t) +    # 5 kHz (high)
              np.sin(2 * np.pi * 15000 * t))    # 15 kHz (very high)
    
    # Test với preset Ambient
    lowcut = 80
    highcut = 8000
    
    print(f"🎵 Test filter với preset Ambient:")
    print(f"   - Lowcut: {lowcut}Hz")
    print(f"   - Highcut: {highcut}Hz")
    print(f"   - Sample rate: {sr}Hz")
    
    # Áp dụng filter
    filtered_signal, b, a = butter_filter(signal, sr, lowcut, highcut)
    
    # Vẽ đáp ứng tần số
    plot_filter_response(b, a, sr, lowcut, highcut)
    
    # Vẽ tín hiệu gốc và đã lọc
    plt.figure(figsize=(15, 10))
    
    # Time domain
    plt.subplot(2, 2, 1)
    plt.plot(t[:1000], signal[:1000], 'b', label='Gốc')
    plt.xlabel('Thời gian [s]')
    plt.ylabel('Amplitude')
    plt.title('Tín hiệu gốc (1000 samples đầu)')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 2)
    plt.plot(t[:1000], filtered_signal[:1000], 'r', label='Đã lọc')
    plt.xlabel('Thời gian [s]')
    plt.ylabel('Amplitude')
    plt.title('Tín hiệu đã lọc (1000 samples đầu)')
    plt.legend()
    plt.grid(True)
    
    # Frequency domain
    plt.subplot(2, 2, 3)
    fft_original = np.fft.fft(signal)
    freqs = np.fft.fftfreq(len(signal), 1/sr)
    plt.plot(freqs[:len(freqs)//2], np.abs(fft_original)[:len(freqs)//2], 'b', label='Gốc')
    plt.axvline(lowcut, color='r', linestyle='--', label=f'Lowcut: {lowcut}Hz')
    plt.axvline(highcut, color='r', linestyle='--', label=f'Highcut: {highcut}Hz')
    plt.xlabel('Tần số [Hz]')
    plt.ylabel('Magnitude')
    plt.title('Spectrum gốc')
    plt.legend()
    plt.grid(True)
    plt.xlim(0, 20000)
    
    plt.subplot(2, 2, 4)
    fft_filtered = np.fft.fft(filtered_signal)
    plt.plot(freqs[:len(freqs)//2], np.abs(fft_filtered)[:len(freqs)//2], 'r', label='Đã lọc')
    plt.axvline(lowcut, color='r', linestyle='--', label=f'Lowcut: {lowcut}Hz')
    plt.axvline(highcut, color='r', linestyle='--', label=f'Highcut: {highcut}Hz')
    plt.xlabel('Tần số [Hz]')
    plt.ylabel('Magnitude')
    plt.title('Spectrum đã lọc')
    plt.legend()
    plt.grid(True)
    plt.xlim(0, 20000)
    
    plt.tight_layout()
    plt.show()
    
    # Lưu file test
    sf.write('test_original.wav', signal, sr)
    sf.write('test_filtered.wav', filtered_signal, sr)
    print("✅ Đã lưu file test_original.wav và test_filtered.wav")

if __name__ == "__main__":
    test_filter() 