#!/usr/bin/env python3

import os
import time
import os.path

DEBUG = 0

def SendAlert(msg, priority=0):
	if priority == 0:
		title = "Warning"
	else:
		priority = 1
		title = "Alert"
	Pushover(title, msg, priority)

def ReportError(errMsg, errPriority=0):
	ts = time.strftime("(%Y%m%d %H%M%S)", time.localtime())
	print("%s %s" % (ts, errMsg))
	if errPriority == 1:
		SendAlert(errMsg, 0)
	elif errPriority > 1:
		SendAlert(errMsg, 1)

def LogMsg(msg, id, errFlag=0, errPriority=0):
	# init local variable
	yearMonth  = time.strftime("%Y%m", time.localtime())
	lineHead = time.strftime("(%Y%m%d %H%M%S) ", time.localtime())
	# format the message
	msg = lineHead + msg
	if msg[-1] != '\n':
		msg += "\n"
	
	# select the error category
	if errFlag == 1:
		# error
		fileLog = ("/root/log/error%02d-%s.log" % (id, yearMonth))
	else:
		# warning
		fileLog = ("/root/log/warning%02d-%s.log" % (id, yearMonth))
	
	# check if the file exists
	if os.path.exists(fileLog) and os.path.isfile(fileLog):
		fileOpt = "a"
	else:
		fileOpt = "w"
	
	with open(fileLog, fileOpt) as fileDsc:
		fileDsc.write(msg)
	if(DEBUG):
		print(msg)
	

