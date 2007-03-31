from boodle.agent import *
import random

s1 = 'percussion/kickdrum-sharp.wav'
s2 = 'percussion/kickdrum-whap.wav'
#s2 = 'percussion/hihat-wide.wav'

nummeasures = 4
beatsper = 4
numbeats = nummeasures * beatsper
rate = 0.20

# swap instruments
# swap measures
# change a few notes

class DrumBar:
	numinsts = 2
	def __init__(self):
		pass
	def clone(self):
		bar = DrumBar()
		bar.seq = self.seq
		bar.insts = self.insts
		return bar
	def randomize(self):
		self.insts = [s1, s2]
		self.seq = []
		for ix in range(numbeats):
			self.seq.append(self.pick_note())
	def pick_note(self):
		if (random.uniform(0.0, 1.0) < 0.33):
			return None
		return self.pick_inst()
	def pick_inst(self):
		return random.randint(0, self.numinsts-1)

class Mutation:
	permanent_chance = 0.33
	duration = (2, 8)
	def apply(self, bar):
		raise Exception('Mutation has no apply method')

class SwapInstMutation(Mutation):
	def __init__(self, bar):
		self.offset = random.randint(1, bar.numinsts-1)
	def apply(self, bar):
		newbar = bar.clone()
		seq = []
		for note in bar.seq:
			if (note != None):
				note = (note+self.offset) % newbar.numinsts;
			seq.append(note)
		newbar.seq = seq
		return newbar

class SuppressInstMutation(Mutation):
	permanent_chance = 0.0
	duration = (2, 4)
	def __init__(self, bar):
		self.tokill = bar.pick_inst()
	def apply(self, bar):
		newbar = bar.clone()
		seq = []
		for note in bar.seq:
			if (note == self.tokill):
				note = None
			seq.append(note)
		newbar.seq = seq
		return newbar

class ChangeSomeMutation(Mutation):
	def __init__(self, bar):
		count = random.randint(1, 5)
		ls = {}
		for ix in range(count):
			pos = random.randint(0, numbeats-1)
			newval = bar.pick_note()
			ls[pos] = newval
		self.changes = ls
	def apply(self, bar):
		newbar = bar.clone()
		seq = []
		for ix in range(len(bar.seq)):
			newval = self.changes.get(ix, '')
			if (newval == ''):
				newval = bar.seq[ix]
			seq.append(newval)
		newbar.seq = seq
		return newbar

class RotateMeasuresMutation(Mutation):
	def __init__(self, bar):
		self.pos = random.randint(1, nummeasures-1) * beatsper
	def apply(self, bar):
		newbar = bar.clone()
		pos = self.pos
		seq = bar.seq[pos:] + bar.seq[:pos]
		newbar.seq = seq
		return newbar

class SwapMeasuresMutation(Mutation):
	def __init__(self, bar):
		perm = range(nummeasures)
		swap1 = random.randint(0, nummeasures-1)
		swap2 = random.randint(0, nummeasures-1)
		if (swap2 == swap1):
			swap2 = (swap1+1) % nummeasures
		perm[swap1] = swap2
		perm[swap2] = swap1
		self.perm = perm
	def apply(self, bar):
		newbar = bar.clone()
		seq = []
		for ix in range(nummeasures):
			pos = self.perm[ix]
			seq = seq + bar.seq[pos*beatsper : (pos+1)*beatsper]
		newbar.seq = seq
		return newbar

def create_mutation():
	ls = [ChangeSomeMutation, ChangeSomeMutation, SwapInstMutation, SuppressInstMutation, RotateMeasuresMutation, SwapMeasuresMutation]
	clas = random.choice(ls)
	return clas

class DrumTrack(Agent):
	name = 'mutating drum track'

	def __init__(self):
		Agent.__init__(self)
		self.bar = DrumBar()
		self.bar.randomize()
		self.mutations = []
		self.recompute()
		self.counter = 0
		self.nexttrip = 4

	def recompute(self):
		#print 'recomputing: ' + str(self.mutations)
		bar = self.bar
		for mut in self.mutations:
			bar = mut.apply(bar)
		self.final = bar
		#print self.final.seq

	def run(self):
		self.counter = self.counter + 1
		mustrecompute = 0

		for mut in self.mutations:
			if (self.counter >= mut.triptime):
				self.mutations.remove(mut)
				mustrecompute = 1
				break

		if (self.counter >= self.nexttrip):
			self.nexttrip = self.counter + 4
			mutclas = create_mutation()
			mut = mutclas(self.bar)
			if (random.uniform(0.0, 1.0) < mut.permanent_chance):
				self.bar = mut.apply(self.bar)
			else:
				(minlife, maxlife) = mut.duration
				lifespan = random.randint(minlife, maxlife)
				mut.triptime = self.counter + lifespan
				self.mutations.append(mut)
			mustrecompute = 1

		if (mustrecompute > 0):
			self.recompute()

		bar = self.final
		for ix in range(numbeats):
			val = bar.seq[ix]
			if (val != None and val >= 0 and val < len(bar.insts)):
				snd = bar.insts[val]
				self.sched_note(snd, 1, 1, ix*rate)
		self.resched(numbeats * rate)

class ClickTrack(Agent):
	name = 'steady click track'
	def run(self):
		for ix in range(numbeats):
			self.sched_note('percussion/hihat-thin.wav', 1, 1, ix*rate)
		self.resched(numbeats * rate)

class DrumsWithClicks(Agent):
	name = 'mutating drum track with added clicks'
	def run(self):
		chan = self.new_channel(0.25)
		self.sched_agent(ClickTrack(), 0, chan)
		self.sched_agent(DrumTrack())

class DualDrums(Agent):
	name = 'two mutating drum tracks, one on each side'
	def run(self):
		chan1 = self.new_channel_pan(stereo.fixed(-1))
		chan2 = self.new_channel_pan(stereo.fixed(1))
		self.sched_agent(DrumTrack(), 0, chan1)
		self.sched_agent(DrumTrack(), 0, chan2)
