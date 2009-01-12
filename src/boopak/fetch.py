# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""fetch: Utility classes for downloading a file from a server.

This is used by PackageCollection to fetch packages from an archive
server.
"""

import urllib2

class Fetcher:
    """Fetcher: represents a file which is being downloaded from a web
    site, or some other source which potentially take a while.

    The idea is to use this object in a loop:

        while (not fetcher.is_done()):
            fetcher.work()

    One could equally well manage several fetchers in parallel. (But, see
    the caveat in URLFetcher.)

    Fetcher(loader) -- constructor

    The argument must be a PackageCollection. (When the download is complete,
    the loader's downloaded_files map will be updated.)

    (This is an abstract base class, so creating a Fetcher is not of
    any particular use.)
    """
    
    def __init__(self, loader):
        self.loader = loader
        
    def is_done(self):
        """is_done() -> bool

        Return whether the fetching process is complete.
        """
        return True
        
    def work(self):
        """work() -> None

        Do another increment of work.
        """
        pass

class URLFetcher(Fetcher):
    """URLFetcher: represents a file which is being downloaded via a URL.

    URLFetcher(loader, url, filename) -- constructor

    The loader argument must be a PackageCollection. The URL is the one
    to download; the data will be written to filename. (The directory
    containing filename must exist already.)

    Caveat: Python's urllib2 always uses a blocking socket. Therefore,
    any call to work() may take arbitrarily long. (It will actually take
    as long as necessary to get another 1000 bytes. Which could be forever.)
    This is not the way the Fetcher class is supposed to work, but it's what
    we've got.
    """
    
    def __init__(self, loader, url, filename):
        Fetcher.__init__(self, loader)
        self.url = url
        self.filename = filename
        self.done = None
        self.infl = None
        self.outfl = None

        try:
            self.infl = urllib2.urlopen(url)
            self.outfl = open(filename, 'wb')
            self.done = False
        finally:
            if (self.done is None):
                self.closeall()

    def __del__(self):
        # If this falls into the GC pit without being completed, close the
        # files.
        self.closeall()

    def closeall(self):
        """closeall() ->

        Close the in (HTTP) and out (file write) streams, if necessary.

        (This is an internal method. Do not call.)
        """
        
        if (self.infl):
            self.infl.close()
            self.infl = None
        if (self.outfl):
            self.outfl.close()
            self.outfl = None

    def is_done(self):
        """is_done() -> bool

        Return whether the fetching process is complete.
        """
        return self.done

    def work(self):
        """work() -> None

        Do another increment of work. If the download is complete, close
        the files.
        """
        
        if (self.done):
            return
        dat = self.infl.read(1000)
        if (dat):
            self.outfl.write(dat)
            return

        # End of the URL download.
        self.done = True
        self.closeall()
        self.loader.downloaded_files[self.url] = self.filename
