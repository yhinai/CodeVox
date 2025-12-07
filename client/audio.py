"""
Audio Capture - Adaptive Voice Activity Detection (VAD)
v3.1 - Auto-calibrates to room noise for accurate speech detection.
"""
import io
import math
import struct
import time
import structlog

log = structlog.get_logger()

# Optional imports
try:
    import pyaudio
    import wave
    PYAUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None
    wave = None
    PYAUDIO_AVAILABLE = False


class AudioCapture:
    """Adaptive VAD with noise calibration."""
    
    def __init__(self, sample_rate: int = 24000, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.silence_threshold = 500  # Default, will calibrate
        self.calibrated = False
        self._stream = None
        self._pyaudio = None
    
    def calibrate(self, stream, seconds: float = 1.0) -> None:
        """Measure background noise to set adaptive threshold."""
        print("   🎤 Calibrating...", end="", flush=True)
        
        chunks = int(seconds * self.sample_rate / self.chunk_size)
        rms_values = []
        
        for _ in range(chunks):
            try:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                rms_values.append(self._calculate_rms(data))
            except Exception:
                pass
        
        if rms_values:
            avg_noise = sum(rms_values) / len(rms_values)
            # Threshold = noise * 2.5, minimum 300
            self.silence_threshold = max(avg_noise * 2.5, 300)
        
        self.calibrated = True
        print(f" Done (threshold: {int(self.silence_threshold)})")
    
    def _calculate_rms(self, data: bytes) -> float:
        """Calculate root mean square of audio samples."""
        if not data:
            return 0.0
        try:
            samples = struct.unpack(f'{len(data) // 2}h', data)
            if not samples:
                return 0.0
            return math.sqrt(sum(s ** 2 for s in samples) / len(samples))
        except Exception:
            return 0.0
    
    def capture(self) -> bytes | None:
        """Capture speech with adaptive VAD. Returns WAV bytes or None."""
        if not PYAUDIO_AVAILABLE:
            log.error("audio.not_available")
            return None
        
        p = pyaudio.PyAudio()
        
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
        except Exception as e:
            log.error("audio.open_failed", error=str(e))
            p.terminate()
            return None
        
        try:
            # Calibrate on first use
            if not self.calibrated:
                self.calibrate(stream)
            
            print("🎤 Listening... ", end="", flush=True)
            
            frames = []
            silent_chunks = 0
            has_spoken = False
            
            # 1.5 seconds of silence to stop
            max_silence = int(1.5 * self.sample_rate / self.chunk_size)
            # 10 second max recording
            max_frames = int(10 * self.sample_rate / self.chunk_size)
            # 5 second timeout if no speech
            no_speech_timeout = int(5 * self.sample_rate / self.chunk_size)
            
            while len(frames) < max_frames:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                except Exception:
                    continue
                
                frames.append(data)
                rms = self._calculate_rms(data)
                
                if rms > self.silence_threshold:
                    has_spoken = True
                    silent_chunks = 0
                else:
                    silent_chunks += 1
                
                # Stop conditions
                if has_spoken and silent_chunks > max_silence:
                    break
                if not has_spoken and len(frames) > no_speech_timeout:
                    print("(timeout)")
                    return None
            
            if not has_spoken:
                print("(no speech)")
                return None
            
            print(f"({len(frames)} chunks)")
            
            # Convert to WAV
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
            
            return buffer.getvalue()
            
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def is_available(self) -> bool:
        """Check if audio capture is available."""
        return PYAUDIO_AVAILABLE
