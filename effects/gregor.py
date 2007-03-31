from boodle.agent import *
from boodle import music
import random

snd = 'voice/z-baa-proc.aiff'

nummeasures = 4
beatsper = 4
numbeats = nummeasures * beatsper
rate = 0.4

arr = [ 0, 0, -5, 0,  3, 2, 0, 0,  -2, -2, -2, 2,  0, 0, 0, 0 ]
#arr = [ 0, 2, 3, 3,  2, 0, -1, -1,  0, 2, -5, -5,  -3, -1, 0, 0 ]
#arr = [ -2, -3, -5, -5,  -7, -9, -10, -10,  -9, -7, -5, -7,  -9, -10, -12, -12 ]
#arr = [ 10, 9, 7, 7,  5, 3, 2, 2,  3, 5, 7, 5,  3, 2, 0, 0 ]

#arr = [ 
#  0, 2, 3, 3,  2, 0, -1, -1,  0, 2, -5, -5,  -3, -1, 0, 0,
#  10, 9, 7, 7,  5, 3, 2, 2,  3, 5, 7, 5,  3, 2, 0, 0
#]

#arr = [ 
#  0, 2, 3, 3,  2, 0, -1, -1,  0, 2, -5, -5,  -3, -1, 0, 0,
#  -2, -3, -5, -5,  -7, -9, -10, -10,  -9, -7, -5, -7,  -9, -10, -12, -12
#]

def choose_sublist(ls, num):
	ls = list(ls)
	if (len(ls) <= num):
		return ls
	res = []
	for ix in range(num):
		el = random.choice(ls)
		ls.remove(el)
		res.append(el)
	return res

class GregorBar:
	basechord = [0, 3, 7, -5, 12]
	def __init__(self):
		pass
	def clone(self):
		bar = GregorBar()
		bar.notes = self.notes
		bar.chords = self.chords
		return bar
	def randomize(self):
		self.notes = arr
		self.chords = []
		ix = 0
		while (ix < numbeats):
			chordlen = random.randint(2, 3)
			chord = choose_sublist(self.basechord, chordlen)
			dur = random.randint(1, 6)
			jx = ix
			while (jx < numbeats and jx < ix+dur):
				self.chords.append(chord)
				jx = jx+1
			ix = jx

class Mutation:
	permanent_chance = 0.33
	duration = (2, 8)
	def apply(self, bar):
		raise Exception('Mutation has no apply method')

class RewriteChordsMutation(Mutation):
	duration = (2, 4)
	def __init__(self, bar):
		self.chords = []
		ix = 0
		while (ix < numbeats):
			chordlen = random.randint(2, 3)
			chord = choose_sublist(bar.basechord, chordlen)
			dur = random.randint(1, 6)
			jx = ix
			while (jx < numbeats and jx < ix+dur):
				self.chords.append(chord)
				jx = jx+1
			ix = jx
	def apply(self, bar):
		newbar = bar.clone()
		newbar.chords = self.chords
		return newbar

class SplatChordMutation(Mutation):
	def __init__(self, bar):
		chordlen = random.randint(2, 3)
		self.chord = choose_sublist(bar.basechord, chordlen)
		self.pos = random.randint(0, numbeats-1)
		self.dur = random.randint(2, 8)
	def apply(self, bar):
		newbar = bar.clone()
		newbar.chords = list(bar.chords)
		for ix in range(self.pos, self.pos+self.dur):
			jx = ix % numbeats
			newbar.chords[jx] = self.chord
		return newbar

class SplatRandChordsMutation(Mutation):
	def __init__(self, bar):
		self.pos = random.randint(0, numbeats-1)
		self.dur = random.randint(2, 6)
		self.chords = []
		for ix in range(self.dur):
			chordlen = random.randint(2, 3)
			self.chords.append(choose_sublist(bar.basechord, chordlen))
	def apply(self, bar):
		newbar = bar.clone()
		newbar.chords = list(bar.chords)
		for ix in range(self.dur):
			jx = (self.pos+ix) % numbeats
			newbar.chords[jx] = self.chords[ix]
		return newbar

class AllRandChordsMutation(Mutation):
	permanent_chance = 0.0
	duration = (2, 4)
	def __init__(self, bar):
		self.chords = []
		for ix in range(numbeats):
			chordlen = random.randint(2, 3)
			self.chords.append(choose_sublist(bar.basechord, chordlen))
	def apply(self, bar):
		newbar = bar.clone()
		newbar.chords = list(self.chords)
		return newbar

class AllChordsMutation(Mutation):
	permanent_chance = 0.0
	duration = (2, 4)
	def __init__(self, bar):
		chordlen = random.randint(1, 4)
		self.chord = choose_sublist(bar.basechord, chordlen)
	def apply(self, bar):
		newbar = bar.clone()
		newbar.chords = [self.chord] * numbeats
		return newbar

def create_mutation():
	ls = [RewriteChordsMutation, SplatChordMutation, SplatChordMutation, SplatRandChordsMutation, AllRandChordsMutation, AllChordsMutation]
	clas = random.choice(ls)
	return clas

class Chant(Agent):
	name = 'mutating chant'

	def __init__(self):
		Agent.__init__(self)
		self.bar = GregorBar()
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
		#print self.final.chords

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

		fn = (lambda semi, chord: map((lambda val1, val2=semi: val1+val2), chord))
		notearr = map(fn, self.final.notes, self.final.chords)
		for ix in range(numbeats):
			while (len(notearr[ix]) > 0):
				val = notearr[ix][0]
				jx = ix
				while (jx < numbeats and (val in notearr[jx])):
					notearr[jx].remove(val)
					jx = jx+1
				pos = ix * rate
				dur = (jx-ix) * rate
				self.sched_note_duration(snd, dur, music.get_pitch(val), 0.6, pos)
		self.resched(numbeats * rate)

class ChantWithDrums(Agent):
	name = 'mutating chant and drum track'
	def run(self):
		self.sched_agent(Chant())
		clas = load_class_by_name('drumbeat.DrumTrack')
		self.sched_agent(clas())

