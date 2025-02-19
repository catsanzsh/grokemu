import pickle
import tkinter as tk
from tkinter import filedialog, messagebox
import random
import time
from pathlib import Path
import threading
import sys
try:
    import winsound  # Windows-specific sound
except ImportError:
    winsound = None  # Fallback for non-Windows systems

class NesticleInspiredGUI:
    def __init__(self, root):
        self.root = root
        # Gray (#808080) and Dark Red (#8B0000) theme inspired by Nesticle
        self.style = {
            'btn': {'bg': '#8B0000', 'fg': '#FFFFFF', 'relief': 'raised', 'padx': 5, 'pady': 2, 'font': ('Fixedsys', 10)},
            'label': {'bg': '#808080', 'fg': '#FFFFFF', 'font': ('Fixedsys', 10)},
            'frame': {'bg': '#808080', 'relief': 'groove', 'borderwidth': 2},
            'canvas_frame': {'bg': '#808080', 'relief': 'sunken', 'borderwidth': 4}
        }

    def create_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, **self.style['btn'])

    def create_label(self, parent, text):
        return tk.Label(parent, text=text, **self.style['label'])

    def create_frame(self, parent):
        return tk.Frame(parent, **self.style['frame'])

    def create_canvas_frame(self, parent):
        return tk.Frame(parent, **self.style['canvas_frame'])

