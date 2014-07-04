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

import subprocess as sub
import serial
import time
import simplejson as json
import os
import brewpiVersion
import expandLogMessage
import settingRestore
from sys import stderr
import BrewPiUtil as util


def printStdErr(string):
    print >> stderr, string + '\n'


def fetchBoardSettings(boardsFile, boardType):
    boardSettings = {}
    for line in boardsFile:
        if line.startswith(boardType):
            setting = line.replace(boardType + '.', '', 1).strip()  # strip board name, period and \n
            [key, sign, val] = setting.rpartition('=')
            boardSettings[key] = val
    return boardSettings


def loadBoardsFile(arduinohome):
    return open(arduinohome + 'hardware/arduino/boards.txt', 'rb').readlines()


def openSerial(port, altport, baud, timeoutVal):
    # open serial port
    try:
        ser = serial.Serial(port, baud, timeout=timeoutVal)
        return [ser, port]
    except serial.SerialException as e:
        printStdErr("Error opening serial port: %s. Trying alternative serial port %s." % (str(e), altport))
        try:
            ser = serial.Serial(altport, baud, timeout=timeoutVal)
            return [ser, altport]
        except serial.SerialException as e:
            printStdErr("Error opening alternative serial port: %s. Script will exit." % str(e))
            return [None, None]


