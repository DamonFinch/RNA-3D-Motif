"""

A program for downloading .pdb, .cif, and .pdb1 files for all RNA-containing
3D structures.

Downloads the files specified in self.filetypes in all directories supplied
as arguments. The file is downloaded to the first folder if necessary
and then copied to the other directories.

Example:
python PdbDownloader.py ~/Desktop/f1 ~/Desktop/f2 ~/Desktop/f3

"""

import logging
import os
import sys
import urllib2
import shutil
import glob
import xml.dom.minidom

import utils


import PdbInfoLoader
from MotifAtlasBaseClass import MotifAtlasBaseClass

logger = logging.getLogger(__name__)


class PdbDownloader(MotifAtlasBaseClass):
    """
    """
    def __init__(self):
        """
            locations is where pdbs will be placed
            pdbs is an array the files to download
        """
        MotifAtlasBaseClass.__init__(self)
        self.baseurl = 'http://www.rcsb.org/pdb/files/'
        self.ba_url = 'http://www.pdb.org/pdb/rest/getEntityInfo?structureId='
        self.filetypes = ['.pdb', '.pdb1', '.cif']
        self.locations = []
        self.pdbs = []
        self.config['email']['subject'] = 'Pdb File Sync'

    def get_pdb_list(self):
        """
            Get the latest list of all RNA-containing 3D structures from PDB
        """
        p = PdbInfoLoader.PdbInfoLoader()
        p.get_all_rna_pdbs()
        self.pdbs = p.pdbs
        logger.info('%i RNA 3D structures found in PDB' % len(self.pdbs))

    def set_locations(self, locations):
        """
            Fail if any of the locations doesn't exist
        """
        for location in locations:
            location = os.path.expanduser(location)
            if os.path.exists(location):
                self.locations.append(location)
            else:
                logger.critical("Location %s doesn't exist" % location)
                self.set_email_subject('Pdb sync failed')
                self.send_report()
                sys.exit(1)
        logger.info('Saving files in %s' % ', '.join(locations))

    def download_files(self):
        """
            Downloads .pdb, .pdb1, and .cif files to the first location, then
            copies all the files over to all the other locations.
        """
        for pdb_id in self.pdbs:
            [self.download(pdb_id, x) for x in self.filetypes]
            if len(self.locations) > 1:
                self.make_copies(pdb_id)

    def get_bio_assemblies_count(self, pdb_id):
        """
            Find the number of biological assemblies associated with a pdb id.
        """
        try:
            response = urllib2.urlopen(self.ba_url + pdb_id)
        except urllib2.HTTPError:
            logger.critical('Bioassembly query failed for  %s' % pdb_id)
            self.set_email_subject('Pdb sync failed')
            self.send_report()
            sys.exit(1)
        try:
            dom = xml.dom.minidom.parseString(response.read())
            tag = dom.getElementsByTagName('PDB')[0]
            raw = tag.attributes['bioAssemblies'].value
            return int(raw)
        except:
            logger.warning('REST query for %s biological assemblies failed' %
                           pdb_id)
            return None

    def download(self, pdb_id, file_type):
        """
            Tries to download the gzipped version of the file. Will crash if
            .pdb or .cif files are not found.
        """
        if file_type == '.pdb1' and self.get_bio_assemblies_count(pdb_id) == 0:
            logger.info('No bio assemblies for %s' % pdb_id)
            return

        filename = pdb_id + file_type
        destination = os.path.join(self.locations[0], filename)

        if os.path.exists(destination):
            logger.info('%s already downloaded' % filename)
            return

        try:
            helper = utils.GzipFetchHelper(allow_fail=True)
            content = helper(self.baseurl + filename + '.gz')
            with open(destination, 'w') as out:
                out.write(content)
        except:
            if file_type == '.pdb' or file_type == '.cif':
                logger.critical('Pdb file %s could not be downloaded' % pdb_id)
                self.set_email_subject('Pdb sync failed')
                self.send_report()
                sys.exit(1)
            else:
                logger.info('%s file not found for %s' % (file_type, pdb_id))
                return

        logger.info('Downloaded %s' % destination)

    def make_copies(self, pdb_id):
        """
            Copy files from the first location to all the other locations
        """
        for location in self.locations[1:]:
            name = self.locations[0], pdb_id + '*'
            source_files = glob.glob(os.path.join(name))
            for source in source_files:
                (head, tail) = os.path.split(source)
                destination = os.path.join(location, tail)
                if os.path.exists(destination):
                    logger.info('%s already exists in %s' % (tail, location))
                    continue
                shutil.copy(source, destination)
                logger.info('Copied %s files to %s' % (pdb_id, location))


def main(argv):
    """
    """
    d = PdbDownloader()
    d.start_logging()
    d.set_locations(argv)
    d.get_pdb_list()
    d.download_files()
    logger.info('Successful update')
    d.set_email_subject('Pdb files successfully synchronized')
    d.send_report()


if __name__ == "__main__":
    main(sys.argv[1:])
