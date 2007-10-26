import StringIO

class ParseError(Exception):
	pass

class Node:
	def __init__(self, *args):
		self.list = list(args)
		self.attrs = {}

	def append(self, val):
		self.list.append(val)

	def __len__(self):
		return len(self.list)

	def __repr__(self):
		ls = [ repr(val) for val in self.list ]
		ls = ls + [ key+'='+repr(self.attrs[key]) for key in self.attrs ]
		return '(' + ' '.join(ls) + ')'

	def __getitem__(self, key):
		return self.list.__getitem__(key)
		
	def __contains__(self, it):
		return self.list.__contains__(it)
		
	def __iter__(self):
		return self.list.__iter__()
		

class ID:
	def __init__(self, id):
		self.id = id
		
	def __repr__(self):
		return self.id
		
	def __len__(self):
		return len(self.id)
		
	def __cmp__(self, other):
		if (isinstance(other, ID)):
			other = other.id
		return cmp(self.id, other)

class EndOfList:
	pass
EndOfList = EndOfList()

class AttrToken:
	def __init__(self, key):
		self.key = key

def parse(val):
	### str/unicode -> Node, str, int
	fl = StringIO.StringIO(val)
	context = ParseContext(fl)
	try:
		res = context.parsenode()
		if (res is EndOfList):
			raise ParseError('unexpected end of list)')
		if (isinstance(res, AttrToken)):
			raise ParseError('attributes may only occur in lists')
		context.finalwhite()
		return res
	finally:
		context.close()

class ParseContext:
	def __init__(self, fl):
		self.fl = fl
		self.nextch = None

	def close(self):
		self.fl.close()

	def finalwhite(self):
		ch = self.nextch
		fl = self.fl

		if (ch is None):
			ch = fl.read(1)

		while (ch and ch.isspace()):
			ch = fl.read(1)
		
		if (ch):
			raise ParseError('extra stuff after value')

	def parsenode(self):
		ch = self.nextch
		fl = self.fl

		if (ch is None):
			ch = fl.read(1)

		while (ch and ch.isspace()):
			ch = fl.read(1)

		if (not ch):
			raise ParseError('unexpected end of input')
		
		if (ch == '('):
			self.nextch = None
			return self.parselist()

		if (ch == ')'):
			self.nextch = None
			return EndOfList

		if (ch=='-' or ch.isdigit()):
			self.nextch = ch
			return self.parsenumber()

		if (ch.isalpha() or ch=='_'):
			self.nextch = ch
			return self.parseid()

		if (ch in ['"', "'"]):
			self.nextch = None
			return self.parsestring(ch)

		raise ParseError('unknown character: ' + ch)

	def parsenumber(self):
		ch = self.nextch
		fl = self.fl

		if (ch is None):
			raise Exception('internal error: lookahead char missing')
		
		idfl = StringIO.StringIO()
		while (ch and not (ch in ['(', ')', '"', "'"]) and not ch.isspace()):
			idfl.write(ch)
			ch = fl.read(1)
		self.nextch = ch

		st = idfl.getvalue()
		try:
			if ('.' in st):
				val = float(st)
			else:
				val = int(st)
		except ValueError, ex:
			raise ParseError(str(ex))
		return val

	def parseid(self):
		ch = self.nextch
		fl = self.fl

		if (ch is None):
			raise Exception('internal error: lookahead char missing')
		
		idfl = StringIO.StringIO()
		while (ch and not (ch in ['(', ')', '"', "'", '='])
			and not ch.isspace()):
			idfl.write(ch)
			ch = fl.read(1)
		self.nextch = ch

		st = idfl.getvalue()
		if (type(st) == unicode):
			try:
				st = str(st)
			except:
				raise ParseError('ID may only contain ASCII')

		if (ch == '='):
			self.nextch = None
			return AttrToken(st)
		return ID(st)

	def parsestring(self, terminator='"'):
		fl = self.fl
		if (not (self.nextch is None)):
			raise Exception('internal error: lookahead char')
		ch = fl.read(1)
		
		idfl = StringIO.StringIO()
		while True:
			if (not ch):
				raise ParseError('unterminated string literal')
			if (ch == terminator):
				break
			if (ch == '\\'):
				ch = fl.read(1)
				if (not (ch in ['"', "'", '\\'])):
					raise ParseError('backslash must be followed by quote or backslash')
			idfl.write(ch)
			ch = fl.read(1)

		self.nextch = None
		return idfl.getvalue()

	def parselist(self):
		if (not (self.nextch is None)):
			raise Exception('internal error: lookahead char')
		
		nod = Node()
		while True:
			val = self.parsenode()
			if (val is EndOfList):
				break
			if (isinstance(val, AttrToken)):
				key = val.key
				val = self.parseattr()
				nod.attrs[key] = val
				continue
			nod.append(val)

		return nod

	def parseattr(self):
		val = self.parsenode()
		if (val is EndOfList):
			raise ParseError('attribute must have a value')
		if (isinstance(val, AttrToken)):
			raise ParseError('attribute may not contain another =')
		return val
