# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""pload: The PackageLoader class.

This module contains PackageLoader, which is responsible for loading and
tracking the Boodler packages in your collection.

(This does not install or modify packages in your collection. The collect
module handles those tasks.)
"""

import sys
import os.path
import imp
import types
import sets

from boopak import version

Filename_Versions = 'Versions'
Filename_Metadata = 'Metadata'
Filename_Resources = 'Resources'

class PackageLoader:
    """PackageLoader: manages a package collection, loading packages as
    requested. Also maintains an (in-memory) cache, to speed up load
    requests.

    You can also specify extra directories, outside the collection,
    to load packages from.

    This class does not deal with writing package files into the
    collection directory. (For that, see PackageCollection, in
    collect.py.)

    The PackageLoader is used in two ways. A Boodler UI will want to
    call the list_all_current_packages() method, which loads all the
    descriptive information in the collection. A Boodler sound-playing
    process will only call the load() method, which loads the particular
    classes desired.

    PackageLoader(dirname, boodler_api_vers=None, importing_ok=False)
        -- constructor

    Create a PackageLoader, given the name of a directory which contains
    a collection of packages.

    If a version is provided (either as a VersionNumber or a string which
    converts to one), then this is noted as the Boodler version which
    packages must be compatible with. (As noted in the boodler.api_required
    metadata field.)

    (Note that the boodler.api_required field is not checked until the
    package is actually loaded, which is after version selection occurs.
    Therefore, it is best if the collection only contains packages which
    are compatible with the installed Boodler version. None of this is
    likely to be important, since the Boodler API version is not expected
    to change much after 2.0.)

    If the importing_ok flag is false, this loader will refuse to load
    (that is, execute) Python code in packages. This is the default.

    Note that only one importing_ok loader can exist in the process.
    (This is because loaded modules need to be able to find the loader
    through static variables.)

    Publicly readable fields:

    collecdir -- the directory containing the package collection
    currently_importing -- during an import operation, the package which is
        being imported (at the moment)

    Public methods:

    load() -- load a package, given its name and a version spec
    load_group() -- load a PackageGroup, given its package name
    clear_cache() -- erase the PackageLoader's entire knowledge
    generate_package_path() -- return a pathname in the collection dir
    add_external_package() -- add an external directory to load a package from
    remove_external_package() -- remove an external directory
    clear_external_packages() -- remove all external directories
    find_all_dependencies() -- determine which packages depend on which others
    list_all_packages() -- return a list of all the available packages
    list_all_current_packages() -- list the most recent versions of packages
    load_package_dependencies() -- load all packages which a package depends on
    import_package_content() -- import the package's content, if it hasn't been
    load_item_by_name() -- import and return an item in a package
    find_item_resources() -- find the Resource for an item in a package
    attrify_filename() -- given a filename, add its File to the module
    start_import_recording() -- stub, overridden in PackageCollection
    stop_import_recording() -- stub, overridden in PackageCollection

    Internal methods:

    load_specific() -- load a package, given its name and a specific version
    discover_all_groups() -- search through the collection directory

    Class global field:

    global_loader -- If a PackageLoader can import packages, it needs to
        be accessible from a global context. (See the package module.)
        PackageLoader.global_loader is where to find it.
    """

    # The PackageLoader which has importing_ok
    global_loader = None

    # This is always None for a PackageLoader; see PackageCollection for
    # its use.
    import_recorder = None

    def __init__(self, collecdir, boodler_api_vers=None, importing_ok=False):
        if (type(boodler_api_vers) in [str, unicode]):
            boodler_api_vers = version.VersionNumber(boodler_api_vers)
        self.boodler_api_vers = boodler_api_vers
            
        if (collecdir is None):
            raise ValueError('PackageLoader requires a collection directory')

        # We allow the loader to run even without a collection directory,
        # so that TestSoundAgent will work.
        #if (not os.path.isdir(collecdir)):
        #   raise ValueError('PackageLoader collection directory is not readable: '
        #       + collecdir)
        
        self.collecdir = collecdir

        self.importing_ok = False
        self.module_info = None

        # Set up the (empty) caches
        self.package_groups = {}
        self.package_names = {}
        self.packages = {}
        self.external_dirs = {}
        self.collection_scanned = False
        self.all_deps = None
        self.currently_importing = None

        if (importing_ok):
            if (PackageLoader.global_loader):
                raise ValueError('A PackageLoader already exists with importing_ok set')
            self.importing_ok = True
            PackageLoader.global_loader = self
            self.module_info = {}

    def load(self, pkgname, versionspec=None):
        """load(pkgname, versionspec=None) -> PackageInfo

        Load a package, given its name and a version spec.

        If no second argument is given, the most recent available version
        of the package is loaded. If the argument is a VersionNumber,
        that version will be loaded. If it is a VersionSpec, the most
        recent version that matches the spec will be loaded. A string
        value will be converted to a VersionSpec (not a VersionNumber).

        This generates a PackageNotFoundError if no matching package
        is available. It generates PackageLoadError if the package
        was malformed in some way which prevented loading.
        """
        
        if (type(versionspec) in [str, unicode]):
            versionspec = version.VersionSpec(versionspec)
            
        pgroup = self.load_group(pkgname)
        if (not pgroup.get_num_versions()):
            raise PackageNotFoundError(pkgname,
                'no versions available')

        if (isinstance(versionspec, version.VersionNumber)):
            if (not pgroup.has_version(versionspec)):
                raise PackageNotFoundError(pkgname,
                    'version \'' + str(versionspec) + '\' not available')
            vers = versionspec
        elif ((versionspec is None)
            or isinstance(versionspec, version.VersionSpec)):
            vers = pgroup.find_version_match(versionspec)
        else:
            raise PackageLoadError(pkgname,
                'load spec must be a string, VersionSpec, or VersionNumber')

        if (not vers):
            raise PackageNotFoundError(pkgname,
                'no version matching \'' + str(versionspec) + '\'')
        
        pkg = self.load_specific(pkgname, vers)
        if (self.currently_importing):
            # Record what package imported this one, and with what spec
            self.currently_importing.imported_pkg_specs[pkgname] = versionspec
        return pkg

    def load_group(self, pkgname):
        """load_group(self, pkgname) -> PackageGroup

        Load a PackageGroup, given its package name.

        This is not tremendously useful for outside users, although you
        can call it if you want. A PackageGroup represents all the
        available versions of a particular package.
        """
        
        pgroup = self.package_groups.get(pkgname)
        if (pgroup):
            return pgroup

        # Make sure the name is valid.
        parse_package_name(pkgname)
        pkgname = str(pkgname)

        dirname = None
        versionfile = None

        # We determine the list of available versions by listing the
        # package directory in the collection tree. But we have to include
        # any versions that come in through external directories, too.
        
        # Create a list of external versions.
        external_versions = []
        for (name, vers) in self.external_dirs.keys():
            if (pkgname == name):
                external_versions.append(vers)

        # Find the package directory. (But it's possible that there *is*
        # no package directory. That's an error, unless we have external
        # versions -- in which case we keep trucking forward with the
        # dirname set to None.)

        dirname = self.generate_package_path(pkgname)
        if (not os.path.isdir(dirname)):
            if (not external_versions):
                raise PackageNotFoundError(pkgname,
                    'package directory does not exist')
            dirname = None

        # Open the Versions file in the package directory. (If we have
        # a package directory, and a Versions file.)

        if (dirname):
            versionfile = os.path.join(dirname, Filename_Versions)
            if (not os.path.isfile(versionfile)):
                # We don't raise an exception here, because the install
                # command needs to tolerate a screwy Collection long
                # enough to fix it.
                versionfile = None

        # Create the PackageGroup object itself.
        pgroup = PackageGroup(self, pkgname, dirname)

        fl = None
        try:
            if (dirname and versionfile):
                fl = open(versionfile, 'rbU')
            # Go through the Versions file and the external versions list
            # (either of which may be nonexistent).
            pgroup.discover_versions(fl, external_versions)
        finally:
            if (not (fl is None)):
                fl.close()

        # Add the new group to the cache.
        self.package_groups[pkgname] = pgroup
        return pgroup

    def load_specific(self, pkgname, vers):
        """load_specific(pkgname, vers) -> PackageInfo

        Load a package, given its name and a specific version number.
        (The version number may be a VersionNumber or a string that
        can be converted to one.)

        This is an internal call; external callers should use load().

        (load_specific() is intended to be called by a package
        function which has already consulted package_groups and a
        PackageGroup object. If you bypass those, you might load
        a package which is not part of any PackageGroup. That would
        leave the cache in a confusing state.)
        """
        
        if (type(vers) in [str, unicode]):
            vers = version.VersionNumber(vers)
            
        pkg = self.packages.get( (pkgname, vers) )
        if (pkg):
            return pkg

        # Make sure the name is valid.
        parse_package_name(pkgname)
        pkgname = str(pkgname)

        exrec = self.external_dirs.get( (pkgname, vers) )
        if (exrec is None):
            is_external = False
            dirname = self.generate_package_path(pkgname, vers)
        else:
            is_external = True
            dirname = exrec.dirname

        # dirname is now the directory where the package should reside.
        # This may be in the collection or external.
            
        if (not os.path.isdir(dirname)):
            raise PackageNotFoundError(pkgname,
                'package version directory does not exist')

        # Read the metadata. (But if the external directory record has
        # an overriding Metadata object, use that instead.)

        if (is_external and exrec.metadata):
            metadata = exrec.metadata
        else:
            metadatafile = os.path.join(dirname, Filename_Metadata)
            if (not os.path.isfile(metadatafile)):
                raise PackageLoadError(pkgname,
                    'package has no metadata file')

            fl = open(metadatafile, 'rbU')
            try:
                metadata = boopak.pinfo.Metadata(pkgname, fl)
            finally:
                fl.close()

        # Read the resources (if there are any). Again, there may be an
        # overriding Resources object.

        if (is_external and exrec.resources):
            resources = exrec.resources
        else:
            resourcesfile = os.path.join(dirname, Filename_Resources)
            if (os.path.isfile(resourcesfile)):
                fl = open(resourcesfile, 'rbU')
                try:
                    resources = boopak.pinfo.Resources(pkgname, fl)
                finally:
                    fl.close()
            else:
                # Create an empty resources object
                resources = boopak.pinfo.Resources(pkgname)

        # Create the PackageInfo object and look through its metadata.
        pkg = PackageInfo(self, pkgname, vers, dirname,
            metadata, resources, is_external)
        pkg.validate_metadata()

        # Valid; we can now add it to the cache.
        self.packages[(pkgname, vers)] = pkg
        self.package_names[pkg.encoded_name] = pkg
        return pkg

    def clear_cache(self):
        """clear_cache() -> None

        Erase the PackageLoader's entire knowledge of what groups and
        packages are available.

        This should be called whenever packages are added to, modified
        in, or deleted from the collection directory.
        """
        
        self.packages.clear()
        self.package_groups.clear()
        self.package_names.clear()
        if (self.all_deps):
            for dic in self.all_deps:
                dic.clear()
            self.all_deps = None
        self.collection_scanned = False

    def generate_package_path(self, pkgname, vers=None):
        """generate_package_path(pkgname, vers=None) -> str

        Return the pathname in the collection directory which contains the
        given package group (if vers is None), or the given package
        (otherwise).

        This does not create the directory or check for its existence.

        This is guaranteed to create a distinct pathname for every
        pkgname or (pkgname, vers) pair. This is true even on case-
        insensitive filesystems, which is a wrinkle, since version
        strings are case-sensitive. We work around this by putting
        a "^" character before each capital letter.
        """
        
        dirname = os.path.join(self.collecdir, pkgname)
        if (not (vers is None)):
            val = str(vers)
            val = boopak.pinfo.capital_letter_regexp.sub('^\\1', val)
            dirname = os.path.join(dirname, val)
        return dirname

    def add_external_package(self, dirname, metadata=None, resources=None):
        """add_external_package(dirname, metadata=None, resources=None) ->
            (str, VersionNumber)

        Add an external directory to load a package from. The argument
        must be a complete (unpacked) Boodler directory, with a
        Metadata file. That package will then be loadable (possibly
        hiding a package in the collection directory).

        The metadata and resources fields, if supplied, override the 
        Metadata and Resources files in the directory. (The files do not
        even have to exist.) If the metadata and resources fields are
        None, the directory's files are checked as usual. (This override
        feature is used by the package creation tool. It should not be
        used for any other purpose.)

        Returns the name and version of the package that was found.

        Since this changes the set of what packages are available,
        it implicitly invokes clear_cache().

        The external package facility is not intended to be how most
        packages are loaded. Most packages should be in the collection
        directory. You might add an external package in your development
        workspace (while developing a soundscape), or in a temporary
        download directory (while deciding whether to install a newly-
        downloaded package).
        """

        label = '<external '+dirname+'>'
        exrec = ExternalDir(dirname, metadata, resources)

        if (not os.path.isdir(dirname)):
            raise PackageLoadError(label,
                'not a directory')

        # Load the metadata file, and see what package/version we are
        # dealing with. (But only if a metadata object wasn't handed to
        # us!)

        if (not metadata):
            metadatafile = os.path.join(dirname, Filename_Metadata)
            if (not os.path.isfile(metadatafile)):
                raise PackageLoadError(label,
                    'package has no metadata file')
        
            fl = open(metadatafile, 'rbU')
            try:
                metadata = boopak.pinfo.Metadata(label, fl)
            finally:
                fl.close()

        val = metadata.get_one('boodler.package')
        if (not val):
            raise PackageLoadError(label,
                'no boodler.package metadata entry')
        parse_package_name(val)
        pkgname = str(val)
        
        val = metadata.get_one('boodler.version')
        if (not val):
            vers = version.VersionNumber()
        else:
            vers = version.VersionNumber(val)

        # Add this to the external directory table. (We have not actually
        # loaded the package.)

        self.external_dirs[(pkgname, vers)] = exrec
        self.clear_cache()
        return (pkgname, vers)

    def remove_external_package(self, dirname):
        """remove_external_package(dirname) -> None

        Remove an external directory. The argument should be one that was
        previously passed to add_external_package(). (If it is not a
        current external directory, this silently does nothing.)

        Since this changes the set of what packages are available,
        it implicitly invokes clear_cache().
        """

        keys = [ key for key in self.external_dirs.keys()
            if (self.external_dirs[key].dirname == dirname) ]
        if (not keys):
            return
        for key in keys:
            self.external_dirs.pop(key)
        self.clear_cache()

    def clear_external_packages(self):
        """clear_external_packages() -> None

        Remove all external directories.

        Since this changes the set of what packages are available,
        it implicitly invokes clear_cache().
        """

        if (not self.external_dirs):
            return
        self.external_dirs.clear()
        self.clear_cache()

    def discover_all_groups(self):
        """discover_all_groups() -> None

        Search through the collection directory, and load all the PackageGroups
        that are available.

        This only searches the on-disk directory the first time you call
        it. To force it to re-scan the directory, call clear_cache() first.
        """
        
        if (self.collection_scanned):
            return

        # This is a little tricky. We go through the collection tree, but
        # we also have to go through the external directory list. (Because
        # there might be some external packages that do not correspond
        # to any group in the collection tree.)
            
        dirlist = os.listdir(self.collecdir)
        for key in dirlist:
            if (key.startswith('.')):
                continue
            dirname = os.path.join(self.collecdir, key)
            # Directories might appear to have upper-case names, but
            # the group name must be lower-case. (This will fail to load
            # an upper-case directory on a case-sensitive filesystem. It
            # will work in a case-preserving filesystem.)
            key = key.lower()
            if (not os.path.isdir(dirname)):
                continue
            try:
                parse_package_name(key)
                self.load_group(key)
            except:
                continue

        # Go through the external directory list. If the external package
        # is not already in a loaded group, load its group. (The load_group
        # method is smart enough to find it, even though there is no
        # matching directory in the collection tree.)

        for (name, vers) in self.external_dirs.keys():
            if (not self.package_groups.has_key(name)):
                try:
                    self.load_group(name)
                except:
                    continue

        # Now we never need to do this again. (Until the cache is cleared.)
        self.collection_scanned = True

    def find_all_dependencies(self):
        """find_all_dependencies() -> (dict, dict, dict)

        Go through the entire collection, and determine exactly which
        packages depend on which other packages.

        This returns a triple (forward, backward, bad). In the forward
        dict, each package key (pkgname,vers) maps to an array of package
        keys which the package depends on. In the backward dict, each
        package key maps to an array of packages which depend *on* it.
        In the bad dict, each package key maps to an array of
        (pkgname,spec) of dependencies which could not be loaded.

        (In the bad dict tuples, the second element may be None, a
        VersionSpec, or a VersionNumber.)
        
        This only searches the on-disk directory the first time you call
        it. To force it to re-scan the directory, call clear_cache() first.
        """
        
        if (self.all_deps):
            return self.all_deps

        # We'll need a complete list of groups, first.
        self.discover_all_groups()
        
        forward = {}
        backward = {}
        bad = {}

        # Iterate through every version of every group.
        
        for (pkgname, pgroup) in self.package_groups.items():
            for vers in pgroup.versions:
                try:
                    pkg = self.load_specific(pkgname, vers)
                    for (deppkg, depspec) in pkg.dependencies:
                        try:
                            dep = self.load(deppkg, depspec)
                            dict_accumulate(forward, pkg.key, dep.key)
                            dict_accumulate(backward, dep.key, pkg.key)
                        except PackageLoadError, ex:
                            dict_accumulate(bad, pkg.key, (deppkg, depspec))
                except PackageLoadError, ex:
                    pass

        self.all_deps = (forward, backward, bad)
        return self.all_deps

    def list_all_packages(self):
        """list_all_packages() -> list of (str, list of VersionNumber)

        Search through the collection directory, and return a list of all the
        available packages. 

        Returns a list of (packagename, list of version) tuples. The top
        list is in no particular order, but the version list will be sorted
        newest-to-oldest.

        This only searches the on-disk directory the first time you call
        it. To force it to re-scan the directory, call clear_cache() first.
        """
        
        self.discover_all_groups()
        res = []
        for (pkgname, pgroup) in self.package_groups.items():
            ls = []
            for vers in pgroup.get_versions():
                try:
                    self.load_specific(pkgname, vers)
                    ls.append(vers)
                except PackageLoadError, ex:
                    pass
            if (ls):
                res.append( (pkgname, ls) )
        return res

    def list_all_current_packages(self):
        """list_all_current_packages() -> list of (str, VersionNumber)

        Search through the collection directory, and return a list of all the
        available packages. If multiple versions of a package are available,
        only the most recent will be listed.

        Returns a list of (packagename, version) tuples (in no particular
        order).

        This only searches the on-disk directory the first time you call
        it. To force it to re-scan the directory, call clear_cache() first.
        """
        
        self.discover_all_groups()
        res = []
        for (pkgname, pgroup) in self.package_groups.items():
            vers = pgroup.find_version_match()
            try:
                self.load_specific(pkgname, vers)
                res.append( (pkgname, vers) )
            except PackageLoadError, ex:
                pass
        return res

    def load_package_dependencies(self, pkg):
        """load_package_dependencies(pkg) -> (set, dict, int)

        Attempt to load all the packages which the given package depends on.
        The argument should be a PackageInfo object.

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
        
        found_ok = sets.Set()
        not_found = {}
        errors = 0

        # Simple breadth-first walk of the dependency tree.

        to_check = [pkg]
        found_ok.add(pkg.key)
        
        while (to_check):
            pkg = to_check.pop(0)
            for (deppkg, depspec) in pkg.dependencies:
                try:
                    dep = self.load(deppkg, depspec)
                    if (not (dep.key in found_ok)):
                        found_ok.add(dep.key)
                        to_check.append(dep)
                except PackageLoadError, ex:
                    if (not isinstance(ex, PackageNotFoundError)):
                        errors += 1
                    dict_accumulate(not_found, deppkg, depspec)

        return (found_ok, not_found, errors)

    def import_package_content(self, pkg):
        """import_package_content(pkg) -> None

        Import the package's content, if it hasn't already been imported.

        Warning: this method imports Python source code from the package
        directory, which means it *executes* Python source code from the
        package directory. Do not call this on untrusted packages.

        A sound-player will have to call this, but a package manager
        should not.
        """

        if (not self.importing_ok):
            raise Exception('this loader may not import package data!')
        if (not (pkg.content is None)):
            return
        if (pkg.import_in_progress):
            raise Exception('package imported while import is in progress: ' + pkg.name)

        attrify_resources = False
        map_resources = False
        
        maincode = pkg.metadata.get_one('boodler.main')
        if (not maincode):
            attrify_resources = True
            (file, pathname, desc) = imp.find_module('emptymodule', boopak.__path__)
        else:
            map_resources = True
            (file, pathname, desc) = imp.find_module(maincode, [pkg.dir])
            
        if (not desc[0] in ['', '.py', '.pyc']):
            if (file):
                file.close()
            raise PackageLoadError(pkg.name,
                'module must be .py or .pyc: ' + pathname)

        # Imports can occur recursively, so we always hold on to the previous
        # value and restore it afterward.

        previously_importing = self.currently_importing
        self.currently_importing = pkg
        pkg.import_in_progress = True
        
        try:
            mod = imp.load_module(pkg.encoded_name, file, pathname, desc)
        finally:
            # Clean up.
            if (file):
                file.close()
            pkg.import_in_progress = False
            checkpkg = self.currently_importing
            self.currently_importing = previously_importing
            if (checkpkg != pkg):
                raise Exception('import stack unstable: ' + pkg.name)

        if (attrify_resources):
            for res in pkg.resources.resources():
                filename = res.get_one('boodler.filename')
                if (filename):
                    self.attrify_filename(pkg, mod, res.key, res, filename)

        if (map_resources):
            # Look for declarations in the module which are named in
            # the resources map. Cache the mapping from the declaration
            # to the resource object.
            for res in pkg.resources.resources():
                keyls = parse_resource_name(res.key)
                submod = mod
                for key in keyls:
                    submod = getattr(submod, key, None)
                    if (submod is None):
                        break
                if (not (submod is None)):
                    pkg.content_info[submod] = res
        
        # The import is complete.
        self.module_info[mod] = pkg
        pkg.content = mod

    def load_item_by_name(self, name, package=None):
        """load_item_by_name(name, package=None) -> value

        Given a string that names a resource -- for example,
        'com.eblong.example/reptile.Hiss' -- import the module and
        return the resource object.

        If the string begins with a slash ('/boodle.builtin.NullAgent')
        then the regular Python modules are searched. No importing
        is done in this case; it is really intended only for the
        contents of boodle.agent.

        If the string ends with a slash ('com.eblong.example/'), then
        the module itself is returned.

        If the package argument is supplied (a PackageInfo object), it
        becomes the package to look in for unqualified resource names
        ('reptile.Hiss'). If no package argument is supplied, then
        an unqualified resource name raises ValueError.
        """

        pos = name.find('/')
        if (pos < 0):
            if (package is None):
                raise ValueError('argument must be of the form package/Resource')
            mod = package.get_content()
        elif (pos == 0):
            # consult Python's module map
            name = name[ 1 : ]
            headtail = name.split('.', 1)
            if (len(headtail) != 2):
                raise ValueError('argument must be of the form package/Resource')
            (modname, name) = headtail
            mod = sys.modules.get(modname)
            if (mod is None):
                raise ValueError('not found in Python modules: ' + modname)
        else:
            pkgname = name[ : pos ]
            name = name[ pos+1 : ]
            
            pkgspec = None
            pos = pkgname.find(':')
            if (pos >= 0):
                val = pkgname[ pos+1 : ]
                pkgname = pkgname[ : pos ]
                if (val.startswith(':')):
                    val = val[ 1 : ]
                    pkgspec = version.VersionNumber(val)
                else:
                    pkgspec = version.VersionSpec(val)

            package = self.load(pkgname, pkgspec)
            mod = package.get_content()

        if (not name):
            # "module/" returns the module itself
            return mod
        
        namels = name.split('.')
        try:
            res = mod
            for el in namels:
                res = getattr(res, el)
            return res
        except AttributeError, ex:
            raise ValueError('unable to load ' + name + ' (' + str(ex) + ')')

    def find_item_resources(self, obj):
        """find_item_resources(obj) -> (PackageInfo, Resource)

        Given an object in a package module, try to find the package,
        and the Resource that represents the object. If it has no metadata
        defined, this returns a blank Resource object.

        This tries to use object attributes such as __module__ and __name__
        to identify it. This will work on classes (but not instances)
        defined in a module; this covers the normal case of Agent classes.
        It will also work on File objects defined in a module. Beyond
        that, results are questionable.
        """
        ### rename to "find_item_metadata"?

        modname = getattr(obj, '__module__', None)
        if (modname is None):
            raise ValueError('does not appear to have been defined inside a module: ' + str(obj))

        pos = modname.find('.')
        if (pos < 0):
            basemodname = modname
            prefix = None
        else:
            basemodname = modname[:pos]
            prefix = modname[pos+1:]

        pkg = self.package_names.get(basemodname)
        if (pkg is None):
            raise ValueError('does not appear to have been defined inside a Boodler package: ' + str(obj))

        # Check the content cache.
        res = pkg.content_info.get(obj)
        if (not (res is None)):
            return (pkg, res)

        # Look for a Resource we missed.
        objname = getattr(obj, '__name__', None)
        if (objname):
            if (prefix):
                objname = prefix+'.'+objname
            res = pkg.resources.get(objname)
            if (not (res is None)):
                pkg.content_info[obj] = res
                return (pkg, res)

        # Return a blank Resource.
        if (objname is None):
            objname = 'UNNAMED'
        res = boopak.pinfo.Resource(objname)
        pkg.content_info[obj] = res
        return (pkg, res)

    def attrify_filename(self, pkg, mod, wholekey, res, filename):
        """attrify_filename(pkg, mod, wholekey, res, filename) -> None

        Given a filename, create a File representing it, and store the
        File in the module at a location defined by wholekey. Submodules
        are created as necessary. The res argument is the Resource
        object associated with wholekey.

        The filename must be in universal format: relative to the package
        root, and written with forward slashes, not backslashes.

        (If the filename is invalid or unsafe, ValueError is raised.
        However, this does not check whether the file exists.)
        """

        file = pkg.get_file(filename)
                
        keyls = parse_resource_name(wholekey)
        attr = keyls.pop()
        for key in keyls:
            submod = getattr(mod, key, None)
            if (submod is None):
                # Create an empty submodule.
                (fl, pathname, desc) = imp.find_module('emptymodule', boopak.__path__)
                try:
                    submod = imp.load_module(mod.__name__+'.'+key,
                        fl, pathname, desc)
                finally:
                    # Clean up.
                    if (fl):
                        fl.close()
                setattr(mod, key, submod)
                
            if (type(submod) != types.ModuleType):
                raise ValueError('resource key based on non-module: ' + wholekey)
            if (mod.__name__+'.'+key != submod.__name__):
                raise ValueError('resource key based on imported module: ' + wholekey)
            mod = submod

        # We've drilled down so that mod is the next-to-last element
        # of the original wholekey.
        
        setattr(mod, attr, file)
        file.metadata = res
        
        # Set properties analogous to a statically-declared object. This
        # will help with find_item_resources() later on.
        file.__module__ = mod.__name__
        file.__name__ = attr

    def start_import_recording(self):
        """start_import_recording() -> None

        Stub, overridden in PackageCollection. In a PackageLoader, this
        does nothing.
        """
        pass

    def stop_import_recording(self):
        """stop_import_recording() -> dic

        Stub, overridden in PackageCollection. In a PackageLoader, this
        does nothing and returns an empty dict.
        """
        return {}
    
