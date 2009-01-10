# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import unittest

from boopak.version import VersionNumber, VersionSpec, VersionFormatError

class TestVersion(unittest.TestCase):

    def test_version_number_init(self):
        valid_args = [
            (), (1,), (1,0), (1,1), (1,2), (2,10),
            (1,2,3), (1,2,3,4), (1,2,0,-10),
            (1,2,'3'), (1,2,'xyzzy'), (1,2,'12_+-','_9'),
            (1,2,'',''), (1,2,'','x'), (1,2,'x',''), (1,2,'x','x'),
        ]
        invalid_args = [
            (0,), (-1,), (0,-1), (1,-2),
            (1,'2'), ([],),
            (1,2,'*'), (1,2,'z/'),
            (1,2,'.3'), (1,2,'.'), (1,2,''),
        ]
        for tup in valid_args:
            vers = VersionNumber(*tup)
            self.assert_(vers == vers)
            self.assert_(vers <= vers)
            self.assert_(vers >= vers)
            self.failIf(vers != vers)
            self.failIf(vers < vers)
            self.failIf(vers > vers)
        for tup in invalid_args:
            self.assertRaises(VersionFormatError, VersionNumber, *tup)

    def test_version_number_string(self):
        valid_args = [
            '', '1', '2', '10', '99', '1.0', '1.5', '1.10',
            '1.2.3', '1.2.3.4', '1.2.0.-10',
            '1.2.xyzzy', '1.2.12_+-._9',
            '1.2..', '1.2..x', '1.2.x..', '1.2.x.x',
            u'1.2.unicode',
        ]
        invalid_args = [
            '0', '-1', '1.-1', '1.*', '1.2.*',
            'x', '1.x', 'x1', '1x',
            '1.2.', '1.2,', '1.2. ',
            u'1.2.unic\u00F8de',
        ]

        for val in valid_args:
            vers = VersionNumber(val)
            self.assert_(vers == vers)
            self.assert_(vers <= vers)
            self.assert_(vers >= vers)
            self.failIf(vers != vers)
            self.failIf(vers < vers)
            self.failIf(vers > vers)
            if ('.' in val):
                self.assert_(str(vers) == val)
                newval = str(vers.major) + '.' + str(vers.minor)
                if (vers.release != None):
                    newval = newval + '.' + vers.release
                self.assertEqual(newval, val)

        for val in invalid_args:
            self.assertRaises(VersionFormatError, VersionNumber, val)

    def test_version_number_simple(self):
        vers = VersionNumber()
        self.assertEqual((1,0), (vers.major, vers.minor))
        self.assertEqual('1.0', str(vers))
        self.assertEqual(vers.release, None)

        self.assertNotEqual(vers, None)
        self.assertNotEqual(None, vers)

        vers = VersionNumber(1)
        self.assertEqual((1,0), (vers.major, vers.minor))
        self.assertEqual('1.0', str(vers))
        self.assertEqual(vers.release, None)

        vers = VersionNumber(2)
        self.assertEqual((2,0), (vers.major, vers.minor))
        self.assertEqual('2.0', str(vers))
        self.assertEqual(vers.release, None)

        vers = VersionNumber(2,0)
        self.assertEqual((2,0), (vers.major, vers.minor))
        self.assertEqual('2.0', str(vers))
        self.assertEqual(vers.release, None)

        vers = VersionNumber(2,1)
        self.assertEqual((2,1), (vers.major, vers.minor))
        self.assertEqual('2.1', str(vers))
        self.assertEqual(vers.release, None)

        vers = VersionNumber(999,1000)
        self.assertEqual((999,1000), (vers.major, vers.minor))
        self.assertEqual('999.1000', str(vers))
        self.assertEqual(vers.release, None)

    def test_version_number_extra(self):
        vers = VersionNumber(2,3,4,'v',6)
        self.assertEqual(vers, vers)

        self.assertEqual((2,3), (vers.major, vers.minor))
        self.assertEqual('2.3.4.v.6', str(vers))
        self.assertEqual(vers.release, '4.v.6')

    def test_version_number_compare(self):
        vers = VersionNumber()
        v1 = VersionNumber(1)
        v10 = VersionNumber(1,0)
        v2 = VersionNumber(2)
        v21 = VersionNumber(2,1)
        v210 = VersionNumber(2,1,0)
        v213 = VersionNumber(2,1,3)
        v22 = VersionNumber(2,2)

        self.assertEqual(vers, v1)
        self.assertEqual(vers, v10)
        self.assertEqual(v1, v10)

        self.assertNotEqual(vers, v2)
        self.assertNotEqual(v1, v2)
        self.assertNotEqual(v10, v2)
        self.assertNotEqual(v2, v21)
        self.assertNotEqual(v21, v22)
        self.assertNotEqual(v21, v213)
        self.assertNotEqual(v22, v213)
        self.assertNotEqual(v21, v210)

        self.assert_(vers < v2)
        self.assert_(v1 < v2)
        self.assert_(v10 < v2)
        self.assert_(vers < v21)
        self.assert_(v1 < v21)
        self.assert_(v10 < v21)
        self.assert_(v21 < v210)
        self.assert_(v21 < v213)
        self.assert_(v210 < v213)
        self.assert_(v213 < v22)

        self.assert_(vers <= v2)
        self.assert_(v1 <= v2)
        self.assert_(v10 <= v2)
        self.assert_(vers <= v21)
        self.assert_(v1 <= v21)
        self.assert_(v10 <= v21)
        self.assert_(v21 <= v210)
        self.assert_(v21 <= v213)
        self.assert_(v210 <= v213)
        self.assert_(v213 <= v22)

        self.assert_(v2 > v1)
        self.assert_(v2 >= v1)
        self.assert_(v2 != v1)
        self.failIf(v1 > v2)
        self.failIf(v1 >= v2)
        self.failIf(v1 == v2)

        self.assert_(v22 > v21)
        self.assert_(v22 >= v21)
        self.assert_(v22 != v21)
        self.failIf(v21 > v22)
        self.failIf(v21 >= v22)
        self.failIf(v21 == v22)

        self.assert_(v213 > v21)
        self.assert_(v213 >= v21)
        self.assert_(v213 != v21)
        self.failIf(v21 > v213)
        self.failIf(v21 >= v213)
        self.failIf(v21 == v213)

    def test_version_number_hetero(self):
        vers = VersionNumber('3.5')

        self.assert_(vers == '3.5')
        self.assert_(vers != '3.5.1')
        self.assert_(vers != '3.5.x')
        self.assert_(vers > '3.4')
        self.assert_(vers < '3.6')
        self.assert_(vers >= '3.5')
        self.assert_(vers <= '3.5')
        self.assert_(vers > 3)
        self.assert_(vers < 4)

        self.failIf(vers != '3.5')
        self.failIf(vers == '3.5.1')
        self.failIf(vers < '3.4')
        self.failIf(vers > '3.6')
        self.failIf(vers < 3)
        self.failIf(vers > 4)
    
    def test_version_number_sort(self):
        ls = [
            VersionNumber(10),
            VersionNumber(5, 9),
            VersionNumber(5, 1, 10),
            VersionNumber(5, 1, 2),
            VersionNumber(5, 1, 1, 1),
            VersionNumber(5, 1, 1, 0),
            VersionNumber(5, 1, 1),
            VersionNumber(5, 1),
            VersionNumber(5),
            VersionNumber(3, 10),
            VersionNumber(3, 6),
            VersionNumber(3, 5),
            VersionNumber(3, 0),
            VersionNumber(1),
        ]
        target = ['1.0', '3.0', '3.5', '3.6', '3.10', 
            '5.0', '5.1', '5.1.1', '5.1.1.0', '5.1.1.1', '5.1.2', '5.1.10', 
            '5.9', 
            '10.0']
            
        ls.sort()
        res = [ str(val) for val in ls ]
        self.assertEqual(res, target)

        ls = [ VersionNumber(val) for val in target ]
        ls.reverse()
        ls.sort()
        res = [ str(val) for val in ls ]
        self.assertEqual(res, target)

    def test_version_number_sort_strings(self):
        orig = [
            '1.2.x', '1.2.10', '1.2.2', '1.2.02', '1.2.0', '1.2..', '1.2', 
        ]
        ls = [ VersionNumber(val) for val in orig ]
        ls.sort()
        
        res = [ str(val) for val in ls ]
        self.assertEqual(res, ['1.2', '1.2.0', '1.2.02',
            '1.2.2', '1.2.10', '1.2..', '1.2.x', ])

    def test_version_number_intstr_similar(self):
        v1 = VersionNumber(1,3)
        v2 = VersionNumber('1.3')
        self.assert_(v1 == v2)
        self.failIf(v1 != v2)

        v1 = VersionNumber(1,3,'5')
        v2 = VersionNumber('1.3.5')
        self.assert_(v1 == v2)
        self.failIf(v1 != v2)

        v1 = VersionNumber(1,3,'05')
        v2 = VersionNumber('1.3.05')
        self.assert_(v1 == v2)
        self.failIf(v1 != v2)

        v1 = VersionNumber(1,2,3)
        v2 = VersionNumber(1,2,'3')

        self.assert_(v1 != v2)
        self.assert_(v1 < v2)
        self.assert_(v1 <= v2)
        self.failIf(v1 == v2)
        self.failIf(v1 > v2)
        self.failIf(v1 >= v2)

    def test_version_spec_init(self):
        valid_args = [ 
            '', '1', '2', '3.0', '3.1', '99.101',
            '1.', '1.5.',
            '2-', '2.3-', '23.456-',
            '-2', '-2.3', '-23.456',
            '2-3', '2.0-3', '2-3.0', '2.0-3.0', '4.5-6.10',
            '-1,2,3-4,5.1-6.2,6.7.,7.5-',
            u'1.2'
        ]
        invalid_args = [
            'x', '0x5', '0', '0.0', '0.1',
            '-0', '0-', '-0.1', '0.1-', '0.0.', '-', 
            '1--2', '1--', '--2',
            ' ', ' 1', '1 ',
            '2-3.', '2.-3', '2..3', '1.2.3',
            ',', '1,', ',1', '1,,2',
            u'1.\u00F8'
        ]
        valid_tups = [ 
            (), (1,), (1,0), (2,), (2,1), 
        ]
        invalid_tups = [ 
            (None,), (1,'x'), (1,2,3),
            (0,), (0,0), (-1,), (1,-1), 
        ]
        for val in valid_args:
            vers = VersionSpec(val)
        for val in invalid_args:
            self.assertRaises(VersionFormatError, VersionSpec, val)
        for tup in valid_tups:
            vers = VersionSpec(*tup)
        for tup in invalid_tups:
            self.assertRaises(VersionFormatError, VersionSpec, *tup)

    def test_version_spec_compare(self):
        ls = [
            VersionSpec('1'),
            VersionSpec('1-'),
            VersionSpec('-1'),
            VersionSpec('1-1.2'),
            VersionSpec('1,2'),
            VersionSpec('1-,2'),
        ]

        for ix in range(len(ls)):
            for jx in range(len(ls)):
                if (ix == jx):
                    self.assert_(ls[ix] == ls[jx])
                    self.failIf(ls[ix] != ls[jx])
                else:
                    self.failIf(ls[ix] == ls[jx])
                    self.failIf(ls[jx] == ls[ix])
                    self.assert_(ls[ix] != ls[jx])
                    self.assert_(ls[jx] != ls[ix])

        s1 = VersionSpec('1-')
        s2 = VersionSpec()
        self.assert_(s1 == s2)
        self.failIf(s1 != s2)

        s1 = VersionSpec('1,2')
        s2 = VersionSpec('1,2')
        self.assert_(s1 == s2)
        self.failIf(s1 != s2)
    
    def test_version_spec_strform(self):
        ls = [ '3.1', '3.1-', '-3.1', '3.1-3.2' ]
        for val in ls:
            vers = VersionSpec(val)
            self.assertEqual(str(vers), val)
        
        vers = VersionSpec('3')
        self.assertEqual(str(vers), '3.0')
        
        vers = VersionSpec('3.4-3.4')
        self.assertEqual(str(vers), '3.4.')
    
    def test_version_spec_match(self):
        ls = [
            ('3',
                ['3', '3.0', '3.0.0', '3.0.1', '3.0.x', '3.1', '3.1.0'],
                ['2.9', '4', '4.0']),
            ('3.5',
                ['3.5', '3.5.1', '3.5.x', '3.6', '3.99', '3.99.1'],
                ['3.4', '3', '4', '4.0', '4.2', '2.5', '2']),
            ('3.',
                ['3', '3.0', '3.0.0', '3.0.1', '3.0.x'],
                ['2.9', '3.1', '3.1.0']),
            ('3.5.',
                ['3.5', '3.5.1', '3.5.x', '3.5.9.10'],
                ['3.4', '3', '3.6', '3.6.1', '3.50', '4', '4.0', '4.2',
                    '2.5', '2']),
            ('3.5-',
                ['3.5', '3.5.1', '3.5.x', '3.6', '3.99', '3.99.1',
                    '4', '4.0', '4.2'],
                ['3.4', '3', '2.5', '2']),
            ('-3.5',
                ['3.4', '3', '2.5', '2', 
                    '3.5', '3.5.1', '3.5.x'],
                ['4', '4.0', '4.2', '6.0.x', '3.6', '3.99', '3.99.1']),
            ('3.5-4.1',
                ['3.5', '3.5.1', '3.5.x', '3.6', '3.99', '3.99.1',
                    '4', '4.0', '4.1', '4.1.9'],
                ['3.4', '3', '2.5', '2', '4.2', '4.3', '5']),
            ('-2.3,5,7.3.,9.9-10.1,13.5-',
                ['1.0', '1.9', '2.0', '2.3', '2.3.9', '5', '5.0',
                    '5.1', '5.9', '7.3', '7.3.9', '9.9', '9.10',
                    '10.0.1', '10.1', '10.1.9', '13.5', '13.9',
                    '14', '99.99', ],
                ['2.4', '2.9', '3', '4', '4.9', '6', '6.0', '7', '7.2',
                    '7.4', '9', '9.8', '10.2', '12', '13.4', ]),
        ]

        for (specstr, goodlist, badlist) in ls:
            spec = VersionSpec(specstr)
            for val in goodlist:
                vnum = VersionNumber(val)
                self.assert_(spec.match(val))
                self.assert_(spec.match(vnum))
                self.assert_(vnum.match(spec))
            for val in badlist:
                vnum = VersionNumber(val)
                self.assert_(not spec.match(val))
                self.assert_(not spec.match(vnum))
                self.assert_(not vnum.match(spec))

    def test_version_number_spec_cmp(self):
        num = VersionNumber()
        spec = VersionSpec()
        def try_equal(v1, v2):
            return (v1 == v2)
        def try_less(v1, v2):
            return (v1 < v2)
            
        self.failIf(spec == num)
        self.failIf(num == spec)
        self.assert_(spec != num)
        self.assert_(num != spec)
        self.assertRaises(TypeError, try_less, num, spec)
        self.assertRaises(TypeError, try_less, spec, num)
