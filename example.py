import chip8
import random
from datetime import datetime
import os
import pygame, sys
from pygame.locals import *

def get_color(val):
    if val == 0:
        return pygame.Color(0,0,0)
    else:
        return pygame.Color(255,255,255)

def draw_screen(emulator, surface):
    for i in range(0, 32):
        for j in range(0,64):
            surface.fill(get_color(emulator.graphics[(i * 64) + j]), pygame.Rect(j*16, i*16 , 16, 16))
    return

def process_input(emulator, inkeys):
    emulator.keys[0] = inkeys[pygame.K_x]
    emulator.keys[1] = inkeys[pygame.K_1]
    emulator.keys[2] = inkeys[pygame.K_2]
    emulator.keys[3] = inkeys[pygame.K_3]
    emulator.keys[4] = inkeys[pygame.K_q]
    emulator.keys[5] = inkeys[pygame.K_w]
    emulator.keys[6] = inkeys[pygame.K_e]
    emulator.keys[7] = inkeys[pygame.K_a]
    emulator.keys[8] = inkeys[pygame.K_s]
    emulator.keys[9] = inkeys[pygame.K_d]
    emulator.keys[10] = inkeys[pygame.K_z]
    emulator.keys[11] = inkeys[pygame.K_c]
    emulator.keys[12] = inkeys[pygame.K_4]
    emulator.keys[13] = inkeys[pygame.K_r]
    emulator.keys[14] = inkeys[pygame.K_f]
    emulator.keys[15] = inkeys[pygame.K_v]
    return

if __name__ == '__main__':
    myemu = chip8.PETChip8CPU(2000)
    name = "PONG2"
    myemu.load(name)
    pygame.init()
    DISPLAY_SURF = pygame.display.set_mode((1024,512))
    pygame.display.set_caption("Chip-8 Emulator -" + name)
    start = datetime.now()
    key_delay = 0
    key_threshold = 100000
    pygame.key.set_repeat(1,2)
    while True:
        newdt = datetime.now()
        delta_us = newdt - start
        key_delay += delta_us.microseconds
        start = newdt
        if not myemu.blocking_keypress:
            myemu.emulate_instruction(delta_us.microseconds)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif (event.type == pygame.KEYDOWN) and (key_delay > key_threshold):
                myemu.blocking_keypress = False
                process_input(myemu, pygame.key.get_pressed())
                key_delay = 0
        if (myemu.draw_flag):
            DISPLAY_SURF.fill(pygame.Color(0,0,0))
            draw_screen(myemu, DISPLAY_SURF)
            myemu.draw_flag = False
            pygame.display.update()
        pygame.time.delay(1)
            
