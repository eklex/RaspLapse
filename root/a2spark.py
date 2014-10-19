#!/usr/bin/env python3

#######################
## designed for Python3
## 2014/04/06
## Alexandre Boni
## For a2Spark
#######################

import smbus
import time


"""
*****************************************************************
***                      I2C Registers                        ***
***                      Offset & Mask                        ***
*****************************************************************
"""
### I2C Address Reg
ADDR          =        (0x00)
### Firmware Version Register
FWVR          =        (0x01)
### Analog Configuration Register
AN1CR         =        (0x04)
AN2CR         =        (0x14)
ANEN          =        (0x01<<0)
LPEN          =        (0x01<<1)
### Average Analog Register
LPF1R         =        (0x05)
LPF2R         =        (0x15)
LP            =        (0x0F<<0)
### Analog Data Register
AN1DRL        =        (0x06)
AN2DRL        =        (0x16)
AN1DRH        =        (0x07)
AN2DRH        =        (0x17)
AN_L          =        (0xFF<<0)
AN_H          =        (0x03<<0)
### Alarm Configuration Register
AL1CR         =        (0x08)
AL2CR         =        (0x18)
ALEN          =        (0x01<<0)
ALO           =        (0x01<<1)
ALME          =        (0x01<<4)
ALM           =        (0x07<<5)
ALM_INV       =        (0x01<<7)
ALM_FE        =        (0x01<<5)
ALM_RE        =        (0x01<<6)
ALM_DE        =        (ALM_RE | ALM_FE)
ALM_L         =        (0x03<<5)
### Alarm Set Value Register
AL1SVL        =        (0x09)
AL2SVL        =        (0x19)
AL1SVH        =        (0x0A)
AL2SVH        =        (0x1A)
ALS_L         =        (0xFF<<0)
ALS_H         =        (0x03<<0)
### Alarm Clear Value Register
AL1CVL        =        (0x0B)
AL2CVL        =        (0x1B)
AL1CVH        =        (0x0C)
AL2CVH        =        (0x1C)
ALC_L         =        (0xFF<<0)
ALC_H         =        (0x03<<0)
### Temperature Register
TCR           =        (0x10)
TEN           =        (0x01<<0)
TUS           =        (0x03<<1)
TUS_C         =        (0x00<<1)
TUS_F         =        (0x01<<1)
TUS_K         =        (0x01<<2)
TSNG_SHIFT    =        (3)
TSNG          =        (0x01<<TSNG_SHIFT)
TOS_SHIFT     =        (4)
TOS           =        (0x0F<<TOS_SHIFT)
TDRL          =        (0x11)
TDRH          =        (0x12)
TP_L          =        (0xFF<<0)
TP_H          =        (0xFF<<0)


"""
*****************************************************************
***                      Local Defines                        ***
***                        Public                             ***
*****************************************************************
"""
i2cBus   = 1
i2cAddr  = 0x42
i2cIndex = 0


"""
*****************************************************************
***                      Local Defines                        ***
***                         Private                           ***
*****************************************************************
"""
bus      = smbus.SMBus(i2cBus)


"""
*****************************************************************
***                    Private Functions                      ***
*****************************************************************
"""
def find(debug=False):
	device = []
	for dev_addr in range(0xFF):
		try:
			val = bus.read_byte_data(dev_addr, ADDR)
		except:
			continue
		if val == dev_addr:
			device.append(val)
			if debug:
				print("a2Spark device found at 0x%02x" % val)
	return device

def get_1byte(dev_addr, offset):
	val = bus.read_byte_data(dev_addr, offset)
	#print("[get_1bytes] %02x=%02x" % (offset,val))
	return val

def get_2bytes(dev_addr, lsb_offset):
	lsb_val = bus.read_byte_data(dev_addr, lsb_offset)
	msb_val = bus.read_byte_data(dev_addr, lsb_offset+1)
	val = (lsb_val & 0xFF) | ((msb_val << 8) & 0xFF00)
	#print("[get_2bytes] %02x-%02x=%02x (%d|%d)" % (lsb_offset,lsb_offset+1,val,msb_val,lsb_val))
	return val

def set_1byte(dev_addr, value, offset):
	value = int(value)
	bus.write_byte_data(dev_addr, offset, value)
	time.sleep(0.5)
	tmp = get_1byte(dev_addr, offset)
	if tmp != value:
		return -1
	return 0

