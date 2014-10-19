#!/usr/bin/env python3

import os, sys
import signal
import time
#import picamera
import subprocess
import shutil
import pickle
import random
try:
	import RPi.GPIO as GPIO
except RuntimeError:
	print("Error importing RPi.GPIO! \
	This is probably because you need superuser privileges.")
import log
import a2spark as a2

# capture period is in seconds
capturePeriod = 300
alarmSetValue = 700 # max value: 1023
alarmClrValue = 800 # max value: 1023
longitude = -75.7527
latitude = 45.4966

rootDir = "/root"
captureDir = "capture"
photoDir = "photo"
backupFile = "capture.bak"
sunsetBin = "./sunset"
LOG_ID = 1
# Debug jumper to prevent automatic power off
JUMPER_PIN = 24
JUMPER_DRIVE = -1

captureDir = rootDir + os.sep + captureDir
photoDir = rootDir + os.sep + photoDir
backupFile = rootDir + os.sep + backupFile
sunsetBin = rootDir + os.sep + sunsetBin

lightAlarm = [0 for i in range(10)]
lightIter = 0
ioError = 0
validDate = -1
photoSeed = -1
photoAcc = 0
runtimeLog = ""

def signalInt(signal_vec, frame):
	global photoDir
	global captureDir
	print("\ncapture process forced to stop!")
	moveCaptures(captureDir, photoDir)
	print("captures transfered...")
	sys.exit(0)
for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
	signal.signal(sig, signalInt)

def backup(elt):
	global backupFile
	with open(backupFile, "wb") as bkf:
		pklr = pickle.Pickler(bkf)
		pklr.dump(elt)

def restore():
	global backupFile
	elt = None
	try:
		with open(backupFile, "rb") as bkf:
			pklr = pickle.Unpickler(bkf)
			elt = pklr.load()
	except IOError:
		return None
	return elt

def checkdate():
	global photoSeed
	retval = -1
	acc = 0
	current_date = int(float(time.time()))
	previous_date = 0
	elt = restore()
	
	if elt == None:
		log.LogMsg("No backup file found.", LOG_ID, 0)
	else:
		acc = int(elt["acc"])
		previous_date = int(elt["time"])
		print("backup run #%d\nbackup time:%d\nbackup path:%s"%(acc, elt["time"], elt["path"]))
	if previous_date == 0:
		retval = 1
	elif previous_date < current_date:
		retval = 0
	
	elt = {}
	elt["acc"] = acc + 1
	elt["path"] = os.getcwd()
	if retval == -1:
		elt["time"] = previous_date
	else:
		elt["time"] = current_date
	backup(elt)
	photoSeed = elt["acc"]
	print("saved run #%d\nsaved time:%d\nsaved path:%s"%(elt["acc"], elt["time"], elt["path"]))
	return retval

def takeOne(folder):
	global validDate
	global photoSeed
	global photoAcc
	photoName = ""
	
	raspistill = "raspistill -t 2000 -rot 180 -e png -w 1440 -h 1080 -th none"
	if folder[-1] != '/':
		folder += "/"
	if validDate != -1:
		photoName = time.strftime("rasp_%Y-%m-%d_%H-%M-%S.png", time.localtime())
	else:
		if photoSeed == -1:
			photoSeed = random.randrange(1001)
		photoName = "rasp_%04d_%03d.png" % (photoSeed, photoAcc)
		photoAcc += 1
	
	command = raspistill + " -o " + folder + photoName
	try:
		#command = "touch " + folder + photoName
		retCall = subprocess.call([command], shell=True, universal_newlines=True)
		#with picamera.PiCamera() as camera:
		#	camera.resolution = (2592, 1944)
		#	camera.rotation = 180
		#	camera.start_preview()
		#	# Camera warm-up time
		#	time.sleep(5)
		#	camera.capture(captureDir + photoName)
		#	camera.stop_preview()
	except:
		retCall = -1
		log.LogMsg("%s Command:%s failed" % (command), LOG_ID, 1)
	return (retCall, photoName)

def findI2cDev():
	try:
		i2cAddr = a2.find()
	except:
		return -1
	if len(i2cAddr) >= 1:
		return i2cAddr[0]
	else:
		return -1

