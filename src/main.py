import os
from threading import Thread
import cv2 as cv    
import time
import numpy as np
import mss
import subprocess
import platform
import json
import fishing.fishing_agent as fishing_agent
import fishing.sound_detect as sound_detect

FPS_REPORT_DELAY = 3
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OPTIONS_PATH = os.path.join(_PROJECT_ROOT, "options.txt")
AREAS_PATH = os.path.join(_PROJECT_ROOT, "areas.json")

def load_areas() -> dict:
    if os.path.exists(AREAS_PATH):
        try:
            with open(AREAS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Listen in Tuples konvertieren, damit startswith() funktioniert
                for k, v in data.items():
                    if isinstance(v["pattern"], list):
                        v["pattern"] = tuple(v["pattern"])
                return data
        except Exception as e:
            print(f"Error loading areas: {e}")
    # Falls keine Datei existiert, geben wir ein leeres Dict zurück
    return {}

def save_areas(areas: dict) -> None:
    try:
        with open(AREAS_PATH, "w", encoding="utf-8") as f:
            json.dump(areas, f, indent=4)
    except Exception as e:
        print(f"Error saving areas: {e}")

AREAS = load_areas()

# --- Optionen (Persistenz) ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OPTIONS_PATH = os.path.join(_PROJECT_ROOT, "options.txt")

def load_options(path: str = OPTIONS_PATH) -> dict:
    opts = {}
    if not os.path.exists(path):
        return opts
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f.readlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                opts[k.strip()] = v.strip()
    except Exception:
        return {}
    return opts

def save_options(opts: dict, path: str = OPTIONS_PATH) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Fishingbot Optionen\n")
            for k, v in opts.items():
                f.write(f"{k}={v}\n")
    except Exception:
        pass

class MainAgent:
    def __init__(self):
        self.agents = []
        self.fishing_thread = None
        self.cur_img = None
        self.audio_device_id = None
        self.cast_button = "middle" # Default
        
        # Zentrales Flag zur Steuerung
        self.running = False

        # Standardwerte initialisieren (Fallback)
        self.selected_area_pattern = ""
        self.selected_area_name = "Unknown"

        # Versuche das erste verfügbare Gebiet zu nehmen, falls vorhanden
        if AREAS:
            first_key = next(iter(AREAS))
            self.selected_area_pattern = AREAS[first_key]["pattern"]
            self.selected_area_name = AREAS[first_key]["name"]

        # Gespeicherte Optionen laden
        opts = load_options()
        saved_area = opts.get("selected_area")
        if saved_area and saved_area in AREAS:
            self.selected_area_pattern = AREAS[saved_area]["pattern"]
            self.selected_area_name = AREAS[saved_area]["name"]
            
        self.cast_button = opts.get("cast_button", "middle")
        
        # Ensure cast_button is in opts for saving
        if "cast_button" not in opts:
            opts["cast_button"] = self.cast_button
            save_options(opts)

        saved_device = opts.get("audio_device_id")
        if saved_device:
            try:
                self.audio_device_id = int(saved_device)
            except ValueError:
                pass

def is_wayland():
    """Check if running on Wayland."""
    if platform.system() != "Linux":
        return False
    return "WAYLAND_DISPLAY" in os.environ

def capture_screen_wayland():
    """Capture screen using spectacle on Wayland."""
    try:
        # Spectacle command to capture active screen to stdout
        # -b: background (no GUI)
        # -n: non-notifying
        # -o: output file (/dev/stdout for pipe)
        # Note: Spectacle might not support direct stdout piping in all versions easily,
        # so we might need a temp file. Let's try temp file for reliability.
        temp_file = "/tmp/fishing_bot_capture.png"
        subprocess.run(["spectacle", "-b", "-n", "-o", temp_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(temp_file):
            img = cv.imread(temp_file)
            return img
    except Exception as e:
        print(f"Spectacle capture error: {e}")
    return None

def update_screen(agent):
    use_wayland = is_wayland()
    if use_wayland:
        print("Starting screen capture (Spectacle/Wayland)...")
        sct = None
    else:
        print("Starting screen capture (MSS)...")
        sct = mss.mss()
        monitor = sct.monitors[1]

    loop_time = time.time()
    fps_print_time = time.time()
    
    while True:
        if not agent.running:
            # Wenn Bot gestoppt ist, kurz warten um CPU zu sparen
            time.sleep(0.5)
            continue

        try:
            img = None
            if use_wayland:
                img = capture_screen_wayland()
            else:
                # Screenshot machen (gibt raw pixels zurück)
                sct_img = sct.grab(monitor)
                # Konvertieren zu Numpy Array für OpenCV
                img = np.array(sct_img)
                # MSS gibt BGRA zurück, OpenCV mag BGR (Alpha Channel entfernen)
                img = cv.cvtColor(img, cv.COLOR_BGRA2BGR)
            
            if img is not None:
                agent.cur_img = img

                cur_time = time.time()
                if cur_time - fps_print_time >= FPS_REPORT_DELAY:
                    print('FPS: {:.2f}'.format(1 / (cur_time - loop_time)))
                    fps_print_time = cur_time
                loop_time = cur_time
            
            # Minimale Pause für CPU-Entlastung
            # Bei Wayland/Spectacle etwas länger warten, da Prozessaufruf teuer ist
            time.sleep(0.1 if use_wayland else 0.01)
            
        except Exception as e:
            print(f"Screen capture error: {e}")
            time.sleep(1)

def print_menu(current_area_name, current_device_id):
    print('\n--- Fishing Bot Menu ---')
    print(f'Current Area: {current_area_name}')
    print(f'Current Audio Device ID: {current_device_id if current_device_id is not None else "Auto"}')
    print('Enter a command:')
    print('\tS\tStart fishing (and screen capture).')
    print('\tA\tSelect Area.')
    print('\tD\tSelect Audio Device.')
    print('\tQ\tQuit.')

def select_area(main_agent):
    print("\nVerfügbare Gebiete:")
    for key, data in AREAS.items():
        print(f"\t{key}: {data['name']} (sucht nach '{data['pattern']}...')")
    
    choice = input("Wähle eine Nummer: ").strip()
    
    if choice in AREAS:
        main_agent.selected_area_pattern = AREAS[choice]["pattern"]
        main_agent.selected_area_name = AREAS[choice]["name"]
        print(f"Gebiet geändert auf: {main_agent.selected_area_name}")

        # Auswahl persistieren (bestehende Optionen laden und aktualisieren)
        opts = load_options()
        opts["selected_area"] = choice
        save_options(opts)
    else:
        print("Ungültige Auswahl.")

def select_audio_device(main_agent):
    print("\nVerfügbare Audio-Eingabegeräte:")
    try:
        devices = sound_detect.get_audio_devices()
        for idx, name in devices:
            marker = " *" if main_agent.audio_device_id == idx else ""
            print(f"\t[{idx}] {name}{marker}")
        
        choice = input("Wähle eine ID (oder Enter für Auto/Reset): ").strip()
        
        opts = load_options()
        
        if not choice:
            main_agent.audio_device_id = None
            print("Audio-Gerät auf 'Auto' zurückgesetzt.")
            if "audio_device_id" in opts:
                del opts["audio_device_id"]
        else:
            dev_id = int(choice)
            # Validierung ob ID existiert (optional)
            if any(d[0] == dev_id for d in devices):
                main_agent.audio_device_id = dev_id
                print(f"Audio-Gerät geändert auf ID: {dev_id}")
                opts["audio_device_id"] = str(dev_id)
            else:
                print("Warnung: ID nicht in der Liste gefunden. Trotzdem gesetzt.")
                main_agent.audio_device_id = dev_id
                opts["audio_device_id"] = str(dev_id)

        save_options(opts)

    except Exception as e:
        print(f"Fehler bei der Geräteauswahl: {e}")

def run():
    main_agent = MainAgent()
    
    screen_capture_started = False
    while True:
        print_menu(main_agent.selected_area_name, main_agent.audio_device_id)
        user_input = input().lower().strip()

        if user_input == 's':
            if not screen_capture_started:
                # Flag setzen, damit update_screen läuft
                main_agent.running = True 
                
                update_screen_thread = Thread(
                    target=update_screen, 
                    args=(main_agent,), 
                    name="update screen thread",
                    daemon=True)
                update_screen_thread.start()
                screen_capture_started = True
                
                print("Waiting for screen capture...")
                while main_agent.cur_img is None:
                    time.sleep(0.1)

            # Hier übergeben wir das ausgewählte Pattern und Audio Device an den FishingAgent
            agent = fishing_agent.FishingAgent(
                main_agent, 
                target_pattern=main_agent.selected_area_pattern,
                audio_device_id=main_agent.audio_device_id,
                cast_button=main_agent.cast_button
            )
            agent.run()

        elif user_input == 'a':
            select_area(main_agent)

        elif user_input == 'd':
            select_audio_device(main_agent)

        elif user_input == 'q':
            print("Shutting down.")
            break
    print("Done.")
    
if __name__ == '__main__':
    run()
