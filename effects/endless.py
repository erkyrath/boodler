from boodle.agent import *
from boodle import music
import random

class Rising(Agent):
	name = 'endlessly rising chord'
	def __init__(self, octaves=3, notes=None, samp=None, rate=0.4):
		Agent.__init__(self)
		self.octaves = int(octaves)
		if (notes == None):
			self.notes = self.octaves
		else:
			self.notes = int(notes)
		self.rate = float(rate)
		if (samp == None):
			samp = 'voice/z-baa-proc.aiff'
		self.samp = samp
	def picknote(self, ix):
		return ix - 6*self.octaves
	def run(self):
		snd = self.samp
		octaves = self.octaves
		rate = self.rate
		orange = 12*octaves
		halforange = 6*octaves
		for ix in range(orange):
			val = self.picknote(ix)
			if (ix <= halforange):
				vol = ((ix+1) / float(halforange+1))
			else:
				vol = ((orange+0.5 - ix) / float(halforange+1))
			vol = vol * 0.8
			self.sched_note_duration(snd, rate, music.get_pitch(val), vol, ix*rate)
		delay = orange / self.notes
		self.resched(delay * rate)

class Falling(Rising):
	name = 'endlessly falling chord'
	def picknote(self, ix):
		return -ix + 6*self.octaves

