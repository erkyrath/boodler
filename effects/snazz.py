from boodle.agent import *
import random

sounds = [
	('percussion/wood-tap-hollow.aiff', 0.33, 1.7, 1.0),
	('environ/droplet-plink-reverb-2.aiff', 0.3, 1.7, 0.75),
	('percussion/drum-echoey.aiff', 0.66, 2.0, 1.0)
]

rate = 2.75
dumpgraph = 0

class Node:
	def __init__(self, isnull=0):
		self.children = []
		self.parent = None
		self.sibnum = None
		self.counter = 0
		self.isnull = isnull
		if (not isnull):
			(snd, minpitch, maxpitch, vol) = random.choice(sounds)
			self.snd = snd
			self.pitch = random.uniform(minpitch, maxpitch)
			self.pan = random.uniform(-0.75, 0.75)
			self.vol = vol
	def append(self, nod):
		self.children.append(nod)
		nod.parent = self
		nod.sibnum = len(self.children) - 1
	def replace(self, ix, nod):
		oldnod = self.children[ix]
		oldnod.parent = None
		oldnod.sibnum = None
		self.children[ix] = nod
		nod.parent = self
		nod.sibnum = ix
	def delete(self, ix):
		oldnod = self.children[ix]
		oldnod.parent = None
		oldnod.sibnum = None
		del self.children[ix]
		while (ix < len(self.children)):
			subnod = self.children[ix]
			subnod.sibnum = ix
			ix = ix + 1
	def getdepth(self):
		count = 0
		nod = self.parent
		while (nod != None):
			count = count+1
			nod = nod.parent
		return count
	def interest(self, metric=None):
		if (metric==None):
			metric = [1, 0, 0]
		count = len(self.children)
		if (count == 0 or count == 1):
			lev = 0
		elif (count == 2 or count == 4):
			lev = 1
		else:
			lev = 2
		allnull = 1
		for nod in self.children:
			nod.interest(metric)
			if (not nod.isnull):
				allnull = 0
		if (not allnull):
			metric[lev] = metric[lev] + 1
		return metric
	def flatten(self, pick=0):
		basis = []
		if (self.isnull):
			if (pick == 0 or pick == 2):
				basis = [self]
		else:
			if (pick == 0 or pick == 1):
				basis = [self]
		res = reduce(lambda x, y, pickv=pick: x + y.flatten(pickv), self.children, basis)
		return res
	def dump(self, count=1, depth=0):
		if (depth == 0):
			if (self.sibnum != None):
				print 'incorrect null sibnum'
		else:
			if (self.sibnum != count-1):
				print 'incorrect sibnum'
		if (self.isnull):
			print ((depth * '  ') + str(count) + ': ' + '<null>')
		else:
			print ((depth * '  ') + str(count) + ': ' + self.snd + ', ' + str(self.pitch))
		count = 1
		for nod in self.children:
			if (nod.parent != self):
				print 'missing parent link'
			nod.dump(count, depth+1)
			count = count+1
	def stats(self):
		if (self.isnull):
			return (0, 1, 1)
		count = len(self.children)
		if (count == 0):
			return (1, 0, 1)
		livecount = 1
		nullcount = 0
		depth = 0.0
		for nod in self.children:
			stat = nod.stats()
			livecount = livecount + stat[0]
			nullcount = nullcount + stat[1]
			depth = depth + stat[2]
		return (livecount, nullcount, 1.0 + (depth / float(count)))
	def apply(self, ag, minrange=0.0, maxrange=rate, depth=0):
		midrange = (minrange+maxrange) * 0.5
		if (not self.isnull):
			ag.sched_note_pan(self.snd, self.pan, self.pitch, self.vol, midrange)
			if (depth == 0):
				ag.sched_note_pan(self.snd, self.pan, self.pitch, self.vol, minrange)
		chillen = len(self.children)
		if (chillen > 0):
			self.counter = (self.counter) % chillen
			nod = self.children[self.counter]
			self.counter = (self.counter+1) % chillen
			nod.apply(ag, minrange, midrange, depth+1)
			nod = self.children[self.counter]
			self.counter = (self.counter+1) % chillen
			nod.apply(ag, midrange, maxrange, depth+1)

class NullNode(Node):
	def __init__(self):
		Node.__init__(self, 1)

def uniformtree(size=2, depth=0):
	if (random.randint(0, 4) < depth):
		return NullNode()
	nod = Node()
	for ix in range(size):
		nod.append(uniformtree(size, depth+1))
	return nod

def randomtree(depth=0, sibs=1):
	if (sibs == 1):
		chance = 0.15 + 0.1 * depth
	else:
		chance = 0.2 * depth
	if (depth > 0 and random.uniform(0.0, 1.0) < chance):
		return NullNode()
	if (depth >= 5):
		return NullNode()
	nod = Node()
	val = random.uniform(0.0, 1.5)
	if (val >= 1.0):
		count = 2
	else:
		count = 0
		while (val < 1.0 and count < 5):
			count = count+1
			val = val * 2.0
	for ix in range(count):
		nod.append(randomtree(depth+1, count))
	return nod

