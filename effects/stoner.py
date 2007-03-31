from boodle.agent import *
import random

# http://www.eblong.com/zarf/stonersound.html

NUM_ELS = 5
NUM_PHASES = 4
#### better sounds
sounds = [
	'voice/z-baa-proc.aiff',
	'voice/z-baa-proc.aiff',
	'voice/z-baa-proc.aiff',
	'voice/z-baa-proc.aiff'
]
pitchfrac = pow(2.0, 1.0/(256*12))

class Oscillator:
	osclist = []
	def __init__(self):
		Oscillator.osclist.append(self)
	def get(self, el):
		return 0
	def increment(self):
		pass

def increment_all():
	for osc in Oscillator.osclist:
		osc.increment()

class OscConstant(Oscillator):
	def __init__(self, val):
		Oscillator.__init__(self)
		self.constval = val
	def get(self, el):
		return self.constval

class OscBounce(Oscillator):
	def __init__(self, min, max, step):
		Oscillator.__init__(self)
		self.min = min
		self.max = max
		self.step = step
		# Pick a random initial value between min and max.
		if (step < 0):
			step = (-step)
		diff = (max-min) / step
		self.val = min + step * random.randint(0, diff-1)
	def get(self, el):
		return self.val
	def increment(self):
		self.val = self.val + self.step
		if (self.val < self.min and self.step < 0):
			self.step = -(self.step);
			self.val = self.min + (self.min - self.val);
		if (self.val > self.max and self.step > 0):
			self.step = -(self.step);
			self.val = self.max + (self.max - self.val);

class OscWrap(Oscillator):
	def __init__(self, min, max, step):
		Oscillator.__init__(self)
		self.min = min
		self.max = max
		self.step = step
		# Pick a random initial value between min and max.
		if (step < 0):
			step = (-step)
		diff = (max-min) / step
		self.val = min + step * random.randint(0, diff-1)
	def get(self, el):
		return self.val
	def increment(self):
		self.val = self.val + self.step
		if (self.val < self.min and self.step < 0):
			self.val = self.val + (self.max - self.min);
		if (self.val > self.max and self.step > 0):
			self.val = self.val - (self.max - self.min);

class OscVeloWrap(Oscillator):
	def __init__(self, min, max, ostep):
		Oscillator.__init__(self)
		self.min = min
		self.max = max
		self.ostep = ostep
		# Pick a random initial value between min and max.
		self.val = random.randint(min, max)
	def get(self, el):
		return self.val
	def increment(self):
		diff = (self.max - self.min)
		self.val = self.val + self.ostep.get(0)
		while (self.val < self.min):
			self.val = self.val + diff
		while (self.val > self.max):
			self.val = self.val - diff

class OscMultiplex(Oscillator):
	def __init__(self, sel, osc0, osc1, osc2, osc3):
		Oscillator.__init__(self)
		self.sel = sel
		self.oscs = [osc0, osc1, osc2, osc3]
	def get(self, el):
		sel = self.sel.get(el)
		val = self.oscs[sel % NUM_PHASES].get(el)
		return val

class OscLinear(Oscillator):
	def __init__(self, base, diff):
		Oscillator.__init__(self)
		self.base = base
		self.diff = diff
	def get(self, el):
		val = self.base.get(el) + el * self.diff.get(el)
		return val

class OscPhaser(Oscillator):
	def __init__(self, phaselen):
		Oscillator.__init__(self)
		self.phaselen = phaselen
		self.count = 0
		self.curphase = random.randint(0, NUM_PHASES-1)
	def get(self, el):
		return self.curphase
	def increment(self):
		self.count = self.count+1
		if (self.count >= self.phaselen):
			self.count = 0
			self.curphase = (self.curphase+1) % NUM_PHASES

class OscRandPhaser(Oscillator):
	def __init__(self, minphaselen, maxphaselen):
		Oscillator.__init__(self)
		self.minphaselen = minphaselen
		self.maxphaselen = maxphaselen
		self.count = 0
		self.curphaselen = random.randint(minphaselen, maxphaselen)
		self.curphase = random.randint(0, NUM_PHASES-1)
	def get(self, el):
		return self.curphase
	def increment(self):
		self.count = self.count+1
		if (self.count >= self.curphaselen):
			self.count = 0
			self.curphaselen = random.randint(self.minphaselen, self.maxphaselen)
			self.curphase = (self.curphase+1) % NUM_PHASES

class OscBuffer(Oscillator):
	def __init__(self, oval):
		Oscillator.__init__(self)
		self.oval = oval
		self.firstel = NUM_ELS - 1
		self.el = []
		for ix in range(NUM_ELS):
			self.el.append(oval.get(0))
	def get(self, el):
		return self.el[(self.firstel + el) % NUM_ELS]
	def increment(self):
		self.firstel = self.firstel - 1
		if (self.firstel < 0):
			self.firstel = self.firstel + NUM_ELS
		self.el[self.firstel] = self.oval.get(0)

class StonerSound(Agent):
	name = 'StonerSound'
	def __init__(self):
		Agent.__init__(self)
		self.pitcho = OscLinear(
			OscMultiplex(
				OscBuffer(OscRandPhaser(5, 15)), 
			OscBounce(0x3500, 0x4500, 0x80), 
			OscBounce(0x3000, 0x4000, 0x120), 
			OscBounce(0x3000, 0x5000, 0x50), 
			OscBounce(0x4000, 0x5000, 0xD0)),
			
			OscMultiplex(
				OscBuffer(OscRandPhaser(6, 20)), 
			OscBounce(-0x400, 0x400, 0x40), 
			OscBounce(-0x400, 0x400, 0x90), 
			OscBounce(-0x400, 0x400, 0x30), 
			OscBounce(-0x400, 0x400, 0x80))
		)

		self.volo = OscConstant(127)

		self.noteleno = OscMultiplex(
			OscRandPhaser(15, 25), 
			OscBounce(60, 150, 3), 
			OscBounce(42, 86, -4), 
			OscBounce(90, 130, -3), 
			OscBounce(70, 160, 4))

		self.parto = OscBuffer(OscRandPhaser(20, 35))

		self.pano = OscBounce(-0x5f, 0x5f, 0x18)

	def run(self):
		time = 0.0
		for el in range(NUM_ELS):
			pitch = self.pitcho.get(el)
			vol = self.volo.get(el) / 127.0
			inst = self.parto.get(el)
			pan = self.pano.get(el) / 127.0
			notelen = self.noteleno.get(el) / 600.0

			pitch = pow(pitchfrac, pitch-0x3c00)
			self.sched_note_pan(sounds[inst], pan, pitch, vol, time)
			time = time + notelen
		increment_all()
		self.resched(time)
