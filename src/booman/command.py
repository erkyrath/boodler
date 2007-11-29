import sets
import os.path
import zipfile
import time
import codecs

from booman import token

class CommandToken(token.Token):
	"""CommandToken: a Token which grabs one of the command words.

	Returns the Command subclass corresponding to the command. (A class
	object, not an instance of it.)

	Class field:

	verb_map -- a dict mapping words to Command subclasses.
	"""
	
	verb_map = None

	def __init__(self):
		# The verb_map only needs to be initialized the first time a
		# CommandToken is created.
		if (CommandToken.verb_map is None):
			CommandToken.verb_map = {}
			for cmd in command_list:
				for verb in ([cmd.name] + cmd.synonyms):
					CommandToken.verb_map[verb] = cmd

	def accept(self, source):
		val = source.pop_word(self)
		val = val.lower()
		cmdclass = CommandToken.verb_map.get(val)
		if (not cmdclass):
			raise CommandError('Unknown command: "' + val + '".'
				+ ' (Type "help" for a list of commands.)')
		return cmdclass

class Command:
	"""Command: represents a possible command. Each subclass of Command
	represents one command (QuitCmd, HelpCmd, etc).

	Class fields:

	name -- the basic command word
	synonyms -- a list of alternate words which are accepted for the command
	description -- one-line description of the command
	help -- more detailed help for the command

	Methods:

	perform() -- carry out the command
	assert_done() -- ensure that the input has been exhausted
	"""
	
	name = '<unknown>'
	synonyms = []
	description = '<unknown>'
	help = None  ### fill out for commands

	def __repr__(self):
		return ('<Command \'' + self.name + '\'>')

	def perform(self, source):
		"""perform(source) -> None

		Carry out the command. Each Command subclass must override this.
		"""
		raise NotImplementedError('command \'' + self.name + '\'')

	def assert_done(self, source):
		"""assert_done(source) -> None

		Ensure that the input has been exhausted. If it has not, raise a
		CommandError.

		(This should be called after all command arguments have been read,
		but before execution begins.)
		"""
		
		if (not source.is_empty()):
			val = ' '.join(source.drain())
			raise CommandError('Unexpected stuff after your command: "' 
				+ val + '".')

class QuitCmd(Command):
	name = 'quit'
	synonyms = ['.', 'q']
	description = 'Exit Boodle-Manager'

	def perform(self, source):
		self.assert_done(source)
		frame.set_quit()

class VerifyCmd(Command):
	name = 'verify'
	synonyms = ['x']
	description = 'Verify that a package is intact'

	def perform(self, source):
		tok = token.PackageFileURLToken()
		(srctype, loc) = tok.accept(source)
		self.assert_done(source)

		ensure_fetched(srctype, loc)
		pkg = frame.loader.find_source(srctype, loc)

		print 'Package:', pkg.name, '   Version:', str(pkg.version)
		meta = pkg.metadata
		print 'Title:', meta.get_one('dc.title', '<not available>')

class ContentsCmd(Command):
	name = 'contents'
	synonyms = ['resources']
	description = 'List the resources in a package'

	def perform(self, source):
		tok = token.PackageFileURLToken()
		(srctype, loc) = tok.accept(source)
		self.assert_done(source)

		ensure_fetched(srctype, loc)
		pkg = frame.loader.find_source(srctype, loc)

		print 'Package:', pkg.name, '   Version:', str(pkg.version)
		ress = pkg.resources

		ls = ress.keys()
		ls.sort()
		print 'Resources:', len(ls)
		
		for key in ls:
			res = ress.get(key)
			typ = res.get_one('boodler.use')
			typval = ''
			if (typ):
				typval = '['+typ+']'
			print '  ', key, typval
		
