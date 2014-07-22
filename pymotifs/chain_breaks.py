import sys
import logging

from MotifAtlasBaseClass import MotifAtlasBaseClass
from models import PolymerInfo
from utils import DatabaseHelper
from utils import CifFileFinder

sys.path.append('rnastructure')
from rnastructure.tertiary.cif import CIF


class ChainBreakFinder(object):

    def __call__(self, cif_file):
        with open(cif_file, 'rb') as raw:
            cif = CIF(raw)

        breaks = []
        for polymer in cif.polymers():
            breaks.append((polymer.first().unit_id(),
                           polymer.last().unit_id()))
        return breaks


class ChainBreakLoader(MotifAtlasBaseClass, DatabaseHelper):
    finder = ChainBreakFinder()

    def __init__(self, maker):
        MotifAtlasBaseClass.__init__(self)
        self.cif = CifFileFinder(self.config)
        DatabaseHelper.__init__(self, maker)

    def data(self, pdb):
        cif_file = self.cif(pdb)
        endpoints = self.finder(cif_file)

        data = []
        for unit1_id, unit2_id in endpoints:
            parts = unit1_id.split('|')
            data.append(PolymerInfo(start_unit_id=unit1_id,
                                    end_unit_id=unit2_id,
                                    chain=parts[2],
                                    model=int(parts[1]),
                                    pdb_id=pdb))
        return data

    def __call__(self, pdbs):
        for pdb in pdbs:
            logging.info("Getting breaks for %s", pdb)
            breaks = self.data(pdb)
            logging.info("Found %s breaks", len(breaks))

            try:
                logging.debug("Storing breaks for %s", pdb)
                self.store(breaks)
            except:
                logging.error("Failed to store breaks for %s", pdb)


if __name__ == '__main__':
    from utils import main
    main(ChainBreakLoader)