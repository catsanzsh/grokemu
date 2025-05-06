import tkinter as tk
from tkinter import filedialog, messagebox
import pygame
import numpy as np
import os

# iNES Header Parser (with Mapper Support)
class ROM:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = bytearray(f.read())
        
        # Parse iNES header
        self.header = self.data[:16]
        if self.header[:4] != b"NES\x1a":
            raise ValueError("Invalid iNES file - missing header")
        
        self.prg_banks = self.header[4]
        self.chr_banks = self.header[5]
        self.mapper = (self.header[6] >> 4) | (self.header[7] & 0xF0)
        self.mirroring = self.header[6] & 0x01
        self.battery = bool(self.header[6] & 0x02)
        self.trainer = self.data[16:528] if self.header[6] & 0x04 else None
        
        prg_start = 16 + (512 if self.trainer else 0)
        prg_end = prg_start + 16384 * self.prg_banks
        self.prg_rom = self.data[prg_start:prg_end]
        self.chr_rom = self.data[prg_end:prg_end + 8192 * self.chr_banks] if self.chr_banks > 0 else bytearray(8192)

# 6502 CPU Emulation (Minimal with Basic Memory)
class CPU:
    def __init__(self, rom):
        self.rom = rom
        self.chr_ram = rom.chr_rom if self.rom.chr_banks == 0 else None  # Reference CHR RAM
        self.ram = bytearray(0x0800)  # 2KB internal RAM
        self.reset()

    def reset(self):
        self.pc = self.read_word(0xFFFC)  # Read reset vector from PRG ROM
        self.sp = 0xFD
        self.acc = 0x00
        self.x = 0x00
        self.y = 0x00
        self.status = 0x24

    def step(self):
        opcode = self.read(self.pc)
        self.pc += 1
        if opcode == 0xA9:  # LDA Immediate
            self.acc = self.read(self.pc)
            self.pc += 1
        elif opcode == 0x4C:  # JMP Absolute
            self.pc = self.read_word(self.pc)
        return opcode

    def read(self, addr):
        if 0x0000 <= addr < 0x2000:
            return self.ram[addr % 0x0800]  # Mirror RAM
        elif 0x8000 <= addr < 0x10000:
            offset = addr - 0x8000
            if len(self.rom.prg_rom) == 0x4000:  # 16KB, mirror
                return self.rom.prg_rom[offset % 0x4000]
            return self.rom.prg_rom[offset % 0x8000]  # 32KB
        return 0x00

    def read_word(self, addr):
        return self.read(addr) | (self.read(addr + 1) << 8)

# PPU Emulation (Tile-Based Rendering)
class PPU:
    def __init__(self, cpu):
        pygame.init()
        pygame.display.set_caption("NES Emulator")
        self.screen = pygame.display.set_mode((256, 240))
        self.clock = pygame.time.Clock()
        self.framebuffer = pygame.Surface((256, 240))
        self.cpu = cpu  # Reference CPU for CHR RAM access

    def render_frame(self, chr_data, palette):
        self.framebuffer.fill((0, 0, 0))
        # Use CHR RAM if available, otherwise CHR ROM
        chr_source = self.cpu.chr_ram if self.cpu.chr_ram is not None else chr_data
        for tile_y in range(30):
            for tile_x in range(32):
                tile_index = tile_y * 32 + tile_x
                if tile_index < len(chr_source) // 16:
                    self.draw_tile(chr_source, tile_x * 8, tile_y * 8, tile_index, palette)
        self.screen.blit(self.framebuffer, (0, 0))
        pygame.display.flip()

    def draw_tile(self, chr_data, x, y, index, palette):
        tile_data = chr_data[index * 16:(index + 1) * 16]
        for row in range(8):
            lsb = tile_data[row]
            msb = tile_data[row + 8]
            for bit in range(8):
                color_bit = ((lsb >> (7 - bit)) & 1) | (((msb >> (7 - bit)) & 1) << 1)
                self.framebuffer.set_at((x + bit, y + row), palette[color_bit])

# APU Emulation (Basic Square Wave)
class APU:
    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
        self.channel = pygame.mixer.Channel(0)  # Use a single channel
        self.sound = self.generate_square(440, 1/60)  # Pre-generate for one frame

    def generate_square(self, frequency, duration):
        samples = int(44100 * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        wave = np.where(np.sin(2 * np.pi * frequency * t) > 0, 16383, -16384)
        return pygame.sndarray.make_sound(wave.astype(np.int16))

    def play(self):
        if not self.channel.get_busy():  # Play only if not already playing
            self.channel.play(self.sound)

# NES Emulator Kernel
class NES:
    def __init__(self, rom_path):
        self.rom = ROM(rom_path)
        self.cpu = CPU(self.rom)
        self.ppu = PPU(self.cpu)
        self.apu = APU()
        self.palette = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 255)]

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            for _ in range(29780):  # ~60 FPS
                self.cpu.step()
            self.ppu.render_frame(self.rom.chr_rom, self.palette)
            self.apu.play()
            self.ppu.clock.tick(60)  # Control frame rate here
        pygame.quit()  # Clean up Pygame on exit

# GUI Integration
class NESticleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NESticle - NES Emulator")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        self.root.configure(bg="#000080")

        self.title_label = tk.Label(root, text="NESticle v0.1", font=("Courier New", 18, "bold"), fg="white", bg="#000080")
        self.title_label.pack(pady=10)

        self.rom_frame = tk.Frame(root, bg="#000080")
        self.rom_frame.pack(pady=5)

        self.rom_listbox = tk.Listbox(self.rom_frame, width=60, height=10, font=("Courier New", 10), bg="#000000", fg="lime")
        self.rom_listbox.pack(side="left", fill="both")

        self.scrollbar = tk.Scrollbar(self.rom_frame, orient="vertical", command=self.rom_listbox.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.rom_listbox.config(yscrollcommand=self.scrollbar.set)

        self.button_frame = tk.Frame(root, bg="#000080")
        self.button_frame.pack(pady=10)

        self.load_button = tk.Button(self.button_frame, text="Load ROM", width=12, bg="#C0C0C0", fg="black", command=self.load_rom)
        self.load_button.grid(row=0, column=0, padx=5)

        self.play_button = tk.Button(self.button_frame, text="Play", width=12, bg="#C0C0C0", fg="black", command=self.play_game)
        self.play_button.grid(row=0, column=1, padx=5)

        self.exit_button = tk.Button(self.button_frame, text="Exit", width=12, bg="#C0C0C0", fg="black", command=root.quit)
        self.exit_button.grid(row=0, column=2, padx=5)

    def load_rom(self):
        file_path = filedialog.askopenfilename(title="Select NES ROM", filetypes=[("NES Files", "*.nes")])
        if file_path:
            self.rom_listbox.delete(0, tk.END)
            self.rom_listbox.insert(tk.END, file_path)

    def play_game(self):
        selected = self.rom_listbox.curselection()
        if selected:
            rom_path = self.rom_listbox.get(selected)
            if not os.path.isfile(rom_path):
                messagebox.showerror("File Not Found", f"The ROM file was not found:\n{rom_path}")
                return
            self.root.withdraw()
            try:
                nes = NES(rom_path)
                nes.run()
            except ValueError as e:
                messagebox.showerror("Invalid ROM", str(e))
            except Exception as e:
                messagebox.showerror("Emulation Error", str(e))
            finally:
                self.root.deiconify()
        else:
            messagebox.showwarning("No Selection", "Please select a ROM first!")

if __name__ == "__main__":
    root = tk.Tk()
    app = NESticleGUI(root)
    root.mainloop()
