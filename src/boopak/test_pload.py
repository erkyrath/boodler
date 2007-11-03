import os.path
import unittest
import tempfile
import sets

from boopak import pload
from boopak import collect
from boopak import version
from boopak import pinfo

collection = {}
def list_collection():
	ls = []
	for name in collection:
		vers = max(collection[name].keys())
		ls.append( (name, vers) )
	return ls

def build_package(loader, name, vers='1.0',
	mod_content = None,
	mod_main = None,
	external_path = None,
	resources = None,
	depends = None,
	metadata = None):
	
	if (type(vers) in [str, unicode]):
		vers = version.VersionNumber(vers)

	if (not external_path):
		path = loader.generate_package_path(name)
		if (not os.path.isdir(path)):
			os.makedirs(path)
		
		fl = open(os.path.join(path, pload.Filename_Versions), 'a')
		fl.write(str(vers)+'\n')
		fl.close()

		path = loader.generate_package_path(name, vers)
	else:
		path = external_path
		
	os.mkdir(path)

	if (mod_main or mod_content):
		if (not mod_main):
			mod_main = 'main'
		if (not mod_content):
			mod_content = []
			
	fl = open(os.path.join(path, pload.Filename_Metadata), 'wb')
	fl.write('boodler.package: ' + name + '\n')
	fl.write('boodler.version: ' + str(vers) + '\n')
	if (mod_main):
		if (mod_main == '__init__'):
			fl.write('boodler.main: .\n')
		else:
			fl.write('boodler.main: ' + mod_main + '\n')
	if (depends):
		if (type(depends) != list):
			depends = [ depends ]
		for (val1, val2) in depends:
			if (val2 is None):
				fl.write('boodler.requires: ' + val1 + '\n')
			elif (isinstance(val2, version.VersionSpec)):
				fl.write('boodler.requires: ' + val1 + ' ' + str(val2) + '\n')
			elif (isinstance(val2, version.VersionNumber)):
				fl.write('boodler.requires_exact: ' + val1 + ' ' + str(val2) + '\n')
			else:
				fl.write('boodler.requires: ' + val1 + ' ' + val2 + '\n')
	if (metadata):
		for key in metadata:
			fl.write(key + ': ' + metadata[key] + '\n')
	fl.close()

	if (mod_main):
		fl = open(os.path.join(path, mod_main+'.py'), 'w')
		if (depends):
			fl.write('from boopak import package\n')
			count = 1
			for (val1, val2) in depends:
				fl.write('imp'+str(count)+'=')
				fl.write('package.bimport')
				if (not val2):
					fl.write('("' + val1 + '")\n')
				else:
					fl.write('("' + val1 + '", "' + val2 + '")\n')
				count += 1
		if (type(mod_content) == dict):
			for key in mod_content:
				val = mod_content[key]
				fl.write(key + ' = ' + repr(val) + '\n')
		else:
			for val in mod_content:
				fl.write(val + '\n')
		fl.close()

	if (resources):
		fl = open(os.path.join(path, pload.Filename_Resources), 'wb')
		for reskey in resources:
			resfile = resources[reskey]
			fl.write(':'+reskey+'\n')
			fl.write('boodler.filename: '+resfile+'\n')
			val = os.path.join(path, *resfile.split('/'))
			if (not os.path.isdir(os.path.dirname(val))):
				os.makedirs(os.path.dirname(val))
			subfl = open(val, 'wb')
			subfl.write('content='+reskey)
			subfl.close()
		fl.close()

	if (not external_path):
		dic = collection.get(name)
		if (not dic):
			dic = {}
			collection[name] = dic
		dic[vers] = path

