# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import StringIO
import unittest
import sets

from boopak import version
from boopak import pinfo
from boopak.pinfo import Metadata, Resources, PackageLoadError
from boopak.pinfo import parse_package_name, parse_resource_name
from boopak.pinfo import parse_package_version_spec
from boopak.pinfo import build_safe_pathname, encode_package_name, deunicode
from boopak.pinfo import dict_accumulate, dict_all_values

class TestPInfo(unittest.TestCase):

    def test_memfile(self):
        dat = 'xyzzy\nplugh\n'
        mfile = pinfo.MemFile(dat, '.txt', 'Stuff')
        self.assertEqual(mfile.suffix, '.txt')
        
        fl = mfile.open()
        res = fl.read()
        fl.close()
        self.assertEqual(dat, res)
        
        fl = mfile.open()
        res = fl.read()
        fl.close()
        self.assertEqual(dat, res)

    def test_metadata(self):
        source = """# Metadata test file

one: 1
two: 2
dc.three: 3
one: 11

four : Four
"""
        fl = StringIO.StringIO(source)
        meta = Metadata('<unit test>', fl)
        fl.close()

        self.assertEqual(meta.get_one('one'), '1')
        self.assertEqual(meta.get_one('dc.three'), '3')
        self.assertEqual(meta.get_one('four'), 'Four')
        self.assertEqual(meta.get_one('four', 'def'), 'Four')
        self.assertEqual(meta.get_one('missing'), None)
        self.assertEqual(meta.get_one('missing', 'def'), 'def')

        self.assertEqual(meta.get_all('two'), ['2'])
        self.assertEqual(meta.get_all('one'), ['1','11'])
        self.assertEqual(meta.get_all('missing'), [])

        ls = meta.keys()
        self.assertEqual(len(ls), len(meta))
        ls.sort()
        self.assertEqual(ls, ['dc.three', 'four', 'one', 'two'])

        meta2 = meta.clone()
        self.assertEqual(len(meta2), len(meta))
        for key in meta.keys():
            self.assertEqual(meta.get_all(key), meta2.get_all(key))

    def test_metadata_empty(self):
        meta = Metadata('<test>')
        self.assertEqual(len(meta), 0)
        self.assertEqual(meta.get_all('foo'), [])
        self.assertEqual(meta.keys(), [])
    
    def test_metadata_modify(self):
        meta = Metadata('<test>')
        meta.add('one', 'two')
        
        meta2 = meta.clone()
        meta2.add('one', 'four')
        self.assertEqual(meta2.get_all('one'), ['two', 'four'])
        
        meta.add('one', 'three')
        self.assertEqual(meta.get_all('one'), ['two', 'three'])
        self.assertEqual(meta2.get_all('one'), ['two', 'four'])

        meta.delete_all('one')
        meta.delete_all('nonexistent')
        self.assertEqual(meta.get_all('one'), [])
        self.assertEqual(meta2.get_all('one'), ['two', 'four'])

    def dump_to_string(self, obj, *args):
        fl = StringIO.StringIO()
        obj.dump(fl, *args)
        fl.seek(0)
        return fl.read()
        
    def test_metadata_dump(self):
        meta = Metadata('<test>')
        
        val = self.dump_to_string(meta)
        self.assertEqual(val, '')
        val = self.dump_to_string(meta, 'I am a comment.')
        self.assertEqual(val, '# I am a comment.\n\n')
        val = self.dump_to_string(meta, ['one', 'two'])
        self.assertEqual(val, '# one\n# two\n\n')

        meta.add('one', 'two')
        val = self.dump_to_string(meta)
        self.assertEqual(val, 'one: two\n')
        meta.add('one', 'three')
        val = self.dump_to_string(meta)
        self.assertEqual(val, 'one: two\none: three\n')
    
    def test_metadata_unicode(self):
        meta = Metadata('<test>')

        meta.add(u'alpha', u'is \u03b1')
        val = self.dump_to_string(meta)
        self.assertEqual(val, u'alpha: is \u03b1\n')

        source = """# Metadata test file
alpha: is \xce\xb1
"""
        fl = StringIO.StringIO(source)
        meta = Metadata('<unit test>', fl)
        fl.close()

        self.assertEqual(meta.get_one('alpha'), u'is \u03b1')
        
    def test_resources(self):
        source = """# Resources test file
        
    # Another comment

:res1
# comment
one: 1
two: 2
two: II

:Foo.Bar
one: eleven
"""
        fl = StringIO.StringIO(source)
        ress = Resources('<unit test>', fl)
        fl.close()
        
        self.assert_(ress.get('foo') is None)

        res = ress.get('res1')
        self.assert_(res in ress.resources())
        self.assertEqual(res.get_one('one'), '1')
        self.assertEqual(res.get_one('two'), '2')
        self.assertEqual(res.get_all('two'), ['2', 'II'])
        self.assertEqual(res.get_one('missing'), None)
        self.assertEqual(res.get_one('missing', 'def'), 'def')
        
        res = ress.get('Foo.Bar')
        self.assert_(res in ress.resources())
        self.assertEqual(res.get_one('one'), 'eleven')
        self.assertEqual(res.get_one('two'), None)

        keys = ress.keys()
        self.assertEquals(len(keys), 2)
        self.assert_('res1' in keys and 'Foo.Bar' in keys)

    def test_resources_empty(self):
        ress = Resources('<test>')
        self.assertEqual(len(ress), 0)
        self.assert_(ress.get('foo') is None)
        self.assertEqual(ress.keys(), [])
        self.assertEqual(ress.resources(), [])

    def test_resources_bad(self):
        ls = [
            'key: without-section\n',
            ':key1\n : key1 \n',
            ':key1\nbad line\n',
            ':key1\nanother bad: line\n',
            ':bad-key\n',
        ]

        for source in ls:
            fl = StringIO.StringIO(source)
            self.assertRaises(PackageLoadError, Resources, '<test>', fl)

    def test_resources_create(self):
        ress = Resources('<test>')
        foo = ress.create('foo')
        ress.create('bar')
        ress.create('x1.x2.x3')
        self.assertRaises(ValueError, ress.create, '$')
        self.assertRaises(ValueError, ress.create, 'foo')

        self.assertEqual(foo, ress.get('foo'))
    
    def test_resources_modify(self):
        ress = Resources('<test>')
        foo = ress.create('foo')
        
        foo.add('one', 'two')
        
        foo.add('one', 'three')
        self.assertEqual(foo.get_all('one'), ['two', 'three'])

        foo.delete_all('one')
        foo.delete_all('nonexistent')
        self.assertEqual(foo.get_all('one'), [])

    def test_resources_dump(self):
        ress = Resources('<test>')
        
        val = self.dump_to_string(ress)
        self.assertEqual(val, '')
        val = self.dump_to_string(ress, 'I am a comment.')
        self.assertEqual(val, '# I am a comment.\n\n')
        val = self.dump_to_string(ress, ['one', 'two'])
        self.assertEqual(val, '# one\n# two\n\n')

        res = ress.create('foo')
        val = self.dump_to_string(ress)
        self.assertEqual(val, ':foo\n\n')

        res.add('one', 'two')
        val = self.dump_to_string(ress)
        self.assertEqual(val, ':foo\none: two\n\n')

    def test_resources_build_tree(self):
        ress = Resources('<test>')
        dic = ress.build_tree()
        self.assertEqual(dic, {})

        ress.create('one')
        dic = ress.build_tree()
        self.assertEqual(dic, {'one':'one'})
        
        ress.create('two')
        dic = ress.build_tree()
        self.assertEqual(dic, {'one':'one', 'two':'two'})
        
        ress.create('foo.three')
        dic = ress.build_tree()
        self.assertEqual(dic, {'one':'one', 'two':'two',
            'foo':{'three':'foo.three'}})
        
        ress.create('foo.four')
        dic = ress.build_tree()
        self.assertEqual(dic, {'one':'one', 'two':'two',
            'foo':{'three':'foo.three', 'four':'foo.four'}})
        
        ress.create('x.y.z')
        dic = ress.build_tree()
        self.assertEqual(dic, {'one':'one', 'two':'two',
            'foo':{'three':'foo.three', 'four':'foo.four'},
            'x':{'y':{'z':'x.y.z'}}})
            
        ress.create('foo.four.bad')
        self.assertRaises(ValueError, ress.build_tree)

    def test_parse_package_version_spec(self):
        valid_list = [
            'foo:1.0', 'foo:2-', 'foo:-3.1', 'foo:2-4',
            'foo::1.2.3', 'foo.bar::1.5.6a',
        ]
        invalid_list = [
            '0x', ':foo', 'foo:0.1', 'foo:1.2.3',
            'foo::0.1', 'foo:::1.0', 'foo:1:2',
            'foo: 1.0', 'foo :1.0', 'foo: :1.0', 'foo:: 1.0',
        ]
        
        (pkg, vers) = parse_package_version_spec('x.y.z')
        self.assertEqual(pkg, 'x.y.z')
        self.assertEqual(vers, None)
        
        (pkg, vers) = parse_package_version_spec('x.y.z:2.4')
        self.assertEqual(pkg, 'x.y.z')
        self.assert_(isinstance(vers, version.VersionSpec))
        self.assertEqual(vers, version.VersionSpec('2.4'))
        
        (pkg, vers) = parse_package_version_spec('x.y.z::2.4.6')
        self.assertEqual(pkg, 'x.y.z')
        self.assert_(isinstance(vers, version.VersionNumber))
        self.assertEqual(vers, version.VersionNumber('2.4.6'))

        for val in valid_list:
            parse_package_version_spec(val)
        for val in invalid_list:
            self.assertRaises(ValueError, parse_package_version_spec, val)
        
    def test_parse_package_name(self):
        valid_list = [
            ('hello', ['hello']),
            ('h.e.l.l.o', ['h', 'e', 'l', 'l', 'o']),
            ('x_00t_99', ['x_00t_99']),
            ('t0.t1', ['t0', 't1']),
            ('_._005_.a', ['_', '_005_', 'a']),
        ]
        invalid_list = [
            '', ' ',
            '.', 'a.', '.b', '.c.', 'd..e', '..',
            'x ', ' y', 'a b', 'a. b', 'a .b',
            '0', '0x', 'a.0', 'x.y.9z',
            'A', 'Hello', 'hello.There', 'olleH',
            'a,b', 'a-b', 'a+b', 'a/b', 'a\\b',
        ]

        for (name, result) in valid_list:
            res = parse_package_name(name)
            self.assertEqual(res, result)

        for name in invalid_list:
            self.assertRaises(ValueError, parse_package_name, name)
            
    def test_parse_resource_name(self):
        valid_list = [
            ('hello', ['hello']),
            ('Hello.FOO.X0', ['Hello', 'FOO', 'X0']),
            ('X', ['X']),
            ('h.e.l.l.o', ['h', 'e', 'l', 'l', 'o']),
            ('x_00t_99', ['x_00t_99']),
            ('t0.t1', ['t0', 't1']),
            ('_._005_.a', ['_', '_005_', 'a']),
        ]
        invalid_list = [
            '', ' ',
            '.', 'a.', '.b', '.c.', 'd..e', '..',
            'x ', ' y', 'a b', 'a. b', 'a .b',
            '0', '0x', 'a.0', 'x.y.9z',
            'a,b', 'a-b', 'a+b', 'a/b', 'a\\b',
        ]

        for (name, result) in valid_list:
            res = parse_resource_name(name)
            self.assertEqual(res, result)

        for name in invalid_list:
            self.assertRaises(ValueError, parse_resource_name, name)
            
    def test_dict_accumulate(self):
        dic = {}
        res = dict_accumulate(dic, 1, 'A')
        self.assertEqual(res, True)
        res = dict_accumulate(dic, 1, 'B')
        self.assertEqual(res, False)
        res = dict_accumulate(dic, 2, 222)
        self.assertEqual(res, True)
        res = dict_accumulate(dic, 3, [])
        self.assertEqual(res, True)
        res = dict_accumulate(dic, 3, None)
        self.assertEqual(res, False)

        target = { 3:[[],None], 2:[222], 1:['A','B'] }
        self.assertEqual(dic, target)

    def test_dict_all_values(self):
        res = dict_all_values({})
        self.assertEqual(res, [])

        dic = {1:11, 2:22, 3:{3:33, 31:331}, 4:44, 5:{55:55}}
        res = dict_all_values(dic)
        res.sort()
        self.assertEqual(res, [11, 22, 33, 44, 55, 331])

        ls = [0]
        res = dict_all_values(dic, ls)
        res.sort()
        self.assertEqual(res, [0, 11, 22, 33, 44, 55, 331])
        self.assert_(res is ls)

    def test_encode_package_name(self):
        (pkgname, vers) = ('xy.zzy', version.VersionNumber('1.2.3a.four'))
        val = encode_package_name(pkgname, vers)
        self.assertEqual(val, '_BooPkg_xy_zzyV1_2_3a_four')

        ls = [
            ('x.y_z', '1.1._'),
            ('x.y.z', '1.1._'),
            ('x.y.z1', '1.1._'),
            ('x.y.z', '11.1._'),
            ('x.y.z', '1.11._'),
            ('x.y.z', '1.1.1_'),
            ('x.y.z', '1.1.a'),
            ('x.y.z', '1.1.A'),
            ('x.y.z', '1.1.U'),
            ('x.y.z', '1.1.C'),
            ('x.y.z', '1.1.CU'),
        ]
        set = sets.Set()

        for (pkgname, vers) in ls:
            vers = version.VersionNumber(vers)
            val = encode_package_name(pkgname, vers)
            self.assert_(pinfo.ident_name_regexp.match(val))
            set.add(val)

        self.assertEqual(len(set), len(ls))

    def test_build_safe_pathname(self):
        invalid_list = [
            '/', '/foo', 'a\\b', 'a/../b', '../xyz', '..',
        ]
        valid_list = [
            ('', '/tmp'),
            ('.', '/tmp'),
            ('foo', '/tmp/foo'),
            ('foo/', '/tmp/foo'),
            ('a/b/c', '/tmp/a/b/c'),
            ('a/././c/.', '/tmp/a/c'),
            ('a///c//', '/tmp/a/c'),
        ]

        for name in invalid_list:
            self.assertRaises(ValueError, build_safe_pathname, 
                '/tmp', name)
        for (name, result) in valid_list:
            val = build_safe_pathname('/tmp', name)
            self.assertEqual(val, result)
        val = build_safe_pathname('/tmp', u'foo')
        self.assertEqual(type(val), str)
            
    def test_deunicode(self):
        val = ' hello '
        self.assertEqual(deunicode(val), ' hello ')
        val = 'alpha is \xce\xb1'
        self.assertEqual(deunicode(val), u'alpha is \u03b1')
        val = '\xef\xbb\xbfalpha is \xce\xb1'
        self.assertEqual(deunicode(val), u'alpha is \u03b1')