def initAlarm(id, i2cAddr):
	global lightAlarm
	global lightIter
	global alarmSetValue
	global alarmClrValue
	lightAlarm = [0 for i in range(10)]
	lightIter = 0
	# disable alarm to set config registers
	while a2.setAlarmEn(id, False, i2cAddr) != 0:
		time.sleep(1)
	# set the alarm configuration
	while a2.setAlarmMode(id, 0x5, i2cAddr) != 0:
		time.sleep(1)
	while a2.setAlarmModeEn(id, True, i2cAddr) != 0:
		time.sleep(1)
	while a2.setSetValue(id, alarmSetValue, i2cAddr) != 0:
		time.sleep(1)
	while a2.setClearValue(id, alarmClrValue, i2cAddr) != 0:
		time.sleep(1)
	# enable alarm
	while a2.setAlarmEn(id, True, i2cAddr) != 0:
		time.sleep(1)

def getAlarm(id, i2cAddr):
	global lightAlarm
	global lightIter
	global ioError
	# store the alarm status in the circular buffer
	try:
		lightAlarm[lightIter] = int(a2.getAlarmOutput(id, i2cAddr))
		msg = "Alarm="+str(lightAlarm[lightIter])+" | "+str(int(a2.getAnalog(id, i2cAddr)))
		log.LogMsg(msg,LOG_ID,0)
		lightIter += 1
	except IOError:
		ioError += 1
		log.LogMsg("getAlarmOutput failed (x%d)"%ioError, LOG_ID, 1)
		print("getAlarmOutput failed (x%d)"%ioError)
	# reset the circular alarm iterator if needed
	if lightIter >= len(lightAlarm):
		lightIter = 0
	# too many Io Error
	if ioError > 10:
		return -1
	# check if capture must stop
	if sum(lightAlarm) >= len(lightAlarm):
		return 1
	return 0

def getSunsetTime():
	global sunsetBin
	global latitude
	global longitude
	current_time = int(float(time.time()))
	utcHour = current_time
	command = "%s %f %f" % (sunsetBin, latitude, longitude)
	# execute the command and get the output
	try:
		output = subprocess.check_output([command], shell=True, universal_newlines=True)
	except:
		if not os.path.exists(sunsetBin):
			log.LogMsg("sunset binary (%s) is missing"%sunsetBin, LOG_ID, 1)
		else:
			log.LogMsg("%s binary failed"%sunsetBin, LOG_ID, 1)
		return -1
	# process if output is not empty
	if output:
		# suppress carriage return
		if output[-1] == '\n':
			output == output[:-1]
		try:
			utcHour = int(output)
		except ValueError:
			log.LogMsg("invalid value (%s) from %s"%(output,sunsetBin), LOG_ID, 1)
			return -1
	else:
		log.LogMsg("%s returns no output"%sunsetBin, LOG_ID, 1)
		return -1
	return utcHour

def moveCaptures(capture_dir, photo_dir):
	for root, dirs, files in os.walk(capture_dir):
		for file in files:
			file = os.path.join(root, file)
			shutil.move(file, photo_dir)

def logRuntime(folder, i2cAddr):
	global runtimeLog
	global photoSeed
	ret = 0
	first_init = False
	temperature = str(0xFFFF)
	battery_level = "-1"
	light_level = "-1"
	light_alarm = "-1"
	
	if folder[-1] != '/':
		folder += "/"
	
	if runtimeLog == "":
		first_init = True
		if validDate != -1:
			runtimeLog = time.strftime("rasp_%Y-%m-%d_%H-%M-%S.csv", time.localtime())
		else:
			if photoSeed == -1:
				photoSeed = random.randrange(1001)
			runtimeLog = "rasp_%04d_999.csv" % (photoSeed)
	
	timesp = str(int(time.time()))
	hour = time.strftime("%H:%M", time.localtime())
	if i2cAddr != -1:
		try:
			temperature = str(a2.getTemp(i2cAddr)) + str(a2.getTempUnit(i2cAddr))
			battery_level = str(a2.getAnalog(2, i2cAddr))
			light_level = str(a2.getAnalog(1, i2cAddr))
			light_alarm = str(a2.getAlarmOutput(1, i2cAddr))
		except IOError:
			log.LogMsg("IO error prevents runtime log to complete properly", LOG_ID, 1)
			ret = 1
	
	try:
		with open(folder+runtimeLog, "a") as logfile:
			if first_init:
				logfile.write("time,hour,temperature,voltage,light,alarm\n")
			logfile.write(("%s,%s,%s,%s,%s,%s\n") % (timesp, hour, temperature, battery_level, light_level, light_alarm))
	except:
		log.LogMsg("Runtime log access failed (%s)" % (runtimeLog), LOG_ID, 1)
		ret = -1
	return ret

