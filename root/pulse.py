#!/usr/bin/env python3

from time import sleep
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
# GPIO 25, ID 6, pin 22
GPIO.setup(25, GPIO.OUT)

GPIO.output(25, GPIO.HIGH)
sleep(0.5)
GPIO.output(25, GPIO.LOW)
sleep(0.1)

GPIO.cleanup()