class DescribeCmd(Command):
	name = 'describe'
	synonyms = ['metadata']
	description = 'List the metadata of a package'

	def perform(self, source):
		tok = token.PackageFileURLToken()
		(srctype, loc) = tok.accept(source)
		self.assert_done(source)

		ensure_fetched(srctype, loc)
		pkg = frame.loader.find_source(srctype, loc)

		print 'Package:', pkg.name, '   Version:', str(pkg.version)
		meta = pkg.metadata

		ls = meta.keys()
		ls.sort()
		print 'Metadata entries:', len(ls)

		for key in ls:
			vals = meta.get_all(key)
			if (not vals):
				continue
			if (len(vals) == 1):
				print '  ', key+':', vals[0]
			else:
				print '  ', key+':'
				for val in vals:
					print '    ', val
		
class InstallCmd(Command):
	name = 'install'
	description = 'Install a package into your collection'

	def perform(self, source):
		tok = token.PackageFileURLToken()
		(srctype, loc) = tok.accept(source)
		self.assert_done(source)

		if (srctype == collect.Source_PACKAGE):
			raise CommandError('### Not yet able to search boodler.org')

		ensure_fetched(srctype, loc)
		try:
			pkg = frame.loader.find_source(srctype, loc)
			frame.loader.load(pkg.name, pkg.version)
			already_got = True
		except:
			pkg = None
			already_got = False

		if (already_got and (not frame.is_force)):
			print ('The package ' + pkg.name
				+ ' (version ' + str(pkg.version) + ') is already installed. Do you want to reinstall it?')
			tok = token.YesNoToken()
			res = tok.accept(source)
			if (not res):
				raise CommandCancelled()
		
		pkg = frame.loader.install_source(srctype, loc)

		print 'Package:', pkg.name, '   Version:', str(pkg.version)
		meta = pkg.metadata
		print 'Title:', meta.get_one('dc.title', '<not available>')

		### check dependencies!
		
class CurrentCmd(Command):
	name = 'current'
	description = 'List all the packages installed (newest version of each)'

	def perform(self, source):
		self.assert_done(source)

		ls = frame.loader.list_all_current_packages()
		ls.sort()
		for key in ls:
			print '  ', format_package(key, False)
		print len(ls), 'packages installed (ignoring multiple versions)'

class ObsoleteCmd(Command):
	name = 'obsolete'
	description = 'Find old versions which are not required by any current package'

	def perform(self, source):
		self.assert_done(source)

		(forward, backward, bad) = frame.loader.find_all_dependencies()

		obsolete = sets.Set()
		found_ok = sets.Set()
		to_check = frame.loader.list_all_current_packages()
		for key in to_check:
			found_ok.add(key)
			(pkgname, vers) = key
			pgroup = frame.loader.load_group(pkgname)
			for oldvers in pgroup.get_versions():
				if (oldvers != vers):
					obsolete.add( (pkgname, oldvers) )

		while (to_check):
			key = to_check.pop(0)
			for depkey in forward.get(key, []):
				if (depkey in found_ok):
					continue
				found_ok.add(depkey)
				to_check.append(depkey)

		res = obsolete.difference(found_ok)
		if (not res):
			print 'No obsolete packages found.'
			return
		print 'The following versions can be deleted safely:'
		for key in res:
			print '  ', format_package(key)

class VersionsCmd(Command):
	name = 'versions'
	description = 'List all the installed versions of a package'

	def perform(self, source):
		tok = token.PackageToken()
		pkgname = tok.accept(source)
		self.assert_done(source)

		try:
			pgroup = frame.loader.load_group(pkgname)
		except pinfo.PackageNotFoundError:
			raise CommandError('No such package installed: ' + pkgname)
		except pinfo.PackageLoadError:
			frame.note_backtrace()
			raise CommandError('Unable to read package: ' + pkgname)

		ls = [(pkgname, vers) for vers in pgroup.versions ]
		ls.sort()
		for key in ls:
			print '  ', format_package(key)

