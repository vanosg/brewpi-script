# Copyright 2012 BrewPi/Elco Jacobs.
# This file is part of BrewPi.

# BrewPi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# BrewPi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with BrewPi.  If not, see <http://www.gnu.org/licenses/>.

import time
import csv

# read in profile and re-compute all offsets as seconds since start
# maintain current segment - start, end time and temp. If current time is end advance to next.

# the start time stored in the profile
profileStartTime = None
startTime = 0
endTime = 0
startTemp = 0
endTEmp = 0
tempReader = None
reachedEnd = False
tempRatio = 0


def flushProfile():
	global tempReader
	tempReader = None


def loadProfile(scriptPath):
	tr = csv.reader(
		open(scriptPath + 'settings/tempProfile.csv', 'rb'), delimiter=',', quoting=csv.QUOTE_ALL)
	tr.next()  # discard the first row, which is the table header
	global tempReader, startTime, endTime, startTemp, endTemp, reachedEnd
	#tempReader = [ item for item in tr ]
	tempReader = tr

	startTime = 0
	endTime = 0
	startTemp = 0
	endTemp = 0
	reachedEnd = False
	# fetch the initial setting for the period
	readNextProfileStep()
	startTemp = endTemp
	startTime = endTime


def readNextProfileStep():
	global tempReader, startTime, endTime, startTemp, endTemp, reachedEnd, tempRatio, profileStartTime

	try:
		row = tempReader.next()
		datestring = row[0]
		if datestring!="null":
			temperature = float(row[1])
			startTime = endTime
			startTemp = endTemp
			asTime = time.mktime(time.strptime(datestring, "%d/%m/%Y %H:%M:%S"))
			if (profileStartTime is None):
				profileStartTime = asTime

			endTemp = temperature
			endTime = asTime-profileStartTime

			if (endTime!=startTime):
				tempRatio = (endTemp - startTemp) / (endTime - startTime)
		else:
			reachedEnd = True
	except:
		reachedEnd = True


def getNewTemp(scriptPath, secondsSinceStart):
	global tempReader, startTime, endTime, startTemp, endTemp, reachedEnd, tempRatio, profileStartTime
	if tempReader is None:
		loadProfile(scriptPath)
	while (secondsSinceStart>=endTime and not reachedEnd):
		readNextProfileStep()
	if (reachedEnd):
		return endTemp

	interpolatedTemp = ((secondsSinceStart - startTime) * tempRatio) + startTemp
	return interpolatedTemp


def getNewTempOriginal(scriptPath):
	temperatureReader = csv.reader(
		open2(scriptPath + 'settings/tempProfile.csv', 'rb'),
									delimiter=',', quoting=csv.QUOTE_ALL)
	temperatureReader.next()  # discard the first row, which is the table header

	prevTemp = -1
	nextTemp = -1
	prevDate = -1
	nextDate = -1
	interpolatedTemp = -1

	now = time.mktime(time.localtime())  # get current time in seconds since epoch

	for row in temperatureReader:
		datestring = row[0]
		if(datestring != "null"):
			temperature = float(row[1])
			prevTemp = nextTemp
			nextTemp = temperature
			prevDate = nextDate
			nextDate = time.mktime(time.strptime(datestring, "%d/%m/%Y %H:%M:%S"))
			timeDiff = now - nextDate
			if(timeDiff < 0):
				if(prevDate == -1):
					interpolatedTemp = nextTemp  # first setpoint is in the future
					break
				else:
					interpolatedTemp = ((now - prevDate) / (nextDate - prevDate) *
										(nextTemp - prevTemp) + prevTemp)
					break

	if(interpolatedTemp == -1):  # all setpoints in the past
		interpolatedTemp = nextTemp
	return round(interpolatedTemp, 2)  # retun temp in tenths of degrees
