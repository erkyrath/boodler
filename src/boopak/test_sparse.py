import unittest

from boopak.sparse import parse, ID, List, ParseError

class TestSParse(unittest.TestCase):

	def test_id_compare(self):
		id = ID('hello')
		id1 = ID(u'hello')
		id2 = ID('goodbye')

		self.failIf(id == id2)
		self.assert_(id != id2)
		self.assert_(id == id)
		self.failIf(id != id)
		self.assert_(id == id1)
		self.failIf(id != id1)

		self.assertEqual(len(id), 5)

		self.assert_(id == 'hello')
		self.assert_(id == u'hello')
		self.assert_('hello' == id)
		self.assert_(id != 'goodbye')
		self.assert_(id != u'goodbye')
		self.assert_('goodbye' != id)

	def test_node_basics(self):
		nod = List()
		self.assertEqual(len(nod), 0)
		self.assertEqual(str(nod), '()')
		self.assertEqual(repr(nod), '()')

		nod.append(1)
		nod.append('hello')
		self.assertEqual(len(nod), 2)
		self.assertEqual(str(nod), "(1 'hello')")
		self.assertEqual(repr(nod), "(1 'hello')")

		nod.append(List(2))
		self.assertEqual(len(nod), 3)
		self.assertEqual(str(nod), "(1 'hello' (2))")
		self.assertEqual(repr(nod), "(1 'hello' (2))")

	def test_node_attr(self):
		nod = List()
		nod.attrs['xyz'] = 1
		self.assertEqual(repr(nod), '(xyz=1)')

		nod.append(2)
		nod.append('zz')
		self.assertEqual(repr(nod), "(2 'zz' xyz=1)")
	
	def test_node_list(self):
		nod = List(1, 'x', ID('a'))
		self.assertEqual(len(nod), 3)
		self.assertEqual(nod[0], 1)
		self.assertEqual(nod[1], 'x')
		self.assertEqual(nod[0:2], [1, 'x'])
		self.assert_(1 in nod)
		self.assert_('x' in nod)
		self.failIf(2 in nod)

		ls = [ val for val in nod ]
		self.assertEqual(ls, [1, 'x', ID('a')])
	
	def test_parse_simple(self):
		ls = [
			('1', 1, int),
			('-23', -23, int),
			('5.000', 5.0, float),
			('1.52', 1.52, float),
			('1462134251412', 1462134251412, long),
			('hello', 'hello', ID),
			('h', 'h', ID),
			('_hello_', '_hello_', ID),
			("'hello'", 'hello', str),
			('"hello"', 'hello', str),
			(u"'hello'", u'hello', unicode),
			(u"'1.2.unic\u00F8de'", u'1.2.unic\u00F8de', unicode),
			("'esc \\' \\\" \\\\.'", "esc \' \" \\.", str),
			('  1  ', 1, int),
			('  hello  ', 'hello', ID),
			('  "hello"  ', 'hello', str),
		]

		for (orig, res, typ) in ls:
			nod = parse(orig)
			if (typ is ID):
				self.assert_(isinstance(nod, ID))
				self.assertEqual(nod, res)
			else:
				self.assertEqual(type(nod), typ)
				self.assertEqual(nod, res)

	def compare(self, nod, ls):
		if (not isinstance(nod, List)):
			return False
		if (type(ls) != list):
			return False
		if (len(nod) != len(ls)):
			return False

		for (el, val) in zip(nod.list, ls):
			if (isinstance(el, List)):
				if (not self.compare(el, val)):
					return False
				continue
			if (isinstance(el, ID)):
				if (not isinstance(val, ID)):
					return False
				if (el != val):
					return False
				continue
			if (type(el) != type(val)):
				return False
			if (el != val):
				return False

		return True

	def test_parse_list(self):
		ls = [
			('()', []),
			('  (  )    ', []),
			('(1 "2" _3)', [1, '2', ID('_3')]),
			('(()(()))', [[],[[]]]),
			('(1()a()"x")', [1, [], ID('a'), [], 'x']),
			('(123()aa()"xx")', [123, [], ID('aa'), [], 'xx']),
			('( 45 ( 1 abc ( ) "$#$" ) ) ', [45, [1, ID('abc'), [], '$#$']]),
			('(abc"123"456"xyz")', [ID('abc'), '123', 456, 'xyz']),
		]

		for (orig, res) in ls:
			nod = parse(orig)
			self.assert_(self.compare(nod, res))

	def test_parse_attr(self):
		nod = parse('(a=1 b=2 c="three" d=())')
		self.assertEqual(len(nod), 0)
		
		self.assertEqual(len(nod.attrs), 4)
		self.assertEqual(nod.attrs['a'], 1)
		self.assertEqual(nod.attrs['b'], 2)
		self.assertEqual(nod.attrs['c'], 'three')
		val = nod.attrs['d']
		self.assertEqual(len(val), 0)
		self.assertEqual(len(val.attrs), 0)

		nod = parse('(1 x=a 2 y=(y1=y2)"three" z=(z)xyzzy(z1=z2))')
		res = [1, 2, 'three', ID('xyzzy'), []]
		self.assert_(self.compare(nod, res))

		self.assertEqual(len(nod.attrs), 3)
		self.assertEqual(nod.attrs['x'], 'a')
		self.assert_(self.compare(nod.attrs['y'], []))
		val = nod[-1]
		self.assert_(self.compare(val, []))
		self.assertEqual(val.attrs['z1'], ID('z2'))

	def test_parse_bad(self):
		ls = [
			'', '   ', '    \n',
			'"\\n"', u'unic\u00F8de',
			'(', ')', '((1)', '(1))', '"', "'", '"waooo ',
			'1 2', '() 1',
			'1.a', '1a', '--2', '45.001.', 'a=z', '123=456',
			'(a123=)', '( a123= )', '(123=5)', '(a=b=c)',
			'(a = 1)', '(a=',
		]

		for val in ls:
			self.assertRaises(ParseError, parse, val)

