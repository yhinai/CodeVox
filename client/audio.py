"""
Audio Capture Module - Voice Activity Detection (VAD)
Extracted from assistant.py for clean separation of concerns.
"""
import io
import math
import struct
import structlog
from typing import Optional

log = structlog.get_logger()


class AudioCapture:
    """Handles microphone capture with voice activity detection."""
    
    def __init__(self, sample_rate: int = 24000, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # VAD settings
        self.silence_threshold = 800  # RMS threshold for speech
        self.max_silence_seconds = 1.5
        self.max_recording_seconds = 30.0
        self.initial_timeout_seconds = 5.0
    
    def capture(self) -> Optional[bytes]:
        """
        Capture audio with dynamic silence detection.
        Returns WAV bytes or None if no speech detected.
        """
        try:
            import pyaudio
            import wave
        except ImportError:
            log.error("audio.missing_pyaudio")
            return None
        
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        print("🎤 Listening... ", end="", flush=True)
        
        frames = []
        silent_chunks = 0
        has_spoken = False
        
        chunks_per_second = self.sample_rate / self.chunk_size
        max_silence_chunks = int(self.max_silence_seconds * chunks_per_second)
        max_total_chunks = int(self.max_recording_seconds * chunks_per_second)
        initial_timeout_chunks = int(self.initial_timeout_seconds * chunks_per_second)
        
        while len(frames) < max_total_chunks:
            data = stream.read(self.chunk_size, exception_on_overflow=False)
            frames.append(data)
            
            # Calculate RMS
            samples = struct.unpack(f'{len(data)//2}h', data)
            rms = math.sqrt(sum(s**2 for s in samples) / len(samples)) if samples else 0
            
            # Visual feedback
            level = min(int(rms / 500), 10)
            bar = "█" * level + "░" * (10 - level)
            is_speech = rms > self.silence_threshold
            
            if is_speech:
                has_spoken = True
                silent_chunks = 0
                status = "Speaking"
            else:
                silent_chunks += 1
                status = "Silent" if has_spoken else "Waiting"
            
            print(f"\r🎤 {status}: [{bar}] {len(frames) / chunks_per_second:.1f}s ", end="", flush=True)
            
            # Stop conditions
            if has_spoken and silent_chunks > max_silence_chunks:
                print("✓ (Done)")
                break
            
            if not has_spoken and len(frames) > initial_timeout_chunks:
                print("× (Timeout)")
                break
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        if not has_spoken:
            return None
        
        # Convert to WAV
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        
        audio_bytes = buffer.getvalue()
        print(f"   Captured {len(audio_bytes)} bytes ({len(frames) / chunks_per_second:.1f}s)")
        return audio_bytes
