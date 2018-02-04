import chip8
import random
from datetime import datetime
import os
import pygame, sys
from pygame.locals import *
import winsound

class SDLChip8(chip8.PETChip8CPU):
    def __init__(self, spd, filename):
        super().__init__(spd)
        super(SDLChip8, self).load(filename)        
        pygame.init()
        pygame.display.set_caption("Chip-8 Emulator -" + filename)
        self.DISPLAY_SURF = pygame.display.set_mode((1024,512))
        self.key_delay = 0
        self.key_threshold = 100000
        pygame.key.set_repeat(1,2)
        self.key_array = [pygame.K_x, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_z,
                          pygame.K_c, pygame.K_4, pygame.K_r, pygame.K_f, pygame.K_v]
    def process_input(self, inkeys):
        for i in range(0, len(self.key_array)):
            self.keys[i] = inkeys[self.key_array[i]]
        return
    def draw_screen(self):
        self.DISPLAY_SURF.fill(pygame.Color(0,0,0))
        self.draw_flag = False
        for i in range(0, 32):
            for j in range(0,64):
                self.DISPLAY_SURF.fill(self.get_color(self.graphics[(i * 64) + j]), pygame.Rect(j*16, i*16 , 16, 16))
        return
    def get_color(self, val):
        if val == 0:
            return pygame.Color(0,0,0)
        else:
            return pygame.Color(255,255,255)
    def process_blocking_keypress(self,key):
        value = -1
        if event.key in self.key_array:
            #A recognized key has been pressed, so stop blocking and acknowledge the input
            self.blocking_keypress = False
            value = self.key_array.index(event.key)
            self.set_register(rts_keypress, value)
        else:
            #No recognized key has been pressed, so keep blocking until one has
            self.blocking_keypress = True
        return
    def check_and_playsound(self):
        if self.sound_timer >= 0:
            if self.sound_just_started:
                self.sound_just_started = False
                winsound.Beep(440, self.sound_timer)
            else:
                self.sound_just_started = False
        else:
            winsound.PlaySound(None)
        return
    def is_awaiting_blocking_input(self):
        return self.blocking_keypress
    def is_to_be_drawn(self):
        return self.draw_flag
    def update_display(self):
        pygame.display.update()
        return
    def event_handler_loop(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif (event.type == pygame.KEYDOWN) and (self.key_delay >= self.key_threshold):
                if not self.is_awaiting_blocking_input():
                    self.process_input(pygame.key.get_pressed())
                    self.reset_key_delay()
                else:
                    self.process_blocking_keypress(event)
        return
    def increment_key_delay(self, micros):
        self.key_delay += micros
    def reset_key_delay(self):
        self.key_delay = 0
    def run(self):
        start = datetime.now()
        while True:
            newtime = datetime.now()
            delta_us = newtime - start
            self.increment_key_delay(delta_us.microseconds)
            start = newtime
            if not self.is_awaiting_blocking_input():
                self.emulate_instruction(delta_us.microseconds)
            self.event_handler_loop()
            self.check_and_playsound()
            if (self.is_to_be_drawn()):       
                self.draw_screen()
                self.update_display()
            pygame.time.delay(1)
        return
        

if __name__ == '__main__':
    myemu = SDLChip8(2000, "PONG2")
    myemu.dump_disassembly("PONG2", "pong2_disasm.asm")
    myemu.run()
    
            
