# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import sys
import types
import os
import os.path
import re
import inspect
import keyword

from booman import CommandError
from boodle.agent import Agent

class ConstructError(CommandError):
    """ConstructError: represents an error during package construction.
    """
    def __init__(self, dirname, msg):
        CommandError.__init__(self, 'Creation error: ' + msg)


def examine_directory(loader, dirname, destname=None):
    """examine_directory(loader, dirname, destname=None) ->
        ((pkgname, pkgvers), contents, metadata, resources)

    Look at a directory containing package data. Figure out its metadata
    and resources, considering both the directory contents and the
    contents of the Metadata and Resources files (if present).

    The destname, if provided, may also be used to figure out the
    package's desired name and version number.

    The loader argument must be a PackageLoader. This is used for a test
    import, during the process.

    Any fatal errors will raise ConstructError. This may also print
    (non-fatal) warning messages.

    This returns a tuple of four items:
        - the package name and version: (str, VersionNumber)
        - a list of the files (not subdirs) in the directory; each
            element in the list is a tuple (realname, resourcename),
            where realname is the current absolute path and
            resourcename is the universal relative path in the
            package.
        - a Metadata object.
        - a Resources object.
    """
    
    # Read in the source Metadata file (which may be missing or
    # incomplete)
    metadatafile = os.path.join(dirname, pload.Filename_Metadata)
    if (os.path.exists(metadatafile)):
        fl = open(metadatafile, 'rbU')
        try:
            try:
                metadata = pinfo.Metadata('<'+metadatafile+'>', fl)
            except pload.PackageLoadError, ex:
                raise ConstructError(dirname, str(ex))
        finally:
            fl.close()
    else:
        metadata = pinfo.Metadata('<original>')

    # Extract the package name and version (if present)
        
    pkgname = None
    pkgvers = None
    
    ls = metadata.get_all('boodler.package')
    if (len(ls) > 1):
        raise ConstructError(dirname, 'Multiple metadata entries: boodler.package')
    if (ls):
        pkgname = ls[0]
        
    ls = metadata.get_all('boodler.version')
    if (len(ls) > 1):
        raise ConstructError(dirname, 'Multiple metadata entries: boodler.version')
    if (ls):
        pkgvers = ls[0]

    # Check the validity of these (if present)

    if (pkgname):
        try:
            pinfo.parse_package_name(pkgname)
        except ValueError, ex:
            raise ConstructError(dirname, str(ex))
    if (pkgvers):
        try:
            pkgvers = version.VersionNumber(pkgvers)
        except ValueError, ex:
            raise ConstructError(dirname, str(ex))

    # See what name/vers information we can extract from the destname.
    # (The "package.version.boop" which the user wants to write the final
    # product to.)

    tmpname = None
    tmpvers = None
        
    if (destname):
        try:
            (tmpname, tmpvers) = parse_package_filename(destname, False)
        except ValueError, ex:
            pass
        
    if (tmpname and not pkgname):
        pkgname = tmpname
    if (tmpvers and not pkgvers):
        pkgvers = tmpvers

    if (tmpname and pkgname and (tmpname != pkgname)):
        warning(dirname, 'Package name is "'+pkgname+'", but the name in the destination file is "'+tmpname+'".')
    if (tmpvers and pkgvers and (tmpvers != pkgvers)):
        warning(dirname, 'Package version is "'+str(pkgvers)+'", but the version in the destination file is "'+str(tmpvers)+'".')

    if (not pkgvers):
        pkgvers = version.VersionNumber()

    # Validate package name.
    if (pkgname is None):
        raise ConstructError(dirname, 'Package name must be given in Metadata or inferred from directory name')
    ls = pinfo.parse_package_name(pkgname)
    if (len(ls) < 3):
        raise ConstructError(dirname, 'Package name must have at least three elements: ' + pkgname)
    if (ls[0:2] == ['org', 'boodler']):
        warning(dirname, 'Package name begins with "org.boodler", which is reserved')

    print 'Creating package: ' + booman.command.format_package( (pkgname, pkgvers) )

    # More sanity checking on the metadata.
    
    ls = metadata.get_all('boodler.requires')
    for val in ls:
        try:
            subls = val.split()
            if (len(subls) == 1):
                reqname = subls[0]
                reqspec = None
            elif (len(subls) == 2):
                reqname = subls[0]
                reqspec = subls[1]
            else:
                raise ValueError('boodler.requires must have one or two elements.')
            
            pinfo.parse_package_name(reqname)
            if (not (reqspec is None)):
                version.VersionSpec(reqspec)
        except Exception, ex:
            warning(dirname, str(ex))
            warning(dirname, 'Invalid boodler.requires: ' + val)
        
    ls = metadata.get_all('boodler.requires_exact')
    for val in ls:
        try:
            subls = val.split()
            if (len(subls) == 2):
                reqname = subls[0]
                reqspec = subls[1]
            else:
                raise ValueError('boodler.requires_exact must have two elements.')
            
            pinfo.parse_package_name(reqname)
            if (not (reqspec is None)):
                version.VersionNumber(reqspec)
        except Exception, ex:
            warning(dirname, str(ex))
            warning(dirname, 'Invalid boodler.requires_exact: ' + val)
        
    # Read in the source Resources file (which may be missing or
    # incomplete)
    resourcesfile = os.path.join(dirname, pload.Filename_Resources)
    if (os.path.exists(resourcesfile)):
        fl = open(resourcesfile, 'rbU')
        try:
            try:
                resources = pinfo.Resources('<'+resourcesfile+'>', fl)
            except pload.PackageLoadError, ex:
                raise ConstructError(dirname, str(ex))
        finally:
            fl.close()
    else:
        resources = pinfo.Resources('<original>')

    # Some resource sanity checking.
    for res in resources.resources():
        val = res.get_one('boodler.filename')
        if (val is None):
            continue
        if ('\\' in val):
            raise ConstructError(dirname, 'boodler.filename cannot contain backslashes: ' + val)
        try:
            fil = pinfo.build_safe_pathname(dirname, val)
        except ValueError, ex:
            raise ConstructError(dirname, str(ex))
        if (not os.path.exists(fil)):
            warning(dirname, 'boodler.filename refers to nonexistent file: ' + val)
        if (os.path.isdir(fil)):
            warning(dirname, 'boodler.filename refers to directory: ' + val)
                
    # Create a handy reverse mapping from boodler.filename to resource
    # entries.

    revmap = {}
    for res in resources.resources():
        resfilename = res.get_one('boodler.filename')
        if (resfilename):
            revmap[resfilename] = res

    # Now we walk the source directory tree, looking for files that need
    # to be copied into the final zip file. We also look for files that look
    # like resources. If the file is already listed as a resource, great;
    # if not, we generate an appropriate resource name.
    ### smartify for the fact that not all resources are files

    # list of (realname, archivename)
    contents = []

    for (dir, subdirs, files) in os.walk(dirname):
        mods = []
        tmpdir = dir
        while (tmpdir != dirname):
            if (not tmpdir):
                raise ConstructError(dirname, 'Unable to figure out subdirectory while walking: ' + dir)
            (tmphead, tmptail) = os.path.split(tmpdir)
            if (not tmptail):
                raise ConstructError(dirname, 'Unable to figure out subdirectory while walking: ' + dir)
            tmpdir = tmphead
            mods.insert(0, tmptail)
            
        for file in subdirs:
            # Ignore dot subdirectories, but print a warning about them.
            if (file.startswith('.')):
                warning(dirname, 'subdir begins with a dot: ' + '/'.join(mods+[file]))
                
        for file in files:
            if ((not mods) and (file in [pload.Filename_Metadata, pload.Filename_Resources])):
                # Ignore Metadata and Resources entirely
                continue

            filelow = file.lower()
            if (filelow.endswith('.pyc')):
                # Package directories always wind up with .pyc files;
                # silently ignore
                continue

            if (filelow.endswith('.pyo')
                or filelow.endswith('.so')
                or filelow.endswith('.o')):
                # Noisily ignore any code file that is not transparent
                warning(dirname, 'skipping file which looks like compiled code: ' + file)
                continue

            if (filelow.endswith('~')):
                # Print a warning, but allow it
                warning(dirname, 'file looks temporary: ' + file)

            # Create the real filename (readable in dirname)
            realfilename = os.path.join(dirname, *(mods + [file]))
            # Create the canonical (forward-slash) filename.
            resfilename = '/'.join(mods + [file])

            # Add to our list of files.
            contents.append( (realfilename, resfilename) )

            # Now we see if this is a resource file.

            # Ignore dot files, but print a warning about them.
            if (file.startswith('.')):
                warning(dirname, 'file begins with a dot: ' + resfilename)
                continue
                
            resuse = None
            filebase = file
            if (file.endswith('.aiff')):
                resuse = 'sound'
                filebase = file[ : -5 ]
            if (file.endswith('.wav')):
                resuse = 'sound'
                filebase = file[ : -4 ]
            if (file.endswith('.mixin')):
                resuse = 'sound'
                filebase = file[ : -6 ]

            if (not resuse):
                continue

            # This file is a resource.

            res = revmap.get(resfilename)
            if (not res):
                # We have to create the resource.
                reskey = '.'.join(mods + [filebase])
                try:
                    ls = pinfo.parse_resource_name(reskey)
                    for el in ls:
                        if (keyword.iskeyword(el)):
                            warning(dirname, resfilename + ' contains Python reserved word "' + el + '"')
                except ValueError:
                    warning(dirname, resfilename + ' looks like a resource, but ' + reskey + ' is not a valid resource name.')
                    continue

                res = resources.get(reskey)
                if (res is None):
                    try:
                        res = resources.create(reskey)
                    except ValueError, ex:
                        warning(dirname, resfilename + ' looks like a resource, but: ' + str(ex))
                        continue
                    
                    revmap[resfilename] = res

                val = res.get_one('boodler.filename')
                if (not val):
                    res.add('boodler.filename', resfilename)
                else:
                    if (val != resfilename):
                        warning(dirname, resfilename + ' looks like a resource, but ' + reskey + ' already has filename: ' + val)

            if (not res.get_one('boodler.use')):
                res.add('boodler.use', resuse)

    try:
        resources.build_tree()
    except ValueError, ex:
        warning(dirname, str(ex))
        raise ConstructError(dirname, 'Resource tree is not valid')

    try:
        # We will now try importing the package. This has two goals:
        # to locate Agent resources, and to keep a record of all imports
        # so that we can notate dependencies.
        
        tup = loader.add_external_package(dirname, metadata, resources)
        if (tup != (pkgname, pkgvers)):
            raise ConstructError(dirname, 'Attempted to import, but got wrong version: ' + booman.command.format_package(tup))

        loader.start_import_recording()
        pkg = loader.load(pkgname, pkgvers)
        mod = pkg.get_content()
        import_record = loader.stop_import_recording()

        loader.currently_creating = pkg

        if (mod.__name__ != pkg.encoded_name):
            raise ConstructError(dirname, 'Module name does not match package: ' + mod.__name__)

        context = WalkContext(pkg)
        walk_module(context, mod)

        resolve_dependency_metadata(dirname, pkgname, pkgvers,
            resources, metadata, import_record, context)
        
        for key in context.agents:
            (ag, origloc) = context.agents[key]
            res = resources.get(key)
            if (not res):
                continue
                
            # Inspect the agent to discover its argument metadata.
            ### Skip if argument metadata is already declared
    
            arglist = resolve_argument_list(dirname, key, ag)
                
            if (not (arglist is None)):
                try:
                    nod = arglist.to_node()
                    #print '### created agent', key, ':', nod.serialize()
                    res.add('boodler.arguments', nod.serialize())
                except Exception, ex:
                    warning(dirname, key + ' argument list error: ' + str(ex))

    finally:
        loader.currently_creating = None
        loader.remove_external_package(dirname)

    try:
        resources.build_tree()
    except ValueError, ex:
        warning(dirname, str(ex))
        raise ConstructError(dirname, 'Resource tree is not valid')

    # More sanity checking: every sound resource should now have a filename.
    # Agent resources should not.
    
    for res in resources.resources():
        use = res.get_one('boodler.use')
        if (use == 'sound'):
            val = res.get_one('boodler.filename')
            if (val is None):
                warning(dirname, 'no filename found for sound resource: ' + res.key)
        if (use == 'agent'):
            val = res.get_one('boodler.filename')
            if (not (val is None)):
                warning(dirname, 'filename found for agent resource: ' + res.key)

    # Done.
    return ((pkgname, pkgvers), contents, metadata, resources)

