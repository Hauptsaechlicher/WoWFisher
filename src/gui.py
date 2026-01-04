import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import cv2 as cv
import numpy as np
import mss
import platform
import subprocess

# Pfade setzen, damit wir Module aus src importieren können
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from main import AREAS, load_options, save_options, MainAgent, save_areas
from fishing import fishing_agent, sound_detect

class FishingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fishing Bot GUI")
        self.root.geometry("400x320") # Fenster etwas vergrößern
        self.root.resizable(False, False)

        self.running = False
        self.main_agent = None
        self.screen_thread = None
        
        # Optionen laden
        self.options = load_options()
        
        # --- UI Elemente ---
        
        # 1. Gebiet Auswahl
        lbl_area = ttk.Label(root, text="Gebiet auswählen:")
        lbl_area.pack(pady=(10, 0))
        
        # Frame für Combobox und Add-Button
        frame_area = ttk.Frame(root)
        frame_area.pack(pady=5, fill='x', padx=20)
        
        self.area_var = tk.StringVar()
        self.area_combo = ttk.Combobox(frame_area, textvariable=self.area_var, state="readonly")
        self.area_combo.pack(side="left", fill='x', expand=True)
        
        # Buttons Container
        frame_btns = ttk.Frame(frame_area)
        frame_btns.pack(side="right")

        btn_del_area = ttk.Button(frame_btns, text="-", width=3, command=self.delete_current_area)
        btn_del_area.pack(side="left", padx=(5, 0))

        btn_add_area = ttk.Button(frame_btns, text="+", width=3, command=self.open_add_area_dialog)
        btn_add_area.pack(side="left", padx=(2, 0))
        
        # Mapping für die ComboBox erstellen (Name -> ID)
        self.refresh_area_list()
        
        # Gespeichertes Gebiet setzen
        saved_area_id = self.options.get("selected_area", "1")
        if saved_area_id in AREAS:
            self.area_combo.set(AREAS[saved_area_id]["name"])
        else:
            if self.area_combo['values']:
                self.area_combo.current(0)

        # 2. Audio Device Auswahl
        lbl_audio = ttk.Label(root, text="Audio Gerät:")
        lbl_audio.pack(pady=(10, 0))
        
        self.audio_var = tk.StringVar()
        self.audio_combo = ttk.Combobox(root, textvariable=self.audio_var, state="readonly")
        self.audio_combo.pack(pady=5, fill='x', padx=20)
        
        self.audio_devices = [] # Liste von (id, name)
        self.refresh_audio_devices()
        
        # 3. Cast Button Auswahl (NEU)
        lbl_cast = ttk.Label(root, text="Angel-Taste:")
        lbl_cast.pack(pady=(10, 0))
        
        self.cast_var = tk.StringVar()
        self.cast_combo = ttk.Combobox(root, textvariable=self.cast_var, state="readonly")
        self.cast_combo.pack(pady=5, fill='x', padx=20)
        
        # Liste der verfügbaren Tasten erweitern
        mouse_buttons = ["middle", "right", "left"]
        f_keys = [f"f{i}" for i in range(1, 13)]
        num_keys = [str(i) for i in range(0, 10)]
        char_keys = [chr(i) for i in range(ord('a'), ord('z')+1)]
        special_keys = ["space", "enter", "shift", "ctrl", "alt"]
        
        all_keys = mouse_buttons + f_keys + num_keys + char_keys + special_keys
        self.cast_combo['values'] = all_keys
        
        saved_cast = self.options.get("cast_button", "middle")
        if saved_cast in all_keys:
            self.cast_combo.set(saved_cast)
        else:
            self.cast_combo.set("middle")

        # 4. Start/Stop Button
        self.btn_action = ttk.Button(root, text="START", command=self.toggle_fishing)
        self.btn_action.pack(pady=20, ipady=10, fill='x', padx=50)

        # Status Label
        self.lbl_status = ttk.Label(root, text="Bereit", foreground="gray")
        self.lbl_status.pack(side="bottom", pady=5)

        # Beim Schließen aufräumen
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def refresh_audio_devices(self):
        """Lädt Audio-Geräte und setzt die Auswahl basierend auf options.txt"""
        try:
            raw_devices = sound_detect.get_audio_devices()
            self.audio_devices = raw_devices
            
            combo_values = ["Auto (Standard)"]
            for idx, name in raw_devices:
                combo_values.append(f"[{idx}] {name}")
            
            self.audio_combo['values'] = combo_values
            
            saved_id = self.options.get("audio_device_id")
            
            if saved_id:
                # Versuche den Eintrag in der Liste zu finden
                found = False
                for i, val in enumerate(combo_values):
                    if val.startswith(f"[{saved_id}]"):
                        self.audio_combo.current(i)
                        found = True
                        break
                if not found:
                    self.audio_combo.current(0)
            else:
                self.audio_combo.current(0)
                
        except Exception as e:
            self.lbl_status.config(text=f"Fehler Audio: {e}")

    def get_selected_audio_id(self):
        selection = self.audio_combo.get()
        if selection.startswith("Auto"):
            return None
        # Extrahiere ID aus "[6] Monitor..."
        try:
            return int(selection.split(']')[0].replace('[', ''))
        except:
            return None

    def save_current_settings(self):
        # Area speichern
        selected_name = self.area_combo.get()
        if selected_name in self.area_name_to_id:
            self.options["selected_area"] = self.area_name_to_id[selected_name]
        
        # Cast Button speichern
        self.options["cast_button"] = self.cast_combo.get()

        # Audio speichern
        dev_id = self.get_selected_audio_id()
        if dev_id is not None:
            self.options["audio_device_id"] = str(dev_id)
        else:
            if "audio_device_id" in self.options:
                del self.options["audio_device_id"]
                
        save_options(self.options)

    def refresh_area_list(self):
        self.area_name_to_id = {data["name"]: key for key, data in AREAS.items()}
        area_names = list(self.area_name_to_id.keys())
        area_names.sort()
        self.area_combo['values'] = area_names
        
        # Falls das aktuelle Gebiet gelöscht wurde oder leer ist
        current = self.area_combo.get()
        if current and current not in area_names:
            self.area_combo.set('')
            if area_names:
                self.area_combo.current(0)

    def delete_current_area(self):
        selected_name = self.area_combo.get()
        if not selected_name:
            return
            
        if not messagebox.askyesno("Löschen", f"Möchtest du das Gebiet '{selected_name}' wirklich löschen?"):
            return
            
        area_id = self.area_name_to_id.get(selected_name)
        if area_id and area_id in AREAS:
            del AREAS[area_id]
            save_areas(AREAS)
            self.refresh_area_list()
            
            # Falls Liste jetzt leer ist
            if not self.area_combo['values']:
                self.area_var.set("")
            else:
                self.area_combo.current(0)

    def open_add_area_dialog(self):
        top = tk.Toplevel(self.root)
        top.title("Gebiet hinzufügen")
        top.geometry("300x220")
        top.resizable(False, False)
        
        # Zentrieren relativ zum Hauptfenster
        x = self.root.winfo_x() + 50
        y = self.root.winfo_y() + 50
        top.geometry(f"+{x}+{y}")
        
        ttk.Label(top, text="Name des Gebiets:").pack(pady=(10, 5), padx=10, anchor="w")
        entry_name = ttk.Entry(top)
        entry_name.pack(fill="x", padx=10)
        entry_name.focus()
        
        ttk.Label(top, text="Pattern (optional):").pack(pady=(10, 5), padx=10, anchor="w")
        ttk.Label(top, text="Kommagetrennt für mehrere. Leer = Name klein.", font=("Arial", 8), foreground="gray").pack(padx=10, anchor="w")
        entry_pattern = ttk.Entry(top)
        entry_pattern.pack(fill="x", padx=10)
        
        def on_save():
            name = entry_name.get().strip()
            if not name:
                messagebox.showerror("Fehler", "Name darf nicht leer sein.", parent=top)
                return
                
            raw_pattern = entry_pattern.get().strip()
            if raw_pattern:
                if "," in raw_pattern:
                    # Liste von Patterns (als Tuple speichern für startswith)
                    pattern = tuple([p.strip() for p in raw_pattern.split(",") if p.strip()])
                else:
                    pattern = raw_pattern
            else:
                # Auto-Generate: lowercase, remove spaces
                pattern = name.lower().replace(" ", "")
            
            # Neue ID finden
            try:
                max_id = max([int(k) for k in AREAS.keys()])
            except ValueError:
                max_id = 0
            new_id = str(max_id + 1)
            
            # Speichern
            AREAS[new_id] = {"name": name, "pattern": pattern}
            save_areas(AREAS)
            
            # GUI aktualisieren
            self.refresh_area_list()
            self.area_combo.set(name)
            
            top.destroy()
            
        ttk.Button(top, text="Speichern", command=on_save).pack(pady=20)

    def toggle_fishing(self):
        if not self.running:
            self.start_fishing()
        else:
            self.stop_fishing()

    def start_fishing(self):
        self.save_current_settings()
        
        # UI sperren
        self.area_combo.config(state="disabled")
        self.audio_combo.config(state="disabled")
        self.cast_combo.config(state="disabled")
        self.btn_action.config(text="STOP")
        self.lbl_status.config(text="Bot läuft...", foreground="green")
        
        self.running = True
        
        # MainAgent initialisieren
        self.main_agent = MainAgent()
        self.main_agent.running = True  # Flag setzen
        
        # Parameter setzen
        selected_name = self.area_combo.get()
        area_id = self.area_name_to_id.get(selected_name, "1")
        self.main_agent.selected_area_pattern = AREAS[area_id]["pattern"]
        self.main_agent.selected_area_name = AREAS[area_id]["name"]
        self.main_agent.audio_device_id = self.get_selected_audio_id()
        self.main_agent.cast_button = self.cast_combo.get()
        
        # Screen Thread starten (angepasste Version mit Stop-Flag)
        self.screen_thread = threading.Thread(
            target=self.update_screen_loop, 
            args=(), 
            daemon=True
        )
        self.screen_thread.start()
        
        # Warten bis erstes Bild da ist, dann Fishing Agent starten
        threading.Thread(target=self.wait_for_image_and_start_agent, daemon=True).start()

    def wait_for_image_and_start_agent(self):
        self.lbl_status.config(text="Warte auf Screenshot...", foreground="orange")
        while self.running and self.main_agent.cur_img is None:
            time.sleep(0.1)
            
        if not self.running:
            return

        self.lbl_status.config(text=f"Fische in: {self.main_agent.selected_area_name}", foreground="green")
        
        # Fishing Agent starten
        try:
            agent = fishing_agent.FishingAgent(
                self.main_agent, 
                target_pattern=self.main_agent.selected_area_pattern,
                audio_device_id=self.main_agent.audio_device_id,
                cast_button=self.main_agent.cast_button
            )
            agent.run()
        except Exception as e:
            print(f"Fehler beim Starten des Agents: {e}")
            self.stop_fishing()

    def stop_fishing(self):
        self.running = False
        self.lbl_status.config(text="Stoppe...", foreground="red")
        
        # Signalisiere dem FishingAgent aufzuhören
        if self.main_agent:
            self.main_agent.running = False # Flag löschen
            self.main_agent.cur_img = None
        
        # UI freigeben
        self.area_combo.config(state="readonly")
        self.audio_combo.config(state="readonly")
        self.cast_combo.config(state="readonly")
        self.btn_action.config(text="START")
        self.lbl_status.config(text="Gestoppt", foreground="black")

    def is_wayland(self):
        """Check if running on Wayland."""
        if platform.system() != "Linux":
            return False
        return "WAYLAND_DISPLAY" in os.environ

    def capture_screen_wayland(self):
        """Capture screen using spectacle on Wayland."""
        try:
            temp_file = "/tmp/fishing_bot_capture_gui.png"
            # -b: background, -n: non-notifying, -o: output
            subprocess.run(["spectacle", "-b", "-n", "-o", temp_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(temp_file):
                img = cv.imread(temp_file)
                return img
        except Exception as e:
            print(f"Spectacle capture error: {e}")
        return None

    def update_screen_loop(self):
        """
        Lokale Implementierung von update_screen mit MSS (Cross-Platform) oder Spectacle (Wayland).
        """
        use_wayland = self.is_wayland()
        
        if use_wayland:
            print("GUI Screen Update Thread gestartet (Spectacle/Wayland).")
            sct = None
        else:
            print("GUI Screen Update Thread gestartet (MSS).")
            sct = mss.mss()
            monitor = sct.monitors[1] # Hauptmonitor

        while self.running:
            try:
                img = None
                if use_wayland:
                    img = self.capture_screen_wayland()
                else:
                    # Screenshot machen
                    sct_img = sct.grab(monitor)
                    img = np.array(sct_img)
                    img = cv.cvtColor(img, cv.COLOR_BGRA2BGR)
                
                if img is not None and self.main_agent:
                    self.main_agent.cur_img = img
                
                # Kurze Pause um CPU zu schonen
                # Bei Wayland/Spectacle etwas länger warten
                time.sleep(0.1 if use_wayland else 0.05)
            except Exception as e:
                print(f"Screenshot Fehler: {e}")
                time.sleep(1)
        
        print("GUI Screen Update Thread beendet.")

    def on_close(self):
        self.stop_fishing()
        self.save_current_settings() # Save on exit
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingBotGUI(root)
    root.mainloop()
