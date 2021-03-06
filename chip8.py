import random
import os
import math

class PETChip8CPU:
    def __init__(self, speed):
        #The chip8 had 4096 (0x1000) memory locations, all of which are 1 byte
        self.program_counter = 0x200 #The chip 8 interpreter itself occupies the first 512 bytes
        self.refresh_pointer = 0xF00 #The uppermost 256 bytes are reserved for display refresh
        self.call_stack = 0xEA0 #The 96 bytes below that are reserved for call stack, internal use and other variables
        #The chip8 has 16 bit data registers named from V0 to VF. I decided to store it as a dictionary instead of a list for semantic purposes
        self.registers = {"V0":0, "V1":0, "V2":0, "V3":0, "V4":0, "V5":0, "V6":0, "V7":0, "V8":0, "V9":0, "V10":0, "V11":0, "V12":0, "V13":0, "V14":0, "V15":0}
        self.address_register = 0 #There is also an address register called I, I decided to store this separately
        self.stack_pointer = 0
        self.stack = [0] * 16 #The stack is used to store return addresses when subroutines are called
        self.memory = [0] * 4096 #The chip8 has 4k of memory in total
        self.graphics = [0] * 2048 #The screen has a total of 2048 pixels
        self.delay_timer = 0
        self.sound_timer = 0 #The two timers count down to zero at a rate of 60 Hz if they are nonzero
        self.keys = [False] * 16 #The chip8 has a hex-based keypad with 16 keys
        self.blocking_keypress = False #Set to true if the chip8 is blocking and waiting for a keypress
        self.draw_flag = True #Says that we updated the screen so we need to redraw
        self.cycle_deltasum = 0
        self.delay_deltasum = 0
        self.sound_deltasum = 0
        self.rts_keypress = -1 #The register number to store the blocking keypress value in
        self.sound_just_started = False
        self.CYCLE_LENGTH_MICROS = speed
        random.seed()
        self.memory[0:80] = [0xF0, 0x90, 0x90, 0x90, 0xF0, 
                          0x20, 0x60, 0x20, 0x20, 0x70,
                          0xF0, 0x10, 0xF0, 0x80, 0xF0,
                          0xF0, 0x10, 0xF0, 0x10, 0xF0,
                          0x90, 0x90, 0xF0, 0x10, 0x10, 
                          0xF0, 0x80, 0xF0, 0x10, 0xF0, 
                          0xF0, 0x80, 0xF0, 0x90, 0xF0,
                          0xF0, 0x10, 0x20, 0x40, 0x40,
                          0xF0, 0x90, 0xF0, 0x90, 0xF0,
                          0xF0, 0x90, 0xF0, 0x10, 0xF0,
                          0xF0, 0x90, 0xF0, 0x90, 0x90,
                          0xE0, 0x90, 0xE0, 0x90, 0xE0,
                          0xF0, 0x80, 0x80, 0x80, 0xF0,
                          0xE0, 0x90, 0x90, 0x90, 0xE0,
                          0xF0, 0x80, 0xF0, 0x80, 0xF0,
                          0xF0, 0x80, 0xF0, 0x80, 0x80]
        return
    
    def create_word(self, highbyte, lowbyte):
        return (highbyte << 8) | lowbyte
    
    def split_word(self, word):
        return (word >> 8, word & 0xF0)

    def execute_zero_series(self, opcode):
        if opcode == 0x00E0:
            self.graphics[0:2048] = [0] * 2048 #Clears the screen
            self.draw_flag = True
            self.program_counter += 2
        elif opcode == 0x00EE:
            #Return from subroutine; sets the program counter to the address at the top of the stack and subtracts 1 from the stack pointer (pops it)
            self.program_counter = self.stack[self.stack_pointer] + 2
            self.stack_pointer -= 1
        elif opcode == 0x0000:
            self.program_counter += 2
        else:
            #Old instruction to jump to a machine code routine at NNN, apparently said to be ignored by most modern interpreters
            self.program_counter = opcode & 0x0FFF
        return
    
    def execute_one_series(self, opcode):
        #Jump to opcode at NNN; I guess the modern equivalent of the other command?
        self.program_counter = opcode & 0x0FFF
        return
    
    def execute_two_series(self, opcode):
        #Call subroutine at NNN; Increments the stack pointer then puts the current program counter at the top of the stack, then sets the program counter to NNN
        self.stack_pointer += 1
        self.stack[self.stack_pointer] = self.program_counter
        self.program_counter = opcode & 0x0FFF
        return
    
    def execute_three_series(self, opcode):
        #Skip next instruction if Vx == kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        if data == self.get_register(register):
            self.program_counter += 4
        else:
            self.program_counter += 2
        return
    
    def execute_four_series(self,opcode):
        #Skip next instruction if Vx != kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        if data != self.get_register(register):
            self.program_counter += 4
        else:
            self.program_counter += 2
        return
    
    def execute_five_series(self, opcode):
        #Skip next instruction if Vx == Vy
        register1 = (opcode & 0x0F00) >> 8
        register2 = (opcode & 0x00F0) >> 4
        if self.get_register(register1) == self.get_register(register2):
            self.program_counter += 4 
        else:
            self.program_counter += 2
        return
    
    def execute_six_series(self, opcode):
        #Set Vx = kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        self.set_register(register, data)
        self.program_counter += 2
        return
    
    def execute_seven_series(self, opcode):
        #Set Vx += kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        value = data + self.get_register(register)
        self.set_register(register, value % 256)
        self.program_counter += 2
        return
    
    def execute_eight_series(self, opcode):
        #A lot of different instructions here
        last_byte = opcode & 0x000F
        if last_byte == 0x0:
            #8xy0 Set Vx = Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register2))
        elif last_byte == 0x1:
            #8xy1 Set Vx |= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register1) | self.get_register(register2))
        elif last_byte == 0x2:
            #8xy2 Set Vx &= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register1) & self.get_register(register2))
        elif last_byte == 0x3:
            #8xy3 Set Vx ^= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register1) ^ self.get_register(register2))
        elif last_byte == 0x4:
            #8xy4 Set Vx = Vx + Vy, with a carry
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            data = self.get_register(register1) + self.get_register(register2)
            if data > 255:
                self.set_register(register1, data % 256)
                self.set_register(15,1)
            else:
                self.set_register(15,0)
                self.set_register(register1, data)
        elif last_byte == 0x5:
            #8xy5 Set Vx = Vx - Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            if self.get_register(register1) > self.get_register(register2):
                self.set_register(15,1)
                self.set_register(register1, self.get_register(register1) - self.get_register(register2))
            else:
                self.set_register(15,0)
                self.set_register(register1, self.get_register(register2) - self.get_register(register1))
        elif last_byte == 0x6:
            #8xy6 Vx = Vy = Vy >> 1, VF becomes the value of LSB of Vx before shift
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            data1 = self.get_register(register2)
            self.set_register(15,data1 & 0x01)
            self.set_register(register1, (data1 >> 1) % 256)
            self.set_register(register2, (data1 >> 1) % 256)
        elif last_byte == 0x7:
            #8xy7 Vx = Vy - Vx, set VF = NOT borrow
            register1 = (opcode & 0x00F0) >> 4
            register2 = (opcode & 0x0F00) >> 8
            if self.get_register(register1) > self.get_register(register2):
                self.set_register(15,1)
                self.set_register(register2, self.get_register(register1) - self.get_register(register2))
            else:
                self.set_register(15,0)
                self.set_register(register2, self.get_register(register2) - self.get_register(register1))
        elif last_byte == 0xE:
            #8xyE Vx = Vy = Vy << 1, VF becomes the value of MSB of Vx before shift
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            data2 = self.get_register(register2)
            self.set_register(15,data2 & 0x80)
            self.set_register(register1, (data2 << 1) % 256)
            self.set_register(register2, (data2 << 1) % 256)
        self.program_counter += 2
        return
    
    def execute_nine_series(self, opcode):
        #Skip next instruction if Vx != Vy
        register1 = (opcode & 0x0F00) >> 8
        register2 = (opcode & 0x00F0) >> 4
        if self.get_register(register1) != self.get_register(register2):
            self.program_counter += 4
        else:
            self.program_counter += 2   
        return
    
    def execute_ten_series(self, opcode):
        #BNNN - Set I = nnn
        self.address_register = opcode & 0x0FFF
        self.program_counter += 2
        return
    
    def execute_eleven_series(opcode):
        #Bnnn - Jump to location nnn + V0
        self.program_counter = (self.get_register(0) + (opcode & 0x0FFF)) + 512
        return
    
    def execute_twelve_series(self, opcode):
        #Cxkk - Set Vx to random byte AND kk
        random_byte = random.randint(0,255)
        register = (opcode & 0x0F00) >> 8
        kk = opcode & 0x00FF
        data = random_byte & kk
        self.set_register(register,data)
        self.program_counter += 2
        return
    
    def wrap_gfx(self, val):
        if val < 2048:
            return val
        else:
            return val & 0x6FF
        
    def execute_thirteen_series(self, opcode):
        #Display n byte sprite starting at memory location I at Vx, Vy
        register1 = (opcode & 0x0F00) >> 8
        register2 = (opcode & 0x00F0) >> 4
        x = self.get_register(register1)
        y = self.get_register(register2)
        height = (opcode & 0x000F)
        pixel = 0
        self.set_register(15,0)
        for yline in range(0, height):
            pixel = self.memory[self.address_register + yline]
            for xline in range(0, 8):
                if pixel & (0x80 >> xline) != 0:
                    if self.graphics[self.wrap_gfx((y + yline)*64 + (x+xline))] == 1:
                        self.set_register(15,1)
                        self.graphics[self.wrap_gfx((y + yline)*64 + (x+xline))] = 0
                    else:
                        self.graphics[self.wrap_gfx((y + yline)*64 + (x+xline))] = 1
        self.draw_flag = True                
        self.program_counter += 2
        return
    
    def execute_fourteen_series(self, opcode):
        last_byte = opcode & 0x00FF
        register = (opcode & 0x0F00) >> 8
        if last_byte == 0x9E:
            #Ex9E - Skip next instruction if key with value of Vx is pressed
            if self.keys[self.get_register(register)] == True:
                self.program_counter += 4
                self.keys[self.get_register(register)] = False
            else:
                self.program_counter += 2
        elif last_byte == 0xA1:
            #ExA1 - Skip next instruction if key with value of Vx is NOT pressed
            if self.keys[self.get_register(register)] == False:
                self.program_counter += 4
            else:
                self.program_counter += 2
                self.keys[self.get_register(register)] = False
        return
    
    def execute_fifteen_series(self, opcode):
        last_byte = opcode & 0x00FF
        register = (opcode & 0x0F00) >> 8
        if last_byte == 0x07:
            #Fx07 - Set Vx = delay timer value
            self.set_register(register, self.delay_timer)
        elif last_byte == 0x0A:
            #Fx0A - Wait for a key press, store the value of the key in Vx
            self.blocking_keypress = True
            self.rts_keypress = register
        elif last_byte == 0x15:
            #Fx15 - Set delay timer = Vx
            self.delay_timer = self.get_register(register)
        elif last_byte == 0x18:
            #Fx18 - Set sound timer = Vx
            self.sound_timer = self.get_register(register)
            self.sound_just_started = True
        elif last_byte == 0x1E:
            #Fx1E - Set I to I+Vx
            #VF is set to 1 when there is a range overflow (the new value of I > 0xFFF; this is an undocumented feature used by Spaceflight 2091 (wiki)
            self.address_register += self.get_register(register)
            if self.address_register > 0xFFF:
                self.address_register &= 0xFFF
                self.set_register(15, 1)
        elif last_byte == 0x29:
            #Fx29 - Set I to memory location of sprite for digit Vx
            self.address_register = self.get_register(register) * 5 #Remember we stored this data from 0 to 80 in the memory array
        elif last_byte == 0x33:
            #Fx33 - Store the BCD representation of Vx in memory locations I to I+2
            #I is increased by 1 for each value written
            data = self.get_register(register)
            self.memory[self.address_register] = int(data/100)
            self.memory[self.address_register + 1] = int((data/10) % 10)
            self.memory[self.address_register + 2] = int(data % 10)
        elif last_byte == 0x55:
            #Fx55 - Store registers V0 through Vx in memory starting at location I
            for i in range(0, register + 1):
                self.memory[self.address_register] = self.get_register(i)
                self.address_register += 1
        elif last_byte == 0x65:
            #Fx65 - Read registers V0 through Vx from memory starting at location I
            for i in range(0, register + 1):
                self.set_register(i, self.memory[self.address_register])
                self.address_register += 1
        self.program_counter += 2
        return
    
    def execute_opcode(self, opcode):
        if opcode < 0x1000:
            self.execute_zero_series(opcode)
        elif opcode < 0x2000:
            self.execute_one_series(opcode)
        elif opcode < 0x3000:
            self.execute_two_series(opcode)
        elif opcode < 0x4000:
            self.execute_three_series(opcode)
        elif opcode < 0x5000:
            self.execute_four_series(opcode)
        elif opcode < 0x6000:
            self.execute_five_series(opcode)
        elif opcode < 0x7000:
            self.execute_six_series(opcode)
        elif opcode < 0x8000:
            self.execute_seven_series(opcode)
        elif opcode < 0x9000:
            self.execute_eight_series(opcode)
        elif opcode < 0xA000:
            self.execute_nine_series(opcode)
        elif opcode < 0xB000:
            self.execute_ten_series(opcode)
        elif opcode < 0xC000:
            self.execute_eleven_series(opcode)
        elif opcode < 0xD000:
            self.execute_twelve_series(opcode)
        elif opcode < 0xE000:
            self.execute_thirteen_series(opcode)
        elif opcode < 0xF000:
            self.execute_fourteen_series(opcode)
        elif opcode >= 0xF000:
            self.execute_fifteen_series(opcode)
        return
    
    def get_register(self, register):
        return self.registers["V" + str(register)]
    
    def set_register(self, register, value):
        self.registers["V" + str(register)] = value        
        return
    
    def emulate_instruction(self, delta):
        #Fetches, decodes and executes the opcode and updates the timers
        self.cycle_deltasum += delta
        self.delay_deltasum += delta
        self.sound_deltasum += delta
        #The chip-8 runs at about 500 Hz, the timer frequency is 60 Hz, so the timers run at approximately 1/8 the speed of the processor
        if self.delay_timer > 0:
                if self.delay_deltasum >= int(self.CYCLE_LENGTH_MICROS * 8.33):
                    self.delay_timer -= 1
                    self.delay_deltasum = 0
        if self.sound_timer > 0:
                if self.sound_deltasum >= int(self.CYCLE_LENGTH_MICROS * 8.33):
                    self.sound_timer -= 1
                    self.sound_deltasum = 0
        if self.cycle_deltasum >= self.CYCLE_LENGTH_MICROS:
            opcode = self.create_word(self.memory[self.program_counter], self.memory[self.program_counter+1])
            self.execute_opcode(opcode)
            self.cycle_deltasum = 0
            return True
        else:
            return False
    
    def load(self, filename):
        romsize = os.stat(filename).st_size
        fin = open(filename, "rb")
        self.memory[512:512+romsize] = list(fin.read())
        fin.close()
        return
    
    def print_state(self):
        print(self.registers)
        print("Stack pointer", self.stack_pointer)
        print("Program counter", self.program_counter)
        print("Address register", self.address_register)
        print("Am I blocking?", self.blocking_keypress)
        return

    def dump_disassembly(self, infile, outfile):
        infile = open(infile, "rb")
        fdata = list(infile.read())
        infile.close()
        outfile = open(outfile, "w")
        for i in range(0, len(fdata), 2):
            opcode = self.create_word(fdata[i],fdata[i+1])
            outfile.write(str(i) + ": ")
            if opcode < 0x1000:
                if opcode == 0x00E0:
                    outfile.write("CLS \n")
                elif opcode == 0x00EE:
                    outfile.write("RET \n")
                else:
                    outfile.write("SPACE \n")
            elif opcode < 0x2000:
                outfile.write("JMPOS " + str((opcode & 0x0FFF) - 512) + "\n")
            elif opcode < 0x3000:
                outfile.write("CALL " + str((opcode & 0x0FFF) - 512) + "\n")
            elif opcode < 0x4000:
                outfile.write("SE " + "V" + str((opcode & 0xF00) >> 8) + ", " + str(opcode & 0x00FF) + "\n")
            elif opcode < 0x5000:
                outfile.write("SNE V" + str((opcode & 0xF00) >> 8) + ", " + str(opcode & 0x00FF) + "\n")
            elif opcode < 0x6000:
                outfile.write("SE " + "V" + str((opcode & 0xF00) >> 8) + ", " + str(opcode & 0x00FF) + "\n")
            elif opcode < 0x7000:
                outfile.write("LD " + "V" + str((opcode & 0xF00) >> 8) + ", " + str(opcode & 0x00FF) + "\n")
            elif opcode < 0x8000:
                outfile.write("ADD V" + str((opcode & 0xF00) >> 8) + ", " + str(opcode & 0x00FF) + "\n")
            elif opcode < 0x9000:
                lesser = opcode & 0x1
                if lesser == 0:
                    outfile.write("LD V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 1:
                    outfile.write("OR V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 2:
                    outfile.write("AND V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 3:
                    outfile.write("XOR V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 4:
                    outfile.write("ADD V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 5:
                    outfile.write("SUB V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 6:
                    outfile.write("SHR V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 7:
                    outfile.write("SUBN V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                elif lesser == 0xE:
                    outfile.write("SHL V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
                else:
                    outfile.write("Not implemented \n")
            elif opcode < 0xA000:
                outfile.write("SNE V" +  str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + "\n")
            elif opcode < 0xB000:
                outfile.write("LD I, " + str(opcode & 0xFFF) + "\n")
            elif opcode < 0xC000:
                outfile.write("JP V" + str(opcode & 0xFFF) + "\n")
            elif opcode < 0xD000:
                outfile.write("RAND V" + str((opcode & 0xF00) >> 8) + " " + str((opcode & 0x00FF)) + "\n")
            elif opcode < 0xE000:
                outfile.write("DRW V" + str((opcode & 0xF00) >> 8) + ", V" + str((opcode & 0x00F0) >> 4) + ", " + str(opcode & 0x000F) + "\n")
            elif opcode < 0xF000:
                lesser = opcode & 0xFF
                if lesser == 0x9E:
                    outfile.write("SKP V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0xA1:
                    outfile.write("SKNP V" + str((opcode & 0x0F00) >> 8) + "\n")
                else:
                    outfile.write("Unimplemented \n")
            else:
                lesser = opcode & 0xFF
                if lesser == 0x07:
                    outfile.write("LD V" + str((opcode & 0x0F00) >> 8) + ", DT \n")
                elif lesser == 0x0A:
                    outfile.write("LD V" + str((opcode & 0x0F00) >> 8) + ", K \n")
                elif lesser == 0x15:
                    outfile.write("LD DT, V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x18:
                    outfile.write("LD ST, V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x1E:
                    outfile.write("ADD I, V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x29:
                    outfile.write("LD F, V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x33:
                    outfile.write("LD B, V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x55:
                    outfile.write("LD [I], V" + str((opcode & 0x0F00) >> 8) + "\n")
                elif lesser == 0x65:
                    outfile.write("LD V" + str((opcode & 0x0F00) >> 8) + ", [I]\n")
                else:
                    outfile.write(str(opcode) + "\n")
        outfile.close()
        return

    def draw_screen(self): #To be implemented by the derived class
        return

    def check_and_playsound(self):
        return

    def process_input(self,inkeys): #To be implemented by the derived class
        return

    def process_blocking_keypress(self, key): #To be implemented by the derived class
        return

    def run(self):  #To be implemented by the derived class
        return

    def event_handler_loop(self): #To be implemented by the derived class
        return
