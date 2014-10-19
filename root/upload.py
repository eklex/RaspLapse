#!/usr/bin/env python

import os, sys
import signal
import time
import subprocess
import shutil
import re
if sys.version_info.major > 2:
	import urllib.request
	import http.client
else:
	import urllib2
try:
	import RPi.GPIO as GPIO
except RuntimeError:
	print("Error importing RPi.GPIO! \
	This is probably because you need superuser privileges.")
import pickle

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

import log
#import logging
#logging.basicConfig(level=logging.DEBUG)

rootDir = "/root"
photoDir = "photo"
errorDir = "error"
remoteDir = "/RaspLapse/photo"
backupFile = "upload.bak"
gdriveFile = "/root/gdrive"
LOG_ID = 2
# Debug jumper to prevent automatic power off
JUMPER_PIN = 23
JUMPER_DRIVE = 22

drive = None
FOLDER_TYPE = "application/vnd.google-apps.folder"

photoDir = rootDir + os.sep + photoDir
errorDir = rootDir + os.sep + errorDir
backupFile = rootDir + os.sep + backupFile
gdriveFile = gdriveFile + os.sep  + "settings.yaml"

def signalInt(signal, frame):
	print("\nupload process forced to stop!")
	sys.exit(0)
for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
	signal.signal(sig, signalInt)

def backup(elt):
	global backupFile
	with open(backupFile, "wb") as bkf:
		if sys.version_info.major > 2:
			pklr = pickle.Pickler(bkf)
			pklr.dump(elt)
		else:
			pickle.dump(elt, bkf)

def restore():
	global backupFile
	elt = None
	try:
		with open(backupFile, "rb") as bkf:
			if sys.version_info.major > 2:
				pklr = pickle.Unpickler(bkf)
				elt = pklr.load()
			else:
				elt = pickle.load(bkf)
	except IOError:
		return None
	return elt

def checkdate():
	retval = -1
	acc = 0
	current_date = int(float(time.time()))
	previous_date = 0
	elt = restore()
	
	if elt != None:
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
	print("saved run #%d\nsaved time:%d\nsaved path:%s"%(elt["acc"], elt["time"], elt["path"]))
	return retval

def checkInternet(site="google"):
	url = "http://www.google.com"
	if site == "dropbox":
		url = "http://www.dropbox.com"
	elif site == "pushover":
		url = "https://api.pushover.net:443"
	else:
		url = "http://www.google.com"
	try:
		if sys.version_info.major > 2:
			urllib.request.urlopen(url)
		else:
			urllib2.urlopen(url)
		return 0
	except:
		return 1
	return -1

def driveUpload(filePath, dirId="root"):
	global drive
	ret = 0
	fileName = filePath.split(os.sep)[-1]
	print(fileName)
	try:
		file = drive.CreateFile({"parents":[{"kind":"drive#fileLink","id":dirId}]})
	except:
		print("[uploadFile] Drive access failed!")
		return -1
	file["title"] = fileName
	file.SetContentFile(filePath)
	try:
		file.Upload()
	except:
		ret = -2
	return ret

def driveCreateFolder(dirName, parentId="root"):
	global drive
	global FOLDER_TYPE
	print("############################################# CREATE: %s" % dirName)
	query = "'"+parentId+"' in parents and mimeType = '" + FOLDER_TYPE + "' and trashed=false"
	try:
		file_list = drive.ListFile({'q':query}).GetList()
	except:
		print("[createDriveFolder] Drive access failed!")
		return -1
	for dir in file_list:
		if dir["title"] == dirName:
			return dir["id"]
	
	dir = drive.CreateFile({"mimeType":FOLDER_TYPE, "parents": [{"kind" : "drive#fileLink","id": parentId}]})
	dir["title"] = dirName
	dir.Upload()
	file_list = drive.ListFile({"q":query}).GetList()
	for dir in file_list:
		if dir["title"] == dirName:
			return dir["id"]
	print("############################################# CREATION FAILED: %s" % dirName)
	return None