def getJumper(gpio_pin, gpio_drive=-1):
	jumper = -1
	try:
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(gpio_pin, GPIO.IN)
		if gpio_drive > 0:
			GPIO.setup(gpio_drive, GPIO.OUT)
			GPIO.output(gpio_drive, GPIO.HIGH)
		jumper = GPIO.input(gpio_pin)
		GPIO.cleanup()
	except:
		return -1
	return int(jumper)

"""
*****************************************************************************
*****************************************************************************
* test if system date is valid
*	VALID DATE:
*		use date in photo filename
*	INVALID DATE:
* 		use accumulator value in capture.bak for photo filename
* find a valid a2Spark device
*	SUCCESS:
*		use the light alarm to stop the capture
*	ERROR:
*		retrieve the sunset time
*			SUCCESS:
*				use the sunset time to stop capture
*			ERROR or INVALID DATE:
*				capture for 8h with no further checks (light or special time)
* i2c device failed 10 times, retrieve the sunset time
*	SUCCESS:
*		use the sunset time to stop capture
*	ERROR or INVALID DATE:
*		capture for 8h with no further checks (light or special time)
*****************************************************************************
*****************************************************************************
"""
if __name__ == "__main__":
	stopCapture = False
	start_time = int(float(time.time()))
	latency_time = 0
	shoot_time = 0
	sunset_time = 0
	alarm = 0
	
	log.LogMsg("capture process started", LOG_ID, 0)
	validDate = checkdate()
	
	i2cAddr = findI2cDev()
	if i2cAddr != -1:
		initAlarm(1, i2cAddr)
		log.LogMsg("capture process initialized with i2c device", LOG_ID, 0)
	else:
		sunset_time = getSunsetTime()
		if validDate == -1 or sunset_time == -1:
			# if getSunsetTime failed, or date not valid
			# let capture for 8h
			log.LogMsg("get sunset time failed", LOG_ID, 0)
			sunset_time = start_time + 8*3600
		log.LogMsg("capture process initialized with sunset time (%d)"%sunset_time, LOG_ID, 0)
	
	print("all init passed")
	while not stopCapture:
		
		# get the current time
		current_time = int(float(time.time()))
		# check if next shoot time reached
		if current_time - shoot_time > capturePeriod:
			print("click clack")
			takeOne(captureDir)
			logRuntime(captureDir, i2cAddr)
			shoot_time = current_time
			latency_time = int(float(time.time())) - current_time
		
		# check if capture must stop
		if i2cAddr != -1:
			alarm = getAlarm(1, i2cAddr)
			if alarm == 1:
				log.LogMsg("light alarm triggered", LOG_ID, 0)
				stopCapture = True
			elif alarm == -1:
				i2cAddr = -1
				sunset_time = getSunsetTime()
				if validDate == -1 or sunset_time == -1:
					# if getSunsetTime failed,
					# let capture for 8h
					sunset_time = start_time + 8*3600
				log.LogMsg("capture process re-initialized with sunset time", LOG_ID, 0)
				print("capture process re-initialized with sunset time")
		elif current_time > sunset_time:
			log.LogMsg("sunset time triggered", LOG_ID, 0)
			stopCapture = True
		
		if latency_time >= capturePeriod:
			time.sleep(capturePeriod/4)
		else:
			time.sleep((capturePeriod-latency_time)/4)
	
	# move captured photos from capture dir to photo dir
	moveCaptures(captureDir, photoDir)
	
	log.LogMsg("capture process terminated", LOG_ID, 0)
	# shutdown the board
	if getJumper(JUMPER_PIN, JUMPER_DRIVE) == 0:
		os.system("shutdown -hP now")
	