class ExternalDir:
    """ExternalDir: information about a package directory outside the
    collection.

    This is a simple data structure, stored as the values in the loader's
    external_dirs mapping.

    ExternalDir(dirname, metadata=None, resources=None) -- constructor

    The dirname contains the (local) pathname of the directory to consider.

    The metadata and resources fields, if supplied, override the Metadata
    and Resources files in the directory. (The files do not even have to
    exist.) If the metadata and resources fields are None, the directory's
    files are checked as usual. (This override feature is used by the
    package creation tool.)

    Publicly readable fields:

    dirname -- the directory which contains the package
    metadata -- the supplied Metadata object (if any)
    resources -- the supplied Resources object (if any)
    """

    def __init__(self, dirname, metadata=None, resources=None):
        self.dirname = dirname
        self.metadata = metadata
        self.resources = resources

class PackageLoadError(Exception):
    """PackageLoadError: represents a failure to load a package.
    
    This represents some kind of internal error or package formatting
    problem. (If the package simply was not available, the subclass
    PackageNotFoundError will be used.)
    """
    def __init__(self, pkgname, val='unable to load'):
        Exception.__init__(self, pkgname + ': ' + val)

class PackageNotFoundError(PackageLoadError):
    """PackageNotFoundError: represents a failure to load a package
    because it was not in the collection.
    """
    pass


# late imports

import boopak
from boopak.pinfo import dict_accumulate, parse_package_name, parse_resource_name
from boopak.pinfo import PackageGroup, PackageInfo