def programArduino(config, boardType, hexFile, restoreWhat):
    printStdErr("****    Arduino Program script started    ****")

    ### Check custom-paths for validity, if they fail, try default path, then error. 
    sdkPath = False
    avrToolsPath = False
    avrConfigPath = False

    if "arduinoHome" not in config.defaults:
        if os.path.isdir(config['arduinoHome']):
            sdkPath = True
            arduinohome = config['arduinoHome']
    if not sdkPath:
        if os.path.isdir(config.default_values['arduinoHome']:
            sdkPath = True
            arduinohome = config.restore_default('arduinoHome')
            printStdErr("arduinoHome: Correct path missing/not set in config, using default SDK path instead")
    if not sdkPath:
        printStdErr("Unable to find the Arduino SDK. Please set arduinoHome in your config file and try again")
        sys.exit()
            
    if "avrdudeHome" not in config.defaults:
        if os.path.isdir(config['avrdudeHome']):
            avrToolsPath = True
            avrdudehome = config['avrdudeHome']
    if not avrToolsPath:
        if os.path.isdir(arduinohome + config.default_values['avrdudeHome']:
            avrToolsPath = True
            avrdudehome = arduinohome + config.restore_default('avrdudeHome')
            printStdErr("avrdudeHome: Correct path missing/not set in config, using default tools path instead")
    if not avrToolsPath:
        printStdErr("Unable to find the avr tools. Please set avrdudeHome in your config file and try again")
        sys.exit()

    if "avrConf" not in config.defaults:
        if os.path.isdir(config['avrConf']):
            avrConfigPath = True
            avrconf = config['avrConf']
    if not avrConfigPath:
        if os.path.isdir(config.default_values['avrConf']:
            avrConfigPath = True
            avrconfpath = avrdudehome + config.restore_default('avrConf')
            printStdErr("avrConf: Correct path missing/not set in config, using default config path instead")
    if not avrConfigPath:
        printStdErr("Unable to find the avr config file. Please set avrConf in your config file and try again")
        sys.exit()

    avrsizehome = config['avrsizeHome']
        
    restoreSettings = False
    restoreDevices = False
    if 'settings' in restoreWhat:
        if restoreWhat['settings']:
            restoreSettings = True
    if 'devices' in restoreWhat:
        if restoreWhat['devices']:
            restoreDevices = True
    # Even when restoreSettings and restoreDevices are set to True here,
    # they might be set to false due to version incompatibility later

    printStdErr("Settings will " + ("" if restoreSettings else "not ") + "be restored" +
                (" if possible" if restoreSettings else ""))
    printStdErr("Devices will " + ("" if restoreDevices else "not ") + "be restored" +
                (" if possible" if restoreSettings else ""))

    ser, port = openSerial(config['port'], config['altport'], 57600, 0.2)
    if ser is None:
        printStdErr("Could not open serial port. Programming aborted.")
        return 0

    time.sleep(5)  # give the arduino some time to reboot in case of an Arduino UNO

    printStdErr("Checking old version before programming.")

    avrVersionOld = brewpiVersion.getVersionFromSerial(ser)
    if avrVersionOld is None:
        printStdErr(("Warning: Cannot receive version number from Arduino. " +
                     "Your Arduino is either not programmed yet or running a very old version of BrewPi. "
                     "Arduino will be reset to defaults."))
    else:
        printStdErr("Found " + avrVersionOld.toExtendedString() + \
                    " on port " + port + "\n")

    oldSettings = {}


    # request all settings from board before programming
    if avrVersionOld is not None:
        printStdErr("Requesting old settings from Arduino...")
        if avrVersionOld.minor > 1:  # older versions did not have a device manager
            ser.write("d{}")  # installed devices
            time.sleep(1)
        ser.write("c")  # control constants
        ser.write("s")  # control settings
        time.sleep(2)

        for line in ser:
            try:
                if line[0] == 'C':
                    oldSettings['controlConstants'] = json.loads(line[2:])
                elif line[0] == 'S':
                    oldSettings['controlSettings'] = json.loads(line[2:])
                elif line[0] == 'd':
                    oldSettings['installedDevices'] = json.loads(line[2:])

            except json.decoder.JSONDecodeError, e:
                printStdErr("JSON decode error: " + str(e))
                printStdErr("Line received was: " + line)

        oldSettingsFileName = 'oldAvrSettings-' + time.strftime("%b-%d-%Y-%H-%M-%S") + '.json'
        printStdErr("Saving old settings to file " + oldSettingsFileName)

        scriptDir = util.scriptPath()  # <-- absolute dir the script is in
        if not os.path.exists(scriptDir + '/settings/avr-backup/'):
            os.makedirs(scriptDir + '/settings/avr-backup/')

        oldSettingsFile = open(scriptDir + '/settings/avr-backup/' + oldSettingsFileName, 'wb')
        oldSettingsFile.write(json.dumps(oldSettings))

        oldSettingsFile.truncate()
        oldSettingsFile.close()

    printStdErr("Loading programming settings from board.txt")

    # parse the Arduino board file to get the right program settings
    for line in boardsFile:
        if line.startswith(boardType):
            # strip board name, period and \n
            setting = line.replace(boardType + '.', '', 1).strip()
            [key, sign, val] = setting.rpartition('=')
            boardSettings[key] = val

    printStdErr("Checking hex file size with avr-size...")

    # start programming the Arduino
    avrsizeCommand = avrsizehome + 'avr-size ' + "\"" + hexFile + "\""

    # check program size against maximum size
    p = sub.Popen(avrsizeCommand, stdout=sub.PIPE, stderr=sub.PIPE, shell=True)
    output, errors = p.communicate()
    if errors != "":
        printStdErr('avr-size error: ' + errors)
        return 0

    programSize = output.split()[7]
    printStdErr(('Program size: ' + programSize +
                 ' bytes out of max ' + boardSettings['upload.maximum_size']))

    # Another check just to be sure!
    if int(programSize) > int(boardSettings['upload.maximum_size']):
        printStdErr("ERROR: program size is bigger than maximum size for your Arduino " + boardType)
        return 0

    hexFileDir = os.path.dirname(hexFile)
    hexFileLocal = os.path.basename(hexFile)

    programCommand = (avrdudehome + 'avrdude' +
                      ' -F ' +  # override device signature check
                      ' -e ' +  # erase flash and eeprom before programming. This prevents issues with corrupted EEPROM
                      ' -p ' + boardSettings['build.mcu'] +
                      ' -c ' + boardSettings['upload.protocol'] +
                      ' -b ' + boardSettings['upload.speed'] +
                      ' -P ' + port +
                      ' -U ' + 'flash:w:' + "\"" + hexFileLocal + "\"" +
                      ' -C ' + avrconf)

    printStdErr("Programming Arduino with avrdude: " + programCommand)

    # open and close serial port at 1200 baud. This resets the Arduino Leonardo
    # the Arduino Uno resets every time the serial port is opened automatically
    ser.close()
    del ser  # Arduino won't reset when serial port is not completely removed
    if boardType == 'leonardo':
        ser, port = openSerial(config['port'], config['altport'], 1200, 0.2)
        if ser is None:
            printStdErr("Could not open serial port at 1200 baud to reset Arduino Leonardo")
            return 0

        ser.close()
        time.sleep(1)  # give the bootloader time to start up

    p = sub.Popen(programCommand, stdout=sub.PIPE, stderr=sub.PIPE, shell=True, cwd=hexFileDir)
    output, errors = p.communicate()

    # avrdude only uses stderr, append its output to the returnString
    printStdErr("result of invoking avrdude:\n" + errors)

    printStdErr("avrdude done!")

    printStdErr("Giving the Arduino a few seconds to power up...")
    countDown = 6
    while countDown > 0:
        time.sleep(1)
        countDown -= 1
        printStdErr("Back up in " + str(countDown) + "...")

    ser, port = openSerial(config['port'], config['altport'], 57600, 0.2)
    if ser is None:
        printStdErr("Error opening serial port after programming. Program script will exit. Settings are not restored.")
        return 0

    printStdErr("Now checking which settings and devices can be restored...")

    # read new version
    avrVersionNew = brewpiVersion.getVersionFromSerial(ser)
    if avrVersionNew is None:
        printStdErr(("Warning: Cannot receive version number from Arduino. " +
                     "Your Arduino is either not programmed yet or running a very old version of BrewPi. "
                     "Arduino will be reset to defaults."))
    else:
        printStdErr("Checking new version: Found " + avrVersionNew.toExtendedString() +
                    " on port " + port + "\n")

    printStdErr("Resetting EEPROM to default settings")
    ser.write('E')
    time.sleep(5)  # resetting EEPROM takes a while, wait 5 seconds
    while 1:  # read all lines on serial interface
        line = ser.readline()
        if line:  # line available?
            if line[0] == 'D':
                # debug message received
                try:
                    expandedMessage = expandLogMessage.expandLogMessage(line[2:])
                    printStdErr("Arduino debug message: " + expandedMessage)
                except Exception, e:  # catch all exceptions, because out of date file could cause errors
                    printStdErr("Error while expanding log message: " + str(e))
                    printStdErr("Arduino debug message was: " + line[2:])
        else:
            break

    if avrVersionNew is None:
        printStdErr(("Warning: Cannot receive version number from Arduino after programming. " +
                     "Something must have gone wrong. Restoring settings/devices settings failed.\n"))
        return 0
    if avrVersionOld is None:
        printStdErr("Could not receive version number from old board, " +
                    "No settings/devices are restored.")
        return 0

    if restoreSettings:
        printStdErr("Trying to restore compatible settings from " +
                    avrVersionOld.toString() + " to " + avrVersionNew.toString())
        settingsRestoreLookupDict = {}

        if avrVersionNew.toString() == avrVersionOld.toString():
            printStdErr("New version is equal to old version, restoring all settings")
            settingsRestoreLookupDict = "all"
        elif avrVersionNew.major == 0 and avrVersionNew.minor == 2:
            if avrVersionOld.major == 0:
                if avrVersionOld.minor == 0:
                    printStdErr("Could not receive version number from old board, " +
                                "resetting to defaults without restoring settings.")
                    restoreDevices = False
                    restoreSettings = False
                elif avrVersionOld.minor == 1:
                    # version 0.1.x, try to restore most of the settings
                    settingsRestoreLookupDict = settingRestore.keys_0_1_x_to_0_2_x
                    printStdErr("Settings can only be partially restored when going from 0.1.x to 0.2.x")
                    restoreDevices = False
                elif avrVersionOld.minor == 2:
                    # restore settings and devices
                    if avrVersionNew.revision == 0:
                        settingsRestoreLookupDict = settingRestore.keys_0_2_x_to_0_2_0
                    elif avrVersionNew.revision == 1:
                        settingsRestoreLookupDict = settingRestore.keys_0_2_x_to_0_2_1
                    elif avrVersionNew.revision == 2:
                        settingsRestoreLookupDict = settingRestore.keys_0_2_x_to_0_2_2
                    elif avrVersionNew.revision == 3:
                        settingsRestoreLookupDict = settingRestore.keys_0_2_x_to_0_2_3
                    elif avrVersionNew.revision == 4:
                        if avrVersionOld.revision >= 3:
                            settingsRestoreLookupDict = settingRestore.keys_0_2_3_to_0_2_4
                        else:
                            settingsRestoreLookupDict = settingRestore.keys_0_2_x_to_0_2_4


                    printStdErr("Will try to restore compatible settings")
        else:
            printStdErr("Sorry, settings can only be restored when updating to BrewPi 0.2.0 or higher")


        restoredSettings = {}
        ccOld = oldSettings['controlConstants']
        csOld = oldSettings['controlSettings']

        ccNew = {}
        csNew = {}
        tries = 0
        while ccNew == {} or csNew == {}:
            if ccNew == {}:
                ser.write('c')
                time.sleep(2)
            if csNew == {}:
                ser.write('s')
                time.sleep(2)
            for line in ser:
                try:
                    if line[0] == 'C':
                        ccNew = json.loads(line[2:])
                    elif line[0] == 'S':
                        csNew = json.loads(line[2:])
                    elif line[0] == 'D':
                        try:  # debug message received
                            expandedMessage = expandLogMessage.expandLogMessage(line[2:])
                            printStdErr(expandedMessage)
                        except Exception, e:  # catch all exceptions, because out of date file could cause errors
                            printStdErr("Error while expanding log message: " + str(e))
                            printStdErr("Arduino debug message: " + line[2:])
                except json.JSONDecodeError, e:
                        printStdErr("JSON decode error: " + str(e))
                        printStdErr("Line received was: " + line)
            else:
                tries += 1
                if tries > 5:
                    printStdErr("Could not receive all keys for settings to restore from Arduino")
                    break

        printStdErr("Trying to restore old control constants and settings")
        # find control constants to restore
        for key in ccNew.keys():  # for all new keys
            if settingsRestoreLookupDict == "all":
                restoredSettings[key] = ccOld[key]
            else:
                for alias in settingRestore.getAliases(settingsRestoreLookupDict, key):  # get valid aliases in old keys
                    if alias in ccOld.keys():  # if they are in the old settings
                        restoredSettings[key] = ccOld[alias]  # add the old setting to the restoredSettings

        # find control settings to restore
        for key in csNew.keys():  # for all new keys
            if settingsRestoreLookupDict == "all":
                restoredSettings[key] = csOld[key]
            else:
                for alias in settingRestore.getAliases(settingsRestoreLookupDict, key):  # get valid aliases in old keys
                    if alias in csOld.keys():  # if they are in the old settings
                        restoredSettings[key] = csOld[alias]  # add the old setting to the restoredSettings

        printStdErr("Restoring these settings: " + json.dumps(restoredSettings))

        for key in settingRestore.restoreOrder:
            if key in restoredSettings.keys():
                # send one by one or the arduino cannot keep up
                if restoredSettings[key] is not None:
                    command = "j{" + str(key) + ":" + str(restoredSettings[key]) + "}\n"
                    ser.write(command)
                    time.sleep(0.5)
                # read all replies
                while 1:
                    line = ser.readline()
                    if line:  # line available?
                        if line[0] == 'D':
                            try:  # debug message received
                                expandedMessage = expandLogMessage.expandLogMessage(line[2:])
                                printStdErr(expandedMessage)
                            except Exception, e:  # catch all exceptions, because out of date file could cause errors
                                printStdErr("Error while expanding log message: " + str(e))
                                printStdErr("Arduino debug message: " + line[2:])
                    else:
                        break

        printStdErr("restoring settings done!")
    else:
        printStdErr("No settings to restore!")

    if restoreDevices:
        printStdErr("Now trying to restore previously installed devices: " + str(oldSettings['installedDevices']))
        detectedDevices = None
        for device in oldSettings['installedDevices']:
            printStdErr("Restoring device: " + json.dumps(device))
            if "a" in device.keys(): # check for sensors configured as first on bus
                if(int(device['a'], 16) == 0 ):
                    printStdErr("OneWire sensor was configured to autodetect the first sensor on the bus, " +
                                "but this is no longer supported. " +
                                "We'll attempt to automatically find the address and add the sensor based on its address")
                    if detectedDevices is None:
                        ser.write("h{}")  # installed devices
                        time.sleep(1)
                        # get list of detected devices
                        for line in ser:
                            try:
                                if line[0] == 'h':
                                    detectedDevices = json.loads(line[2:])
                            except json.decoder.JSONDecodeError, e:
                                printStdErr("JSON decode error: " + str(e))
                                printStdErr("Line received was: " + line)
                    for detectedDevice in detectedDevices:
                        if device['p'] == detectedDevice['p']:
                            device['a'] = detectedDevice['a'] # get address from sensor that was first on bus

            ser.write("U" + json.dumps(device))

            time.sleep(3)  # give the Arduino time to respond

            # read log messages from arduino
            while 1:  # read all lines on serial interface
                line = ser.readline()
                if line:  # line available?
                    if line[0] == 'D':
                        try:  # debug message received
                            expandedMessage = expandLogMessage.expandLogMessage(line[2:])
                            printStdErr(expandedMessage)
                        except Exception, e:  # catch all exceptions, because out of date file could cause errors
                            printStdErr("Error while expanding log message: " + str(e))
                            printStdErr("Arduino debug message: " + line[2:])
                    elif line[0] == 'U':
                        printStdErr("Arduino reports: device updated to: " + line[2:])
                else:
                    break
        printStdErr("Restoring installed devices done!")
    else:
        printStdErr("No devices to restore!")

    printStdErr("****    Program script done!    ****")
    printStdErr("If you started the program script from the web interface, BrewPi will restart automatically")
    ser.close()
    return 1