def walk_module(context, mod, prefix=''):
    """walk_module(context, mod, prefix='') -> None

    Walk through the contents of the given module, and all its submodules.
    This looks for Agents.

    Callers should not pass a prefix argument. That is used for the
    recursion.
    """

    # We respect the standard Python rules for which identifiers are
    # private. If mod.__all__ exists, anything listed in it is public.
    # If not, anything beginning with an underscore is private.
    
    alllist = getattr(mod, '__all__', None)
    
    for key in dir(mod):
        isprivate = False
        if (alllist is None):
            isprivate = (key.startswith('_'))
        else:
            isprivate = (not (key in alllist))

        if (isprivate):
            continue
            
        val = getattr(mod, key)
        
        if (type(val) == types.ModuleType):
            if (mod.__name__+'.'+key == val.__name__):
                walk_module(context, val, prefix+key+'.')

        if (type(val) == types.ClassType and issubclass(val, Agent)):
            if (val == Agent):
                continue
            if (not (val.__module__ == context.root_module_name
                or val.__module__.startswith(context.root_module_name+'.'))):
                # Not defined in this package
                continue

            # Is this the Agent's defined location?
            origloc = (mod.__name__ == val.__module__
                and key == val.__name__)
            
            context.agents[prefix+key] = (val, origloc)
    
