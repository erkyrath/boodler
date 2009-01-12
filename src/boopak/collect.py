# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""collect: The PackageCollection class.

This module contains PackageCollection, which is responsible for installing
and updating the Boodler packages in your collection. It is a subclass
of PackageLoader.
"""

import os
import os.path
import zipfile

from boopak import pload
from boopak import version
from boopak import fetch

# Filenames of particular significance.
Filename_Collection = 'Collection'
Filename_Download = 'Download'
Suffix_PackageArchive = '.boop'

# Three places that a user can grab a package from.
Source_PACKAGE = 1
Source_FILE    = 2
Source_URL     = 3

# The Boodler repository URL. (With closing slash, please.)
REPOSITORY_URL = 'http://boodler.org/lib/'

### between commands, this maintains a state of no external packages.

class PackageCollection(pload.PackageLoader):
    """PackageCollection: manages a package collection. This is a subclass
    of PackageLoader; it adds the ability to install and delete packages.

    This class is intended to be used by a Boodler UI. It should not be
    used by a sound-playing process.

    Most of the methods defined here (installing, deleting, even examining
    packages) invoke the clear_cache() method defined in PackageLoader.
    This reflects the fact that any package change can change the
    dependency tree, which is part of what PackageLoader caches. Clearing
    the cache entirely is somewhat crude, but it's simple and it works.

    PackageCollection(basedir=None, coldir=None, dldir=None,
        boodler_api_vers=None, importing_ok=False) -- constructor

    Create a PackageCollection. It requires two directory names:
    coldir is the collection of packages, and dldir is a temporary
    workspace for storing downloaded and unzipped files. Or you can just
    provide a basedir, in which case these will be basedir/Collection
    and basedir/Download (respectively).

    The coldir and dldir will be created, if necessary. When the
    PackageCollection shuts down, it will delete the files it has created
    in the dldir.
        
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
    It should only be true if the create-package command is to be used.

    Publicly readable fields:

    collecdir -- the directory containing the package collection
    downloaddir -- the directory containing temporary files and directories
    currently_creating -- during a create operation, the package which is
        being created (at the moment)

    Public methods:

    find_source() -- load a package from the collection, a .boop file, or
        the Internet
    install_source() -- install a package into the collection from a file
        or the Internet
    fetch_source() -- prepare to download a package from the Internet
    delete_package() -- delete a package from the collection
    delete_group() -- delete all versions of a package from the collection
    delete_whole_collection() -- delete all packages in the entire collection
    start_import_recording() -- begin noting all bimport() calls
    stop_import_recording() -- stop noting bimport() calls, and return them
    record_import() -- note a bimport() call by a package being imported
    create_temp_dir() -- create a new, empty directory in the temporary dir
    create_temp_file() -- create the pathname of a new temporary file
    clean_temp() -- clean up the temporary workspace
    shut_down() -- shut down the PackageCollection

    Internal methods:
    
    rewrite_versions_file() -- write (or overwrite) a new Versions file
    """
    
    # Counter for creating unique names for the download directory.
    instance_count = 0
    
    def __init__(self, basedir=None, coldir=None, dldir=None,
        boodler_api_vers=None, importing_ok=False):

        # basedir is overridden by coldir and dldir, if they are provided.
        if (coldir is None and not (basedir is None)):
            coldir = os.path.join(basedir, Filename_Collection)
        if (dldir is None and not (basedir is None)):
            dldir = os.path.join(basedir, Filename_Download)
        
        if (coldir is None):
            raise ValueError('PackageCollection requires a collection directory (or base directory)')
        if (dldir is None):
            raise ValueError('PackageCollection requires a download directory (or base directory)')
        if (coldir == dldir):
            raise ValueError('PackageCollection collection and download directories must be different')

        # Create coldir, if needed, and then initialize the base class to
        # use it.
        if (not os.path.isdir(coldir)):
            os.makedirs(coldir)
        pload.PackageLoader.__init__(self, coldir,
            boodler_api_vers=boodler_api_vers,
            importing_ok=importing_ok)

        # Generate a unique subdirectory of dldir to work in.
        PackageCollection.instance_count += 1
        val = ('tmp-' + str(os.getpid()) + '-'
            + str(PackageCollection.instance_count))
        dldir = os.path.join(dldir, val)
        self.downloaddir = dldir

        # Various caches.
        self.download_count = 0
        self.downloaded_files = {}
        self.unpacked_files = {}
        self.currently_creating = None

    def find_source(self, srctype, loc):
        """find_source(srctype, loc) -> PackageInfo

        Load a package given (srctype, loc) in one of the following forms:

            (Source_PACKAGE, (pkgname, vers))
            (Source_FILE, filename)
            (Source_URL, url)

        Source_PACKAGE will be found and loaded from the collection.
        (The vers part may be a VersionNumber, VersionSpec, or None.)
        
        Source_FILE will be unzipped (in the temporary work directory)
        and then loaded. (However, the temporary directory will not be
        kept in the loader's external package list. So you cannot reload
        the package without doing another find_source(). To install the
        file permanently, use install_source().)

        Source_URL will be unzipped and loaded, but only if it has already
        been fetched with fetch_source(). This is a blivet in the API;
        it would be nice if find_source() could fetch the URL too, but
        that is potentially a slow operation, and find_source() is not
        set up for slow operations.
        """
        
        if (srctype == Source_PACKAGE):
            (pkgname, vers) = loc
            return self.load(pkgname, vers)
            
        if (srctype == Source_URL):
            # See where it was fetched to.
            localfile = self.downloaded_files.get(loc)
            if (not localfile):
                raise ValueError('URL not downloaded: ' + loc)
            loc = localfile

        # We now have a file (either downloaded or specified directly).
        # See if we have already unzipped it to the temp directory. (We
        # identify files by name and modtime, so that if a file changes
        # on disk, we will unzip it again.)
        
        if (not os.path.isfile(loc)):
            raise ValueError('Unable to read file: ' + loc)
        modtime = os.path.getmtime(loc)
        
        pkg = self.unpacked_files.get( (loc, modtime) )
        if (pkg):
            return pkg

        # We need to unzip this. Pick a new temporary directory.
        self.download_count += 1
        dirname = 'unpack-' + str(self.download_count)
        dirname = os.path.join(self.downloaddir, dirname)

        unpack_zip_file(loc, dirname)

        # Find the directory in the unzipped package which contains the
        # Metadata file. Then try to load the package.
        realdirname = locate_package_directory(dirname)
        (pkgname, vers) = self.add_external_package(realdirname)

        try:
            pkg = self.load(pkgname, vers)
            if (not pkg.external):
                raise ValueError('Unpacked package does not appear to be external: ' + str(pkg))
        
            self.unpacked_files[(loc, modtime)] = pkg
            return pkg
        finally:
            # We don't leave the package in the loader's list. (We do
            # keep the unzipped directory around, in case the user wants
            # to examine it again.
            self.clear_external_packages()
        
    def install_source(self, srctype, loc):
        """install_source(srctype, loc) -> PackageInfo

        Install a package given (srctype, loc) in one of the following forms:

            (Source_PACKAGE, (pkgname, vers))
            (Source_FILE, filename)
            (Source_URL, url)

        Source_PACKAGE is not a valid argument for this function, since
        it refers to a package which is already installed.

        Source_FILE will be unzipped (in the temporary work directory)
        and then moved to the collection directory.

        Source_URL will be unzipped and installed, but only if it has
        already been fetched with fetch_source(). This is a blivet in
        the API; it would be nice if install_source() could fetch the
        URL too, but that is potentially a slow operation, and
        install_source() is not set up for slow operations.
        """
        
        if (srctype == Source_PACKAGE):
            ### should this fetch from a known URL on boodler.org?
            (pkgname, vers) = loc
            raise ValueError('Package is already installed: ' + pkgname + ' ' + str(vers))

        # Tentatively load the package, so that we are sure that it
        # exists. This also lets us determine the package name and version.
        pkg = self.find_source(srctype, loc)
        if (not pkg.external):
            raise ValueError('Install package does not appear to be external: ' + str(pkg))
        
        # If we successfully install, we will be moving the unzipped
        # version of the package from our temporary workspace. This
        # invalidates the entry in self.unpacked_files, so we will have
        # to remove that entry.
        download_keys = [ key for key in self.unpacked_files.keys()
            if (self.unpacked_files[key] == pkg) ]

        (pkgname, vers) = pkg.key
        # Tentatively load the package group, so we can add to its
        # Versions file.
        groupdir = self.generate_package_path(pkgname)
        try:
            pgroup = self.load_group(pkgname)
            if (groupdir != pgroup.dir):
                raise ValueError('PackageGroup is in wrong directory: ' + pgroup.dir)
            newversions = pgroup.get_versions()
        except pload.PackageNotFoundError, ex:
            # The group does not exist at all, yet.
            newversions = []
        srcdir = pkg.dir
        destdir = self.generate_package_path(pkgname, vers)

        # Time to install. Start by clearing all the cached information
        # we are about to invalidate.
        self.clear_cache()
        for key in download_keys:
            self.unpacked_files.pop(key)

        # This slightly overwrought code ensures that the *parent*
        # directory (the group directory) exists, but the package directory
        # does not. (There might be an old package directory, which we
        # must clear out.) Then we move the newly-unzipped directory from
        # the temp workspace.
        if (not os.path.exists(destdir)):
            os.makedirs(destdir)
        remove_recursively(destdir)
        os.rename(srcdir, destdir)

        # Write a new Versions file.
        if (not (vers in newversions)):
            newversions.append(vers)
        self.rewrite_versions_file(groupdir, newversions, pkgname)

        # Load the newly-installed package, to make sure that it works,
        # and return it.
        return self.load(pkgname, vers)

    def fetch_source(self, srctype, loc):
        """fetch_source(srctype, loc) -> None or Fetcher
        
        Make sure that a package of the form (Source_URL, url) is
        downloaded and ready to be passed to find_source() or
        install_source(). If it already is (or if srctype is Source_FILE
        or Source_PACKAGE), then this function returns None, and the
        caller may proceed.

        If the URL is *not* downloaded, this returns a Fetcher object.
        This should be called in some wise like this:
        
            while (not fetcher.is_done()):
                fetcher.work()

        Once fetcher.is_done() returns true, the package is downloaded,
        and the caller may proceed to find_source() or install_source().
        """
        
        if (srctype == Source_PACKAGE):
            return None
        if (srctype == Source_FILE):
            return None

        if (self.downloaded_files.has_key(loc)):
            return None

        # Create the download directory, if necessary.      
        if (not os.path.isdir(self.downloaddir)):
            os.makedirs(self.downloaddir)
        # Invent a filename for the download.
        self.download_count += 1
        filename = 'dl-' + str(self.download_count) + Suffix_PackageArchive
        filename = os.path.join(self.downloaddir, filename)
        fetcher = fetch.URLFetcher(self, loc, filename)
        return fetcher

    def delete_package(self, pkgname, vers=None):
        """delete_package(pkgname, vers=None) -> None

        Delete a package from the collection.
        
        If no second argument is given, the most recent available version
        of the package is deleted. If the argument is a VersionNumber,
        that version will be deleted. If it is a VersionSpec, the most
        recent version that matches the spec will be deleted. A string
        value will be converted to a VersionSpec (not a VersionNumber).

        If the last version of a package is deleted, the entire group
        directory is deleted too.
        """
        
        pgroup = self.load_group(pkgname)
        pkg = self.load(pkgname, vers)
        if (pkg.external):
            raise ValueError('External package cannot be deleted: ' + pkg.dir)
        newversions = [ vers for vers in pgroup.get_versions()
            if (vers != pkg.version) ]

        self.clear_cache()
        if (not newversions):
            if (pgroup.dir):
                remove_recursively(pgroup.dir)
        else:
            self.rewrite_versions_file(pgroup.dir, newversions, pkg.name)
            remove_recursively(pkg.dir)

    def delete_group(self, pkgname):
        """delete_group(pkgname) -> None

        Delete all versions of a package from the collection.

        This method does not generate an error if the package group
        is malformed, or even missing.
        """
        
        dirname = self.generate_package_path(pkgname)
        self.clear_cache()
        remove_recursively(dirname)

    def delete_whole_collection(self):
        """delete_whole_collection() -> None

        Delete all packages in the entire collection.
        """
        
        self.clear_cache()
        remove_recursively(self.collecdir)
        if (not os.path.isdir(self.collecdir)):
            os.makedirs(self.collecdir)

    def rewrite_versions_file(self, dirname, versionlist, pkgname='<unknown>'):
        """rewrite_versions_file(dirname, versionlist,
            pkgname='<unknown>') -> None

        Write (or overwrite) a new Versions file, in the given directory,
        with the given list of VersionNumber objects. The pkgname is stored
        in a comment line.

        The versionlist may be altered (sorted) by this function, so the
        caller should not pass a list object which will be used again.
        """
        
        versionlist.sort()
        if (not os.path.isdir(dirname)):
            os.makedirs(dirname)
        filename = os.path.join(dirname, pload.Filename_Versions)
        outfl = open(filename, 'w')
        try:
            outfl.write('# Package: ' + pkgname + '\n')
            for vers in versionlist:
                outfl.write(str(vers) + '\n')
        finally:
            outfl.close()

    def start_import_recording(self):
        """start_import_recording() -> None

        Set the collection to noting all bimport() calls in packages being
        imported. (This is used only during package creation, to figure
        out dependencies.)
        """
        
        if (not (self.import_recorder is None)):
            raise ValueError('Recording was already started')
        self.import_recorder = {}

    def stop_import_recording(self):
        """stop_import_recording() -> dic

        Stop noting bimport() calls, and return a list of all such calls
        noted. The return dict maps (name,version) pairs to lists
        of import requests by that package. Each request in such a list
        looks like (name,spec), or (name,version) for an exact request,
        for (name,None) for an any-version request.
        """
        
        if (self.import_recorder is None):
            raise ValueError('Recording was never started')
        res = self.import_recorder
        self.import_recorder = None
        return res

    def record_import(self, pkg, name, spec=None):
        """record_import(pkg, name, spec=None) -> None

        Note a bimport() call by a package being imported. This should
        only be called by bimport().
        """
        
        if (type(spec) in [str, unicode]):
            spec = version.VersionSpec(spec)
            
        if (isinstance(spec, version.VersionNumber)):
            isexact = True
        elif ((spec is None) or isinstance(spec, version.VersionSpec)):
            # ok
            isexact = False
        else:
            return

        ls = self.import_recorder.get(pkg.key)
        if (not ls):
            ls = []
            self.import_recorder[pkg.key] = ls

        ls.append( (name,spec) )

    def create_temp_dir(self, label='tmp'):
        """create_temp_dir(label='tmp') -> str

        Return the pathname of a new, empty directory in the temporary
        workspace. This directory will be deleted by the next clean_temp()
        call.

        The optional label argument will be used in the directory name.
        """
        
        # Invent a new name.
        self.download_count += 1
        dirname = 'dir-' + label + '-' + str(self.download_count)
        dirname = os.path.join(self.downloaddir, dirname)
        # Create it.
        os.makedirs(dirname)
        return dirname
        
    def create_temp_file(self, label='tmp'):
        """create_temp_file(label='tmp') -> str

        Return the pathname of a new file in the temporary workspace.
        The file will not exist, but can be opened for writing. This
        file will be deleted by the next clean_temp() call.

        The optional label argument will be used in the file name.
        """
        
        # Create the download directory, if necessary.      
        if (not os.path.isdir(self.downloaddir)):
            os.makedirs(self.downloaddir)
        # Invent a new name.
        self.download_count += 1
        filename = 'file-' + label + '-' + str(self.download_count)
        filename = os.path.join(self.downloaddir, filename)
        return filename
        
    def clean_temp(self):
        """clean_temp() -> None

        Clean up the temporary download workspace. Delete all files, and
        clear the internal caches that referred to them.
        """
        
        self.unpacked_files.clear()
        self.downloaded_files.clear()
        self.clear_external_packages()
        remove_recursively(self.downloaddir)

    def shut_down(self):
        """shut_down() -> None

        Shut down the PackageCollection. It may not be used again.

        This cleans up the temporary download workspace.
        """
        
        self.clear_cache()
        self.clean_temp()
        self.downloaddir = None
        self.collecdir = None


def remove_recursively(name):
    """remove_recursively(path) -> None

    Delete a file or directory (including all contents, for a directory).
    This deletes symlinks but does not follow them.
    """

    if (not name):
        raise ValueError('Attempt to remove nameless directory.')
    
    if (name.startswith(os.sep) and not (os.sep in name[1:])):
        raise ValueError('Cannot remove top-level directory: ' + name)

    if (os.path.islink(name)):
        os.remove(name)
        return

    if (not os.path.exists(name)):
        return

    if (not os.path.isdir(name)):
        os.remove(name)
        return
        
    dirlist = os.listdir(name)
    for key in dirlist:
        remove_recursively(os.path.join(name, key))
    os.rmdir(name)

def unpack_zip_file(filename, dirname):
    """unpack_zip_file(filename, dirname) -> None

    Unpack the Zip archive at filename, creating directory dirname.

    If there was a directory dirname already, it is deleted before the
    unpacking begins.

    This raises zipfile.BadZipfile if filename is not a valid Zip file.
    """
    
    fl = zipfile.ZipFile(filename)

    try:
        # Delete the original directory, if it exists
        remove_recursively(dirname)
        # And then create it, empty
        os.makedirs(dirname)
        
        for name in fl.namelist():
            # Some sanity-checking. Remember that filenames come out of Zip
            # files with / delimiters, regardless of what OS you're on or
            # what OS created the Zip file.
            if (name.startswith('/')):
                raise ValueError('Absolute pathname found in Zip file: ' + filename)
            ls = name.split('/')
            if ('..' in ls):
                raise ValueError('.. found in pathname in Zip file: ' + filename)
            if (ls[-1] == ''):
                # Directory
                ls.pop()
                dest = os.path.join(dirname, *ls)
                if (not os.path.isdir(dest)):
                    os.makedirs(dest)
            else:
                # File
                dat = fl.read(name)
                if (len(ls) > 1):
                    dest = os.path.join(dirname, *(ls[:-1]))
                    if (not os.path.isdir(dest)):
                        os.makedirs(dest)
                dest = os.path.join(dirname, *ls)
                outfl = open(dest, 'wb')
                outfl.write(dat)
                outfl.close()
                dat = None
    finally:
        fl.close()

def locate_package_directory(dirname):
    """locate_package_directory(dirname) -> str

    Given a directory name, locate the (sole) subdirectory which is a
    package directory. (This may be the same as the directory that was
    passed in.)

    This is necessary because some Zip archives unpack directly into the
    destination directory; others create a subdirectory and unpack there.
    We locate the "real" package directory by looking for a Metadata file.
    If there is none, but there is a single subdirectory, we search
    there. (Files and directories beginning with "." are ignored in this
    process; that lets us cope with Mac directories and their ".DS_Store"
    annoyances.)

    Raises ValueError if no package directory is found.
    """
    
    if (not os.path.isdir(dirname)):
        raise ValueError('Not a directory: ' + dirname)
        
    while (True):
        name = os.path.join(dirname, pload.Filename_Metadata)
        if (os.path.isfile(name)):
            return dirname
        ls = os.listdir(dirname)
        ls = [ name for name in ls if (not name.startswith('.')) ]
        if (not ls):
            raise ValueError('Directory is empty: ' + dirname)
        if (len(ls) > 1):
            raise ValueError('Directory does not contain '
                + pload.Filename_Metadata + ': ' + dirname)
        dirname = os.path.join(dirname, ls[0])
        if (not os.path.isdir(dirname)):
            raise ValueError('Directory does not contain '
                + pload.Filename_Metadata + ': ' + dirname)
