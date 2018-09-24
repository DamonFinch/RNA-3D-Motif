"""Stage to populate the units.ife table.

This module contains a loader to load all unit-ife cross-reference
information into the database.
"""

import itertools as it

import pymotifs.core as core

from pymotifs import models as mod
from pymotifs.utils import units
#from pymotifs.download import Downloader
#from pymotifs.pdbs.info import Loader as PdbLoader


class Loader(core.SimpleLoader):
    """The loader that will populate the unit_info table in the database.
    """

    #dependencies = set([Downloader, PdbLoader])
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
        return session.query(mod.UnitInfo).filter_by(pdb_id=pdb)
        #return session.query(mod.UnitInfo).filter_by(pdb_id=pdb).\
        #                        filter_by(unit_type_id='rna')

    def ife_list(self, session, pdb):
        """Identify all valid IFEs for the input PDB.

        Parameters
        ----------
        session : Session
            The session to use.
        pdb : str
            The PDB ID to use.

        Returns
        -------
        query : sqlalchemy.orm.query.Query
            A query to find all IFEs for the given structure.
        """
        return session.query(mod.IfeInfo.ife_id).filter_by(pdb_id=pdb)

    def as_unit(self, nt):
        """Turn a `Component` into a `UnitIfe`.

        Parameters
        ----------
        nt : Component
            The `Component` to turn into a `UnitIfe`.

        Returns
        -------
        unit : UnitIfe
            The `Component` as a `UnitIfe`
        """
        ife_parts = [nt.pdb, nt.model, nt.chain]
        pseudo_ife = '|'.join(ife_parts)

        self.logger.info("Pseudo_ife = %s", pseudo_ife)

        pass

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
        self.logger.info("PDB file: %s", pdb)

        structure = self.structure(pdb)
        self.logger.info("Structure: %s", structure)

        mapping = it.imap(self.as_unit, structure.residues(polymeric=None))
        self.logger.info("Mapping: %s", mapping)
        return mapping
        #return it.imap(self.as_unit, structure.residues(polymeric=None))
