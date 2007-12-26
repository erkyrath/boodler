import sys

# We use "type" as an argument and local variable sometimes, but we need
# to keep track of the standard type() function.
_typeof = type

class ArgList:
	def __init__(self, *ls, **dic):
		self.args = []
		
		pos = 1
		for arg in ls:
			if (arg.index is None):
				arg.index = pos
			pos += 1
			self.args.append(arg)
			
		for key in dic.keys():
			arg = dic[key]
			if (arg.name is None):
				arg.name = key
			else:
				if (arg.name != key):
					raise ArgDefError('argument name does not match: ' + key + ', ' + arg.name)
			self.args.append(arg)

		self.sort_args()

	def sort_args(self):
		self.args.sort(_argument_sort_func)
		for arg in self.args:
			if (arg.index is None):
				continue
			ls = [ arg2 for arg2 in self.args if arg2.index == arg.index ]
			if (len(ls) > 1):
				raise ArgDefError('more than one argument with index ' + str(arg.index))
		for arg in self.args:
			if (arg.name is None):
				continue
			ls = [ arg2 for arg2 in self.args if arg2.name == arg.name ]
			if (len(ls) > 1):
				raise ArgDefError('more than one argument with name ' + str(arg.name))

	def __len__(self):
		return len(self.args)

	def __nonzero__(self):
		return True

	def get_index(self, val):
		for arg in self.args:
			if ((not (arg.index is None)) and (arg.index == val)):
				return arg
		return None

	def get_name(self, val):
		for arg in self.args:
			if ((not (arg.name is None)) and (arg.name == val)):
				return arg
		return None

	def clone(self):
		arglist = ArgList()
		for arg in self.args:
			arglist.args.append(arg.clone())
		# Don't need to sort, because self is already sorted.
		return arglist

	def dump(self, fl=sys.stdout):
		fl.write('ArgList:\n')
		for arg in self.args:
			fl.write('  Arg:\n')
			if (not (arg.index is None)):
				val = ''
				if (arg.optional):
					val = ' (optional)'
				fl.write('    index: ' + str(arg.index) + val + '\n')
			if (not (arg.name is None)):
				fl.write('    name: ' + arg.name + '\n')
			if (arg.hasdefault):
				fl.write('    default: ' + repr(arg.default) + '\n')
			if (not (arg.type is None)):
				fl.write('    type: ' + repr(arg.type) + '\n')

	def max_accepted(self):
		return len(self.args)
		
	def min_accepted(self):
		ls = [ arg for arg in self.args if (not arg.optional) ]
		return len(ls)

	def invoke(self, func, node):
		ls = [] ###
		dic = {} ###
		return func(*ls, **dic)
	
	def from_argspec(args, varargs, varkw, defaults):
		if (varargs):
			raise ArgDefError('cannot understand *' + varargs)
		if (varkw):
			raise ArgDefError('cannot understand **' + varkw)
		arglist = ArgList()

		if (defaults is None):
			defstart = len(args)
		else:
			defstart = len(args) - len(defaults)
		
		pos = 1
		for key in args[1:]:
			dic = {}
			if (pos >= defstart):
				val = defaults[pos-defstart]
				dic['default'] = val
				if (not (val is None)):
					dic['type'] = _typeof(val)
			arg = Arg(name=key, index=pos, **dic)
			pos += 1
			arglist.args.append(arg)
			
		arglist.sort_args()
		return arglist
	from_argspec = staticmethod(from_argspec)

	def merge(arglist1, arglist2=None):
		arglist = arglist1.clone()
		if (arglist2 is None):
			return arglist

		unmerged = []
		for arg2 in arglist2.args:
			arg = None
			if (not (arg2.index is None)):
				arg = arglist.get_index(arg2.index)
			if ((arg is None) and not (arg2.name is None)):
				arg = arglist.get_name(arg2.name)
			if (arg is None):
				unmerged.append(arg2)
			else:
				arg.absorb(arg2)
		for arg in unmerged:
			arglist.args.append(arg)
		arglist.sort_args()
		return arglist
	merge = staticmethod(merge)

