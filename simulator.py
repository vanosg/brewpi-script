'''
Simple simulation of a fridge with a single fermenting beer.
'''
import math

IDLE = 0
STARTUP = 1
STATE_OFF = 2
DOOR_OPEN = 3
HEATING = 4
COOLING = 5

VOL_HC_AIR = 0.00121        # J/cm^3/K
MASS_HC_AIR = 1.012         # J/g/K
MASS_HC_WATER = 4.18        # J/g/K

def quantize(value, quantity):
	return math.trunc((value+(quantity/2.0))/quantity)*quantity

class FermentPhases:
	def __init__(self, lagPhase=8, logPhase=12, activePhase=24, stationaryPhase=48):
		self.lagPhase = lagPhase                    # 0 heat output
		self.logPhase = logPhase                    # 0 -> max heat output, as more cells stop budding and start fermenting
		self.activePhase = activePhase              # hold at max - yeast fermenting at max rate
		self.stationaryPhase = stationaryPhase      # max -> 0  - prepare for stationary phase



class Simulator:


	"""Simulates a chamber with a quantity of liquid of given gravity"""
	def __init__(self):
		self.time = 0               # time since start of simulation in seconds
		self.fridgeVolume = 150     # liters
		self.beerDensity = 1.060    # SG
		self.beerTemp = 17.0          # C
		self.beerVolume = 20.0        # liters
		self.roomTemp = 20.0          # C
		self.fridgeTemp = self.roomTemp #
		self.heatPower = 25.0         # W
		self.coolPower = 60.0        # W
		self.quantizeTempOutput = 0.0625
		self.Ke = 1.67              # W / K - thermal conductivity compartment <> environment
		self.Kb = 15.0   # just a guess               # W / K  - thermal conductivity compartment <> beer
		self.sensorNoise = 0.0          # how many quantization units of noise is generated
		self.fridgeHeatCapacity = self.fridgeVolume * 1000 * VOL_HC_AIR                               # Heat capacity potential in J of the fridge per deg C.
		self.beerHeatCapacity = self.beerVolume * self.beerDensity * 1000 * MASS_HC_WATER             # Heat capacity potential in J of the beer per deg C.
		self.fermentPowerMax = 5    # todo - make fermentation time rather than power
									# W - max energy produced by fermentation
									# 8 W very aggressive
									#
		self.heating = False
		self.cooling = False
		self.doorOpen = False

	def hours(self):
		return self.time/3600.0

	''' the mode is the output from the temp control algorithm '''
	def setMode(self, mode):
		self.heating = mode==HEATING
		self.cooling = mode==COOLING


	def step(self):
		""" Make a step of one second """
		fermentDiff = self.beerFerment()

		heatingDiff = self.chamberHeating()
		coolingDiff = self.chamberCooling()
		doorDiff = self.doorLosses()

		newBeerTemp = self.beerTemp + fermentDiff
		newFridgeTemp = self.fridgeTemp + heatingDiff + coolingDiff + doorDiff

		fridgeBeerDiff, beerDiff = self.chamberBeerTransfer((self.fridgeTemp, newFridgeTemp), (self.beerTemp, newBeerTemp))
		fridgeRoomDiff, roomDiff = self.chamberRoomTransfer((self.fridgeTemp, newFridgeTemp+fridgeBeerDiff), (self.roomTemp,self.roomTemp))

		newFridgeTemp += fridgeBeerDiff + fridgeRoomDiff
		newBeerTemp += beerDiff

		self.fridgeTemp = newFridgeTemp
		self.beerTemp = newBeerTemp
		self.time += 1.0


	def chamberBeerTransfer(self, fridgeTemp, beerTemp):
		''' how much energy energy transfers between the beer and the chamber '''
		return self.heatTransfer((fridgeTemp, self.fridgeHeatCapacity),
							(beerTemp, self.beerHeatCapacity),
							self.Kb)

	def chamberRoomTransfer(self, fridgeTemp, roomTemp):
		''' transfers energy between the beer and the chamber '''
		return self.heatTransfer((fridgeTemp, self.fridgeHeatCapacity),
							(roomTemp, self.fridgeHeatCapacity),
							self.Ke)

	def heatTransfer(self, r1, r2, k):
		""" compute the heat transferred between two heat energy sources.
		   r1, r2  (temp, heatCapacity)
		   k - coefficient of heat transfer in W / K
		   returns the temperature change caused by the heat transfer
		"""
		t1, c1 = self.tempCapacity(r1)
		t2, c2 = self.tempCapacity(r2)
		e1 = (t2-t1)*k      # energy transferred
		e2 = -e1
		return (e1/c1, e2/c2)

	def energy(self, t, c):
		return t * c

	def tempCapacity(self, r):
		temp, capacity = r
		return self.avgtemp(temp), capacity

	def avgtemp(self, temp):
		return self.mean(temp[0], temp[1]) if type(temp) is tuple else temp

	def mean(self, v1, v2):
		return (v1+v2)/2.0

	def chamberHeating(self):
		return self.heatPower / self.fridgeHeatCapacity if self.heating else 0.0

	def chamberCooling(self):
		return -self.coolPower / self.fridgeHeatCapacity if self.cooling else 0.0

	def beerFerment(self):
		days = self.hours()/24.0
		scale = (     0                     if (days>5)
		         else (1.0-((days-3)/3))    if (days>2)
				 else 1.0                   if (days>1)
				 else days)
		power = self.fermentPowerMax
		return power / self.beerHeatCapacity

	def outputBeerTemp(self):
		return self.outputTemp(self.beerTemp)

	def outputFridgeTemp(self):
		return self.outputTemp(self.fridgeTemp)

	def outputTemp(self, temp):
		return quantize(temp, self.quantizeTempOutput)

	def doorLosses(self):
		return 0.0


'''
The simulation is based on energy potentials and energy transfer.

Consider energy potential as heat energy above absolute 0.

Running the cooler transfers power into the air chamber, raising the temperature of the air
The chamber continually loses engergy to the environment, at a rate proportional to the ambient temperature difference.

energy produced by fermentation. This raises the temperature of the beer. (Assume instantaneous and uniform.)
Temperature raise is computed from the energy by using the SHC.

Loop each time and add/subtract energy in/out


- energy transfer to chamber from environment  (Te-Tc*k) Ke =
  - Ke thermal conduction constant from fridge to environment
  - Ca. 40Wh per day / C, 144kJ / day / K = 1.67 W / K
  - also ties in with that light buib at 15W is just able to maintain 10 C above ambient
- energy transfer to chamber from cooler       Kc
  - assume 50% efficient  = 60 W
- energy transfer to chamber from heater        Kh  (15-100W)

- energy produced by fermentation - enough to maintain 5C above ambient, so 5 * Ke. Need to fit this to a curve related to time since start of ferment.
- For now, if t < 24h   t/24h * max.  if t>24h < 48h, t=max, t>=48h<24*5h,t=1-((48-t)/72)*max t>7.

- door opening: assume it takes a minute to replace all the eir with environment air. Work out energy transfer based on quantity of air.


'''

