import unittest
import inspect

from boopak.argdef import *

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
        
    def test_clone_arg(self):
        origarg = Arg()
        arg = origarg.clone()
        self.assertFalse(arg is origarg)
        
        self.assert_(arg.index is None)
        self.assert_(arg.name is None)
        self.assert_(arg.type is None)
        self.assert_(arg.description is None)
        self.assert_(arg.hasdefault is False)
        self.assert_(arg.default is None)
        self.assert_(arg.optional is False)
        
        origarg = Arg(name='foo', index=2, type=float, default=1.5,
            description='Argument')
        arg = origarg.clone()
        self.assertFalse(arg is origarg)
        
        self.assertEqual(arg.index, 2)
        self.assertEqual(arg.name, 'foo')
        self.assertEqual(arg.type, float)
        self.assertEqual(arg.description, 'Argument')
        self.assert_(arg.hasdefault is True)
        self.assertEqual(arg.default, 1.5)
        self.assert_(arg.optional is True)

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
        self.assertFalse(arglist is arglist2)
        
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