class TestPLoad(unittest.TestCase):
	def setUp(self):
		basedir = tempfile.mkdtemp(prefix='test_pload')
		self.basedir = basedir
		coldir = os.path.join(basedir, 'Collection')
		os.makedirs(coldir)
		self.coldir = coldir

		self.loader = pload.PackageLoader(coldir, importing_ok=True)

		build_package(self.loader, 'simple.test', '1.0')
		
		build_package(self.loader, 'import.module',
			mod_content={'key':'val'}, mod_main='main')
		build_package(self.loader, 'import.module', '2.0',
			mod_content={'key':'val2'}, mod_main='__init__')
			
		build_package(self.loader, 'version.specs', '1.2')
		build_package(self.loader, 'version.specs', '1.5')
		build_package(self.loader, 'version.specs', '1.5.3')
		build_package(self.loader, 'version.specs', '2.5')

		self.empty_dir_path = os.path.join(basedir, 'empty-dir')
		os.mkdir(self.empty_dir_path)

		self.external_one_path = os.path.join(basedir, 'external-one')
		build_package(self.loader, 'external.one', '1.0',
			external_path=self.external_one_path,
			metadata={'key':'ext1'})
			
		build_package(self.loader, 'external.two', '2.5',
			mod_content={'key':'orig'})
		self.external_two_path = os.path.join(basedir, 'external-two')
		build_package(self.loader, 'external.two', '2.5',
			external_path=self.external_two_path,
			mod_content={'key':'replacement'})
			
		build_package(self.loader, 'external.three', '2.0',
			mod_content={'key':'orig'})
		self.external_three_path = os.path.join(basedir, 'external-three')
		build_package(self.loader, 'external.three', '2.5',
			external_path=self.external_three_path,
			mod_content={'key':'replacement'})

		build_package(self.loader, 'only.files',
			resources={
				'one':'one.txt',
				'dir.two':'dir/two.txt',
				'dir.three':'dir/three.txt',
			})

		build_package(self.loader, 'mod.and.files',
			mod_content=[
				'from boopak import package',
				'package.bexport("one")',
				'package.bexport("dir")',
				'package.bexport("alt.four")',
			],
			resources={
				'zero':'zero.txt',
				'one':'one.txt',
				'dir.two':'dir/two.txt',
				'dir.three':'dir/three.txt',
				'alt.four':'alt/four.txt',
				'alt.five':'alt/five.txt',
			})

		build_package(self.loader, 'depend.one', '1',
			mod_content={'key':11})
		build_package(self.loader, 'depend.one', '2',
			mod_content={'key':12})
		build_package(self.loader, 'depend.two',
			depends=('depend.one', '1'),
			mod_content={'key':21})
		build_package(self.loader, 'depend.two', '2',
			depends=('depend.one', '2'),
			mod_content={'key':22})
		build_package(self.loader, 'depend.three',
			depends=('depend.two', None),
			mod_content={'key':3})
		
		build_package(self.loader, 'self.depend', '1',
			depends=('self.depend', '1'),
			mod_content={'key':1})
		build_package(self.loader, 'self.depend', '2',
			depends=('self.depend', '1'),
			mod_content={'key':2})
			
		build_package(self.loader, 'mutual.depend.one',
			depends=('mutual.depend.two', None),
			mod_content={'key':1})
		build_package(self.loader, 'mutual.depend.two',
			depends=('mutual.depend.one', None),
			mod_content={'key':2})
			
		build_package(self.loader, 'depend.on.fail',
			depends=('external.one', None),
			mod_content={'key':1})

		build_package(self.loader, 'depend.on.cases',
			depends=[
				('depend.one', None),
				('missing.nospec', None),
				('missing.spec', version.VersionSpec('2')),
				('missing.num', version.VersionNumber('3')),
			])

		build_package(self.loader, 'unicode.metadata',
			metadata={
				'test.plain':'result',
				'test.unicode':'alpha is \xce\xb1',
			})
			
	def tearDown(self):
		collect.remove_recursively(self.basedir)

	def test_all(self):
		subtests = [ val for val in dir(self) if val.startswith('subtest_') ]
		subtests.sort()
		for val in subtests:
			func = getattr(self, val)
			func()

	def subtest_generate_package_path(self):
		coldir = self.coldir
		
		path = self.loader.generate_package_path('foo.bar')
		self.assertEqual(path, os.path.join(coldir, 'foo.bar'))
		
		path = self.loader.generate_package_path('foo.bar',
			version.VersionNumber('2.1'))
		self.assertEqual(path, os.path.join(coldir, 'foo.bar', '2.1'))
		
		path = self.loader.generate_package_path('foo.bar',
			version.VersionNumber('2.1.0a'))
		self.assertEqual(path, os.path.join(coldir, 'foo.bar', '2.1.0a'))

		path = self.loader.generate_package_path('foo.bar',
			version.VersionNumber('2.1.0A'))
		self.assertEqual(path, os.path.join(coldir, 'foo.bar', '2.1.0^A'))
		
	def subtest_simple_import(self):
		pkg = self.loader.load('simple.test')
		self.assertEqual(pkg.key, ('simple.test', '1.0'))
		mod = pkg.get_content()

	def subtest_import_module(self):
		pkg = self.loader.load('import.module', '1.0')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'val')

		pkg = self.loader.load('import.module', '2.0')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'val2')

		pkg = self.loader.load('import.module', u'2.0')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'val2')

	def assertResourceReadable(self, file, key):
		fl = file.open()
		dat = fl.read()
		fl.close()
		self.assertEqual(dat, 'content='+key)
		
	def subtest_import_files(self):
		pkg = self.loader.load('only.files')
		mod = pkg.get_content()

		self.assertResourceReadable(mod.one, 'one')
		self.assertResourceReadable(mod.dir.two, 'dir.two')
		self.assertResourceReadable(mod.dir.three, 'dir.three')
	
	def subtest_import_some_files(self):
		pkg = self.loader.load('mod.and.files')
		mod = pkg.get_content()

		self.assertResourceReadable(mod.one, 'one')
		self.assertResourceReadable(mod.dir.two, 'dir.two')
		self.assertResourceReadable(mod.dir.three, 'dir.three')
		self.assertResourceReadable(mod.alt.four, 'alt.four')
		self.assertRaises(AttributeError, getattr, mod, 'zero')
		self.assertRaises(AttributeError, getattr, mod.alt, 'five')

	def subtest_version_specs(self):
		pkg = self.loader.load('version.specs')
		self.assertEqual(pkg.key, ('version.specs', '2.5'))
		pkg = self.loader.load('version.specs', '1')
		self.assertEqual(pkg.key, ('version.specs', '1.5.3'))
		pkg = self.loader.load('version.specs', '1.3')
		self.assertEqual(pkg.key, ('version.specs', '1.5.3'))
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'version.specs', '1.6')
		pkg = self.loader.load('version.specs', '2')
		self.assertEqual(pkg.key, ('version.specs', '2.5'))
		pkg = self.loader.load('version.specs', '2.4')
		self.assertEqual(pkg.key, ('version.specs', '2.5'))
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'version.specs', '2.6')
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'version.specs', '3')
		pkg = self.loader.load('version.specs', '1.2')
		self.assertEqual(pkg.key, ('version.specs', '1.5.3'))
		pkg = self.loader.load('version.specs', version.VersionNumber('1.2'))
		self.assertEqual(pkg.key, ('version.specs', '1.2'))

	def subtest_load_group(self):
		grp = self.loader.load_group('version.specs')

		ls = grp.get_versions()
		ls.sort()
		ls = [ str(val) for val in ls ]
		self.assertEqual(ls, ['1.2', '1.5', '1.5.3', '2.5'])

		self.assertEqual(grp.get_num_versions(), 4)
		
		vers = grp.find_version_match()
		self.assertEqual(vers, '2.5')
		vers = grp.find_version_match(version.VersionSpec('1'))
		self.assertEqual(vers, '1.5.3')

	def subtest_load_by_name(self):
		pass ####

	def subtest_external_dir(self):
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'external.one')

		tup = self.loader.add_external_package(self.external_one_path)
		self.assertEqual(tup, ('external.one', '1.0'))

		pkg = self.loader.load('external.one')
		self.assertEqual(pkg.key, tup)

		self.loader.remove_external_package(self.external_one_path)
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'external.one')

		self.loader.remove_external_package('nonexistent')

		tup = self.loader.add_external_package(self.external_one_path)
		self.assertEqual(tup, ('external.one', '1.0'))

		self.loader.clear_external_packages()
		self.assertRaises(pload.PackageNotFoundError, 
			self.loader.load, 'external.one')

	def subtest_external_dir_shadow(self):
		pkg = self.loader.load('external.two')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'orig')

		tup = self.loader.add_external_package(self.external_two_path)
		self.assertEqual(tup, ('external.two', '2.5'))

		pkg = self.loader.load('external.two')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'replacement')

		self.loader.remove_external_package(self.external_two_path)
		pkg = self.loader.load('external.two')
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'orig')

	def subtest_external_dir_upgrade(self):
		pkg = self.loader.load('external.three')
		self.assertEqual(pkg.key, ('external.three', '2.0'))
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'orig')

		tup = self.loader.add_external_package(self.external_three_path)
		self.assertEqual(tup, ('external.three', '2.5'))

		pkg = self.loader.load('external.three')
		self.assertEqual(pkg.key, ('external.three', '2.5'))
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'replacement')

		self.loader.clear_external_packages()
		pkg = self.loader.load('external.three')
		self.assertEqual(pkg.key, ('external.three', '2.0'))
		mod = pkg.get_content()
		self.assertEqual(mod.key, 'orig')

	def subtest_external_dir_override(self):
		meta = pinfo.Metadata('<override>')
		meta.add('boodler.package', 'external.one')
		meta.add('boodler.version', '1.1')
		meta.add('key', 'override')
		ress = pinfo.Resources('<override>')
		ress.create('res.name')

		self.assertRaises(pload.PackageLoadError,
			self.loader.add_external_package, self.empty_dir_path)
		
		tup = self.loader.add_external_package(self.empty_dir_path,
			meta, ress)
		self.assertEqual(tup, ('external.one', '1.1'))
		pkg = self.loader.load('external.one')
		val = pkg.metadata.get_one('key')
		self.assertEqual(val, 'override')
		self.assertEqual(pkg.resources.keys(), ['res.name'])
		
		self.loader.clear_external_packages()
		
		tup = self.loader.add_external_package(self.external_one_path,
			meta, ress)
		self.assertEqual(tup, ('external.one', '1.1'))
		pkg = self.loader.load('external.one')
		val = pkg.metadata.get_one('key')
		self.assertEqual(val, 'override')
		self.assertEqual(pkg.resources.keys(), ['res.name'])
		
		self.loader.clear_external_packages()
		
		tup = self.loader.add_external_package(self.external_one_path)
		self.assertEqual(tup, ('external.one', '1.0'))
		pkg = self.loader.load('external.one')
		val = pkg.metadata.get_one('key')
		self.assertEqual(val, 'ext1')
		self.assertEqual(pkg.resources.keys(), [])
	
		self.loader.clear_external_packages()
		
	def subtest_list_all_current_packages(self):
		ls = self.loader.list_all_current_packages()
		ls2 = list_collection()
			
		ls.sort()
		ls2.sort()
		self.assertEqual(ls, ls2)
		
	def subtest_list_all_current_packages_ext(self):
		tup = self.loader.add_external_package(self.external_one_path)
		self.assertEqual(tup, ('external.one', '1.0'))
		
		ls = self.loader.list_all_current_packages()

		ls2 = list_collection()
		ls2.append(tup)
			
		ls.sort()
		ls2.sort()
		self.assertEqual(ls, ls2)

		self.loader.clear_external_packages()

	def packages_to_set(self, ls):
		ls = [ (name, version.VersionNumber(vers)) for (name, vers) in ls ]
		return sets.Set(ls)

	def subtest_dependencies(self):
		pkg21 = self.loader.load('depend.two', '1')
		pkg22 = self.loader.load('depend.two', '2')
		self.assertNotEqual(pkg21, pkg22)

		tup = self.loader.load_package_dependencies(pkg21)
		deplist = [('depend.one', '1'), ('depend.two', '1')]
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))
		
		tup = self.loader.load_package_dependencies(pkg22)
		deplist = [('depend.one', '2'), ('depend.two', '2')]
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))

		pkg11 = self.loader.load('depend.one', '1')
		pkg12 = self.loader.load('depend.one', '2')

		mod21 = pkg21.get_content()
		mod22 = pkg22.get_content()
		mod11 = pkg11.get_content()
		mod12 = pkg12.get_content()

		self.assert_(mod21.imp1 is mod11)
		self.assert_(mod22.imp1 is mod12)
		self.assertEqual(mod21.key, 21)
		self.assertEqual(mod22.key, 22)
		self.assertEqual(mod21.imp1.key, 11)
		self.assertEqual(mod22.imp1.key, 12)

		pkg3 = self.loader.load('depend.three')
		mod3 = pkg3.get_content()
		self.assert_(mod3.imp1.imp1 is mod12)

	def subtest_self_dependency(self):
		pkg1 = self.loader.load('self.depend', '1')

		tup = self.loader.load_package_dependencies(pkg1)
		deplist = [('self.depend', '1')]
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))
		
		mod1 = pkg1.get_content()
		self.assert_(mod1.imp1 is mod1)
		self.assertEqual(mod1.key, 1)
		self.assertEqual(mod1.imp1.key, 1)

		pkg2 = self.loader.load('self.depend', '2')
		
		tup = self.loader.load_package_dependencies(pkg2)
		deplist = [('self.depend', '1'), ('self.depend', '2')]
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))
		
		mod2 = pkg2.get_content()
		self.assert_(mod2.imp1 is mod1)
		
	def subtest_mutual_dependency(self):
		pkg1 = self.loader.load('mutual.depend.one')
		mod1 = pkg1.get_content()
		pkg2 = self.loader.load('mutual.depend.two')
		mod2 = pkg2.get_content()

		self.failIf(mod1 is mod2)

		deplist = [('mutual.depend.one', '1'), ('mutual.depend.two', '1')]
		tup = self.loader.load_package_dependencies(pkg1)
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))
		tup = self.loader.load_package_dependencies(pkg2)
		self.assertEqual(tup, (self.packages_to_set(deplist), {}, 0))

		self.assert_(mod1.imp1 is mod2)
		self.assert_(mod2.imp1 is mod1)
		self.assert_(mod1.imp1.imp1 is mod1)

	def subtest_mutual_dependency(self):
		pkg = self.loader.load('depend.on.fail')
		
		deplist = [('depend.on.fail', '1')]
		tup = self.loader.load_package_dependencies(pkg)
		self.assertEqual(tup,
			(self.packages_to_set(deplist), {'external.one': [None]}, 0))

		self.assertRaises(pload.PackageNotFoundError, pkg.get_content)

		tup = self.loader.add_external_package(self.external_one_path)
		self.assertEqual(tup, ('external.one', '1.0'))
		pkg = self.loader.load('depend.on.fail')
		deplist = [('depend.on.fail', '1'), ('external.one', '1')]
		tup = self.loader.load_package_dependencies(pkg)
		self.assertEqual(tup,
			(self.packages_to_set(deplist), {}, 0))
		pkg.get_content()
		self.loader.clear_external_packages()

	def subtest_dependency_cases(self):
		pkg = self.loader.load('depend.on.cases')
		tup = pkg.load_dependencies()

		badls = [
				('missing.nospec', None),
				('missing.spec', version.VersionSpec('2.0')),
				('missing.num', version.VersionNumber('3.0')),
			]
		badls.sort()

		baddict = dict([ (key,[val]) for (key,val) in badls ])
		
		self.assertEqual(tup, 
			(self.packages_to_set([
				('depend.on.cases', '1.0'),
				('depend.one', '2.0'),
			]),
			baddict,
			0))

		bad = self.loader.find_all_dependencies()[2]
		ls = bad[('depend.on.cases', version.VersionNumber('1.0'))]
		ls.sort()
		self.assertEqual(ls, badls)
	
	def subtest_unicode_metadata(self):
		pkg = self.loader.load('unicode.metadata')

		val = pkg.metadata.get_one('test.plain')
		self.assertEqual(val, 'result')

		val = pkg.metadata.get_one('test.unicode')
		self.assertEqual(val, u'alpha is \u03b1')
