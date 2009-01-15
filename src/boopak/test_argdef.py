# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import unittest
import inspect

from boopak.argdef import *
from boopak import sparse
from boodle import sample, agent, builtin

from boopak.argdef import node_to_value, value_to_node
from boopak.argdef import node_to_type, type_to_node
from boopak.argdef import resolve_value
from boopak.argdef import ArgListWrapper, ArgTupleWrapper

class TestArgDef(unittest.TestCase):

    def test_basic_arg(self):
        arg = Arg()
        self.assert_(arg.index is None)
        self.assert_(arg.name is None)
        self.assert_(arg.type is None)
        self.assert_(arg.description is None)
        self.assert_(arg.hasdefault is False)
        self.assert_(arg.default is None)
        self.assert_(arg.optional is False)
        
        arg = Arg(name='foo', index=2, type=float, default=1.5,
            description='Argument')
        self.assertEqual(arg.index, 2)
        self.assertEqual(arg.name, 'foo')
        self.assertEqual(arg.type, float)
        self.assertEqual(arg.description, 'Argument')
        self.assert_(arg.hasdefault is True)
        self.assertEqual(arg.default, 1.5)
        self.assert_(arg.optional is True)

    def assert_arglists_identical(self, arglist1, arglist2):
        self.assertEqual(len(arglist1.args), len(arglist2.args))
        for (arg1, arg2) in zip(arglist1.args, arglist2.args):
            self.assert_args_identical(arg1, arg2)
        self.assert_types_identical(arglist1.listtype, arglist2.listtype)
        
    def assert_args_identical(self, arg1, arg2):
        self.assertEqual(arg1.index,       arg2.index)
        self.assertEqual(arg1.name,        arg2.name)
        if (isinstance(arg1.type, SequenceOf)):
            self.assertEqual(arg1.type.classname, arg2.type.classname)
        else:
            self.assertEqual(arg1.type,    arg2.type)
        self.assertEqual(arg1.description, arg2.description)
        self.assertEqual(arg1.hasdefault,  arg2.hasdefault)
        self.assertEqual(arg1.default,     arg2.default)
        self.assertEqual(arg1.optional,    arg2.optional)

    def assert_types_identical(self, typ1, typ2):
        if (not isinstance(typ1, SequenceOf)):
            self.assertEqual(typ1, typ2)
            return

        self.assert_(isinstance(typ1, SequenceOf))
        self.assert_(isinstance(typ2, SequenceOf))
        self.assertEqual(typ1.classname, typ2.classname)
        self.assertEqual(typ1.min, typ2.min)
        self.assertEqual(typ1.max, typ2.max)
        self.assertEqual(typ1.repeat, typ2.repeat)
        self.assertEqual(len(typ1.types), len(typ2.types))
        for (val1, val2) in zip(typ1.types, typ2.types):
            self.assert_types_identical(val1, val2)
        
    def test_clone_arg(self):
        origarg = Arg()
        arg = origarg.clone()
        self.assert_(not (arg is origarg))
        self.assert_args_identical(arg, origarg)
        
        origarg = Arg(name='foo', index=2, type=float, default=1.5,
            description='Argument')
        arg = origarg.clone()
        self.assert_(not (arg is origarg))
        self.assert_args_identical(arg, origarg)

    def test_arg_unicode(self):
        arg = Arg(name='foo')
        arg = Arg(name=u'foo')
        arg = Arg(name=u'f\x6fo')
        self.assertEqual(arg.name, 'foo')
        self.assertEqual(type(arg.name), str)
        
        self.assertRaises(ArgDefError, Arg, name=u'f\xa1o')
        
    def test_arg_absorb(self):
        arg = Arg()
        arg.absorb(Arg(index=2))
        self.assertEqual(arg.index, 2)
        arg.absorb(Arg(name='foo'))
        self.assertEqual(arg.name, 'foo')
        arg.absorb(Arg(type=float))
        self.assertEqual(arg.type, float)
        arg.absorb(Arg(description='Argument'))
        self.assertEqual(arg.description, 'Argument')
        arg.absorb(Arg(default=1.5))
        self.assert_(arg.hasdefault is True)
        self.assertEqual(arg.default, 1.5)
        self.assert_(arg.optional is True)
        arg.absorb(Arg(optional=False))
        self.assert_(arg.optional is False)
        arg.absorb(Arg(optional=True))
        self.assert_(arg.optional is True)

        arg.absorb(Arg())
        
        self.assertEqual(arg.index, 2)
        self.assertEqual(arg.name, 'foo')
        self.assertEqual(arg.type, float)
        self.assertEqual(arg.description, 'Argument')
        self.assert_(arg.hasdefault is True)
        self.assertEqual(arg.default, 1.5)
        self.assert_(arg.optional is False)

        arg2 = Arg(type=str, description='Undescribed', default=2.0)
        arg.absorb(arg2)
        
        self.assertEqual(arg.index, 2)
        self.assertEqual(arg.name, 'foo')
        self.assertEqual(arg.type, float)
        self.assertEqual(arg.description, 'Argument')
        self.assert_(arg.hasdefault is True)
        self.assertEqual(arg.default, 1.5)
        self.assert_(arg.optional is True)

    def test_arg_absorb_mismatch(self):
        arg = Arg(index=1)
        arg2 = Arg(index=1)
        arg.absorb(arg2)
        self.assertEqual(arg.index, 1)

        arg = Arg(name='foo')
        arg2 = Arg(name='foo')
        arg.absorb(arg2)
        self.assertEqual(arg.name, 'foo')
        
        arg = Arg(index=1)
        arg2 = Arg(index=2)
        self.assertRaises(ArgDefError, arg.absorb, arg2)
        
        arg = Arg(name='foo')
        arg2 = Arg(name='bar')
        self.assertRaises(ArgDefError, arg.absorb, arg2)

    def test_arg_serialize(self):
        ls = [
            Arg(),
            Arg(name='foo'),
            Arg(name='foo', index=5, default=3.1, description='A thing.'),
            Arg(type=bool),
            Arg(type=ListOf(int, str, bool, repeat=2)),
            Arg(optional=True),
            Arg(default=[]),
            Arg(name='bar', optional=False),
            Arg(default='foo', optional=False),
            Arg(default=True, optional=True),
        ]

        for arg in ls:
            nod = arg.to_node()
            arg2 = Arg.from_node(nod)
            self.assert_args_identical(arg, arg2)
        
    def argspec_testfunc(self, baz, foo=3, bar='two'):
        pass
        
    def test_from_argspec(self):
        argspec = inspect.getargspec(self.argspec_testfunc)
        arglist = ArgList.from_argspec(*argspec)
        self.assertEquals(len(arglist), 3)
        self.assertEquals(arglist.max_accepted(), 3)
        self.assertEquals(arglist.min_accepted(), 1)
        
        arg = arglist.args[0]
        self.assert_(arglist.get_index(1) is arg)
        self.assert_(arglist.get_name('baz') is arg)
        self.assertEquals(arg.index, 1)
        self.assertEquals(arg.name, 'baz')
        self.assertEquals(arg.hasdefault, False)
        self.assert_(arg.optional is False)
        
        arg = arglist.args[1]
        self.assert_(arglist.get_index(2) is arg)
        self.assert_(arglist.get_name('foo') is arg)
        self.assertEquals(arg.index, 2)
        self.assertEquals(arg.name, 'foo')
        self.assert_(arg.hasdefault is True)
        self.assertEquals(arg.default, 3)
        self.assertEquals(arg.type, int)
        self.assert_(arg.optional is True)
        
        arg = arglist.args[2]
        self.assert_(arglist.get_index(3) is arg)
        self.assert_(arglist.get_name('bar') is arg)
        self.assertEquals(arg.index, 3)
        self.assertEquals(arg.name, 'bar')
        self.assert_(arg.hasdefault is True)
        self.assertEquals(arg.default, 'two')
        self.assertEquals(arg.type, str)
        self.assert_(arg.optional is True)
        
    def test_init_arglist(self):
        arglist = ArgList(
            Arg(default=11), Arg(default=22),
            foo=Arg(default=33), bar=Arg(default=44))
        self.assertEquals(len(arglist), 4)
        self.assertEquals(arglist.max_accepted(), 4)
        self.assertEquals(arglist.min_accepted(), 0)

        arg = arglist.args[0]
        self.assertEquals(arg.index, 1)
        self.assertEquals(arg.default, 11)
        
        arg = arglist.args[1]
        self.assertEquals(arg.index, 2)
        self.assertEquals(arg.default, 22)
        
        arg1 = arglist.args[2]
        arg2 = arglist.args[3]
        if (arg1.name == 'bar'):
            (arg1, arg2) = (arg2, arg1)
        self.assertEquals(arg1.default, 33)
        self.assertEquals(arg1.name, 'foo')
        self.assertEquals(arg2.default, 44)
        self.assertEquals(arg2.name, 'bar')

    def test_arglist_bad_format(self):
        self.assertRaises(ArgDefError, ArgList, 1)
        self.assertRaises(ArgDefError, ArgList, str)
        self.assertRaises(ArgDefError, ArgList, x=str)
        self.assertRaises(ArgDefError, ArgExtra, 1)
        self.assertRaises(ArgDefError, ArgExtra, str)

    def test_arglist_extra(self):
        arglist = ArgList(Arg('x'), ArgExtra(ListOf(int)), Arg('y'))
        self.assertEquals(arglist.min_accepted(), 2)
        self.assertEquals(arglist.max_accepted(), None)
        arg = arglist.get_index(1)
        self.assertEquals(arg.name, 'x')
        arg = arglist.get_index(2)
        self.assertEquals(arg.name, 'y')

        arglist2 = arglist.clone()
        self.assertEquals(arglist2.min_accepted(), 2)
        self.assertEquals(arglist2.max_accepted(), None)
        arg = arglist2.get_index(1)
        self.assertEquals(arg.name, 'x')
        arg = arglist2.get_index(2)
        self.assertEquals(arg.name, 'y')

        self.assert_(isinstance(arglist2.listtype, ListOf))
        self.assertEqual(arglist2.listtype.types, (int,))

    def test_sort_arglist(self):
        arglist = ArgList(
            foo=Arg(index=3, default=33),
            bar=Arg(index=2, default=22),
            baz=Arg(index=1, default=11),
        )
        
        arg = arglist.args[0]
        self.assertEquals(arg.index, 1)
        self.assertEquals(arg.name, 'baz')
        self.assertEquals(arg.default, 11)
        
        arg = arglist.args[1]
        self.assertEquals(arg.index, 2)
        self.assertEquals(arg.name, 'bar')
        self.assertEquals(arg.default, 22)
        
        arg = arglist.args[2]
        self.assertEquals(arg.index, 3)
        self.assertEquals(arg.name, 'foo')
        self.assertEquals(arg.default, 33)

        arglist = ArgList(
            Arg(index=1),
            Arg(index=2),
            baz=Arg(name='baz'),
        )
        self.assertEquals(len(arglist), 3)
        
        self.assertRaises(ArgDefError, ArgList,
            foo=Arg(index=1, default=11),
            baz=Arg(index=1, default=22))
        
        self.assertRaises(ArgDefError, ArgList,
            Arg(name='foo', default=11),
            Arg(name='foo', default=22))

    def test_merge_common(self):
        arglist1 = ArgList(
            bar=Arg(description='Bar'),
            foo=Arg(description='Foo'),
            baz=Arg(description='Baz', default=1.5),
        )
        argspec = inspect.getargspec(self.argspec_testfunc)
        arglist2 = ArgList.from_argspec(*argspec)

        arglist = ArgList.merge(arglist1, arglist2)
        self.assertEquals(len(arglist), 3)

        arg = arglist.args[0]
        self.assertEquals(arg.description, 'Baz')
        self.assertEquals(arg.default, 1.5)
        self.assert_(arg.optional is False)
        
        arg = arglist.args[1]
        self.assertEquals(arg.description, 'Foo')
        self.assertEquals(arg.default, 3)
        self.assert_(arg.optional is True)
        
        arg = arglist.args[2]
        self.assertEquals(arg.description, 'Bar')
        self.assertEquals(arg.default, 'two')
        self.assert_(arg.optional is True)
        
    def test_clone_arglist(self):
        arglist2 = ArgList(
            Arg(default=11), Arg(default=22),
            foo=Arg(default=33), bar=Arg(default=44))
        arglist = arglist2.clone()
        self.assert_(not (arglist is arglist2))
        
        self.assertEquals(len(arglist), 4)

        arg = arglist.args[0]
        self.assertEquals(arg.index, 1)
        self.assertEquals(arg.default, 11)
        
        arg = arglist.args[1]
        self.assertEquals(arg.index, 2)
        self.assertEquals(arg.default, 22)
        
        arg1 = arglist.args[2]
        arg2 = arglist.args[3]
        if (arg1.name == 'bar'):
            (arg1, arg2) = (arg2, arg1)
        self.assertEquals(arg1.default, 33)
        self.assertEquals(arg1.name, 'foo')
        self.assertEquals(arg2.default, 44)
        self.assertEquals(arg2.name, 'bar')

    def test_arglist_serialize(self):
        ls = [
            ArgList(),
            ArgList(Arg('x'), Arg('y')),
            ArgList(Arg(name='x', type=str), ArgExtra(TupleOf(int, int))),
            ArgList(Arg(name='foo'), x=Arg(default=3.1), y=Arg(type=ListOf())),
            ArgList(Arg(type=ListOf(bool), default=[False,True])),
        ]

        for arglist in ls:
            nod = arglist.to_node()
            arglist2 = ArgList.from_node(nod)
            self.assert_arglists_identical(arglist, arglist2)
        
    def test_bad_format_sequenceof(self):
        self.assertRaises(Exception, SequenceOf)
        self.assertRaises(ArgDefError, ListOf, 1)
        self.assertRaises(ArgDefError, ListOf, complex)
        self.assertRaises(ArgDefError, ListOf, min=-1)
        self.assertRaises(ArgDefError, ListOf, min=5, max=4)
        self.assertRaises(ArgDefError, ListOf, repeat=2)
        self.assertRaises(ArgDefError, ListOf, repeat=0)
        self.assertRaises(ArgDefError, ListOf, foo=0)
        
    def test_simple_node_to_val(self):

        goodls = [
            (int, '5', 5),
            (int, '005', 5),
            (int, '"5"', 5),
            (long, '5', 5),
            (float, '5', 5.0),
            (str, '5', '5'),
            (str, 'foo', 'foo'),
            (unicode, 'foo', 'foo'),
            (str, u'foo', u'foo'),
            (bool, '""', False),
            (bool, '0', False),
            (bool, 'no', False),
            (bool, 'FALSE', False),
            (bool, '1', True),
            (bool, 'YES', True),
            (bool, 'true', True),
            (list, '(() foo)', [[], 'foo']),
            (ListOf(), '(())', [[]]),
            (ListOf(), '(() foo)', [[], 'foo']),
            (ListOf(str), '(foo bar)', ['foo', 'bar']),
            (ListOf(int), '(1 3 2)', [1, 3, 2]),
            (ListOf(bool), '(0 1 false true NO YES)', [False, True, False, True, False, True]),
            (ListOf(int, str), '(1 2 3 4)', [1, '2', 3, '4']),
            (ListOf(str, None), '(foo (bar) baz (()))', ['foo', ['bar'], 'baz', [[]]]),
            (ListOf(TupleOf(int, str)), '((1 2) (3 4))', [(1, '2'), (3, '4')]),
            (tuple, '(() foo)', ([], 'foo')),
            (TupleOf(), '(() 1 2)', ([], '1', '2')),
            (TupleOf(int, str), '(1 2)', (1, '2')),
            (None, 'foo', 'foo'),
            (None, '()', []),
            (None, '(foo (1) ())', ['foo', ['1'], []]),
            (int, '(no=value)', None),
            (str, '(no=value)', None),
            (list, '(no=value)', None),
            (ListOf(), '(no=value)', None),
            (None, '(no=value)', None),
        ]
        
        badls = [
            (int, '()'),
            (int, '(1)'),
            (int, 'foo'),
            (int, '5.0'),
            (int, '5x'),
            (str, '()'),
            (float, '()'),
            (float, 'foo'),
            (bool, '()'),
            (list, 'foo'),
            (list, '(foo x=1)'),
            (ListOf(), 'foo'),
            (ListOf(str), 'foo'),
            (ListOf(str), '(())'),
            (ListOf(int), '(foo)'),
            (ListOf(str, int), '(foo bar)'),
            (ListOf(int, str), '(1 foo bar)'),
            (TupleOf(str, str), '(baz)'),
            (TupleOf(str, str), '(baz foo bar)'),
            (int, '(none=one)'),
            (int, '(foo none=none)'),
        ]

        for (typ, st, res) in goodls:
            nod = sparse.parse(st)
            val = node_to_value(typ, nod)
            val = resolve_value(val)
            self.assertEqual(val, res)
            self.assertEqual(type(val), type(res))
            if (type(val) == list):
                for (sub1, sub2) in zip(val, res):
                    self.assertEqual(type(sub1), type(sub2))

        for (typ, st) in badls:
            nod = sparse.parse(st)
            self.assertRaises(ValueError, node_to_value, typ, nod)

    def test_sequence_node_to_val(self):
        typ = ListOf()
        self.assertEqual(typ.min, 0)
        self.assertEqual(typ.max, None)
        self.assertEqual(typ.repeat, 1)

        typ = TupleOf()
        self.assertEqual(typ.min, 0)
        self.assertEqual(typ.max, None)
        self.assertEqual(typ.repeat, 1)

        typ = ListOf(int, str, bool)
        self.assertEqual(typ.min, 0)
        self.assertEqual(typ.max, None)
        self.assertEqual(typ.repeat, 3)

        typ = TupleOf(int, str, bool)
        self.assertEqual(typ.min, 3)
        self.assertEqual(typ.max, 3)
        self.assertEqual(typ.repeat, 3)

        typ = ListOf(int, str, bool, min=1, max=4, repeat=2)
        self.assertEqual(typ.min, 1)
        self.assertEqual(typ.max, 4)
        self.assertEqual(typ.repeat, 2)

        typ = TupleOf(int, str, bool, min=1, max=4, repeat=2)
        self.assertEqual(typ.min, 1)
        self.assertEqual(typ.max, 4)
        self.assertEqual(typ.repeat, 2)

        typ = TupleOf(int, str, bool, max=4)
        self.assertEqual(typ.min, 0)
        self.assertEqual(typ.max, 4)
        self.assertEqual(typ.repeat, 3)

        typ = ListOf(int, str, bool, min=1)
        self.assertEqual(typ.min, 1)
        self.assertEqual(typ.max, None)
        self.assertEqual(typ.repeat, 3)

        goodls = [
            (TupleOf(str, str), '(x y)', ('x', 'y')),
            (TupleOf(str, int, max=4), '(1 2 3 4)', ('1', 2, '3', 4)),
            (TupleOf(str, min=1, max=3), '(x)', ('x',)),
            (TupleOf(str, min=1, max=3), '(x y)', ('x', 'y')),
            (TupleOf(str, min=1, max=3), '(x y z)', ('x', 'y', 'z')),
            (TupleOf(str, int, repeat=1), '(1)', ('1',)),
            (TupleOf(str, int, repeat=1), '(1 2)', ('1', 2)),
            (TupleOf(str, int, repeat=1), '(1 2 3)', ('1', 2, 3)),
            (TupleOf(str, int, bool, repeat=2), '(1 2 3 4)', ('1', 2, True, 4)),
        ]
        badls = [
            (TupleOf(str, str), '(x)'),
            (TupleOf(str, str), '(x y z)'),
            (TupleOf(str, min=1, max=3), '()'),
            (TupleOf(str, min=1, max=3), '(x y z w)'),
        ]

        for (typ, st, res) in goodls:
            nod = sparse.parse(st)
            val = node_to_value(typ, nod)
            val = resolve_value(val)
            self.assertEqual(val, res)
            self.assertEqual(type(val), type(res))
            if (type(val) == list):
                for (sub1, sub2) in zip(val, res):
                    self.assertEqual(type(sub1), type(sub2))

        for (typ, st) in badls:
            nod = sparse.parse(st)
            self.assertRaises(ValueError, node_to_value, typ, nod)

    def test_wrapping_node_to_val(self):
        nod = sparse.parse('foo')
        val = node_to_value(str, nod)
        self.assertEqual(type(val), str)
        self.assertEqual(val, 'foo')

        nod = sparse.parse('(foo bar)')
        val = node_to_value(list, nod)
        self.assert_(isinstance(val, ArgListWrapper))
        self.assertEqual(val.ls, ['foo', 'bar'])

        nod = sparse.parse('(foo bar)')
        val = node_to_value(tuple, nod)
        self.assertEqual(val, ('foo', 'bar'))

        nod = sparse.parse('(foo ())')
        val = node_to_value(tuple, nod)
        self.assert_(isinstance(val, ArgTupleWrapper))

    def test_value_to_node(self):
        ls = [
            (int, 5, '5'),
            (long, 5, '5'),
            (float, 5.1, '5.1'),
            (bool, False, 'false'),
            (bool, True, 'true'),
            (bool, 0, 'false'),
            (bool, 3, 'true'),
            (str, 'foo', 'foo'),
            (str, 'foo space', '"foo space"'),
            (unicode, 'foo', 'foo'),
            (str, u'foo', 'foo'),
            (str, u'unic\u0153de', u'unic\u0153de'),
            (list, [], '()'),
            (tuple, (), '()'),
            (list, ['foo', 'bar', ('x', 'y')], '(foo bar (x y))'),
            (tuple, ['foo', 'bar', ('x', 'y')], '(foo bar (x y))'),
            (ListOf(bool), [1, 0], '(true false)'),
            (TupleOf(int, bool, repeat=1), [1,1,0], '(1 true false)'),
            (None, 'foo', 'foo'),
            (None, 12, '12'),
            (None, [], '()'),
            (None, (), '()'),
            (None, ['foo', 'bar', ['x']], '(foo bar (x))'),
            (int, None, '(no=value)'),
            (str, None, '(no=value)'),
            (list, None, '(no=value)'),
            (ListOf(), None, '(no=value)'),
            (None, None, '(no=value)'),
            (agent.Agent, builtin.NullAgent(), '/boodle.builtin.NullAgent'),
            (Wrapped(agent.Agent), builtin.NullAgent, '/boodle.builtin.NullAgent'),
        ]

        for (typ, val, res) in ls:
            nod = value_to_node(typ, val)
            st = nod.serialize()
            self.assertEqual(st, res)

    def one_test_resolve(self, arglist, goodls, badls):
        if (goodls):
            for (src, wantls, wantdic) in goodls:
                nod = sparse.parse(src)
                (ls, dic) = arglist.resolve(nod)
                ils = [ resolve_value(val) for val in ls ]
                idic = dict([ (key, resolve_value(val)) for (key,val) in dic.items() ])
                self.assertEqual(ils, wantls)
                self.assertEqual(idic, wantdic)
        if (badls):
            for src in badls:
                nod = sparse.parse(src)
                self.assertRaises(ValueError, arglist.resolve, nod)
        
    def test_resolve(self):
        arglist = ArgList(Arg('x'), Arg('y'))
        goodls = [
            ('(A xx yy)', ['xx', 'yy'], {}),
            ('(A xx ())', ['xx', []], {}),
            ('(A ((xx)) (yy))', [[['xx']], ['yy']], {}),
        ]
        badls = [
            'A',
            '()',
            '(A)',
            '(A xx)',
            '(A xx yy z=1)',
            '(A xx yy zz)',
            '(A xx x=xxx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg(name='x', type=int), Arg(name='y', type=str))
        goodls = [
            ('(A 1 yy)', [1, 'yy'], {}),
            ('(A -5 "1 2 3")', [-5, '1 2 3'], {}),
            ('(A y=yy x=1)', [1, 'yy'], {}),
            ('(A 1 y=yy)', [1, 'yy'], {}),
        ]
        badls = [
            '(A)',
            '(A 1)',
            '(A xx yy)',
            '(A 1 yy zz)',
            '(A 1 ())',
        ]
        self.one_test_resolve(arglist, goodls, badls)
        
        arglist = ArgList(Arg(name='x', type=str), ArgExtra(ListOf(int)))
        goodls = [
            ('(A xx)', ['xx'], {}),
            ('(A xx 1 2 3)', ['xx', 1, 2, 3], {}),
            ('(A 0 1 2 3)', ['0', 1, 2, 3], {}),
        ]
        badls = [
            '(A xx 1 2 z)', '(A xx z 2 3)',
            '(A xx 1 2 3 z=0)',
            '(A 1 2 3 x=xx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg(name='x', type=str), ArgExtra(TupleOf(int, int)))
        goodls = [
            ('(A xx 1 2)', ['xx', 1, 2], {}),
        ]
        badls = [
            '(A xx)',
            '(A xx 1 2 3)',
            '(A xx 1 2 z)', '(A xx z 2 3)',
            '(A xx 1 2 3 z=0)',
            '(A 1 2 3 x=xx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg(name='x', type=str), ArgExtra(ListOf(int, str, repeat=1, min=1, max=3)))
        goodls = [
            ('(A xx 1)', ['xx', 1], {}),
            ('(A xx 1 2)', ['xx', 1, '2'], {}),
            ('(A xx 1 2 3)', ['xx', 1, '2', '3'], {}),
        ]
        badls = [
            '(A xx)',
            '(A xx 1 2 3 4)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg(type=int), Arg(type=str))
        goodls = [
            ('(A 1 yy)', [1, 'yy'], {}),
        ]
        badls = [
            '(A)',
            '(A 1)',
            '(A 1 ())',
            '(A 1 yy zz)',
            '(A xx yy)',
            '(A 1 yy z=zz)',
            '(A x=1 y=yy)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg(type=ListOf(int)), Arg(type=list))
        goodls = [
            ('(A () ())', [[], []], {}),
            ('(A (1) (yy))', [[1], ['yy']], {}),
            ('(A (1 2 3) (yy () 33))', [[1,2,3], ['yy',[],'33']], {}),
        ]
        badls = [
            '(A)',
            '(A 1)',
            '(A 1 ())',
            '(A (x) ())',
            '(A (()) ())',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(x=Arg(), y=Arg())
        goodls = [
            ('(A x=xx y=yy)', [], {'x':'xx', 'y':'yy'}),
        ]
        badls = [
            '(A)',
            '(A xx)',
            '(A xx yy)',
            '(A xx yy zz)',
            '(A x=xx)',
            '(A y=yy)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg('x', default='xd'), Arg('y', default='yd'))
        goodls = [
            ('(A xx yy)', ['xx', 'yy'], {}),
            ('(A xx y=yy)', ['xx', 'yy'], {}),
            ('(A x=xx y=yy)', ['xx', 'yy'], {}),
            ('(A xx)', ['xx', 'yd'], {}),
            ('(A x=xx)', ['xx', 'yd'], {}),
            ('(A y=yy)', ['xd', 'yy'], {}),
            ('(A)', ['xd', 'yd'], {}),
        ]
        badls = [
            '(A xx yy z=1)',
            '(A xx yy zz)',
            '(A xx x=xxx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(x=Arg(default='xd'), y=Arg(default='yd'))
        goodls = [
            ('(A x=xx)', [], {'x':'xx'}),
            ('(A y=yy)', [], {'y':'yy'}),
            ('(A x=xx y=yy)', [], {'x':'xx', 'y':'yy'}),
            ('(A)', [], {}),
        ]
        badls = [
            '(A xx)',
            '(A xx yy)',
            '(A xx y=yy)',
            '(A xx yy z=1)',
            '(A xx yy zz)',
            '(A xx x=xxx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(Arg('x', default='xd', optional=False), Arg('y', default='yd'))
        goodls = [
            ('(A xx yy)', ['xx', 'yy'], {}),
            ('(A xx y=yy)', ['xx', 'yy'], {}),
            ('(A x=xx y=yy)', ['xx', 'yy'], {}),
            ('(A xx)', ['xx', 'yd'], {}),
            ('(A x=xx)', ['xx', 'yd'], {}),
            ('(A y=yy)', ['xd', 'yy'], {}),
            ('(A)', ['xd', 'yd'], {}),
        ]
        badls = [
            '(A xx yy z=1)',
            '(A xx yy zz)',
            '(A xx x=xxx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

        arglist = ArgList(x=Arg(default='xd', optional=False), y=Arg(default='yd'))
        goodls = [
            ('(A x=xx)', [], {'x':'xx'}),
            ('(A y=yy)', [], {'x':'xd', 'y':'yy'}),
            ('(A x=xx y=yy)', [], {'x':'xx', 'y':'yy'}),
            ('(A)', [], {'x':'xd'}),
        ]
        badls = [
            '(A xx)',
            '(A xx yy)',
            '(A xx y=yy)',
            '(A xx yy z=1)',
            '(A xx yy zz)',
            '(A xx x=xxx)',
        ]
        self.one_test_resolve(arglist, goodls, badls)

    def test_basetype_serialize(self):
        ls = [
            int, str, bool, float, list, tuple,
            sample.Sample, agent.Agent,
        ]
        
        for typ in ls:
            val = type_to_node(typ)
            typ2 = node_to_type(val)
            self.assertEqual(typ, typ2)

        ls = [
            (long,int), (unicode,str),
            (builtin.NullAgent, agent.Agent),
            (sample.MixinSample, sample.Sample),
        ]
        
        for (typ, restyp) in ls:
            val = type_to_node(typ)
            typ2 = node_to_type(val)
            self.assertEqual(restyp, typ2)
        
    def test_wrapped_serialize(self):
        typ = Wrapped(int)
        val = type_to_node(typ)
        typ2 = node_to_type(val)
        self.assert_(isinstance(typ2, Wrapped))
        self.assertEqual(typ2.type, int)
        
        typ = Wrapped(ListOf(int, bool))
        val = type_to_node(typ)
        typ2 = node_to_type(val)
        self.assert_(isinstance(typ2, Wrapped))
        self.assert_(isinstance(typ2.type, ListOf))
        self.assertEqual(typ2.type.types, (int, bool))
        
    def test_seqtype_serialize(self):
        ls = [
            ListOf(),
            ListOf(int),
            ListOf(int, str, bool, float),
            ListOf(int, str, min=1),
            ListOf(int, str, max=5),
            ListOf(int, str, bool, repeat=2),
            ListOf(int, str, bool, min=1, max=5, repeat=2),
            TupleOf(),
            TupleOf(int),
            TupleOf(int, str, bool, float),
            TupleOf(int, str, min=1),
            TupleOf(int, str, max=5),
            TupleOf(int, str, bool, repeat=2),
            TupleOf(int, str, bool, min=1, max=5, repeat=2),
        ]

        for typ in ls:
            val = typ.to_node()
            typ2 = node_to_type(val)
            self.assert_types_identical(typ, typ2)
            
        typ = ListOf(
            TupleOf(int, str, bool),
            TupleOf(int, str, min=1, max=5, repeat=1),
            ListOf()
        )
        val = typ.to_node()
        typ2 = node_to_type(val)
        self.assertEqual(repr(typ), repr(typ2))