class OptimizedChip8Emulator:
    def __init__(self, root):
        self.root = root
        self.gui = NesticleInspiredGUI(root)
        self.root.title("CHIP-8 Emulator - Nesticle Style")
        self.root.geometry("900x600")
        self.root.resizable(False, False)
        self.root.configure(bg='#808080')

        # Constants
        self.WIDTH, self.HEIGHT = 64, 32
        self.SCALE = 10
        self.CPU_SPEED = 500  # Hz
        self.FRAME_RATE = 60  # Hz

        # Display setup with a sunken frame like Nesticle
        self.canvas_frame = self.gui.create_canvas_frame(self.root)
        self.canvas_frame.pack(pady=10)
        self.canvas = tk.Canvas(self.canvas_frame, 
                              width=self.WIDTH * self.SCALE,
                              height=self.HEIGHT * self.SCALE,
                              bg='black',
                              highlightthickness=0)
        self.canvas.pack()
        
        # Emulator state
        self.memory = bytearray(4096)
        self.V = bytearray(16)
        self.display = bytearray(self.WIDTH * self.HEIGHT)
        self.stack = []
        self.PC = 0x200
        self.I = 0
        self.delay_timer = 0
        self.sound_timer = 0
        self.keypad = bytearray(16)
        self.running = False
        self.paused = False
        self.draw_flag = False

        # Key mapping (CHIP-8 standard)
        self.key_map = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
            'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
            'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
            'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF,
            'KP_1': 0x1, 'KP_2': 0x2, 'KP_3': 0x3, 'KP_4': 0xC,
            'KP_5': 0x4, 'KP_6': 0x5, 'KP_7': 0x6, 'KP_8': 0xD,
            'KP_9': 0x7, 'KP_0': 0x8, 'KP_Period': 0x9, 'KP_Enter': 0xE
        }
        self.root.bind('<KeyPress>', self.key_press)
        self.root.bind('<KeyRelease>', self.key_release)

        # Fontset
        fontset = [
            0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70,
            0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
            0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0,
            0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
            0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0,
            0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
            0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0,
            0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80
        ]
        self.memory[0:80] = fontset

        self.setup_ui()
        self.pixel_coords = [(x * self.SCALE, y * self.SCALE, (x + 1) * self.SCALE, (y + 1) * self.SCALE)
                           for y in range(self.HEIGHT) for x in range(self.WIDTH)]
        self.emulation_thread = None

    def setup_ui(self):
        control_frame = self.gui.create_frame(self.root)
        control_frame.pack(pady=5, fill='x', padx=10)

        self.gui.create_button(control_frame, "Load ROM", self.load_rom_dialog).pack(side=tk.LEFT, padx=5)
        self.run_btn = self.gui.create_button(control_frame, "Run", self.toggle_run)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.gui.create_button(control_frame, "Pause", self.toggle_pause).pack(side=tk.LEFT, padx=5)
        self.gui.create_button(control_frame, "Reset", self.reset).pack(side=tk.LEFT, padx=5)
        self.gui.create_button(control_frame, "Step", self.step).pack(side=tk.LEFT, padx=5)
        self.gui.create_button(control_frame, "Save State", self.save_state).pack(side=tk.LEFT, padx=5)
        self.gui.create_button(control_frame, "Load State", self.load_state).pack(side=tk.LEFT, padx=5)

        self.status_frame = self.gui.create_frame(self.root)
        self.status_frame.pack(fill='x', padx=10, pady=5)
        self.status_label = self.gui.create_label(self.status_frame, "Status: Stopped")
        self.status_label.pack(side=tk.LEFT, padx=5)

        speed_frame = self.gui.create_frame(control_frame)
        speed_frame.pack(side=tk.RIGHT, padx=5)
        self.gui.create_label(speed_frame, "Speed:").pack(side=tk.LEFT)
        self.speed_scale = tk.Scale(speed_frame, from_=100, to=1000, 
                                  orient=tk.HORIZONTAL, length=150, 
                                  command=self.update_speed,
                                  bg='#808080', fg='#FFFFFF', 
                                  troughcolor='#8B0000', highlightthickness=0,
                                  font=('Fixedsys', 8))
        self.speed_scale.set(self.CPU_SPEED)
        self.speed_scale.pack(side=tk.LEFT)

    def update_speed(self, value):
        self.CPU_SPEED = int(value)

    def load_rom_dialog(self):
        rom_path = filedialog.askopenfilename(filetypes=[("CHIP-8 ROMs", "*.ch8 *.rom")])
        if rom_path:
            try:
                self.load_rom(rom_path)
                self.reset()
                self.status_label.config(text=f"Loaded: {Path(rom_path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ROM: {str(e)}")

    def load_rom(self, path):
        with open(path, 'rb') as f:
            rom = f.read()
            if len(rom) > 3584:
                raise ValueError("ROM size exceeds 3584 bytes")
            self.memory[0x200:0x200 + len(rom)] = rom

    def reset(self):
        self.PC = 0x200
        self.I = 0
        self.stack.clear()
        self.V = bytearray(16)
        self.display = bytearray(self.WIDTH * self.HEIGHT)
        self.keypad = bytearray(16)
        self.delay_timer = 0
        self.sound_timer = 0
        self.draw_flag = True
        self.paused = False
        self.running = False
        self.update_display()
        self.status_label.config(text="Status: Stopped")

    def key_press(self, event):
        if event.keysym in self.key_map:
            self.keypad[self.key_map[event.keysym]] = 1

    def key_release(self, event):
        if event.keysym in self.key_map:
            self.keypad[self.key_map[event.keysym]] = 0

    def toggle_run(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.run_btn.config(text="Stop")
            self.status_label.config(text="Status: Running")
            if not self.emulation_thread or not self.emulation_thread.is_alive():
                self.emulation_thread = threading.Thread(target=self.emulation_loop, daemon=True)
                self.emulation_thread.start()
        else:
            self.running = False
            self.run_btn.config(text="Run")
            self.status_label.config(text="Status: Stopped")

    def toggle_pause(self):
        if self.running:
            self.paused = not self.paused
            self.status_label.config(text=f"Status: {'Paused' if self.paused else 'Running'}")

    def step(self):
        if not self.running or self.paused:
            self.process_opcode()
            self.update_display()

    def save_state(self):
        state = {
            'memory': self.memory.copy(),
            'V': self.V.copy(),
            'display': self.display.copy(),
            'stack': self.stack.copy(),
            'PC': self.PC,
            'I': self.I,
            'delay_timer': self.delay_timer,
            'sound_timer': self.sound_timer,
            'keypad': self.keypad.copy()
        }
        path = filedialog.asksaveasfilename(defaultextension=".c8state")
        if path:
            with open(path, 'wb') as f:
                pickle.dump(state, f)
            messagebox.showinfo("Success", "State saved successfully")

    def load_state(self):
        path = filedialog.askopenfilename(filetypes=[("CHIP-8 State", "*.c8state")])
        if path:
            with open(path, 'rb') as f:
                state = pickle.load(f)
                self.memory = state['memory']
                self.V = state['V']
                self.display = state['display']
                self.stack = state['stack']
                self.PC = state['PC']
                self.I = state['I']
                self.delay_timer = state['delay_timer']
                self.sound_timer = state['sound_timer']
                self.keypad = state['keypad']
                self.draw_flag = True
                self.update_display()
                self.status_label.config(text="Status: State Loaded")

    def play_sound(self):
        if winsound and sys.platform == "win32":
            winsound.Beep(440, 100)  # 440 Hz for 100ms
        else:
            print("\a", end='', flush=True)  # Fallback beep

    def emulation_loop(self):
        cycles_per_frame = self.CPU_SPEED // self.FRAME_RATE
        frame_time = 1.0 / self.FRAME_RATE
        
        while self.running:
            start_time = time.time()
            
            if not self.paused:
                for _ in range(cycles_per_frame):
                    self.process_opcode()
                
                if self.delay_timer > 0:
                    self.delay_timer -= 1
                if self.sound_timer > 0:
                    self.sound_timer -= 1
                    if self.sound_timer == 1:
                        self.play_sound()
                
                self.root.after(0, self.update_display)
            
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

    def process_opcode(self):
        opcode = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        x = (opcode >> 8) & 0x0F
        y = (opcode >> 4) & 0x0F
        nnn = opcode & 0x0FFF
        kk = opcode & 0x00FF
        n = opcode & 0x000F

        if opcode == 0x00E0:  # CLS
            self.display = bytearray(self.WIDTH * self.HEIGHT)
            self.draw_flag = True
            self.PC += 2
        elif opcode == 0x00EE:  # RET
            self.PC = self.stack.pop() if self.stack else 0x200
            self.PC += 2
        elif opcode & 0xF000 == 0x1000:  # JP addr
            self.PC = nnn
        elif opcode & 0xF000 == 0x2000:  # CALL addr
            self.stack.append(self.PC)
            self.PC = nnn
        elif opcode & 0xF000 == 0x3000:  # SE Vx, byte
            self.PC += 4 if self.V[x] == kk else 2
        elif opcode & 0xF000 == 0x4000:  # SNE Vx, byte
            self.PC += 4 if self.V[x] != kk else 2
        elif opcode & 0xF00F == 0x5000:  # SE Vx, Vy
            self.PC += 4 if self.V[x] == self.V[y] else 2
        elif opcode & 0xF000 == 0x6000:  # LD Vx, byte
            self.V[x] = kk
            self.PC += 2
        elif opcode & 0xF000 == 0x7000:  # ADD Vx, byte
            self.V[x] = (self.V[x] + kk) & 0xFF
            self.PC += 2
        elif opcode & 0xF00F == 0x8000:  # LD Vx, Vy
            self.V[x] = self.V[y]
            self.PC += 2
        elif opcode & 0xF00F == 0x8001:  # OR Vx, Vy
            self.V[x] |= self.V[y]
            self.PC += 2
        elif opcode & 0xF00F == 0x8002:  # AND Vx, Vy
            self.V[x] &= self.V[y]
            self.PC += 2
        elif opcode & 0xF00F == 0x8003:  # XOR Vx, Vy
            self.V[x] ^= self.V[y]
            self.PC += 2
        elif opcode & 0xF00F == 0x8004:  # ADD Vx, Vy
            result = self.V[x] + self.V[y]
            self.V[0xF] = 1 if result > 0xFF else 0
            self.V[x] = result & 0xFF
            self.PC += 2
        elif opcode & 0xF00F == 0x8005:  # SUB Vx, Vy
            self.V[0xF] = 1 if self.V[x] > self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
            self.PC += 2
        elif opcode & 0xF00F == 0x8006:  # SHR Vx
            self.V[0xF] = self.V[x] & 0x1
            self.V[x] >>= 1
            self.PC += 2
        elif opcode & 0xF00F == 0x8007:  # SUBN Vx, Vy
            self.V[0xF] = 1 if self.V[y] > self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
            self.PC += 2
        elif opcode & 0xF00F == 0x800E:  # SHL Vx
            self.V[0xF] = (self.V[x] >> 7) & 0x1
            self.V[x] = (self.V[x] << 1) & 0xFF
            self.PC += 2
        elif opcode & 0xF00F == 0x9000:  # SNE Vx, Vy
            self.PC += 4 if self.V[x] != self.V[y] else 2
        elif opcode & 0xF000 == 0xA000:  # LD I, addr
            self.I = nnn
            self.PC += 2
        elif opcode & 0xF000 == 0xB000:  # JP V0, addr
            self.PC = nnn + self.V[0]
        elif opcode & 0xF000 == 0xC000:  # RND Vx, byte
            self.V[x] = random.randint(0, 255) & kk
            self.PC += 2
        elif opcode & 0xF000 == 0xD000:  # DRW Vx, Vy, nibble
            x_coord = self.V[x] % self.WIDTH
            y_coord = self.V[y] % self.HEIGHT
            self.V[0xF] = 0
            for row in range(n):
                if y_coord + row >= self.HEIGHT:
                    break
                sprite_byte = self.memory[self.I + row]
                for col in range(8):
                    if x_coord + col >= self.WIDTH:
                        break
                    if sprite_byte & (0x80 >> col):
                        idx = (y_coord + row) * self.WIDTH + (x_coord + col)
                        if self.display[idx]:
                            self.V[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True
            self.PC += 2
        elif opcode & 0xF0FF == 0xE09E:  # SKP Vx
            self.PC += 4 if self.keypad[self.V[x]] else 2
        elif opcode & 0xF0FF == 0xE0A1:  # SKNP Vx
            self.PC += 4 if not self.keypad[self.V[x]] else 2
        elif opcode & 0xF0FF == 0xF007:  # LD Vx, DT
            self.V[x] = self.delay_timer
            self.PC += 2
        elif opcode & 0xF0FF == 0xF00A:  # LD Vx, K
            for i, key in enumerate(self.keypad):
                if key:
                    self.V[x] = i
                    self.PC += 2
                    break
        elif opcode & 0xF0FF == 0xF015:  # LD DT, Vx
            self.delay_timer = self.V[x]
            self.PC += 2
        elif opcode & 0xF0FF == 0xF018:  # LD ST, Vx
            self.sound_timer = self.V[x]
            self.PC += 2
        elif opcode & 0xF0FF == 0xF01E:  # ADD I, Vx
            self.I = (self.I + self.V[x]) & 0xFFF
            self.PC += 2
        elif opcode & 0xF0FF == 0xF029:  # LD F, Vx (font)
            self.I = (self.V[x] & 0xF) * 5
            self.PC += 2
        elif opcode & 0xF0FF == 0xF033:  # LD B, Vx (BCD)
            value = self.V[x]
            self.memory[self.I] = value // 100
            self.memory[self.I + 1] = (value // 10) % 10
            self.memory[self.I + 2] = value % 10
            self.PC += 2
        elif opcode & 0xF0FF == 0xF055:  # LD [I], Vx
            for i in range(x + 1):
                self.memory[self.I + i] = self.V[i]
            self.PC += 2
        elif opcode & 0xF0FF == 0xF065:  # LD Vx, [I]
            for i in range(x + 1):
                self.V[i] = self.memory[self.I + i]
            self.PC += 2
        else:
            print(f"Unknown opcode: 0x{opcode:04X}")
            self.PC += 2

    def update_display(self):
        if not self.draw_flag:
            return
        self.canvas.delete("all")
        for i, pixel in enumerate(self.display):
            if pixel:
                coords = self.pixel_coords[i]
                self.canvas.create_rectangle(*coords, fill='white', outline='')
        self.draw_flag = False

if __name__ == "__main__":
    root = tk.Tk()
    emulator = OptimizedChip8Emulator(root)
    root.mainloop()