def _argument_sort_func(arg1, arg2):
	ix1 = arg1.index
	ix2 = arg2.index
	if (ix1 is None and ix2 is None):
		return 0
	if (ix1 is None):
		return 1
	if (ix2 is None):
		return -1
	return cmp(ix1, ix2)
	
_DummyDefault = object()
	
class Arg:
	def __init__(self, name=None, index=None,
		type=None, default=_DummyDefault, optional=None,
		description=None):
		
		self.name = name
		if (not (index is None) and index <= 0):
			raise ArgDefError('index must be positive')
		self.index = index
		self.type = type
		self.optional = optional
		if (default is _DummyDefault):
			self.hasdefault = False
			self.default = None
		else:
			self.hasdefault = True
			self.default = default
			if ((self.type is None) and not (default is None)):
				self.type = _typeof(default)
		if (self.optional is None):
			self.optional = self.hasdefault
		else:
			self.optional = bool(self.optional)
		self.description = description

	def __repr__(self):
		val = '<Arg'
		if (not (self.index is None)):
			val += ' ' + str(self.index)
		if (not (self.name is None)):
			val += " '" + self.name + "'"
		val += '>'
		return val
	
	def clone(self):
		if (self.hasdefault):
			default = self.default
		else:
			default = _DummyDefault
		arg = Arg(name=self.name, index=self.index,
			type=self.type, default=default, optional=self.optional,
			description=self.description)
		return arg

	def absorb(self, arg):
		attrlist = ['name', 'index']
		for key in attrlist:
			val = getattr(arg, key)
			if (val is None):
				continue
			sval = getattr(self, key)
			if (sval is None):
				setattr(self, key, val)
				continue
			if (val != sval):
				raise ArgDefError('argument ' + key + ' does not match: ' + str(val) + ', ' + str(sval))
			
		attrlist = ['type', 'description']
		for key in attrlist:
			val = getattr(arg, key)
			if (val is None):
				continue
			sval = getattr(self, key)
			if (sval is None):
				setattr(self, key, val)
				continue
			# No warning if these attrs don't match
			
		if (arg.hasdefault):
			if (not self.hasdefault):
				self.hasdefault = True
				self.default = arg.default
			# No warning if defaults don't match

		self.optional = arg.optional
		# Always absorb the optional attribute

class ArgDefError(ValueError):
	pass


class ArgWrapper:
	pass

class ArgClassWrapper(ArgWrapper):
	def create(cla, ls, dic=None):
		ls = list(ls)
		return ArgClassWrapper(ls, dic)
	create = staticmethod(create)

	def __init__(self, cla, ls, dic=None):
		self.cla = cla
		self.argls = ls
		self.argdic = dic
	def unwrap(self):
		ls = [ instantiate(val) for val in self.argls ]
		if (not self.argdic):
			return self.cla(*ls)
		dic = dict([ (key,instantiate(val)) for (key,val) in self.argdic.items() ])
		return self.cla(*ls, **dic)

class ArgListWrapper(ArgWrapper):
	def create(ls):
		ls = list(ls)
		return ArgListWrapper(ls)
	create = staticmethod(create)
	
	def __init__(self, ls):
		self.ls = ls
	def unwrap(self):
		return [ instantiate(val) for val in self.ls ]

class ArgTupleWrapper(ArgWrapper):
	def create(tup):
		tup = tuple(tup)
		muts = [ val for val in tup if isinstance(val, ArgWrapper) ]
		if (not muts):
			return tup
		return ArgTupleWrapper(tup)
	create = staticmethod(create)
	
	def __init__(self, tup):
		self.tup = tup
	def unwrap(self):
		ls = [ instantiate(val) for val in self.tup ]
		return tuple(ls)

	
def instantiate(val):
	if (not isinstance(val, ArgWrapper)):
		return val
	return val.unwrap()