def driveFolder(path):
	global drive
	global FOLDER_TYPE
	dirList = []
	if path[0] != os.sep:
		print("Wrong path format: %s"%path)
		return None
	dirList.append({"id":"root","name":"root"})
	folderList = path.split(os.sep)
	# create list of directory
	for item in folderList:
		if item not in ("", " ", None):
			dirList.append({"id":"","name":item})
	# create folder if needed
	for iter, dir in enumerate(dirList):
		if dir["name"] != "root":
			try:
				QUERY = "mimeType = '" + FOLDER_TYPE + "' and '" + dirList[iter-1]["id"] + "' in parents\
				and trashed=false and title = '" + dir["name"] + "'"
			except IndexError:
				print("ID folder missing")
			# retrieve directory list in drive
			try:
				dir_list = drive.ListFile({"q": QUERY}).GetList()
			except Exception, ex:
				print("[createFolder] Drive access failed!")
				return None
			if len(dir_list) > 0:
				for folder in dir_list:
					print("title: %s, id: %s" % (folder["title"], folder["id"]))
					dir["id"] = folder['id']
			else:
				#print("Need to be created: %s"%dir["name"])
				dirId = driveCreateFolder(dir["name"], dirList[iter-1]["id"])
				if dirId != None:
					dir["id"] = dirId
				else:
					print("Creating folder %s failed"%dir["name"])
	return dirList

def deleteFile(filepath):
	if os.path.exists(filepath):
		try:
			os.remove(filepath)
			return 0
		except:
			log.LogMsg("delete %s failed" % (filepath), LOG_ID, 1)
	else:
		log.LogMsg("file %s does not exist" % (filepath), LOG_ID, 0)
		return 0
	return 1

def createFolder(destDir, remote=0):
	command = "mkdir " + str(destDir)
	if remote == 1:
		dir = driveFolder(destDir)
		if dir != None:
			return dir[-1]["id"]
		return -2
	else:
		if not os.path.exists(destDir):
			retCall = subprocess.call([command], shell=True)
			if retCall != 0:
				log.LogMsg("creating local folder %s failed" % (destDir), LOG_ID, 1)
				return retCall
			else:
				log.LogMsg("local folder created", LOG_ID, 0)
		return 0
	return -1

def uploadFile(baseDir, fileName, destDir):
	# extract the date or accumulator number in filename
	try:
		yyyy_mm_dd = re.search('rasp_(.+?)_', fileName).group(1)
	except AttributeError:
		print("splitting filename %s failed" % (fileName))
		return 1
	# filename has a valid date format
	if "-" in yyyy_mm_dd and len(yyyy_mm_dd) == 10:
		yyyy_mm_dd_split = yyyy_mm_dd.split("-")
		if len(yyyy_mm_dd_split) < 3:
			yyyy_mm = yyyy_mm_dd[0:7]
			dd = yyyy_mm_dd[8:10]
		else:
			yyyy_mm = yyyy_mm_dd_split[0] + "-" + yyyy_mm_dd_split[1]
			dd = yyyy_mm_dd_split[2]
	# filename has an invalid date
	else:
		yyyy_mm = "accumulator"
		dd = yyyy_mm_dd
	# build the path, then create the remote folder
	remoteDestDir = destDir + os.sep + yyyy_mm + os.sep + dd
	retDir = createFolder(remoteDestDir, 1)
	# retDir is the deepest folder ID, which is the parent folder of the file
	if retDir < 0:
		log.LogMsg("creating remote folder %s failed" % (remoteDestDir), LOG_ID, 1)
		return retDir
	# upload the file in google drive
	retCall = driveUpload(baseDir+os.sep+fileName, retDir)
	if retCall != 0:
		log.LogMsg("upload file %s failed" % (fileName), LOG_ID, 1)
	return retCall