class RequiresCmd(Command):
	name = 'requires'
	description = 'List what depends on a package'

	def perform(self, source):
		tok = token.PackageOptVersionToken()
		(pkgname, vers) = tok.accept(source)
		self.assert_done(source)

		try:
			pkg = frame.loader.load(pkgname, vers)
		except pinfo.PackageNotFoundError:
			raise CommandError('No such package installed: ' 
				+ format_package((pkgname, vers)))
		except pinfo.PackageLoadError:
			frame.note_backtrace()
			raise CommandError('Unable to read package: '
				+ format_package((pkgname, vers)))

		(forward, backward, bad) = frame.loader.find_all_dependencies()

		found_ok = sets.Set()
		to_check = [pkg.key]
		found_ok.add(pkg.key)

		while (to_check):
			key = to_check.pop(0)
			for depkey in backward.get(key, []):
				if (depkey in found_ok):
					continue
				found_ok.add(depkey)
				to_check.append(depkey)

		found_ok.discard(pkg.key)

		ls = list(found_ok)
		print len(ls), 'packages require', format_package(pkg)
		ls.sort()
		for key in ls:
			print '  ', format_package(key)

class DeleteCmd(Command):
	name = 'delete'
	description = 'Delete a package from your collection'

	def perform(self, source):
		tok = token.PackageOptVersionToken()
		(pkgname, vers) = tok.accept(source)
		self.assert_done(source)

		if (vers is None):
			dirname = frame.loader.generate_package_path(pkgname)
			if (not os.path.exists(dirname)):
				raise CommandError('No such package group: ' + pkgname)

			if (not frame.is_force):
				print ('Are you sure you want to delete all versions of ' 
					+ pkgname + '?')
				tok = token.YesNoToken()
				res = tok.accept(source)
				if (not res):
					raise CommandCancelled()

			frame.loader.delete_group(pkgname)
			print 'All versions of package', pkgname, 'deleted.'
		else:
			pkg = frame.loader.load(pkgname, vers)
		
			if (not frame.is_force):
				print ('Are you sure you want to delete ' + pkg.name
					+ ' (version ' + str(pkg.version) + ')?')
				tok = token.YesNoToken()
				res = tok.accept(source)
				if (not res):
					raise CommandCancelled()

			frame.loader.delete_package(pkg.name, pkg.version)
			print 'Package', format_package(pkg), 'deleted.'

class DeleteAllCmd(Command):
	name = 'deleteall'
	description = 'Delete your entire collection (all packages)'

	def perform(self, source):
		self.assert_done(source)
		
		if (not frame.is_force):
			print 'Are you sure you want to delete every package in your collection?'
			tok = token.YesNoToken()
			res = tok.accept(source)
			if (not res):
				raise CommandCancelled()

		frame.loader.delete_whole_collection()
		print 'All packages deleted.'

class CreateCmd(Command):
	name = 'create'
	description = 'Create a package file from a directory'

	def perform(self, source):
		tok = token.DirToken()
		(dirname, direxists) = tok.accept(source)

		destname = None
		if (not source.is_empty()):
			tok = token.FileToken(False)
			(destname, destexists) = tok.accept(source)

		self.assert_done(source)

		if (not frame.loader.importing_ok):
			raise CommandError('Creating requires importing packages, and the import option has not been set.')

		absdirname = os.path.abspath(dirname)
		abscoldir = os.path.abspath(frame.loader.collecdir)
		if (absdirname.startswith(abscoldir)):
			raise CommandError('Directory is inside the collection tree: ' + absdirname)

		if (destname):
			if (not destname.endswith(collect.Suffix_PackageArchive)):
				destname = destname+collect.Suffix_PackageArchive
		
		tup = create.examine_directory(frame.loader, absdirname, destname)
		((pkgname, pkgvers), contents, meta, ress) = tup

		frame.loader.clear_external_packages()

		if (not destname):
			destname = os.path.dirname(absdirname)
			destfile = create.build_package_filename(pkgname, pkgvers)
			destname = os.path.join(destname, destfile)

		if (os.path.exists(destname) and not frame.is_force):
			print 'Are you sure you want to overwrite ' + destname + '?'
			tok = token.YesNoToken()
			res = tok.accept(source)
			if (not res):
				raise CommandCancelled()

		metafile = frame.loader.create_temp_file('metadata')
		ressfile = None
		if (ress):
			ressfile = frame.loader.create_temp_file('resources')

		# Comments for the head of the metadata and resource files
		comments = [ format_package( (pkgname, pkgvers) ),
			'package built ' + time.ctime() ]
		
		writer = codecs.getwriter('utf-8')

		fl = open(metafile, 'wb')
		ufl = writer(fl)
		try:
			meta.dump(ufl, comments)
		finally:
			ufl.close()
			fl.close()
			
		if (ress):
			fl = open(ressfile, 'wb')
			ufl = writer(fl)
			try:
				ress.dump(ufl, comments)
			finally:
				ufl.close()
				fl.close()
				
		fl = zipfile.ZipFile(destname, 'w')
		try:
			create.construct_zipfile(fl,
				(pkgname, pkgvers), absdirname, contents, metafile, ressfile)
		finally:
			fl.close()
		print 'Package created:', destname

