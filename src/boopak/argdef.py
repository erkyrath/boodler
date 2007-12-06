import sys

class Arglist:
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
			self.args.append(arg)

		self.sort_args()

	def sort_args(self):
		pass ###
		### raise on index or name conflicts.

	def __len__(self):
		return len(self.args)

	def __nonzero__(self):
		return True

	def clone(self):
		arglist = Arglist()
		for arg in self.args:
			arglist.args.append(arg.clone())
		# Don't need to sort, because self is already sorted.

	def dump(self, fl=sys.stdout):
		fl.write('Arglist:\n')
		for arg in self.args:
			fl.write('  Arg:\n')
			if (not (arg.index is None)):
				fl.write('    index: ' + str(arg.index) + '\n')
			if (not (arg.name is None)):
				fl.write('    name: ' + arg.name + '\n')
			if (arg.hasdefault):
				fl.write('    default: ' + repr(arg.default) + '\n')
			if (not (arg.type is None)):
				fl.write('    type: ' + repr(arg.type) + '\n')
		
	def from_argspec(args, varargs, varkw, defaults):
		if (varargs):
			raise ArgDefError('cannot understand *' + varargs)
		if (varkw):
			raise ArgDefError('cannot understand **' + varkw)
		arglist = Arglist()

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
					dic['type'] = type(val)
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
		return arglist ###
	merge = staticmethod(merge)

DummyDefault = object()
	
class Arg:
	def __init__(self, name=None, index=None,
		type=None, default=DummyDefault,
		description=None):
		
		self.name = name
		self.index = index
		self.type = type
		if (default is DummyDefault):
			self.hasdefault = False
			self.default = None
		else:
			self.hasdefault = True
			self.default = default
		self.description = description
	
	def clone(self):
		if (self.hasdefault):
			default = self.default
		else:
			default = DummyDefault
		arg = Arg(name=self.name, index=self.index,
			type=self.type, default=default,
			description=self.description)
		return arg
	
class ArgDefError(ValueError):
	pass