def construct(obj):
	if (type(obj) == type(1)):
		if (obj):
			return Node()
		else:
			return NullNode()
	nod = Node()
	for ch in obj:
		nod.append(construct(ch))
	return nod

class Mutation:
	pass

class TotalMutation(Mutation):
	def apply(self, nod):
		newnod = randomtree()
		return newnod

class ExpandBranchMutation(Mutation):
	def apply(self, nod):
		while (1):
			if (len(nod.children) == 0):
				return randomtree()
			subnod = nod.children[0]
			nod.delete(0)
			if (not subnod.isnull):
				return subnod

class ChangeSubtreeMutation(Mutation):
	def apply(self, nod):
		subnod = random.choice(nod.flatten())
		parent = subnod.parent
		if (parent == None):
			return randomtree()
		newnod = randomtree(subnod.getdepth(), len(parent.children))
		if (subnod.isnull and newnod.isnull):
			newnod = Node()
		parent.replace(subnod.sibnum, newnod)
		return nod

class ReduceChildrenMutation(Mutation):
	def apply(self, nod):
		subnod = random.choice(nod.flatten(1))
		if (len(subnod.children) <= 1):
			return randomtree()
		ix = random.choice(range(len(subnod.children)))
		subnod.delete(ix)
		return nod

class IncreaseChildrenMutation(Mutation):
	def apply(self, nod):
		subnod = random.choice(nod.flatten(1))
		if (len(subnod.children) >= 5):
			return randomtree()
		newnod = randomtree(subnod.getdepth()+1, len(subnod.children))
		subnod.append(newnod)
		return nod

class ReverseChildrenMutation(Mutation):
	def apply(self, nod):
		subnod = random.choice(nod.flatten(1))
		if (len(subnod.children) <= 1):
			return randomtree()
		ls = []
		while (len(subnod.children) > 0):
			ix = len(subnod.children) - 1
			chnod = subnod.children[ix]
			subnod.delete(ix)
			ls.append(chnod)
		for chnod in ls:
			subnod.append(chnod)
		return nod

def create_mutation():
	ls = [ 
		TotalMutation,
		ChangeSubtreeMutation,
		ChangeSubtreeMutation,
		ChangeSubtreeMutation,
		ChangeSubtreeMutation,
	]
	clas = random.choice(ls)
	return clas

class Simple(Agent):
	name = 'a simple repeating rhythm, changing at fixed intervals'
	def __init__(self, repeat=4):
		Agent.__init__(self)
		self.counter = -1
		self.nod = None
		self.repeat = int(repeat)
	def run(self):
		if (self.counter < 0 or self.counter >= self.repeat):
			self.nod = uniformtree()
			if (dumpgraph):
				self.nod.dump()
			self.counter = 0
		self.counter = self.counter + 1
		self.nod.apply(self)
		self.resched(rate)

class Complex(Agent):
	name = 'a rhythm which changes at fixed intervals'
	def __init__(self, repeat=4):
		Agent.__init__(self)
		self.counter = -1
		self.nod = None
		self.repeat = int(repeat)
	def run(self):
		if (self.counter < 0 or self.counter >= self.repeat):
			self.nod = randomtree()
			if (dumpgraph):
				self.nod.dump()
			self.counter = 0
		self.counter = self.counter + 1
		self.nod.apply(self)
		self.resched(rate)

class ComplexWeight(Agent):
	name = 'a rhythm which changes at appropriate intervals'
	def __init__(self):
		Agent.__init__(self)
		self.counter = -1
		self.nod = None
		self.repeat = 1
	def run(self):
		if (self.counter < 0 or self.counter >= self.repeat):
			self.nod = randomtree()
			if (dumpgraph):
				self.nod.dump()
			metric = self.nod.interest()
			if (metric[2] > 0):
				self.repeat = 6
			elif (metric[1] > 0):
				self.repeat = 4
			else:
				self.repeat = 2
			self.counter = 0
		self.counter = self.counter + 1
		self.nod.apply(self)
		self.resched(rate)

class Mutate(Agent):
	name = 'a rhythm which mutates at fixed intervals'
	def __init__(self, repeat=4):
		Agent.__init__(self)
		self.counter = None
		self.nod = None
		self.repeat = int(repeat)
	def run(self):
		if (self.counter == None):
			self.nod = randomtree()
			if (dumpgraph):
				self.nod.dump()
			self.counter = self.repeat
		elif (self.counter <= 0):
			clas = create_mutation()
			mut = clas()
			self.nod = mut.apply(self.nod)
			if (dumpgraph):
				self.nod.dump()
			self.counter = self.repeat
		self.counter = self.counter - 1
		self.nod.apply(self)
		self.resched(rate)