def set_2bytes(dev_addr, value, lsb_offset):
	value = int(value)
	bus.write_byte_data(dev_addr, lsb_offset, value & 0xFF)
	bus.write_byte_data(dev_addr, lsb_offset+1, (value>>8) & 0xFF)
	time.sleep(0.5)
	tmp = get_2bytes(dev_addr, lsb_offset)
	if tmp != value:
		return -1
	return 0

def print_reg(dev_addr, nbreg=0x1F):
	bus.write_byte(dev_addr, 0)
	for x in range(0, nbreg):
		response = bus.read_byte(dev_addr)
		print("Reg 0x%02x: 0x%02x - 0b%s" % (x, response, bin(response)[2:].zfill(8)))


def get_1byte_byId(dev_addr, id, *offset):
	if id == 0:
		id += 1
	if id > len(offset):
		return -1
	return get_1byte(dev_addr, offset[id-1])

def set_1byte_byId(dev_addr, id, value, *offset):
	if id == 0:
		id += 1
	if id > len(offset):
		return -1
	return set_1byte(dev_addr, value, offset[id-1])

def get_2bytes_byId(dev_addr, id, *offset):
	if id == 0:
		id += 1
	if id > len(offset):
		return -1
	return get_2bytes(dev_addr, offset[id-1])

def set_2bytes_byId(dev_addr, id, value, *offset):
	if id == 0:
		id += 1
	if id > len(offset):
		return -1
	return set_2bytes(dev_addr, value, offset[id-1])

def set_bit(dev_addr, reg_val, bit_val, bit_mask):
	reg_val = int(reg_val)
	bit_val = int(bit_val)
	bit_mask = int(bit_mask)
	if bit_val & bit_mask == reg_val & bit_mask:
		# bits already set, no change
		return (reg_val, 0)
	else:
		# bits not set, update reg_val
		reg_val = (reg_val & ~bit_mask) | (bit_val & bit_mask)
		return (reg_val, 1)

"""
*****************************************************************
***                     Public Functions                      ***
*****************************************************************
"""
def getAddress(addr=i2cAddr):
	return get_1byte(addr, ADDR)

def getFirmware(addr=i2cAddr):
	return get_1byte(addr, FWVR)

def getAnalogConf(id, addr=i2cAddr):
	return get_1byte_byId(addr, id, AN1CR, AN2CR) & (ANEN | LPEN)

def setAnalogConf(id, value, addr=i2cAddr):
	return set_1byte_byId(addr, id, value & (ANEN | LPEN), AN1CR, AN2CR)

def getAnalogEn(id, addr=i2cAddr):
	en = getAnalogConf(id, addr) & ANEN
	if en:
		return True
	else:
		return False

def setAnalogEn(id, value, addr=i2cAddr):
	if value == True:
		val = ANEN
	else:
		val = ~ANEN
	(regVal, change) = set_bit(addr, getAnalogConf(id, addr), val, ANEN)
	if change == 1:
		return setAnalogConf(id, regVal, addr)
	return 0

def getLPEn(id, addr=i2cAddr):
	en = getAnalogConf(id, addr) & LPEN
	if en:
		return True
	else:
		return False

def setLPEn(id, value, addr=i2cAddr):
	if value == True:
		val = LPEN
	else:
		val = ~LPEN
	(regVal, change) = set_bit(addr, getAnalogConf(id, addr), val, LPEN)
	if change == 1:
		return setAnalogConf(id, regVal, addr)
	return 0

def getLPFilter(id, addr=i2cAddr):
	return get_1byte_byId(addr, id, LPF1R, LPF2R) & LP

def setLPFilter(id, value, addr=i2cAddr):
	return set_1byte_byId(addr, id, value & LP, LPF1R, LPF2R)

def getAnalog(id, addr=i2cAddr):
	return get_2bytes_byId(addr, id, AN1DRL, AN2DRL) & (AN_L | (AN_H << 8))

def getAlarmConf(id, addr=i2cAddr):
	return get_1byte_byId(addr, id, AL1CR, AL2CR) & (ALEN | ALO | ALME | ALM)

def setAlarmConf(id, value, addr=i2cAddr):
	return set_1byte_byId(addr, id, value & (ALEN | ALO | ALME | ALM), AL1CR, AL2CR)

def getAlarmEn(id, addr=i2cAddr):
	en = getAlarmConf(id, addr) & ALEN
	if en:
		return True
	else:
		return False

