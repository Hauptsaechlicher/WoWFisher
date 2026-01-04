import cv2 as cv
import pyautogui
import time
import random
from threading import Thread
import os
from .sound_detect import SoundDetector

class FishingAgent:
    def __init__(self, main_agent, target_pattern="fishing_target", audio_device_id=None, cast_button="middle"):
        self.main_agent = main_agent
        self.sound_detector = SoundDetector(device_id=audio_device_id)
        self.cast_button = cast_button
        
        here_path = os.path.dirname(os.path.realpath(__file__))
        assets_path = os.path.join(here_path, "assets")

        self.fishing_targets = []
        print(f"Lade Templates für Muster: '{target_pattern}'...")

        if os.path.exists(assets_path):
            for f in os.listdir(assets_path):
                if f.startswith(target_pattern) and f.endswith(".png"):
                    path = os.path.join(assets_path, f)
                    img = cv.imread(path)
                    if img is not None:
                        self.fishing_targets.append(img)
                        print(f"Loaded template: {f}")
        
        if not self.fishing_targets:
             print(f"Warning: No fishing targets found starting with '{target_pattern}'!")
        
        self.fishing_thread = None
        self.lure_location = None

    def _should_stop(self):
        """Hilfsfunktion um zu prüfen ob wir stoppen sollen"""
        return not self.main_agent.running

    def cast_lure(self):
        if self._should_stop(): return

        print(f"Casting with {self.cast_button} button!...")
        
        # Check for mouse buttons
        if self.cast_button == "right":
            pyautogui.rightClick()
        elif self.cast_button == "left":
            pyautogui.leftClick()
        elif self.cast_button == "middle":
            pyautogui.middleClick()
        else:
            # Assume it's a keyboard key
            try:
                pyautogui.press(self.cast_button)
            except Exception as e:
                print(f"Error pressing key '{self.cast_button}': {e}")
        
        # Warten mit Unterbrechungsmöglichkeit
        for _ in range(30): # 3 Sekunden warten (30 * 0.1s)
            if self._should_stop(): return
            time.sleep(0.1)
            
        self.find_lure()

    def find_lure(self):
        if self._should_stop(): return

        best_max_val = -1
        best_loc = None
        
        if self.main_agent.cur_img is None:
            return

        for target in self.fishing_targets:
            try:
                res = cv.matchTemplate(self.main_agent.cur_img, target, cv.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv.minMaxLoc(res)
                
                if max_val > best_max_val:
                    best_max_val = max_val
                    best_loc = max_loc
            except Exception as e:
                print(f"Error matching template: {e}")
                continue

        print(f"Best match confidence: {best_max_val}")
        self.lure_location = best_loc
        self.move_to_lure()

    def move_to_lure(self):
        if self._should_stop(): return

        if self.lure_location:
            # Bevor wir die Maus bewegen, nochmal prüfen
            if self._should_stop(): return
            
            pyautogui.moveTo(self.lure_location[0] + 25, self.lure_location[1], .45, pyautogui.easeOutQuad)
            self.watch_lure()
        else:
            print("Warning: Lure not found. Recasting...")
            self.pull_line()

    def watch_lure(self):
        if self._should_stop(): return

        print("Beobachte Köder via Sound...")
        
        # Wir übergeben eine Lambda-Funktion, damit der SoundDetector weiß, wann er abbrechen soll
        detected = self.sound_detector.wait_for_sound(
            timeout=30.0, 
            stop_callback=lambda: not self.main_agent.running
        )
        
        if self._should_stop(): return # Falls während des Wartens gestoppt wurde

        if not detected:
            print("Timeout oder Abbruch!")

        self.pull_line()

    def pull_line(self):
        if self._should_stop(): return

        pyautogui.rightClick()
        time.sleep(1)
        self.run()

    def run(self):
        if self._should_stop(): 
            print("Agent gestoppt.")
            return

        if self.main_agent.cur_img is None:
            print("Image capture not found!")
            return
            
        print("Starting fishing thread in 1 to 2 seconds...")
        
        # Warten mit Check
        sleep_time = random.uniform(1, 2)
        start = time.time()
        while time.time() - start < sleep_time:
            if self._should_stop(): return
            time.sleep(0.1)
        
        self.fishing_thread = Thread(
            target=self.cast_lure, 
            args=(),
            name="fishing thread",
            daemon=True)    
        self.fishing_thread.start()