class WalkContext:
    """WalkContext: context structure used by walk_module().
    """
    def __init__(self, pkg):
        self.pkg = pkg
        self.root_module_name = pkg.encoded_name
        
        # Maps resource keys to (Agent, bool); the bool indicates whether
        # the agent is in its defined location. An Agent copied out of its
        # defined location will show up more than once.
        self.agents = {}


def resolve_dependency_metadata(dirname, pkgname, pkgvers,
    resources, metadata, import_record, context):

    # Add the dependencies to the metadata.
    ls = import_record.get( (pkgname, pkgvers) )
    if (ls):
        entls = []
        for (reqname, reqspec) in ls:
            if (reqspec is None):
                entls.append( ('boodler.requires', reqname) )
            elif (isinstance(reqspec, version.VersionSpec)):
                entls.append( ('boodler.requires', reqname+' '+str(reqspec)) )
            elif (isinstance(reqspec, version.VersionNumber)):
                entls.append( ('boodler.requires_exact', reqname+' '+str(reqspec)) )
        for (key, val) in entls:
            if (val in metadata.get_all(key)):
                # This exact line is already present.
                warning(dirname, 'skipping dependency which already exists in Metadata: "' + key + ': ' + val + '"')
                continue
            metadata.add(key, val)

    # Warn about packages which appear in the dependencies twice.
    dic = {}
    for val in (metadata.get_all('boodler.requires') + metadata.get_all('boodler.requires_exact')):
        ls = val.split()
        if (ls):
            pinfo.dict_accumulate(dic, ls[0], True)
    for reqname in dic.keys():
        val = len(dic[reqname])
        if (val > 1):
            warning(dirname, 'package dependency appears in ' + str(val)
                + ' different forms: ' + reqname)
            
    revmap = {}
        
    for key in context.agents:
        res = resources.get(key)
        if (res):
            (ag, origloc) = context.agents[key]

            realname = ag.__module__+'.'+ag.__name__
            if (revmap.has_key(realname)):
                warning(dirname, 'Agent appears as two different resources: ' +
                    key + ', ' + revmap[realname])
            else:
                revmap[realname] = key

            use = res.get_one('boodler.use')
            if (not use):
                res.add('boodler.use', 'agent')
            else:
                if (use != 'agent'):
                    warning(dirname, 'Agent resource conflicts with use: ' +
                        key)
                
    for key in context.agents:
        (ag, origloc) = context.agents[key]
        if (not origloc):
            continue

        realname = ag.__module__+'.'+ag.__name__
        if (revmap.has_key(realname)):
            continue

        try:
            res = resources.create(key)
        except ValueError, ex:
            warning(dirname, key + ' looks like an Agent, but: ' + str(ex))
            continue
            
        revmap[realname] = key
        
        res.add('boodler.use', 'agent')