class ReloadCmd(Command):
	name = 'reload'
	description = 'Force the manager to re-scan the collection directory.'

	def perform(self, source):
		self.assert_done(source)
		frame.loader.clear_cache()
		frame.loader.clean_temp()
		print 'Done.'
		
class HelpCmd(Command):
	name = 'help'
	synonyms = ['?']
	description = 'Show this list'

	def perform(self, source):
		if (not source.is_empty()):
			cmdclass = CommandToken().accept(source)
			self.assert_done(source)

			cmd = cmdclass()

			extra = ''
			if (cmd.synonyms):
				extra = ' ("' + '", "'.join(cmd.synonyms) + '")'
			print 'Command "' + cmd.name + '"' + extra + ':'

			helptext = cmd.help
			if (not helptext):
				helptext = cmd.description
			print helptext
			return

		self.assert_done(source)

		### tidy
		for cmd in command_list:
			print cmd.name+':', cmd.description

class LastErrorCmd(Command):
	name = 'lasterror'
	description = 'Display a debugging trace of the most recent error'

	def perform(self, source):
		self.assert_done(source)

		val = frame.get_last_backtrace()
		if (val is None):
			val = 'No Python exceptions have occurred.'
		print val

# All the Command subclasses defined above. This list is used to
# make the CommandToken.verb_map table, and also when listing the
# help commands.
command_list = [
	HelpCmd,
	VerifyCmd,
	ContentsCmd,
	DescribeCmd,
	CurrentCmd,
	ObsoleteCmd,
	VersionsCmd,
	RequiresCmd,
	InstallCmd,
	DeleteCmd,
	DeleteAllCmd,
	CreateCmd,
	ReloadCmd,
	LastErrorCmd,
	QuitCmd
]

def format_package(val, full=True):
	"""format_package(val, full=True) -> str

	Create a human-readable label for a package. The val may be a
	PackageInfo object or a (pkgname, vers) pair. If full is false,
	the version is ignored.
	"""
	
	if (isinstance(val, pinfo.PackageInfo)):
		val = val.key
	(name, vers) = val
	if (full and vers):
		return name+' '+str(vers)
	else:
		return name

def ensure_fetched(srctype, loc):
	"""ensure_fetched(srctype, loc) -> None

	Make sure the (srctype, loc) pair is fetched by the loader. (See the
	PackageCollection.fetch_source() method for the arguments.) This
	does any slow processing -- that is, HTTP downloading -- which is
	necessary before the command is executed.
	"""
	
	fetcher = frame.loader.fetch_source(srctype, loc)
	if (fetcher is None):
		return
	print 'Loading',
	while (not fetcher.is_done()):
		fetcher.work()
		print '.',
	print '.'

# Late imports
from boopak import pinfo
from boopak import collect
from booman import CommandError, CommandCancelled
from booman import frame
from booman import create
