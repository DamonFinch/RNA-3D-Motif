"""Load all unit centers into the database.
"""

import pymotifs.core as core

from pymotifs import models as mod

from pymotifs.units.info import Loader as InfoLoader

from pymotifs.skip_files import SKIP

from sqlalchemy import and_


class Loader(core.SimpleLoader):
    """A class to load all glycosidic centers into the database.
    """

    dependencies = set([InfoLoader])
    allow_no_data = True

    def to_process(self, pdbs, **kwargs):
        # with self.session() as session:
        #     query_all_pdb_ids = session.query(mod.ChainInfo.pdb_id).distinct()
        #     query_glycosidic_present = session.query(mod.UnitCenters.pdb_id).\
        #                                 filter(mod.UnitCenters.name == 'glycosidic').distinct()
        #                                 #filter(and_(mod.UnitCenters.name == 'base',mod.UnitCenters.name != 'glycosidic')).distinct()

        # pdb_ids = []
        # for id in query_all_pdb_ids:
        #     pdb_ids.append(str(id)[2:6])
        # existed_ids = []
        # for id in query_glycosidic_present:
        #     existed_ids.append(str(id)[2:6])
        # passing_pdb_ids = set()
        # for pdb_id in pdb_ids:
        #     if (pdb_id not in SKIP) and (pdb_id not in existed_ids):
        #         passing_pdb_ids.add(pdb_id)
        # list(set-set-set)

        # # return [pdb_id for pdb_id in result for skip_id in SKIP if pdb_id != skip_id]
        # # print(len([pdb_id for pdb_id in result for skip_id in SKIP if pdb_id != skip_id]))
        # # print(len(pdb_ids))
        # # print(len(passing_pdb_ids))
        # # print(len(SKIP))
        # # self.logger.info('length of pdb_ids:%s length of processing:%s length of existed ids:%s' % (len(pdb_ids),len(passing_pdb_ids),len(existed_ids)))

        # return passing_pdb_ids
        return ['4V3P']

    def query(self, session, pdb):
        return session.query(mod.UnitCenters).\
            filter(mod.UnitCenters.pdb_id == pdb).\
            filter(mod.UnitCenters.name == 'glycosidic')

    def data(self, pdb, **kwargs):
        structure = self.structure(pdb)
        for residue in structure.residues():
            for name in residue.centers.definitions():
                center = residue.centers[name]
                if len(center) == 3 and name == 'glycosidic':
                    yield mod.UnitCenters(unit_id=residue.unit_id(),
                                          name=name,
                                          pdb_id=pdb,
                                          x=float(center[0]),
                                          y=float(center[1]),
                                          z=float(center[2]))