def resolve_argument_list(dirname, key, ag):
    arglist = None
    
    argspec = inspect.getargspec(ag.init)
    # argspec is (args, varargs, varkw, defaults)
    maxinitargs = None
    mininitargs = None
    
    try:
        arglist = argdef.ArgList.from_argspec(*argspec)
        maxinitargs = arglist.max_accepted()
        mininitargs = arglist.min_accepted()
    except argdef.ArgDefError, ex:
        warning(dirname, key + '.init() could not be inspected: ' + str(ex))

    if (not (ag._args is None)):
        try:
            arglist = argdef.ArgList.merge(ag._args, arglist)
        except argdef.ArgDefError, ex:
            warning(dirname, key + '.init() does not match _args: ' + str(ex))
            arglist = ag._args

    if (not (arglist is None)):
        ls = [ arg for arg in arglist.args if (arg.index is None) ]
        unindexed = len(ls)
        indexed = len(arglist.args) - unindexed
        ls = [ arg.index for arg in arglist.args ]
        if (ls[ : indexed] != range(1,1+indexed)):
            ls1 = [ str(val) for val in ls[ : indexed] ]
            ls2 = [ str(val) for val in range(1,1+indexed) ]
            warning(dirname, 'found arguments ' + (', '.join(ls1))
                + '; should have been ' + (', '.join(ls2)))
        else:
            if (ls[ indexed : ] != [ None ] * unindexed):
                warning(dirname, 'the ' + str(unindexed) + ' unindexed arguments must be last')

        val = arglist.max_accepted()
        if ((val is None) and (not (maxinitargs is None))):
            warning(dirname, key + '.init() takes at most ' + str(maxinitargs) + ' arguments, but _args describes extra arguments')
        if ((not (val is None)) and (not (maxinitargs is None))):
            if (val > maxinitargs):
                warning(dirname, key + '.init() takes at most ' + str(maxinitargs) + ' arguments, but including _args describes ' + str(val))
        
        val = arglist.min_accepted()
        if ((not (val is None)) and (not (mininitargs is None))):
            if (val < mininitargs):
                warning(dirname, key + '.init() takes at least ' + str(mininitargs) + ' arguments, but including _args describes ' + str(val))

    return arglist
        
