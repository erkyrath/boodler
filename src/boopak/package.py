# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""package: Import and export utilities for Boodler sound packages.

These functions allow a Boodler package to manage itself, its metadata,
and its dependencies. Most Python scripts in sound packages will start 
with "import package".

Some of these functions are meant to be called only during a package 
import operation. That is, when the package's module code is being
evaluated. You can call these functions at the module's top level, but
not later on. Do not try to call them from inside your module's functions 
or methods.

Public functions:

now_building() -- locate the module which is currently being imported
get_info() -- get the PackageInfo which describes a Boodler module
get_metadata() -- get the metadata which describes a Boodler module
open_file() -- open a file by name, in a Boodler module
get_file() -- get a File by name, in a Boodler module
subimport() -- import a submodule from a Boodler module
bimport() -- import and return a Boodler sound module
bexport() -- make a module's file resources available in the module's namespace

Internal functions:

info_being_imported() -- locate the PackageInfo which is being imported
"""

__all__ = [ 
    'now_building', 
    'get_info', 'get_metadata', 'open_file', 'get_file', 
    'subimport', 'bimport', 'bexport'
]

import pinfo
import pload

GLOBAL_WARNING = '(perhaps you tried to import a Boodler package outside the Boodler loader, or you called a top-level package function while not at the top level of your package)'

def info_being_imported():
    """info_being_imported() -> PackageInfo

    Locate the PackageInfo which is currently in the process of being
    loaded. If no import is in progress, this raises an exception.

    (This is an internal function; do not call.)
    """
    
    loader = pload.PackageLoader.global_loader
    if (loader is None or loader.currently_importing is None):
        raise Exception('unable to determine which package is being imported ' + GLOBAL_WARNING)
    return loader.currently_importing

def now_building():
    """now_building() -> module

    Locate the module which is currently being imported. You may only call
    this from a sound module's top level; it returns the very module in
    whose top level it is.

    This function exists because various parts of Boodler associate
    information with the module, and a module might want to get that
    information for itself.
    """

    curpkg = info_being_imported()
    return curpkg.get_content()
            
def get_info(mod=None):
    """get_info(mod=None) -> PackageInfo

    Get the PackageInfo which describes a Boodler module.

    If no argument is given (mod=None), this returns information about 
    the module itself. You may only use this form from a sound module's 
    top level.

    If mod is an already-imported module, this returns information about
    it. You may call this form at any time.

    If mod is a PackageInfo, this returns it. (This form exists for 
    consistency with other functions in this package.)
    """

    if (mod is None):
        return info_being_imported()
    if (isinstance(mod, pinfo.PackageInfo)):
        return mod
    loader = pload.PackageLoader.global_loader
    if (loader is None):
        raise Exception('unable to find module importer ' + GLOBAL_WARNING)
    if (not (loader.currently_importing is None)):
        curpkg = loader.currently_importing
        if (curpkg.get_content() == mod):
            return curpkg
    pkg = loader.module_info.get(mod)
    if (pkg is None):
        raise Exception('module not recognized: ' + str(mod))
    return pkg

def get_metadata(mod=None):
    """get_metadata(mod=None) -> Metadata

    Get the metadata which describes a Boodler module.

    If no argument is given (mod=None), this returns metadata about 
    the module itself. You may only use this form from a sound module's 
    top level.

    If mod is an already-imported module, this returns metadata about
    it. You may call this form at any time.

    If mod is a PackageInfo, this returns metadata from the module it
    describes.
    """

    pkg = get_info(mod)
    return pkg.metadata

def open_file(filename, binary=False, mod=None):
    """open_file(filename, binary=False, mod=None) -> file

    Open a file by name, in a Boodler module. This is equivalent to
    get_file(filename, mod).open(binary).

    The filename should be relative to the module root, and written
    in universal form -- forward slashes only. An invalid or unsafe
    filename will raise ValueError.

    If no argument is given (mod=None), this opens a file from
    the module itself. You may only use this form from a sound module's 
    top level.

    If mod is an already-imported module, this opens a file from
    it. You may call this form at any time.

    If mod is a PackageInfo, this opens a file from the module it
    describes.
    """

    pkg = get_info(mod)
    return pkg.open_file(filename, binary)

def get_file(filename, mod=None):
    """get_file(filename, mod=None) -> File

    Get a File by name, in a Boodler module. This returns a File object --
    see the pinfo package -- not an open Python file.

    The filename should be relative to the module root, and written
    in universal form -- forward slashes only. An invalid or unsafe
    filename will raise ValueError.

    If no argument is given (mod=None), this gets a file from
    the module itself. You may only use this form from a sound module's 
    top level.

    If mod is an already-imported module, this gets a file from
    it. You may call this form at any time.

    If mod is a PackageInfo, this gets a file from the module it
    describes.
    """

    pkg = get_info(mod)
    return pkg.get_file(filename)

def subimport(modname, mod=None):
    """subimport(modname, mod=None) -> value or None

    Import a submodule from a Boodler sound module. This replicates
    the standard "import" statement. The modname may be a qualified
    symbol name, or '*', or a symbol name ending with '.*'

    If no argument is given (mod=None), this imports symbols from
    the module itself. You may only use this form from a sound module's 
    top level.

    If mod is an already-imported module, this imports symbols from
    it. You may call this form at any time.

    If mod is a PackageInfo, this imports symbols from the module it
    describes.

    NOTE: The exact behavior of this function may change, as I figure out
    what it's good for. At the moment, the primary use is to allow
    a module to import its submodules:

        import package
        # A top-level declaration in the module:
        package.subimport('submodule')
    """

    pkg = get_info(mod)
    glob = pkg.get_content().__dict__

    if (modname == '*' or modname.endswith('.*')):
        if (modname == '*'):
            fullname = pkg.encoded_name
        else:
            fullname = pkg.encoded_name+'.'+(modname[ : -2 ])
        __import__(fullname, glob, locals(), ['*'])
        return
        
    res = __import__(pkg.encoded_name+'.'+modname, glob, locals(), [])
    for el in modname.split('.'):
        res = getattr(res, el)
    return res

def bimport(pkgname, spec=None):
    """bimport(pkgname, spec=None) -> module

    Import and return a Boodler sound module. You must pass the fully-
    qualified module name. 

    You may also supply a version specification. (If you do not, you will 
    get the latest available version.) The spec may be a VersionSpec
    object, a string (representing a VersionSpec), or a VersionNumber (to 
    request an exact version).

    You may only call this from a sound module's top level. (When one
    sound module depends on another, it generally wants to load it
    immediately. This ensures that dependency problems show up right
    away. The dependency tracking system in Boodler's package creator
    also relies on this pattern.)

    (To load packages and agents at runtime, based on user input, use
    Agent.load_described().)
    """

    curpkg = info_being_imported()
    loader = curpkg.loader
    if (not (loader.import_recorder is None)):
        loader.record_import(curpkg, pkgname, spec)
    pkg = loader.load(pkgname, spec)
    mod = pkg.get_content()
    return mod

def bexport(resname=None):
    """bexport(resname=None) -> None

    Make a module's file resources available in the module's namespace.
    (This exports them, in the sense that another module will be able
    to look up yourmodule.file_resource to get the file.)

    If you provide no argument (resname=None), all file resources are
    loaded in. If you provide the name of a resource, it alone is loaded;
    if you provide the name of a resource group, all resources in that
    group (and subgroups) are loaded.

    In all cases, submodules are created where necessary. (So if the
    resource name is 'sub.file', your module will end up with a 'dir'
    submodule, if it didn't have one already.) 

    If you plan a submodule which contains both Python code and file
    resources, you must call subimport() before bexport().

    You may only call this from a sound module's top level.
    """
    ### Just about files -- maybe rename

    curpkg = info_being_imported()
    loader = pload.PackageLoader.global_loader
    mod = curpkg.get_content()
    
    grp = curpkg.resource_tree
    if (resname):
        ls = resname.split('.')
        for key in ls:
            if (not grp.has_key(key)):
                raise Exception('resource not found: ' + resname)
            grp = grp.get(key)

    ls = pinfo.dict_all_values(grp)
    for resname in ls:
        res = curpkg.resources.get(resname)
        if (not res):
            raise Exception('resource not found: ' + resname)
        filename = res.get_one('boodler.filename')
        if (filename):
            loader.attrify_filename(curpkg, mod, resname, res, filename)
