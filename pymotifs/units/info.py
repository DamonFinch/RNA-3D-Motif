"""Stage to populate the units.info table.

This module contains a loader to load all unit level information into the
database.
"""

import itertools as it

import pymotifs.core as core

from pymotifs import models as mod
from pymotifs.utils import units
from pymotifs.download import Downloader
from pymotifs.pdbs.info import Loader as PdbLoader


class Loader(core.SimpleLoader):
    """The loader that will populate the unit_info table in the database.
    """

    dependencies = set([Downloader, PdbLoader])
    """The dependencies for this stage."""

    def query(self, session, pdb):
        """Create a query for all units for the given PDB.

        Parameters
        ----------
        session : Session
            The session to use.
        pdb : str
            The PDB ID to use.

        Returns
        -------
        query : sqlalchemy.orm.query.Query
            A query to find all units from the given structure.
        """
        # return session.query(mod.UnitInfo).filter_by(pdb_id='6X')
        return session.query(mod.UnitInfo).filter_by(pdb_id=pdb)

    def type(self, unit):
        """Compute the component type, ie A, C, G, U is RNA, DA, DC, etc is DNA
        and so forth.

        Parameters
        ----------
        unit : Component
            The unit to get the component for

        Returns
        -------
        component_type : str
            The component type.
        """
        return units.component_type(unit)

    def as_unit(self, nt):
        """Turn a `Component` into a `UnitInfo`.

        Parameters
        ----------
        nt : Component
            The `Component` to turn into a `UnitInfo`.

        Returns
        -------
        unit : UnitInfo
            The `Component` as a `UnitInfo`
        """
        # self.logger.info("unit_id: %s, pdb: %s, model: %s, chain: %s, unit: %s, number: %s, alt_id: %s, ins_code: %s, sym_op: %s, chain_index: %s, unit_type_id: %s" % (nt.unit_id(), nt.pdb, nt.model, nt.chain, nt.sequence, nt.number, getattr(nt, 'alt_id', None), nt.insertion_code, nt.symmetry, nt.index, self.type(nt)))


        return mod.UnitInfo(unit_id=nt.unit_id(),
                            pdb_id=nt.pdb,
                            model=nt.model,
                            chain=nt.chain,
                            unit=nt.sequence,
                            number=nt.number,
                            alt_id=getattr(nt, 'alt_id', None),
                            ins_code=nt.insertion_code,
                            sym_op=nt.symmetry,
                            chain_index=nt.index,
                            unit_type_id=self.type(nt))

    def data(self, pdb, **kwargs):
        """Compute the data to store. This will extract all components from the
        structure, include water, ligands and other non-polymers and create
        `UnitInfo` objects.

        Parameters
        ----------
        pdb : str
            The PDB id to compute the units for.

        Returns
        -------
        data : iterator
            An iterable over all units in the structure.
        """

        structure = self.structure(pdb)
        # for i in it.imap(self.as_unit, structure.residues(polymeric=None)):
        #     print(dir(i))
        #     print(i.sym_op)
        #     print(type(i))
        # print("list or not: ",type(it.imap(self.as_unit, structure.residues(polymeric=None))))
        # ### fixing process ###
        # new_6xbu = it.imap(self.as_unit, structure.residues(polymeric=None))
        # new_return = []
        # for obj in new_6xbu:
        #     if obj.sym_op != '1_555':
        #         new_return.append(obj)
        # print([i.unit_id for i in new_return])
        # return new_return
        return it.imap(self.as_unit, structure.residues(polymeric=None))