def construct_zipfile(fl, tup, dirname, contents,
    metadatafile, resourcesfile=None):
    """construct_zipfile(fl, (pkgname, pkgvers), dirname, contents,
        metadatafile, resourcesfile=None) -> None

    Write out a zip file containing the given package data.
    The fl must be a ZipFile object, newly opened for writing.
    The dirname contains the package data; metadatafile and
    resourcesfile must be valid Metadata and Resources files.
    (Not Metadata and Resources objects, but rather the files
    produced by dump()ing them.)
    """
    
    (pkgname, pkgvers) = tup

    fl.write(metadatafile, pload.Filename_Metadata)
    if (resourcesfile):
        fl.write(resourcesfile, pload.Filename_Resources)

    # Copy in the files, as described in the contents list.

    for (realname, resname) in contents:
        if (resname in [pload.Filename_Metadata, pload.Filename_Resources]):
            raise Exception('Should not happen; contents list contains ' + resname)
        fl.write(realname, resname)
            

def warning(dirname, msg):
    """warning(dirname, msg) -> None

    Print a warning.
    """
    print 'Warning: ' + msg

def build_package_filename(pkgname, pkgvers):
    """build_package_filename(pkgname, pkgvers) -> str

    Given a package name and version, return the canonical name of
    the file containing it. (This is also used for constructing
    package URLs; the filename of a package on a server is the same
    as on disk.)

    This will look like "PACKAGE.VERSION.boop".

    This is guaranteed to create a distinct pathname for every
    (pkgname, vers) pair. This is true even on case-insensitive
    filesystems, which is a wrinkle, since version strings are
    case-sensitive. We work around this by putting a "^" character
    before each capital letter.
    """
    # This would more naturally live in command.py.
    val = str(pkgvers)
    val = pinfo.capital_letter_regexp.sub('^\\1', val)
    res = pkgname+'.'+val+collect.Suffix_PackageArchive
    return res

version_start_regexp = re.compile('\\.[0-9]')
        
