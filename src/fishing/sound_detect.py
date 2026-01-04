import sounddevice as sd
import numpy as np
import librosa
from scipy import signal
import os
import time

def get_audio_devices():
    """Gibt eine Liste von (index, name) Tupeln für Eingabegeräte zurück."""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append((i, dev['name']))
    return input_devices

class SoundDetector:
    def __init__(self, device_id=None):
        # --- KONFIGURATION ---
        self.TEMPLATE_FILENAME = 'Catchsound.mp3'
        self.SAMPLE_RATE = 48000 
        self.THRESHOLD = 60.0    
        self.DEBUG = True        
        
        # Pfad relativ zur aktuellen Datei auflösen
        base_path = os.path.dirname(os.path.realpath(__file__))
        template_path = os.path.join(base_path, "assets", self.TEMPLATE_FILENAME)
        
        self.template = self.load_template(template_path)
        
        if device_id is not None:
            self.device_id = int(device_id)
            print(f"Verwende konfiguriertes Audio-Gerät ID: {self.device_id}")
        else:
            self.device_id = self.find_loopback_device()
        
        if self.template is not None:
            self.template_len = len(self.template)
            print(f"SoundDetector initialisiert. Template Länge: {self.template_len}")
        else:
            self.template_len = 0

    def load_template(self, path):
        if not os.path.exists(path):
            print(f"Fehler: Datei {path} nicht gefunden.")
            return None
        print(f"Lade {path}...")
        try:
            y, sr = librosa.load(path, sr=self.SAMPLE_RATE, mono=True)
            y, _ = librosa.effects.trim(y, top_db=20)
        except Exception as e:
            print(f"Fehler beim Laden der MP3: {e}")
            return None
            
        if np.max(np.abs(y)) > 0:
            y = y / np.max(np.abs(y))
        return y

    def find_loopback_device(self):
        print("Suche nach Audio-Geräten...")
        devices = sd.query_devices()
        monitor_index = None
        
        for i, dev in enumerate(devices):
            if 'monitor' in dev['name'].lower():
                monitor_index = i
                break
                
        if monitor_index is not None:
            print(f"Monitor-Gerät gefunden: {devices[monitor_index]['name']} (ID: {monitor_index})")
            return monitor_index
        else:
            print("Kein spezifisches 'Monitor'-Gerät gefunden. Verwende Standard.")
            return None

    def wait_for_sound(self, timeout=30.0, stop_callback=None):
        """
        Lauscht auf den Sound.
        stop_callback: Eine Funktion, die True zurückgibt, wenn abgebrochen werden soll.
        """
        if self.template is None or self.template_len == 0:
            print("Kein Template geladen oder Länge 0.")
            return False

        print(f"Warte auf Sound (Timeout: {timeout}s)...")
        
        chunk_duration = 0.1 
        chunk_size = int(chunk_duration * self.SAMPLE_RATE)
        overlap_buffer = np.zeros(self.template_len)
        
        start_time = time.time()

        try:
            with sd.InputStream(
                device=self.device_id, 
                channels=1, 
                samplerate=self.SAMPLE_RATE, 
                blocksize=chunk_size, 
                dtype='float32'
            ) as stream:
                while True:
                    # 1. Prüfen ob wir stoppen sollen (vom Bot aus)
                    if stop_callback and stop_callback():
                        print("Sound-Erkennung abgebrochen.")
                        return False

                    # 2. Timeout prüfen
                    if timeout is not None and (time.time() - start_time) > timeout:
                        return False

                    data, overflow = stream.read(chunk_size)
                    if overflow:
                        pass
                    
                    new_audio = data[:, 0]
                    
                    combined = np.concatenate((overlap_buffer, new_audio))
                    overlap_buffer = combined[-self.template_len:]
                    
                    if np.max(np.abs(combined)) < 0.01:
                        continue

                    corr = signal.correlate(combined, self.template, mode='valid', method='fft')
                    peak = np.max(np.abs(corr)) if len(corr) > 0 else 0
                    
                    if self.DEBUG and peak > 10.0:
                        print(f"Score: {peak:.2f}")

                    if peak > self.THRESHOLD:
                        print(f"\n>>> FISCH ERKANNT! (Score: {peak:.2f}) <<<\n")
                        return True
                        
        except KeyboardInterrupt:
            print("\nAbbruch durch Benutzer.")
            return False
        except Exception as e:
            print(f"Fehler bei der Audio-Überwachung: {e}")
            return False

def main():
    # Standalone Test
    detector = SoundDetector()
    if detector.template is None:
        return
    
    print("Starte Endlos-Überwachung für Testzwecke...")
    while True:
        if detector.wait_for_sound(timeout=None):
            print("Erkannt! Warte kurz...")
            time.sleep(2)

if __name__ == "__main__":
    main()