def setAlarmEn(id, value, addr=i2cAddr):
	if value == True:
		val = ALEN
	else:
		val = ~ALEN
	(regVal, change) = set_bit(addr, getAlarmConf(id, addr), val, ALEN)
	if change == 1:
		return setAlarmConf(id, regVal, addr)
	return 0

def getAlarmOutput(id, addr=i2cAddr):
	out = getAlarmConf(id, addr) & ALO
	if out:
		return True
	else:
		return False

def getAlarmModeEn(id, addr=i2cAddr):
	en = getAlarmConf(id, addr) & ALME
	if en:
		return True
	else:
		return False

def setAlarmModeEn(id, value, addr=i2cAddr):
	if value == True:
		val = ALME
	else:
		val = ~ALME
	(regVal, change) = set_bit(addr, getAlarmConf(id, addr), val, ALME)
	if change == 1:
		return setAlarmConf(id, regVal, addr)
	return 0

def getAlarmMode(id, addr=i2cAddr):
	mode = getAlarmConf(id, addr) & ALM
	mode = (mode >> 5) & 0x07
	return mode

def setAlarmMode(id, value, addr=i2cAddr):
	val = (value << 5) & ALM
	(regVal, change) = set_bit(addr, getAlarmConf(id, addr), val, ALM)
	if change == 1:
		return setAlarmConf(id, regVal, addr)
	return 0

def getSetValue(id, addr=i2cAddr):
	return get_2bytes_byId(addr, id, AL1SVL, AL2SVL) & (ALS_L | (ALS_H << 8))

def setSetValue(id, value, addr=i2cAddr):
	return set_2bytes_byId(addr, id, value & (ALS_L | (ALS_H << 8)), AL1SVL, AL2SVL)

def getClearValue(id, addr=i2cAddr):
	return get_2bytes_byId(addr, id, AL1CVL, AL2CVL) & (ALC_L | (ALC_H << 8))

def setClearValue(id, value, addr=i2cAddr):
	return set_2bytes_byId(addr, id, value & (ALC_L | (ALC_H << 8)), AL1CVL, AL2CVL)

def getTempConf(addr=i2cAddr):
	return  get_1byte(addr, TCR) & (TEN | TUS | TSNG | TOS)

def setTempConf(value, addr=i2cAddr):
	return set_1byte(addr, value & (TEN | TUS | TSNG | TOS), TCR)

def getTempEn(addr=i2cAddr):
	en = getTempConf(addr) & TEN
	if en:
		return True
	else:
		return False

def setTempEn(value, addr=i2cAddr):
	if value == True:
		val = TEN
	else:
		val = ~TEN
	(regVal, change) = set_bit(addr, getTempConf(addr), val, TEN)
	if change == 1:
		return setTempConf(regVal, addr)
	return 0

def getTempUnit(addr=i2cAddr):
	unit = getTempConf(addr) & TUS
	if unit == TUS_C:
		return "C"
	elif unit == TUS_F:
		return "F"
	elif (unit & TUS_K) == TUS_K:
		return "K"
	else:
		return None

def setTempUnit(value, addr=i2cAddr):
	if value == "C" or value == "c":
		val = TUS_C
	elif value == "F" or value == "f":
		val = TUS_F
	elif value == "K" or value == "k":
		val = TUS_K
	else:
		val = TUS_C
	(regVal, change) = set_bit(addr, getTempConf(addr), val, TUS)
	if change == 1:
		return setTempConf(regVal, addr)
	return 0

def getTempOffSign(addr=i2cAddr):
	sign = getTempConf(addr) & TSNG
	if sign:
		return True
	else:
		return False

def setTempOffSign(value, addr=i2cAddr):
	if value == True:
		val = TSNG
	else:
		val = ~TSNG
	(regVal, change) = set_bit(addr, getTempConf(addr), val, TSNG)
	if change == 1:
		return setTempConf(regVal, addr)
	return 0

def getTempOff(addr=i2cAddr):
	offset = getTempConf(addr) & TOS
	offset = (offset >> TOS_SHIFT) & 0x0F
	return offset

def setTempOff(value, addr=i2cAddr):
	val = (value << TOS_SHIFT) & TOS
	(regVal, change) = set_bit(addr, getTempConf(addr), val, TOS)
	if change == 1:
		return setTempConf(regVal, addr)
	return 0

def getTemp(addr=i2cAddr):
	val = get_2bytes(addr, TDRL) & (TP_L | (TP_H << 8))
	if (val & 0x8000):
		val &= ~0x8000
		val *= -1
	else:
		val &= ~0x8000
	return val
