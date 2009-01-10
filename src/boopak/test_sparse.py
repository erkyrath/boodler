# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

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

    def test_id_serialize(self):
        ls = [
            ('xyz', 'xyz'),
            ('"xyz"', 'xyz'),
            ('"xy z"', '"xy z"'),
            ('"xy=z"', '"xy=z"'),
            ('"xy(z"', '"xy(z"'),
            ('"xy)z"', '"xy)z"'),
            ('"xy\tz"', '"xy\tz"'),
            ('"xy\'z"', '"xy\'z"'),
            ('"xy\\"z"', "'xy\"z'"),
            ('"x\'y\\"z"', '"x\'y\\"z"'),
            ("'xy\\'z'", '"xy\'z"'),
            ("'xy\"z'", "'xy\"z'"),
            ("'x\\'y\"z'", '"x\'y\\"z"'),
            ('"xy\\\\z"', '"xy\\\\z"'),
            ('"x\'\\"y\\\\z"', '"x\'\\"y\\\\z"'),
        ]

        for (src, dest) in ls:
            nod = parse(src)
            self.assertEqual(nod.serialize(), dest)
            nod2 = parse(nod.serialize())
            self.assertEqual(nod, nod2)
            
    def test_id_completeness(self):
        ls = [
            '', 'a', 'Abd', '    ', ' $ # ^ ',
            'a(b', 'a)b', 'a()b', 'a=b',
            '"', ' " ', "'", " ' ", ' \' " ', ' "\' \'" ',
            '\\', ' \\ \\ ', '\\\'', '\\"', '\\" \\\'',
            'a(\')b', 'a(")b', 'a("\')b', 'a("\')b\\c',
            'tab\tnew\nspace ',
            u'unicode', u'unic\u00F8de', u'unic\u0153de',
        ]

        for val in ls:
            nod = ID(val)
            st = nod.serialize()
            nod2 = parse(st)
            self.assertEqual(nod, nod2)
            self.assertEqual(val, nod2.id)
        
    def test_node_basics(self):
        nod = List()
        self.assertEqual(len(nod), 0)
        self.assertEqual(nod.serialize(), '()')
        self.assertEqual(str(nod), '()')
        self.assertEqual(repr(nod), '()')

        nod.append(ID('1'))
        nod.append(ID('hello'))
        self.assertEqual(len(nod), 2)
        self.assertEqual(nod.serialize(), "(1 hello)")
        self.assertEqual(str(nod), "(1 hello)")
        self.assertEqual(repr(nod), "(1 hello)")

        nod.append(List(ID('2')))
        self.assertEqual(len(nod), 3)
        self.assertEqual(nod.serialize(), "(1 hello (2))")
        self.assertEqual(str(nod), "(1 hello (2))")
        self.assertEqual(repr(nod), "(1 hello (2))")

    def test_list_bad(self):
        self.assertRaises(ValueError, List, 'x')
        self.assertRaises(ValueError, List, key='x')
        nod = List()
        self.assertRaises(ValueError, nod.append, 'x')
        self.assertRaises(ValueError, nod.set_attr, 'key', 'x')
        self.assertRaises(ValueError, nod.set_attr, 1, ID('x'))
        self.assertRaises(ValueError, nod.set_attr, ID('key'), ID('x'))

    def test_node_attr(self):
        nod = List()
        nod.set_attr('xyz', ID('1'))
        self.assertEqual(nod.serialize(), '(xyz=1)')

        nod.append(ID('2'))
        nod.append(ID('zz'))
        self.assertEqual(nod.serialize(), "(2 zz xyz=1)")

        nod = List(foo=ID('x'))
        self.assert_(nod.has_attr('foo'))
        self.assert_(not nod.has_attr('bar'))
        self.assertEqual(nod.attrs['foo'], nod.get_attr('foo'))
        self.assert_(nod.get_attr('bar') is None)
        self.assert_(isinstance(nod.attrs['foo'], ID))
        self.assertEqual(nod.attrs['foo'], 'x')
    
    def test_node_list(self):
        nod = List(ID('1'), ID('x'), ID('a'))
        self.assertEqual(len(nod), 3)
        self.assertEqual(nod[0], '1')
        self.assertEqual(nod[1], 'x')
        self.assertEqual(nod[0:2], ['1', 'x'])
        self.assert_('1' in nod)
        self.assert_('x' in nod)
        self.failIf('2' in nod)

        ls = [ val for val in nod ]
        self.assertEqual(ls, ['1', 'x', 'a'])
    
    def test_parse_simple(self):
        ls = [
            ('1', '1'),
            ('-23', '-23'),
            ('5.000', '5.000'),
            ('1.52', '1.52'),
            ('1462134251412', '1462134251412'),
            ('hello', 'hello'),
            ('h', 'h'),
            ('#', '#'),
            ('_hello_', '_hello_'),
            ("'hello'", 'hello'),
            ('"hello"', 'hello'),
            (u"'hello'", 'hello'),
            (u"'1.2.unic\u00F8de'", u'1.2.unic\u00F8de'),
            (u"1.2.unic\u00F8de", u'1.2.unic\u00F8de'),
            ("'esc \\' \\\" \\\\.'", "esc \' \" \\."),
            ('  1  ', '1'),
            (' \t#\t  ', '#'),
            ('  hello  ', 'hello'),
            ('  "hello"  ', 'hello'),
        ]

        for (orig, res) in ls:
            nod = parse(orig)
            self.assert_(isinstance(nod, ID))
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
                if (el != val):
                    return False
                continue
            return False

        return True

    def test_parse_list(self):
        ls = [
            ('()', []),
            ('  (  )    ', []),
            ('(1 "2" _3)', ['1', '2', '_3']),
            ('(()(()))', [[],[[]]]),
            ('(1()a()"x")', ['1', [], 'a', [], 'x']),
            ('(123()aa()"xx")', ['123', [], 'aa', [], 'xx']),
            ('( 45 ( 1 abc ( ) "$#$" ) ) ', ['45', ['1', 'abc', [], '$#$']]),
            ('(abc"123"456"xyz")', ['abc', '123', '456', 'xyz']),
        ]

        for (orig, res) in ls:
            nod = parse(orig)
            self.assert_(self.compare(nod, res))

    def test_parse_attr(self):
        nod = parse('(a=1 b=2 c="three" d=())')
        self.assert_(isinstance(nod, List))
        self.assertEqual(len(nod), 0)
        
        self.assertEqual(len(nod.attrs), 4)
        self.assertEqual(nod.get_attr('a'), '1')
        self.assert_(isinstance(nod.get_attr('a'), ID))
        self.assertEqual(nod.get_attr('b'), '2')
        self.assertEqual(nod.get_attr('c'), 'three')
        val = nod.get_attr('d')
        self.assert_(isinstance(val, List))
        self.assertEqual(len(val), 0)
        self.assertEqual(len(val.attrs), 0)

        nod = parse('(1 x=a 2 y=(y1=y2)"three" z=(z)xyzzy(z1=z2))')
        res = ['1', '2', 'three', 'xyzzy', []]
        self.assert_(self.compare(nod, res))

        self.assertEqual(len(nod.attrs), 3)
        self.assertEqual(nod.get_attr('x'), 'a')
        self.assert_(self.compare(nod.get_attr('y'), []))
        val = nod[-1]
        self.assert_(self.compare(val, []))
        self.assertEqual(val.attrs['z1'], 'z2')

        nod = parse('("#=$" $=#)')
        self.assertEqual(len(nod), 1)
        self.assertEqual(nod[0], "#=$")
        self.assertEqual(nod.get_attr('$'), '#')
        
        nod = parse('(a = x)')
        self.assertEqual(len(nod), 0)
        self.assertEqual(nod.get_attr('a'), 'x')
        
        nod = parse('("a" = x)')
        self.assertEqual(len(nod), 0)
        self.assertEqual(nod.get_attr('a'), 'x')
        
        nod = parse('("a"=x)')
        self.assertEqual(len(nod), 0)
        self.assertEqual(nod.get_attr('a'), 'x')
        
    def test_parse_bad(self):
        ls = [
            '', '   ', '    \n',
            '\\', 'x\\y', '=',
            '"\\n"',
            '(', ')', '((1)', '(1))', '"', "'", '"waooo ',
            '1 2', '() 1',
            'a=z', '123=456',
            '(a123=)', '( a123= )', '(a=b=c)',
            '(a=', '(=1)', '(()=1)',
        ]

        for val in ls:
            self.assertRaises(ParseError, parse, val)

