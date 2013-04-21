import unittest
from unittest import TestCase
import simulator
from simulator import Simulator

__author__ = 'mat'


class TestSimulator(TestCase):
	def test_hours(self):
		s = Simulator()
		s.time = 1800
		self.assertEqual(s.hours(), 0.5)

	def test_setMode_Heating(self):
		s = Simulator()
		s.setMode(simulator.HEATING)
		self.assertTrue(s.heating)
		self.assertFalse(s.cooling)

	def test_setMode_Cooling(self):
		s = Simulator()
		s.setMode(simulator.COOLING)
		self.assertTrue(s.cooling)
		self.assertFalse(s.heating)

	def test_setMode_Cooling(self):
		s = Simulator()
		s.setMode(simulator.IDLE)
		self.assertFalse(s.cooling)
		self.assertFalse(s.heating)

	def test_beerFerment_within_first_day_ramps_to_max(self):
		self.assertBeerFerment(0.0, 0.0)
		self.assertBeerFerment(0.5, 50)
		self.assertBeerFerment(1.0, 100)

	def assertBeerFerment(self, day, expected):
		s = Simulator()
		s.fermentPowerMax = 100
		s.time = day*24*60*60
		actual = s.beerFerment()
		self.assertEqual(actual, expected)

	def test_energy_single_temp(self):
		s = Simulator()
		actual = s.energy(10.5, 0.00035)
		expected = 10.5 * 0.00035
		self.assertEqual(actual, expected)

	def test_avgtemp_single(self):
		self.assertEqual(20.5, Simulator().avgtemp(20.5))

	def test_avgtemp_single(self):
		self.assertEqual(22.5, Simulator().avgtemp((20,25)))

	def test_mean(self):
		self.assertEqual(22.5, Simulator().mean(20,25))


	def testQuantizeUp(self):
		self.assertEquals(10.5, simulator.quantize(10.4, 0.5))

	def testQuantizeDown(self):
		self.assertEquals(10.5, simulator.quantize(10.6, 0.5))

	def testQuantizeUp(self):
		self.assertEquals(10.0, simulator.quantize(10.1, 0.5))

	def testQuantizeDown(self):
		self.assertEquals(10.0, simulator.quantize(9.8, 0.5))

	def simulatorStepIncreasesTime(self):
		s = Simulator()
		s.step()
		s.step()
		self.assertEqual(s.time, 2)


"""
	def test_chamberBeerTransfer(self):
		self.fail()

	def test_chamberRoomTransfer(self):
		self.fail()

	def test_heatTransfer(self):
		self.fail()


	def test_tempCapacity(self):
		self.fail()


	def test_chamberHeating(self):
		self.fail()

	def test_chamberCooling(self):
		self.fail()

"""

if __name__ == '__main__':
     unittest.main()