def photoFile(baseDir, errorDir, fileName, destDir="files"):
	# remove the separator at the end the path if there
	if "/" in baseDir[-1] or "\\" in baseDir[-1]:
		baseDir = baseDir[-1]
	if "/" in errorDir[-1] or "\\" in errorDir[-1]:
		errorDir = errorDir[-1]
	if "/" in destDir[-1] or "\\" in destDir[-1]:
		destDir = destDir[-1]
	
	if checkInternet() == 0:
		retCall = uploadFile(baseDir, fileName, destDir)
		# upload file failed
		if retCall != 0:
			try:
				# move the file in error directory
				shutil.move(baseDir+os.sep+fileName, errorDir+os.sep+fileName)
				return retCall
			except:
				log.LogMsg("moving %s into %s failed" % (fileName, errorDir), LOG_ID, 1)
				return -1
		else:
			log.LogMsg("file %s updated" % (fileName), LOG_ID, 0)
			deleteFile(baseDir+os.sep+fileName)
			return 0
	else:
		log.LogMsg("connexion to Internet failed", LOG_ID, 1)
		return -2
	return -1

def errorFile(baseDir, fileName, destDir="files"):
	# remove the separator at the end the path if there
	if "/" in baseDir[-1] or "\\" in baseDir[-1]:
		baseDir = baseDir[-1]
	if "/" in destDir[-1] or "\\" in destDir[-1]:
		destDir = destDir[-1]
	
	if checkInternet() == 0:
		retCall = uploadFile(baseDir, fileName, destDir)
		# upload file failed
		if retCall == 0:
			log.LogMsg("file %s updated" % (fileName), LOG_ID, 0)
			deleteFile(baseDir+os.sep+fileName)
			return 0
		else:
			return retCall
	else:
		log.LogMsg("connexion to Internet failed", LOG_ID, 1)
		return 1
	return -1

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

if __name__ == "__main__":
	invalidUpload = 0
	retCall = -1
	
	log.LogMsg("upload process started", LOG_ID, 0)
	#time.sleep(3*60)
	
	while checkInternet() != 0:
		log.LogMsg("waiting Internet", LOG_ID, 1)
		time.sleep(20)
	log.LogMsg("Internet pass", LOG_ID, 0)
	#"""
	if checkdate() == -1:
		log.LogMsg("wrong system time", LOG_ID, 1)
		sys.exit(1)
	#"""
	
	# initialize Google Drive instance
	gauth = GoogleAuth(gdriveFile)
	drive = GoogleDrive(gauth)
	
	
	retCall = createFolder(photoDir)
	if retCall != 0:
		log.LogMsg("fail to create photo local folder %d" % retCall, LOG_ID, 1)
		sys.exit(retCall)
	log.LogMsg("createFolder photoDir pass", LOG_ID, 0)
	retCall = createFolder(errorDir)
	if retCall != 0:
		log.LogMsg("fail to create error local folder %d" % retCall, LOG_ID, 1)
		sys.exit(retCall)
	log.LogMsg("createFolder errorDir pass", LOG_ID, 0)
	retCall = createFolder(remoteDir, 1)
	if retCall < 0:
		log.LogMsg("fail to create remote folder %d" % retCall, LOG_ID, 1)
		sys.exit(retCall)
	log.LogMsg("createFolder remoteDir pass", LOG_ID, 0)
	# retrieve photo files
	fileList = []
	for (dirPath, dirName, fileName) in os.walk(photoDir):
		fileList.extend(fileName)
		break
	# photo file list is not empty
	if fileList:
		for item in fileList:
			print(item)
			retCall = photoFile(photoDir, errorDir, item, remoteDir)
			if retCall != 0:
				invalidUpload += 1
	# no upload error detected,
	# then error folder can be process
	if invalidUpload <= 0:
		# retrieve error files
		fileList = []
		for (dirPath, dirName, fileName) in os.walk(errorDir):
			fileList.extend(fileName)
			break
		# error file list is not empty
		if fileList:
			log.LogMsg("errors=%s" % (fileList), LOG_ID, 0)
			for item in fileList:
				print(item)
				retCall = errorFile(errorDir, item, remoteDir)
				if retCall != 0:
					break
	
	log.LogMsg("upload process terminated", LOG_ID, 0)
	if getJumper(JUMPER_PIN, JUMPER_DRIVE) == 0:
		command = rootDir + os.sep + "./off.usb"
		retCall = subprocess.check_output([command], shell=True, universal_newlines=True)
	else:
		retCall = 0
	sys.exit(retCall)
	