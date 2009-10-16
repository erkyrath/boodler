# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""pinfo: Classes which describe a Boodler module and its contents.

Classes:

PackageInfo -- represents a single package
PackageGroup -- represents all the versions of a particular package
Metadata -- represents the contents of a Metadata file
Resources -- represents the contents of a Resources file
Resource -- represents one section in a Resources file
File -- represents a file in a package

Utility functions:

parse_package_name() -- parse a package name into a list of elements
encode_package_name() -- convert a package name and version number into an ID
parse_resource_name() -- parse a resource name into a list of elements
build_safe_pathname() -- turn a relative pathname into an absolute one, safely
dict_accumulate() -- build a dict which maps keys to arrays
dict_all_values() -- get list of all the values in a dict, recursively
deunicode() -- decode a UTF-8 string into a unicode object
"""

import sys
import os.path
import types
import re
import sets
import codecs
import cStringIO

from boopak import version

class PackageInfo:
    """PackageInfo: represents a single package.

    A PackageInfo is not the imported module object which a Boodler module 
    sees from the inside. It's a wrapper around that.

    PackageInfo(loader, name, vers, dir, metadata, resources,
        external) -- constructor

    Publicly readable fields:

    name -- the package name
    version -- the package version number
    key -- a tuple containing (name, version)
    encoded_name -- the name of the package's module
    metadata -- the Metadata for the package
    resources -- the Resources for the package
    loader -- the PackageLoader which loaded the package

    Public methods:

    load_dependencies() -- attempt to load everything this package depends on
    get_content() -- return the module which is the content of this package
    get_file() -- get a File object contained within this package
    open_file() -- open a File object contained within this package

    Internal methods:

    validate_metadata() -- check the metadata, and load information from it
    """

    def __init__(self, loader, name, vers, dir, metadata, resources, external):
        self.loader = loader
        self.name = name
        self.version = vers
        self.key = (name, vers)
        self.encoded_name = encode_package_name(name, vers)
        self.dir = dir
        self.content = None
        self.content_info = {}
        self.import_in_progress = False
        self.metadata = metadata
        self.resources = resources
        self.resource_tree = None
        self.external = external
        self.dependencies = sets.Set()
        self.imported_pkg_specs = {}

    def __repr__(self):
        return '<PackageInfo \'' + self.name + ' ' + str(self.version) + '\'>'

    def validate_metadata(self):
        """validate_metadata() -> None

        Make sure that the metadata object attached to this package
        correctly describes the package. Also loads up various fields
        with information from the metadata object.

        Also checks that the resource tree has a valid shape.

        If anything is discovered to be wrong, this raises PackageLoadError.

        This is called by the package loader (and nothing else should
        call it).
        """

        pkgname = self.name
        metadata = self.metadata

        val = metadata.get_one('boodler.package')
        if (not val):
            raise PackageLoadError(pkgname,
                'no boodler.package metadata entry')
        if (val != pkgname):
            raise PackageLoadError(pkgname,
                'boodler.package does not match package location: ' + val)
                
        val = metadata.get_one('boodler.version')
        if (not val):
            val = '(missing, 1.0 assumed)'
            vers = version.VersionNumber()
        else:
            vers = version.VersionNumber(val)
        if (vers != self.version):
            raise PackageLoadError(pkgname,
                'boodler.version does not match package version: ' + val)

        val = metadata.get_one('boodler.main')
        if (not val):
            pass
        elif (val == '.'):
            pass
        elif (ident_name_regexp.match(val)):
            pass
        else:
            raise PackageLoadError(pkgname,
                'boodler.main is not a module or . :' + val)
                
        val = metadata.get_one('boodler.api_required')
        if (val):
            spec = version.VersionSpec(val)
            if (self.loader.boodler_api_vers):
                if (not spec.match(self.loader.boodler_api_vers)):
                    raise PackageLoadError(pkgname,
                        'boodler.api_required does not match Boodler version: '
                        + val)

        for val in metadata.get_all('boodler.requires'):
            try:
                pos = val.find(' ')
                if (pos < 0):
                    deppkg = val
                    depspec = None
                else:
                    deppkg = val[:pos].strip()
                    depspec = val[pos+1:].strip()
                    depspec = version.VersionSpec(depspec)
                parse_package_name(deppkg)
                deppkg = str(deppkg)
                self.dependencies.add( (deppkg, depspec) )
            except ValueError, ex:
                raise PackageLoadError(pkgname,
                    'boodler.requires line invalid: ' + val)

        for val in metadata.get_all('boodler.requires_exact'):
            try:
                pos = val.find(' ')
                if (pos < 0):
                    raise ValueError('version number required')
                else:
                    deppkg = val[:pos].strip()
                    depspec = val[pos+1:].strip()
                    depspec = version.VersionNumber(depspec)
                parse_package_name(deppkg)
                deppkg = str(deppkg)
                self.dependencies.add( (deppkg, depspec) )
            except ValueError, ex:
                raise PackageLoadError(pkgname,
                    'boodler.requires_exact line invalid: ' + val)

        try:
            self.resource_tree = self.resources.build_tree()
        except ValueError, ex:
            raise PackageLoadError(pkgname,
                'unable to map resources: ' + str(ex))

    def load_dependencies(self):
        """load_dependencies() -> (set, dict, int)

        Attempt to load all the packages which this package depends on.
        
        This returns a triple (good, bad, count):

        - good is a set containing (packagename, version) pairs for every
        package that was loaded successfully. (This will include the original
        package.)
        - bad is a dict. The keys are packagenames which did not load
        successfully. Each maps to a (nonempty) list of version requests
        for that package, which could not be fulfilled. (The list contains
        None, VersionSpecs, and VersionNumbers. Values may occur more than
        once.)
        - count is an int, representing how many actual errors occurred.
        This describes package format problems and read errors. It does not
        include packages that were simply not available. (The bad dict
        includes both errors and not-availables; so len(bad) >= count.)

        If bad is empty, then all dependencies are available.

        Note that the good list may include more than one version of a
        package.
        """
        return self.loader.load_package_dependencies(self)

    def get_content(self):
        """get_content() -> module

        Return the module which is the content of this package.

        Warning: this method imports Python source code from the package
        directory, which means it *executes* Python source code from the
        package directory. Do not call this on untrusted packages.

        A sound-player will have to call this, but a package manager
        should not. (The package creation tool does, though.)
        """
        
        if (not (self.content is None)):
            return self.content
        if (self.import_in_progress):
            # Annoying intermediate case; the module has been added to
            # sys.modules, but not yet to pkg.content.
            return sys.modules.get(self.encoded_name)
        self.loader.import_package_content(self)
        return self.content

    def get_file(self, filename):
        """get_file(filename) -> File

        Get a File object representing a file contained in this package.
        The filename must be in universal format: relative to the package
        root, and written with forward slashes, not backslashes.

        (If the filename is invalid or unsafe, ValueError is raised.
        However, this does not check whether the file exists.)
        """
        
        pathname = build_safe_pathname(self.dir, filename)
        return File(self, pathname, filename)

    def open_file(self, filename, binary=False):
        """open_file(filename, binary=False) -> file

        Open a file contained within this package. The filename must be
        in universal format: relative to the package root, and written
        with forward slashes, not backslashes.

        This is equivalent to get_file(filename).open(binary).
        
        (If the filename is invalid or unsafe, ValueError is raised.
        If the file does not exist, IOError is raised.)
        """
        
        tmpfile = self.get_file(filename)
        return tmpfile.open(binary)

class PackageGroup:
    """PackageGroup: represents all the versions of a particular package
    that are currently available.

    PackageGroup(loader, pkgname) -- constructor

    Create a PackageGroup attached to the given PackageLoader, with the
    given package name.

    Publicly readable fields:

    name -- the package name
    loader -- the PackageLoader which loaded the package

    Public methods:

    get_num_versions() -- return the number of versions available
    get_versions() -- return the versions available for this package
    has_version() -- return whether the package has the given version number
    find_version_match() -- find the most recent version matching the spec

    Internal methods:
    
    discover_versions() -- determine what versions are available
    """

    def __init__(self, loader, pkgname, dirname):
        self.loader = loader
        self.name = pkgname
        self.dir = dirname     # May be None
        self.versions = []

    def __repr__(self):
        return '<PackageGroup \'' + self.name + '\'>'

    def discover_versions(self, fl, external_versions=None):
        """discover_versions(file, external_versions=None) -> None

        Determine what versions are available. We look both at the contents
        of an open Versions file, and at a list of versions found in external
        packages. Either of these may be None.

        This is an internal method; it is called only by load_group, when
        the PackageGroup is created.
        """

        res = {}

        if (fl):
            while (True):
                ln = fl.readline()
                if (not ln):
                    break
                ln = deunicode(ln)
                ln = ln.strip()
                if (not ln):
                    continue
                if (ln.startswith('#')):
                    continue
                vers = version.VersionNumber(ln)
                res[vers] = False

        if (external_versions):
            for vers in external_versions:
                res[vers] = True
            
        self.versions = list(res.keys())
        self.versions.sort()
        self.versions.reverse()

    def get_num_versions(self):
        """get_num_versions() -> int

        Return the number of versions available for this package.
        """
        return len(self.versions)

    def get_versions(self):
        """get_versions() -> list of VersionNumbers

        Return the versions available for this package.
        """
        return list(self.versions)

    def has_version(self, vers):
        """has_version(vers) -> bool
        
        Return whether the package has the given version number available.
        The argument must be a VersionNumber.
        """
        return (vers in self.versions)

    def find_version_match(self, spec=None):
        """find_version_match(spec=None) -> VersionNumber

        Find the most recent version matching the given VersionSpec.
        If no spec is given, just return the most recent version. If
        there are no versions that fit the requirement, returns None.
        """

        for vers in self.versions:
            if (spec is None or spec.match(vers)):
                return vers
        return None

class Metadata:
    """Metadata: represents the contents of a Metadata file.

    Metadata(pkgname, file=None) -- constructor

    Create a Metadata object by reading the given file. (This should
    be a readable file object; typically, the result of opening a
    Metadata file.) It is the caller's responsibility to close the
    file afterwards. If no file is provided, the Metadata will be
    empty.

    (The file should be opened with mode 'rbU'. This is relaxed about
    newlines, but careful about high-bit characters, so that UTF-8
    decoding will work. Note that the file should offer bytes, not
    Unicode characters.)

    The first argument is a package name, but this is only used for
    error messages. If the package name is not known when you read the
    metadata, pass in something usable as a label.

    Public methods:

    get_all() -- get all metadata entries with the given key
    get_one() -- get the metadata entry with the given key
    keys() -- get the keys contained in this Metadata object
    clone() -- create a Metadata object identical to this one
    dump() -- write the contents of this Metadata object to a file
    add() -- add a metadata entry with the given key and value
    delete_all() -- delete all metadata entries with the given key
    """

    def __init__(self, pkgname, fl=None):
        self.pkgname = pkgname
        
        # Map of unicode -> list of unicode.
        self.map = {}

        if (fl is None):
            return

        while True:
            ln = fl.readline()
            if (not ln):
                break
            ln = deunicode(ln)
            ln = ln.strip()
            # Ignore blank lines and comments.
            if (not ln):
                continue
            if (ln.startswith('#')):
                continue

            pos = ln.find(':')
            if (pos < 0):
                raise PackageLoadError(pkgname,
                    'metadata file contains invalid line: ' + ln)
            key = ln[:pos].strip()
            val = ln[pos+1:].strip()
            if (' ' in key):
                raise PackageLoadError(pkgname,
                    'metadata file contains invalid line: ' + ln)

            dict_accumulate(self.map, key, val)

    def __repr__(self):
        return '<Metadata \'' + self.pkgname + '\'>'

    def __len__(self):
        return len(self.map)

    def get_all(self, key):
        """get_all(key) -> list of unicode

        Returns all metadata entries with the given key. If there are none,
        this returns an empty list.

        This maintains the order of entries loaded (or added).
        """
        return self.map.get(key, [])

    def get_one(self, key, default=None):
        """get_one(key, default=None) -> unicode

        Returns the metadata entry with the given key. If there are none,
        this returns None (or the default argument, if supplied). If there
        is more than one such entry, this returns the first.
        """

        res = self.get_all(key)
        if (not res):
            return default
        return res[0]

    def keys(self):
        """keys() -> list of unicode

        Get the keys contained in this Metadata object.
        """
        return list(self.map.keys())

    def clone(self):
        """clone() -> Metadata

        Create a Metadata object identical to this one. (This is a deep
        copy.)
        """

        res = Metadata('<clone>')
        for key in self.map.keys():
            res.map[key] = list(self.map[key])
        return res

    def dump(self, fl, comment=None):
        """dump(file, comment=None) -> None

        Write the contents of this Metadata object to a file. The file
        must be able to accept unicode writes. (Preferably by encoding
        them via UTF-8.) (Note: this doesn't match the constructor,
        which does its own UTF-8 decoding.)

        If comment is a string, or a list of strings, they will appear
        at the top of the file. You need not include the '#' character in
        the comment argument.
        """

        if (type(comment) in [str, unicode]):
            comment = [comment]
        if (comment):
            for val in comment:
                fl.write('# ')
                fl.write(val)
                fl.write('\n')
            fl.write('\n')

        ls = self.keys()
        ls.sort()
        for key in ls:
            for val in self.map[key]:
                fl.write(key)
                fl.write(': ')
                fl.write(val)
                fl.write('\n')

    def add(self, key, val):
        """add(key, val) -> None

        Add a metadata entry with the given key and value.

        (This should only be called by a package management tool. A
        package should not modify its own metadata.)
        """
        dict_accumulate(self.map, key, val)

    def delete_all(self, key):
        """delete_all(key) -> None

        Delete all metadata entries with the given key. If there are none,
        this does nothing.

        (This should only be called by a package management tool. A
        package should not modify its own metadata.)
        """

        if (self.map.has_key(key)):
            self.map.pop(key)

class Resources:
    """Resources: represents the contents of a Resources file.

    Resources(pkgname, file=None) -- constructor

    Create a Resources object by reading the given file. (This should
    be a readable file object; typically, the result of opening a
    Resources file.) It is the caller's responsibility to close the
    file afterwards. If no file is provided, the Resources object will
    be empty.

    (The file should be opened with mode 'rbU'. This is relaxed about
    newlines, but careful about high-bit characters, so that UTF-8
    decoding will work. Note that the file should offer bytes, not
    Unicode characters.)

    The first argument is a package name, but this is only used for
    error messages. If the package name is not known when you read the
    resources, pass in something usable as a label.

    This does not take any pains to verify that the resources exist. That
    is the responsibility of whoever created the package.

    Public methods:

    get() -- get the Resource object with the given key
    keys() -- get the keys contained in this Resources object
    resources() -- get the Resources contained in this Resources object
    build_tree() -- construct a nested dict representing the resources
    dump() -- write the contents of this Resources object to a file
    create() -- create a Resource object with the given key
    """
    
    def __init__(self, pkgname, fl=None):
        self.pkgname = pkgname
        
        # Map of str -> Resource.
        self.map = {}
        # List of keys, in order added
        self.keylist = []

        if (fl is None):
            return

        curdata = None
        
        while True:
            ln = fl.readline()
            if (not ln):
                break
            ln = deunicode(ln)
            ln = ln.strip()
            # Ignore blank lines and comments.
            if (not ln):
                continue
            if (ln.startswith('#')):
                continue

            if (ln.startswith(':')):
                # Beginning of a new section
                key = ln[1:].strip()
                try:
                    parse_resource_name(key)
                    key = str(key)
                except ValueError:
                    raise PackageLoadError(pkgname,
                        'invalid resource: ' + key)
                if (self.map.has_key(key)):
                    raise PackageLoadError(pkgname,
                        'duplicate resource: ' + key)
                curdata = Resource(key)
                self.map[key] = curdata
                self.keylist.append(key)
                continue

            if (not curdata):
                raise PackageLoadError(pkgname,
                    'resource file needs initial ":resource" line')

            pos = ln.find(':')
            if (pos < 0):
                raise PackageLoadError(pkgname,
                    'resource file contains invalid line: ' + ln)
            key = ln[:pos].strip()
            val = ln[pos+1:].strip()
            if (' ' in key):
                raise PackageLoadError(pkgname,
                    'resource file contains invalid line: ' + ln)

            dict_accumulate(curdata.map, key, val)

    def __repr__(self):
        return '<Resources \'' + self.pkgname + '\'>'

    def __len__(self):
        return len(self.map)

    def get(self, key):
        """get(key) -> Resource

        Get the Resource object with the given key. If not found, returns
        None.
        """
        return self.map.get(key)

    def keys(self):
        """keys() -> list of str

        Get the keys contained in this Resources object.

        This maintains the order of resources loaded (or created).
        """
        return list(self.keylist)

    def resources(self):
        """resources() -> list of Resource

        Get the Resources contained in this Resources object.
        """
        return self.map.values()

    def build_tree(self):
        """build_tree() -> dict

        Construct a dict containing the namespaced groups and resources 
        in this Resources object. Individual resources are represented by
        keys; groups are represented by dicts containing more groups
        and resources.

        Example: if the resource keys are
            'one', 'two', 'grp.three', 'grp.four'
        then build_tree() will return {
            'one': 'one',
            'two': 'two',
            'grp': { 'three': 'grp.three', 'four': 'grp.four' }
        }

        A single entry cannot be both a group and a resource. (That is,
        'one' and 'one.two' cannot both be resource keys.) If this
        rule is violated, build_tree() will raise ValueError. Duplicate
        keys also raise ValueError.
        """

        res = {}
        for key in self.keys():
            ls = parse_resource_name(key)
            resel = ls.pop()
            grp = res
            for el in ls:
                subgrp = grp.get(el)
                if (subgrp is None):
                    subgrp = {}
                    grp[el] = subgrp
                if (type(subgrp) != types.DictType):
                    raise ValueError('resource cannot be an attr of another resource: ' + key)
                grp = subgrp
            if (grp.has_key(resel)):
                raise ValueError('resource cannot contain an attr of another resource: ' + key)
            grp[resel] = key

        return res

    def dump(self, fl, comment=None):
        """dump(file, comment=None) -> None

        Write the contents of this Resources object to a file. The file
        must be able to accept unicode writes. (Preferably by encoding
        them via UTF-8.) (Note: this doesn't match the constructor,
        which does its own UTF-8 decoding.)

        If comment is a string, or a list of strings, they will appear
        at the top of the file. You need not include the '#' character in
        the comment argument.
        """

        if (type(comment) in [str, unicode]):
            comment = [comment]
        if (comment):
            for val in comment:
                fl.write('# ')
                fl.write(val)
                fl.write('\n')
            fl.write('\n')

        ls = self.keys()
        ls.sort()
        for key in ls:
            fl.write(':')
            fl.write(key)
            fl.write('\n')
            res = self.map[key]
            res.dump(fl)
            fl.write('\n')

    def create(self, key):
        """create(key) -> Resource

        Create a Resource object with the given key. If the key is not
        a valid resource key, or if it already exists, this raises ValueError.
        
        (This should only be called by a package management tool. A
        package should not modify its own metadata.)
        """
        
        try:
            parse_resource_name(key)
            key = str(key)
        except ValueError:
            raise ValueError(self.pkgname + ': invalid resource name: ' + key)
            
        if (self.map.has_key(key)):
            raise ValueError(self.pkgname + ': resource already exists: ' + key)
        res = Resource(key)
        self.map[key] = res
        self.keylist.append(key)
        return res

class Resource:
    """Resource: represents one section in a Resources file.

    Resource(key) -- constructor

    Create a Resource with the given key. (The resource key is a
    Python-style qualified identifier: "foo" or "Mod.Foo".)

    Public methods:

    get_all() -- get all metadata entries with the given key
    get_one() -- get the metadata entry with the given key
    keys() -- get the keys contained in this Resource object
    dump() -- write the contents of this Resource object to a file
    add() -- add a metadata entry with the given key and value
    delete_all() -- delete all metadata entries with the given key
    """
    
    def __init__(self, key):
        # Map of unicode -> list of unicode.
        self.key = key
        self.map = {}

    def __repr__(self):
        return '<Resource \'' + self.key + '\'>'

    def get_all(self, key):
        """get_all(key) -> list of unicode

        Returns all metadata entries with the given key. If there are none,
        this returns an empty list.
        """
        return self.map.get(key, [])

    def get_one(self, key, default=None):
        """get_one(key, default=None) -> unicode

        Returns the metadata entry with the given key. If there are none,
        this returns None (or the default argument, if supplied). If there
        is more than one such entry, this returns the first.
        """

        res = self.get_all(key)
        if (not res):
            return default
        return res[0]

    def keys(self):
        """keys() -> list of unicode

        Get the keys contained in this Resource object.
        """
        return list(self.map.keys())

    def dump(self, fl):
        """dump(file) -> None

        Write the contents of this Resource object to a file.
        """

        ls = self.keys()
        ls.sort()
        for key in ls:
            for val in self.map[key]:
                fl.write(key)
                fl.write(': ')
                fl.write(val)
                fl.write('\n')

    def add(self, key, val):
        """add(key, val) -> None

        Add a metadata entry with the given key and value.

        (This should only be called by a package management tool. A
        package should not modify its own metadata.)
        """
        dict_accumulate(self.map, key, val)

    def delete_all(self, key):
        """delete_all(key) -> None

        Delete all metadata entries with the given key. If there are none,
        this does nothing.

        (This should only be called by a package management tool. A
        package should not modify its own metadata.)
        """

        if (self.map.has_key(key)):
            self.map.pop(key)


class File:
    """File: represents a file in a package.

    File(pkg, pathname, univname=None) -- constructor

    Creates a file in the given package. (The package may be None if you
    are creating a File object ad-hoc. Unless it's for a "mix-in" sound
    file -- those need to know where they live.)

    The pathname should be a valid, non-relative pathname in native
    form. You can also supply the universal, relative-to-the-package
    pathname as univname; this is used only when printing the filename
    for human eyes.

    The file need not exist. But since this class only handles reading
    files, a File that refers to a nonexistent path can only generate
    IOError when opened.

    Public method:

    open() -- open the file for reading
    """
    
    def __init__(self, pkg, pathname, univname=None):
        self.package = pkg
        self.pathname = pathname
        self.univname = univname
        # If the file was pulled from Resource metadata, the metadata
        # field will be set (by the caller). See attrify_filename().
        self.metadata = None
    def __repr__(self):
        if (self.univname):
            return '<File \'./' + self.univname + '\'>'
        else:
            return '<File \'' + self.pathname + '\'>'
    def open(self, binary=False):
        """open(binary=False) -> file

        Open the file for reading. Returns a Python file object.
        If binary is False, the file is opened with newline translation
        ('rU'); otherwise, in binary mode ('rb').
        """
        if (binary):
            mode = 'rb'
        else:
            mode = 'rU'
        return open(self.pathname, mode)

class MemFile(File):
    """MemFile: represents a file which exists only in memory.
    This is a subclass of File.

    MemFile(dat, suffix, label) -- constructor

    Creates a file whose contents are the (byte) string dat. The label
    is used for displaying the object. The suffix is available to any
    user of the file who wants to know what type it is by filename.
    (Bleah, Unix.) The suffix should begin with a dot (".aiff", etc.)

    Publicly readable fields:

    suffix -- the suffix passed in

    Public method:

    open() -- open the file for reading
    """
    
    def __init__(self, dat, suffix, label):
        File.__init__(self, None, '<'+label+'>')
        self.data = dat
        self.suffix = suffix
        self.label = label
    def __repr__(self):
        return '<MemFile <' + self.label + '>>'
    def open(self, binary=False):
        return cStringIO.StringIO(self.data)

# Regular expression for valid Python identifiers: letters, digits, and
# underscores. (But not starting with a digit.)
ident_name_regexp = re.compile('\\A[a-zA-Z_][a-zA-Z_0-9]*\\Z')
        
# Regular expression for valid package names: one or more elements,
# separated by periods. Each element must contain only lower-case letters,
# digits, and underscores. An element may not start with a digit.
package_name_regexp = re.compile('\\A[a-z_][a-z_0-9]*(\.([a-z_][a-z_0-9]*))*\\Z')

# Regular expression for valid resource names: one or more elements,
# separated by periods. Each element must contain only letters, digits,
# and underscores. An element may not start with a digit.
resource_name_regexp = re.compile('\\A[a-zA-Z_][a-zA-Z_0-9]*(\.([a-zA-Z_][a-zA-Z_0-9]*))*\\Z')

# Regexp which matches one capital letter (as a group)
capital_letter_regexp = re.compile('([A-Z])')

# Regexp which matches a caret followed by one letter (as a group)
caret_letter_regexp = re.compile('\\^([A-Za-z])')

def parse_package_version_spec(val):
    """parse_package_version_spec(val) -> (pkgname, VersionNumber)
        or (pkgname, VersionSpec) or (pkgname, None)

    Parse a package identifier together with its version spec 
    (e.g., "org.boodler.sample:1.0") or exact version spec 
    (e.g., "org.boodler.sample::1.0"). If neither is present,
    the second value of the return tuple will be None.
    
    Raises a ValueError if the name was in any way invalid. (Thus,
    this function can be used to ensure that a package name is valid.)
    """

    vers = None
    
    pos = val.find(':')
    if (pos >= 0):
        spec = val[ pos+1 : ]
        val = val[ : pos ]
        if (spec.startswith(':')):
            vers = version.VersionNumber(spec[ 1 : ])
        else:
            vers = version.VersionSpec(spec)

    parse_package_name(val)

    return (val, vers)

def parse_package_name(pkgname):
    """parse_package_name(pkgname) -> list of str

    Parse a package name (e.g., "org.boodler.sample") into a list of
    elements (["org", "boodler", "sample"]).

    Raises a ValueError if the name was in any way invalid. (Thus,
    this function can be used to ensure that a package name is valid.)
    """
    
    res = package_name_regexp.match(pkgname)
    if (not res):
        raise ValueError('invalid package name: ' + pkgname)

    # Now we know there are no Unicode-only characters
    pkgname = str(pkgname)

    ls = pkgname.split('.')
    if ('' in ls):
        raise ValueError('invalid package name: ' + pkgname)
    return ls

def encode_package_name(pkgname, vers):
    """encode_package_name(pkgname, vers) -> str

    Convert a Boodler package name and VersionNumber into a legal Python
    identifier. (This is used as the "real" name for the package module --
    the name Python knows about.)

    The encoding guarantees that two modules with different (pkgname, vers)
    keys will produce different identifiers.
    """

    vers = str(vers)
    vers = capital_letter_regexp.sub('C\\1', vers)
    res = pkgname + 'V' + vers
    res = res.replace('+', 'P')
    res = res.replace('-', 'M')
    res = res.replace('_', 'U')
    res = res.replace('.', '_')
    return '_BooPkg_'+res

def parse_resource_name(resname):
    """parse_resource_name(resname) -> list of str

    Parse a resource name (e.g., "voice.Doh") into a list of elements
    (["voice", "Doh"]).

    Raises a ValueError if the name was in any way invalid. (Thus,
    this function can be used to ensure that a resource name is valid.)
    """
    
    res = resource_name_regexp.match(resname)
    if (not res):
        raise ValueError('invalid resource name: ' + resname)

    # Now we know there are no Unicode-only characters
    resname = str(resname)

    ls = resname.split('.')
    if ('' in ls):
        raise ValueError('invalid resource name: ' + resname)
    return ls

def build_safe_pathname(basedir, filename):
    """build_safe_pathname(basedir, filename) -> str

    Take a relative filename and append it to a base pathname, checking
    for dangerous practices.

    The relative filename must be in universal format: slashes, no
    backslashes. It must not begin with a slash, and it must not contain
    '..' elements. (Single dots are okay.) If these rules are violated,
    this function raises a ValueError.

    The base pathname must be in platform format (ie, on Windows, it
    should be backslash-delimited). The result will be in platform
    format as well.

    The result will be plain ascii characters, and will be stored as a
    str (even if the arguments are unicode). This is mostly to work around
    some annoyances with the aifc module, which refuses to accept unicode
    pathnames.
    """

    if ('\\' in filename):
        raise ValueError('attempt to get filename with backslash: ' + filename)
    if (filename.startswith('/')):
        raise ValueError('attempt to get absolute filename: ' + filename)
    els = filename.split('/')
    if ('..' in els):
        raise ValueError('attempt to get filename with ..: ' + filename)
    # Normalize out double slashes and trailing slashes
    els = [ el for el in els if el ]
    # Normalize out single dots
    els = [ el for el in els if (el != '.') ]
    pathname = os.path.join(basedir, *els)
    pathname = str(pathname)
    return pathname

def dict_accumulate(dic, key, val):
    """dict_accumulate(dic, key, val) -> bool

    Build a dict which maps keys to arrays. dic[key] is an array containing
    all the values which have been added under the key. (If none have,
    the dict will not contain that key.)

    Returns whether this is the first time this key has been added.
    """

    ls = dic.get(key)
    if (ls is None):
        dic[key] = [val]
        return True
    else:
        ls.append(val)
        return False

def dict_all_values(dic, ls=None):
    """dict_all_values(dic, ls=None) -> ls

    Return a list of all the values in dic, walking recursively into
    all dicts that are values. (If the argument is not a dict, this
    just returns [dic].)

    If the optional argument ls is provided, the values are appended
    to it (and it is also returned).
    """

    if (ls is None):
        ls = []
    if (type(dic) != dict):
        ls.append(dic)
    else:
        for val in dic.values():
            dict_all_values(val, ls)
    return ls
        
utf8_decoder = codecs.getdecoder('utf-8')
def deunicode(ln):
    """deunicode(ln) -> unicode

    Decode a UTF-8 string into a unicode object. This also strips off the
    BOM character (byte order mark, U+FEFF) which occurs at the start of
    some UTF-8 files.

    (The 'utf-8-sig' decoder would take care of the BOM for us, but it
    doesn't exist in Python 2.3.5)
    """

    (ln, dummy) = utf8_decoder(ln)
    return ln.lstrip(u'\ufeff')

# late imports
from boopak.pload import PackageLoadError, PackageNotFoundError

