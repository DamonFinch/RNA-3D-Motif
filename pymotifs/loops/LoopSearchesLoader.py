"""

Import information about all pairwise all-against-all searches, detailed
loop annotations and search disqualification data.

Disqualification codes are imported from text files created by Matlab during
the execution of aSymmetrizeMatrix and aAnalyzeExtraNucleotides.

"""

__author__ = 'Anton Petrov'

import pdb
import sys
import getopt
import logging
import os
import re
import csv
import glob

from models import session, LoopSearches, LoopSearchQa, LoopPositions
from MotifAtlasBaseClass import MotifAtlasBaseClass

logger = logging.getLogger(__name__)


class LoopSearchesLoader(MotifAtlasBaseClass):
    """
    """
    def __init__(self):
        MotifAtlasBaseClass.__init__(self)

        self.loopSearchDir = self.config['locations']['loops_search_dir']
        self.precomputedData = self.config['locations']['loops_mat_files']
        self.loop_regex = '(IL|HL)_\w{4}_\d{3}'
        self.pdb_regex = '^[0-9A-Za-z]{4}$'
        self.update = True # determines whether to update existing values in the db

    def load_loop_positions(self):
        """update loop_positions table by loading data from the mat files
        stored in the PrecomputedData folder"""
        if not self.mlab:
            self._setup_matlab()

        # loop over directories
        for folder in os.listdir(self.precomputedData):
            if re.search(self.pdb_regex, folder):
                logger.info('Importing loop annotations from %s', folder)
            else:
                continue
            [outputFile, err_msg] = self.mlab.loadLoopPositions(os.path.join(self.precomputedData, folder), nout=2)
            if err_msg != '':
                MotifAtlasBaseClass._crash(self, err_msg)
            else:
                reader = csv.reader(open(outputFile), delimiter=',', quotechar='"')
                for row in reader:
                    (loop_id, position, nt_id, bulge, flanking, border) = row
                    existing = session.query(LoopPositions). \
                                       filter(LoopPositions.loop_id==loop_id). \
                                       filter(LoopPositions.position==position). \
                                       filter(LoopPositions.border==border). \
                                       first()
                    if existing:
                        if self.update:
                            existing.flanking = int(flanking)
                            existing.bulge = int(bulge)
                            existing.nt_id = nt_id
                            existing.border = int(border)
                            session.merge(existing)
                        else:
                            logger.info('Keeping existing annotations')
                    else:
                        session.add(LoopPositions(loop_id=loop_id,
                                                  position=position,
                                                  nt_id=nt_id,
                                                  flanking=int(flanking),
                                                  bulge=int(bulge),
                                                  border=int(border)))
                session.commit()
                os.remove(outputFile) # delete temporary csv file

    def _get_imported_loop_searches(self, loop_id):
        """
            get loop pairs for which search data has been stored in the database
        """
        done = []
        for search in session.query(LoopSearches).\
                              filter(LoopSearches.loop_id1==loop_id).\
                              filter(LoopSearches.disc>=0).\
                              all():
            done.append('_'.join([search.loop_id1, search.loop_id2]))
        return set(done)

    def _get_stored_no_candidates(self, loop_id):
        """
            get loops pairs that didn't match in all-against-all searches
        """
        done = []
        for search in session.query(LoopSearches).\
                              filter(LoopSearches.loop_id1==loop_id).\
                              filter(LoopSearches.disc==-1).\
                              all():
            done.append('_'.join([search.loop_id1, search.loop_id2]))
        return set(done)

    def _get_saved_mat_files(self, folder):
        """
            list all mat files in a given folder
        """
        mat = []
        for f in glob.glob(folder):
            mat.append(os.path.splitext(os.path.basename(f))[0])
        return set(mat)

    def load_loop_searches(self):
        """
            directory structure: loopSearchDir filesep IL_1S72_001 filesep IL_1S72_001_IL_1J5E_001.mat
        """
        # loop over directories
        for loop_id in os.listdir(self.loopSearchDir):
            if re.search(self.loop_regex, loop_id):
                logger.info('Importing %s searches', loop_id)
            else:
                continue

            # read in No_candidates.txt if it exists
            self._read_no_candidates_file(loop_id)

            # get stored loop searches and list all matfiles
            imported = self._get_imported_loop_searches(loop_id)
            matfiles = self._get_saved_mat_files(os.path.join(self.loopSearchDir, loop_id, '*.mat'))
            toImport = matfiles - imported;

            if len(toImport) == 0:
                continue

            toImport = [os.path.join(self.loopSearchDir, loop_id, x + '.mat') for x in toImport]

            if not self.mlab:
                self._setup_matlab()

            # run matlab to create a temporary csv file with results
            [outputFile, err_msg] = self.mlab.loadLoopSearchFile(','.join(toImport), os.path.join(self.loopSearchDir, loop_id), nout=2)

            if err_msg != '':
                MotifAtlasBaseClass._crash(self, err_msg)
            else:
                reader = csv.reader(open(outputFile), delimiter=',', quotechar='"')
                for row in reader:
                    (loop_id1, loop_id2, disc, nt_list1, nt_list2) = row
                    self._store_in_database(loop_id1, loop_id2, disc, nt_list1, nt_list2)
                os.remove(outputFile) # delete temporary csv file

    def _store_in_database(self, loop_id1, loop_id2, disc=-1, nt_list1=None, nt_list2=None):
        """
        """
        existing = session.query(LoopSearches). \
                           filter(LoopSearches.loop_id1==loop_id1). \
                           filter(LoopSearches.loop_id2==loop_id2). \
                           first()
        if existing:
            if self.update:
                existing.disc = float(disc)
                existing.nt_list1 = nt_list1
                existing.nt_list2 = nt_list2
                session.merge(existing)
        else:
            session.add(LoopSearches(loop_id1=loop_id1,
                                   loop_id2=loop_id2,
                                   disc=float(disc),
                                   nt_list1=nt_list1,
                                   nt_list2=nt_list2))
        session.commit()

    def _read_no_candidates_file(self, folder):
        """
        """
        no_candidates_file = os.path.join(self.loopSearchDir,
                                          folder,
                                          'No_candidates.txt')
        if os.path.exists(no_candidates_file):
            loop_id1 = folder
            loops = open(no_candidates_file, 'r').readlines()
            loops = [x.rstrip() for x in loops]
            imported = self._get_stored_no_candidates(loop_id1)
            for loop_id2 in loops:
                if '_'.join([loop_id1, loop_id2]) not in imported:
                    self._store_in_database(loop_id1, loop_id2)

    def load_loop_search_qa_text_file(self, file):
        """independent method used to load search QA data (disqualification
        codes from the text files created by matlab during clustering"""
        reader = csv.reader(open(file, 'r'))
        for row in reader:
            existing = session.query(LoopSearchQa). \
                               filter(LoopSearchQa.loop_id1==row[0]). \
                               filter(LoopSearchQa.loop_id2==row[1]). \
                               first()
            if existing:
                if self.update:
                    existing.status = int(row[2])
                    existing.message = row[3]
                    session.merge(existing)
            else:
                session.add(LoopSearchQa(loop_id1=row[0],
                                         loop_id2=row[1],
                                         status=int(row[2]),
                                         message=row[3]))
        session.commit()


def main(argv):
    """
    """
    S = LoopSearchesLoader()
    S.start_logging()
    S.load_loop_searches()
    S.load_loop_positions()

#     S.load_loop_search_qa_text_file('/Users/anton/FR3D/MM_extraNTs.txt')
#     S.load_loop_search_qa_text_file('/Users/anton/FR3D/MM_symmetrize.txt')



if __name__ == "__main__":
    main(sys.argv[1:])