def parse_package_filename(val, assume_1=True):
    """parse_package_filename(val, assume_1) -> (str, VersionNumber)

    Given a package filename, return the package name and version that
    it should contain. If the filename is not a canonical form, raise
    ValueError.

    The name can look like "PACKAGE.VERSION.boop" or "PACKAGE.boop".
    In the latter case, the version returned depends on the assume_1
    argument. To get version 1.0, pass True; to get None, pass False.
    """

    # We can't trust the case of filenames on Windows.
    val = val.lower()
    if ('^' in val):
        def reconstruct_caps(match):
            return match.group(1).upper()
        val = pinfo.caret_letter_regexp.sub(reconstruct_caps, val)

    suffix = collect.Suffix_PackageArchive
    if (not val.endswith(suffix)):
        raise ValueError('filename does not end with ' + suffix + ': ' + val)
    base = val[ : -len(suffix) ]

    match = version_start_regexp.search(base)
    if (not match):
        pkgname = base
        pkgvers = None
    else:
        pos = match.start()
        pkgname = base[ : pos ]
        pkgvers = base[ pos+1 : ]

    pinfo.parse_package_name(pkgname)
    if (pkgvers):
        pkgvers = version.VersionNumber(pkgvers)
    else:
        if (assume_1):
            pkgvers = version.VersionNumber()
        else:
            pkgvers = None

    return (pkgname, pkgvers)

# Late imports

from boopak import version
from boopak import pinfo
from boopak import pload
from boopak import collect
from boopak import argdef
import booman

# Unit tests

import unittest
        
class TestCreate(unittest.TestCase):

    def test_build_package_filename(self):
        ls = [
            ('foo.bar', '1.0', 'foo.bar.1.0.boop'),
            ('foo.bar', '2.30.xyzzy.1', 'foo.bar.2.30.xyzzy.1.boop'),
            ('foo.bar.baz', '9.8.A.b.Cd.EF', 'foo.bar.baz.9.8.^A.b.^Cd.^E^F.boop'),
        ]
        for (pkgname, pkgvers, result) in ls:
            pkgvers = version.VersionNumber(pkgvers)
            val = build_package_filename(pkgname, pkgvers)
            self.assertEqual(val, result)

    def test_parse_package_filename(self):
        ls = [
            ('foo.bar', '1.0', 'foo.bar.1.0.boop'),
            ('foo.bar', '1.0', 'FOO.BAR.1.0.BOOP'),
            ('foo.bar', '2.30.xyzzy.1', 'foo.bar.2.30.xyzzy.1.boop'),
            ('foo', '1.2..3', 'foo.1.2..3.boop'),
            ('hello.a.string', '12.95.a._.X', 'hello.a.string.12.95.a._.^x.boop'),
            ('foo.bar', '1.0', 'foo.bar.boop'),
            ('foo.bar', '2.0', 'foo.bar.2.boop'),
            ('foo.bar.baz', '9.8.A.b.Cd.EF', 'foo.bar.baz.9.8.^A.b.^Cd.^E^F.boop'),
            ('foo.bar.baz', '9.8.A.b.Cd.EF', 'foo.bar.baz.9.8.^a.b.^cd.^e^f.boop'),
            ('foo.bar.baz', '9.8.A.b.Cd.EF', 'foo.BAR.baz.9.8.^a.B.^CD.^e^F.Boop'),
        ]

        for (pkgname, pkgvers, result) in ls:
            (resname, resvers) = parse_package_filename(result)
            self.assertEqual(resname, pkgname)
            self.assertEqual(str(resvers), pkgvers)

    def test_parse_package_filename_assume(self):
        (resname, resvers) = parse_package_filename('foo.boop')
        self.assertEqual(str(resvers), '1.0')
        (resname, resvers) = parse_package_filename('foo.boop', False)
        self.assertEqual(resvers, None)
    
        (resname, resvers) = parse_package_filename('foo.1.boop')
        self.assertEqual(str(resvers), '1.0')
        (resname, resvers) = parse_package_filename('foo.1.boop', False)
        self.assertEqual(str(resvers), '1.0')
    
        (resname, resvers) = parse_package_filename('foo.2.5.boop')
        self.assertEqual(str(resvers), '2.5')
        (resname, resvers) = parse_package_filename('foo.2.5.boop', False)
        self.assertEqual(str(resvers), '2.5')
    
    def test_parse_package_filename_bad(self):
        ls = [
            '', 'fooboop', '.boop', '!.boop', 'hel lo.boop', 'foo. boop',
            '1.2.3.boop', '1.2.$.boop', 'foo.1.$.boop', 'foo.$.boop',
            'zero.0.1.boop', 'foo.1._.boop',
            'foo..boop', 'foo..1.boop', 'foo.1..2.boop',
            'front^caret.boop', 'mis.1.0.caret^.boop',
            'mis.1.0.^1.boop', 'mis.1.0.^^x.boop', 'mis.1.0.bo^op', 
        ]

        for val in ls:
            self.assertRaises(ValueError, parse_package_filename, val)

