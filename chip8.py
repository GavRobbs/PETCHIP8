import random
import os

class PETChip8CPU:
    def __init__(self, speed):
        #The chip8 had 4096 (0x1000) memory locations, all of which are 1 byte
        self.program_counter = 0x200 #The chip 8 interpreter itself occupies the first 512 bytes
        self.refresh_pointer = 0xF00 #The uppermost 256 bytes are reserved for display refresh
        self.call_stack = 0xEA0 #The 96 bytes below that are reserved for call stack, internal use and other variables
        #The chip8 has 16 bit data registers named from V0 to VF. I decided to store it as a dictionary instead of a list for semantic purposes
        self.registers = {"V0":0, "V1":0, "V2":0, "V3":0, "V4":0, "V5":0, "V6":0, "V7":0, "V8":0, "V9":0, "V10":0, "V11":0, "V12":0, "V13":0, "V14":0, "V15":0}
        self.address_register = int(0) #There is also an address register called I, I decided to store this separately
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
        self.lastdisasm = ""
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
            self.lastdisasm = "Screen cleared"
            self.draw_flag = True
            self.program_counter += 2
        elif opcode == 0x00EE:
            #Return from subroutine; sets the program counter to the address at the top of the stack and subtracts 1 from the stack pointer (pops it)
            self.program_counter = self.stack[self.stack_pointer] + 2
            self.stack_pointer -= 1
            self.lastdisasm = "Returned from subroutine, back to address: " + str(self.program_counter)
        else:
            #Old instruction to jump to a machine code routine at NNN, apparently said to be ignored by most modern interpreters
            self.program_counter = opcode & 0x0FFF
            self.lastdisasm = "Old style opcode jump to: " + str(self.program_counter)
        return
    
    def execute_one_series(self, opcode):
        #Jump to opcode at NNN; I guess the modern equivalent of the other command?
        self.program_counter = opcode & 0x0FFF
        self.lastdisasm = "Program counter set to: " + str(self.program_counter)
        return
    
    def execute_two_series(self, opcode):
        #Call subroutine at NNN; Increments the stack pointer then puts the current program counter at the top of the stack, then sets the program counter to NNN
        self.stack_pointer += 1
        self.stack[self.stack_pointer] = self.program_counter
        self.program_counter = opcode & 0x0FFF
        self.lastdisasm = "Called subroutine at: " + str(self.program_counter)
        return
    
    def execute_three_series(self, opcode):
        #Skip next instruction if Vx == kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        if data == self.get_register(register):
            self.program_counter += 4
            self.lastdisasm = "Skipped program counter to: " + str(self.program_counter) + " because register " + str(register) + " equals " + str(data)
        else:
            self.lastdisasm = "Did not skip program counter because register " + str(register) + " is not equal to " + str(data)
            self.program_counter += 2
        return
    
    def execute_four_series(self,opcode):
        #Skip next instruction if Vx != kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        if data != self.get_register(register):
            self.program_counter += 4
            self.lastdisasm = "Skipped program counter to: " + str(self.program_counter) + " because register " + str(register) + " not equals " + str(data)
        else:
            self.program_counter += 2
            self.lastdisasm = "Did not skip program counter because register " + str(register) + " is equal to " + str(data)
        return
    
    def execute_five_series(self, opcode):
        #Skip next instruction if Vx == Vy
        register1 = (opcode & 0x0F00) >> 8
        register2 = (opcode & 0x00F0) >> 4
        if self.get_register(register1) == self.get_register(register2):
            self.program_counter += 4
            self.lastdisasm = "Register " + str(register1) + " was equal to register " + str(register2) + " so skipped program counter to: " + str(self.program_counter)
        else:
            self.program_counter += 2
            self.lastdisasm = "Did not skip program counter since register " + str(register1) + " was not equal to " + str(register2)
        return
    
    def execute_six_series(self, opcode):
        #Set Vx = kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        self.set_register(register, data)
        self.program_counter += 2
        self.lastdisasm = "Register " + str(register) + " set to " + str(data)
        return
    
    def execute_seven_series(self, opcode):
        #Set Vx += kk
        register = (opcode & 0x0F00) >> 8
        data = opcode & 0x00FF
        value = data + self.get_register(register)
        self.set_register(register, value & 0xFF)
        self.program_counter += 2
        self.lastdisasm = "Register " + str(register) + " set to " + str(value) + " by adding " + str(data)
        return
    
    def execute_eight_series(self, opcode):
        #A lot of different instructions here
        last_byte = opcode & 0x000F
        if last_byte == 0x0:
            #8xy0 Set Vx = Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register2))
            self.lastdisasm  = "Register " + str(register1) + " set to equal register " + str(register2) + " with value of " + str(self.get_register(register1))
        elif last_byte == 0x1:
            #8xy1 Set Vx |= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, (self.get_register(register1) | self.get_register(register2)) & 0xFF)
            self.lastdisasm  = "Register " + str(register1) + " OR register " + str(register2) + " equals " + str(self.get_register(register1)) + " stored in register " + str(register1)
        elif last_byte == 0x2:
            #8xy2 Set Vx &= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, (self.get_register(register1) & self.get_register(register2)) & 0xFF)
            self.lastdisasm  = "Register " + str(register1) + " AND register " + str(register2) + " equals " + str(self.get_register(register1)) + " stored in register " + str(register1)
        elif last_byte == 0x3:
            #8xy3 Set Vx ^= Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, (self.get_register(register1) ^ self.get_register(register2)) & 0xFF)
            self.lastdisasm  = "Register " + str(register1) + " XOR register " + str(register2) + " equals " + str(self.get_register(register1)) + " stored in register " + str(register1)
        elif last_byte == 0x4:
            #8xy4 Set Vx = Vx + Vy, with a carry
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register1) + self.get_register(register2))
            if self.get_register(register1) > 255:
                self.set_register(register1, self.get_register(register1) & 0xFF)
                self.set_register(15,1)
            else:
                self.set_register(15,0)
            self.lastdisasm = "Register " + str(register1) + " added to register " + str(register2) + " to give value of " + str(self.get_register(register1)) + " with carry = " + str(self.get_register(15))
        elif last_byte == 0x5:
            #8xy5 Set Vx = Vx - Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            if self.get_register(register1) > self.get_register(register2):
                self.set_register(15,1)
                self.set_register(register1, self.get_register(register1) - self.get_register(register2))
                self.lastdisasm = "Register " + str(register1) + " subtracted from register " + str(register2) + " to give value of " + str(self.get_register(register1)) + " with non-borrow = " + str(self.get_register(15))
            else:
                self.set_register(15,0)
                self.set_register(register1, self.get_register(register2) - self.get_register(register1))
                self.lastdisasm = "Register " + str(register2) + " subtracted from register " + str(register1) + " to give value of " + str(self.get_register(register1)) + " with non-borrow = " + str(self.get_register(15))
        elif last_byte == 0x6:
            #8xy6 Vx = Vx >> 1, VF becomes the value of LSB of Vx before shift
            register1 = (opcode & 0x0F00) >> 8
            self.set_register(15, self.get_register(register1) & 0x01)
            self.set_register(register1, (self.get_register(register1) >> 1) & 0xFF)
            self.lastdisasm = "Bitshifted register " + str(register1) + " by 1 to right to get " + str(self.get_register(register1)) + " and flag register equals " + str(self.get_register(15))
        elif last_byte == 0x7:
            #8xy7 SUBN Vx, Vy
            register1 = (opcode & 0x0F00) >> 8
            register2 = (opcode & 0x00F0) >> 4
            self.set_register(register1, self.get_register(register2) - self.get_register(register1))
            if self.get_register(register2) > self.get_register(register1):
                self.set_register(15,1)
                self.lastdisasm = "Something complex done here"
            else:
                self.set_register(15,0)
                self.lastdisasm = "Something complex done here"
        elif last_byte == 0xE:
            #8xyE Vx = Vx << 1, VF becomes the value of MSB of Vx before shift
            register1 = (opcode & 0x0F00) >> 8
            self.set_register(15, self.get_register(register1) & 0x8000)
            self.set_register(register1, (self.get_register(register1) << 1) & 0xFF)
            self.lastdisasm = "Bitshifted register " + str(register1) + " by 1 to left to get " + str(self.get_register(register1)) + " and flag register equals " + str(self.get_register(15))
        self.program_counter += 2
        return
    
    def execute_nine_series(self, opcode):
        #Skip next instruction if Vx != Vy
        register1 = (opcode & 0x0F00) >> 8
        register2 = (opcode & 0x00F0) >> 4
        if self.get_register(register1) != self.get_register(register2):
            self.program_counter += 4
            self.lastdisasm = "Skipped next instruction because " + str(register1) + " isn't equal to " + str(register2)
        else:
            self.program_counter += 2
            self.lastdisasm = "Didn't skip next instruction because " + str(register1) + " IS equal to " + str(register2)   
        return
    
    def execute_ten_series(self, opcode):
        #Set I = nnn
        self.address_register = opcode & 0x0FFF
        self.program_counter += 2
        self.lastdisasm = "Set address register to " + str(self.address_register)
        return
    
    def execute_eleven_series(opcode):
        self.program_counter = self.get_register(0) + (opcode & 0x0FFF)
        self.lastdisasm = "Set program counter to " + str(self.program_counter) + " by adding " + str(opcode & 0x0FFF)
        return
    
    def execute_twelve_series(self, opcode):
        random_byte = random.randint(0,255)
        register = (opcode & 0x0F00) >> 8
        kk = opcode & 0x00FF
        data = random_byte & kk
        self.set_register(register,data & 0xFF)
        self.program_counter += 2
        self.lastdisasm = "Set register " + str(register) + " to " + str(random_byte) + " AND " + str(kk) + "= " + str(data & 0xFF)
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
                    self.graphics[self.wrap_gfx((y + yline)*64 + (x+xline))] ^= 1
        self.draw_flag = True                
        self.program_counter += 2
        self.lastdisasm = "Displayed " + str(height) + " byte sprite at memory location " + str(self.address_register) + " starting at coordinates " + str(x) + "," + str(y) + " and collision flag is now " + str(self.get_register(15))
        return
    
    def execute_fourteen_series(self, opcode):
        last_byte = opcode & 0x00FF
        register = (opcode & 0x0F00) >> 8
        if last_byte == 0x9E:
            #Skip next instruction if key with value of Vx is pressed
            if self.keys[self.get_register(register)] == True:
                self.program_counter += 4
                self.lastdisasm = "Skipped next instruction because key with value of " + str(self.get_register(register)) + " was pressed."
                self.keys[self.get_register(register)] = False
            else:
                self.program_counter += 2
                self.lastdisasm = "Didn't skip next instruction because key with value of " + str(self.get_register(register)) + " was NOT pressed."
        elif last_byte == 0xA1:
            #Skip next instruction if key with value of Vx is NOT pressed
            if self.keys[self.get_register(register)] == False:
                self.program_counter += 4
                self.lastdisasm = "Skipped next instruction because key with value of " + str(self.get_register(register)) + " was NOT pressed."
            else:
                self.program_counter += 2
                self.lastdisasm = "Didn't skip next instruction because key with value of " + str(self.get_register(register)) + " was pressed."
                self.keys[self.get_register(register)] = False
        return
    
    def execute_fifteen_series(self, opcode):
        last_byte = opcode & 0x00FF
        register = (opcode & 0x0F00) >> 8
        if last_byte == 0x07:
            #Set Vx = delay timer value
            self.set_register(register, self.delay_timer)
            self.lastdisasm = "Put timer value of " + str(self.delay_timer) + " in register " + str(register)
        elif last_byte == 0x0A:
            #Wait for a key press, store the value of the key in Vx
            self.blocking_keypress = True
            self.lastdisasm = "Waiting for keypress - blocking version"
        elif last_byte == 0x15:
            #Set delay timer = Vx
            self.delay_timer = self.get_register(register)
            self.lastdisasm = "Set the delay timer to the value of " + str(self.get_register(register)) + " held in register " + str(register)
        elif last_byte == 0x18:
            #Set sound timer = Vx
            self.sound_timer = self.get_register(register)
            self.lastdisasm = "Set the sound timer to the value of " + str(self.get_register(register)) + " held in register " + str(register)
        elif last_byte == 0x1E:
            #Set I to I+Vx
            self.address_register += self.get_register(register)
            self.lastdisasm = "Incremented I by the value in register " + str(register) + " to set address_register to " + str(self.address_register)
        elif last_byte == 0x29:
            #Set I to memory location of sprite for digit Vx
            self.address_register = self.get_register(register) * 5
            self.lastdisasm = "Set address register to " + str(self.address_register) + " to get sprite for character " + str(self.get_register(register)) + " stored in register " + str(register) 
        elif last_byte == 0x33:
            #Store the BCD representation of Vx in memory locations I to I+2
            self.memory[self.address_register] = int(self.get_register(register)/100)
            self.memory[self.address_register + 1] = int((self.get_register(register)/10) % 10)
            self.memory[self.address_register + 2] = int((self.get_register(register)/100) % 10)
            self.lastdisasm = "Binary coded decimal of " + str(self.get_register(register)) + " stored starting at memory location " + str(self.address_register) + " as " + str(self.memory[self.address_register]) + "," + str(self.memory[self.address_register+1]) + "," + str(self.memory[self.address_register+2])
        elif last_byte == 0x55:
            #Store registers V0 through Vx in memory starting at location I
            for i in range(0, register + 1):
                self.memory[self.address_register + i] = self.get_register(i)
            self.lastdisasm = "Stored registers 0 through " + str(register) + " starting at memory location " + str(self.address_register)    
        elif last_byte == 0x65:
            #Read registers V0 through Vx from memory starting at location I
            for i in range(0, register + 1):
                self.set_register(i, self.memory[self.address_register + i])
            self.lastdisasm = "Read registers 0 through " + str(register) + " starting at memory location " + str(self.address_register)   
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
        return True
    
    def clear_input(self):
        for i in range(0,16):
            self.keys[i] = False
        return
    
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
