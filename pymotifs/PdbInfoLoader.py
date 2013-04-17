from __future__ import with_statement
"""

Update pdb_info and pdb_obsolete tables. Pdb_info only contains the current
pdb files, old files are removed. Uses PDB RESTful services for getting a list
of all RNA-containing structures and for getting custom reports.

Usage: python PdbInfoLoader.py

"""

__author__ = 'Anton Petrov'

import csv
import logging
import traceback
import re
import urllib2
import sys
import os
from datetime import datetime
from ftplib import FTP
import pdb
import collections

from models import session, PdbInfo, PdbObsolete
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir)
from pdbx.reader.PdbxParser import PdbxReader


class GetAllRnaPdbsError(Exception):
    """Raise when `get_all_rna_pdbs()` fails"""
    pass
class GetCustomReportError(Exception):
    """Raise when `_get_custom_report()` fails"""
    pass


class PdbInfoLoader():
    """Class for retrieving RNA containing PDB files from the PDB."""

    def __init__(self):
        self.pdbs = []
        self.adv_query_url     = 'http://www.rcsb.org/pdb/rest/search'
        self.custom_report_url = 'http://www.rcsb.org/pdb/rest/customReport'

    def update_rna_containing_pdbs(self):
        """Get custom reports for all pdb files or for self.pdbs, if not empty,
           load into the database."""
        if not self.pdbs:
            self.get_all_rna_pdbs()
        failures = 0
        for pdb_id in self.pdbs:
            try:
                report = self._get_custom_report(pdb_id)
                self.__load_into_db(report)
            except:
                logging.error("Could not get and upate report for: %s", pdb_id)
                failures += 1
        if not failures:
            logging.info('Successful update of RNA-containing pdbs')
        else:
            logging.info('Partially successful update of RNA-containing pdbs')
            logging.info('Failed to update %s pdbs', failures)
        logging.info('%s', '+'*40)
        return True

    def get_all_rna_pdbs(self):
        """Get a list of all rna-containing pdb files, including hybrids. Raise
           a specific error if it fails."""
        logging.info('Getting a list of all rna-containing pdbs')
        query_text = """
        <orgPdbQuery>
        <queryType>org.pdb.query.simple.ChainTypeQuery</queryType>
        <containsProtein>I</containsProtein>
        <containsDna>I</containsDna>
        <containsRna>Y</containsRna>
        <containsHybrid>I</containsHybrid>
        </orgPdbQuery>
        """
        result = ''
        req = urllib2.Request(self.adv_query_url, data=query_text)
        f = urllib2.urlopen(req)
        result = f.read()

        if result:
            self.pdbs = result.split('\n')
            """filter out possible garbage in query results"""
            self.pdbs = filter(lambda x: len(x) == 4, self.pdbs)
            logging.info("Found %i PDB entries", len(self.pdbs))
        else:
            logging.critical("Failed to retrieve results")
            raise GetAllRnaPdbsError

    def _get_custom_report(self, pdb_id):
        """Gets a custom report in csv format for a single pdb file. Each chain
           is described in a separate line"""
        custom_report = '&customReportColumns=emResolution,structureId,chainId,structureTitle,experimentalTechnique,depositionDate,releaseDate,revisionDate,ndbId,resolution,classification,structureMolecularWeight,macromoleculeType,structureAuthor,entityId,sequence,chainLength,db_id,db_name,molecularWeight,secondaryStructure,entityMacromoleculeType,hetId,Ki,Kd,EC50,IC50,deltaG,deltaH,deltaS,Ka,compound,plasmid,source,taxonomyId,biologicalProcess,cellularComponent,molecularFunction,ecNo,expressionHost,cathId,cathDescription,scopId,scopDomain,scopFold,pfamAccession,pfamId,pfamDescription,crystallizationMethod,crystallizationTempK,phValue,densityMatthews,densityPercentSol,pdbxDetails,unitCellAngleAlpha,unitCellAngleBeta,unitCellAngleGamma,spaceGroup,lengthOfUnitCellLatticeA,lengthOfUnitCellLatticeB,lengthOfUnitCellLatticeC,Z_PDB,rObserved,rAll,rWork,rFree,refinementResolution,highResolutionLimit,reflectionsForRefinement,structureDeterminationMethod,conformerId,selectionCriteria,contents,solventSystem,ionicStrength,ph,pressure,pressureUnits,temperature,softwareAuthor,softwareName,version,method,details,conformerSelectionCriteria,totalConformersCalculated,totalConformersSubmitted,emdbId,emResolution,aggregationState,symmetryType,reconstructionMethod,specimenType&format=csv'
        url = '%s?pdbids=%s%s' % (self.custom_report_url, pdb_id, custom_report)
        logging.info('Getting custom report for %s', pdb_id)
        success = False
        retries = 0
        while success == False and retries < 3:
            try:
                f = urllib2.urlopen(url)
                result = f.read()
                success = True
            except:
                logging.warning(traceback.format_exc(sys.exc_info()))
                logging.warning("Failed to retrieve results")
                retries += 1
                result = None
                continue
        if result:
            logging.info("Retrieved custom report for %s", pdb_id)
        else:
            logging.critical("Failed to retrieve results")
            raise GetCustomReportError
        lines = result.split('<br />')
        return lines

    def _update_info(self, obj1, obj2):
        """obj1 - new instance as a dictionary, obj2 - old instance as a db object"""
        for k, v in obj1.iteritems():
            if k[0] == '_':
                continue # skip internal attributes
            setattr(obj2, k, v) # update the existing object
        return obj2

    def __load_into_db(self, lines):
        """Compares the custom report data with what's already in the database,
           reports any discrepancies and stores the most recent version."""
        logging.info('Loading custom report')
        description = lines.pop(0) # discard field names
        keys = description.split(',')

        for line in lines:
            """one line per chain"""
            if len(line) < 10:
                continue # skip empty lines
            """replace quotechars that are not preceded and followed by commas,
            except for the beginning and the end of the string
            example: in 1HXL unescaped doublequotes in the details field"""
            line = re.sub('(?<!^)(?<!,)"(?!,)(?!$)', "'", line)
            """parse the line using csv reader"""
            reader = csv.reader([line], delimiter=',', quotechar='"')
            """temporary store all field in a dictionary"""
            chain_dict = dict()
            for read in reader:
                for i, part in enumerate(read):
                    if not part:
                        part = None # to save as NULL in the db
                    chain_dict[keys[i]] = part
            """to save emResolution in resolution column"""
            if chain_dict['emResolution'] and not chain_dict['resolution']:
                chain_dict['resolution'] = chain_dict['emResolution']
            del(chain_dict['emResolution'])
            logging.info('%s %s', chain_dict['structureId'], chain_dict['chainId'])
            """check if this chain from this pdb is present in the db"""
            existing_chain = session.query(PdbInfo). \
                                     filter(PdbInfo.structureId==chain_dict['structureId']). \
                                     filter(PdbInfo.chainId==chain_dict['chainId']). \
                                     first()
            if existing_chain:
                """compare and merge objects"""
                existing_chain = self._update_info(chain_dict, existing_chain)
                session.merge(existing_chain)
            else:
                """create a new chain object"""
                new_chain = PdbInfo()
                for k, v in chain_dict.iteritems():
                    if not v:
                        v = None # to save as NULL in the db
                    setattr(new_chain, k, v)
                session.add(new_chain)

        session.commit()
        logging.info('Custom report saved in the database')

    def check_obsolete_structures(self):
        """Download the file with all obsolete structures over ftp, store
           the data in the database, remove obsolete entries
           from the pdb_info table"""

        TEMPFILE = 'obsolete.dat'
        REPEAT = 10
        done = False

        """download the data file from PDB"""
        for i in xrange(REPEAT):
            try:
                ftp = FTP('ftp.wwpdb.org')
                ftp.login()
                ftp.cwd('/pub/pdb/data/status')
                ftp.retrbinary("RETR %s" % TEMPFILE, open(TEMPFILE,"wb").write)
                ftp.quit()
                done = True
                logging.info('Downloaded obsolete.dat')
                break
            except Exception, e:
                logging.warning(e)
                logging.warning('Ftp download failed. Retrying...')

        if not done:
            logging.critical('All attempts to download obsolete.dat over ftp failed')
            logging.critical('Obsolete PDB files not updated')
            return

        """parse the data file"""
        obsolete_ids = []
        f = open(TEMPFILE, 'r')
        for line in f:
            # OBSLTE    26-SEP-06 2H33     2JM5 2OWI
            if 'OBSLTE' in line:
                parts = line.split()
                obsolete_date = datetime.strptime(parts[1], '%d-%b-%y')
                obsolete_ids.append(parts[2])
                replaced_by = ','.join(parts[3:])
                dbObj = PdbObsolete(obsolete_id=obsolete_ids[-1],
                                    date=obsolete_date,
                                    replaced_by=replaced_by)
                session.merge(dbObj)
        session.commit()

        """remove obsoleted files from pdb_info"""
        session.query(PdbInfo).\
                filter(PdbInfo.structureId.in_(obsolete_ids)).\
                delete(synchronize_session='fetch')

        """delete tempfile"""
        os.remove(TEMPFILE)

    def read_cif_file(self, pdb_id):
        """
            Open cif file with cif reader and return the object.
        """
        data = []
        filename = '/Servers/rna.bgsu.edu/nrlist/pdb/' + pdb_id + '.cif'
        with open(filename, 'r') as raw:
            parser = PdbxReader(raw)
            parser.read(data)
        cif = data[0]
        return cif

    def _get_chain_id_map(self, cif):
        """
            Loop over the coordinates section to map chain ids to entity ids
            used internally in cif files. Inefficient, but guaranteed to work.
        """
        atom_site = cif.getObj('atom_site')
        chain_map = dict()
        for i in xrange(atom_site.getRowCount()):
            chain = atom_site.getValue('auth_asym_id', i)
            entity_id = atom_site.getValue('label_entity_id', i)
            chain_map[entity_id] = chain
        return chain_map

    def _get_source_organism_map(self, cif):
        """
            Get organism name for each internal cif entity id.
            entity_src_nat:
            Scientific name of the organism of the natural source.
            pdbx_entity_src_syn:
            Scientific name of the organism from which the entity was isolated.

            There are two additional fields related to source organisms:
            _pdbx_entity_src_syn.organism_scientific
            _em_entity_assembly.ebi_organism_scientific
            They seem to be empty for all RNA-containing 3D structures.
        """
        records = {'entity_src_nat':      'pdbx_organism_scientific', # Corresponds to SOURCE
                   'pdbx_entity_src_syn': 'organism_scientific',      # chemically synthesized
                   'em_entity_assembly':  'ebi_organism_scientific',
                   'pdbx_reference_entity_src_nat': 'organism_scientific'}
        organism_map = dict()
        organism_data = collections.defaultdict(dict)
        found = False
        for cif_category, cif_item in records.iteritems():
            block = cif.getObj(cif_category)
            if block is None:
                continue
            else:
                found = True
            for i in xrange(block.getRowCount()):
                organism  = block.getValue(cif_item, i)
                entity_id = block.getValue('entity_id', i)
                organism_map[entity_id] = organism
                organism_data[entity_id][cif_category] = organism
        if not found:
            logging.info('No cif source organisms')
        return (organism_map, organism_data)

    def _compare_with_database(self, pdb_id, organisms):
        """
        """
        for chain, organism in organisms.iteritems():
            db_data = session.query(PdbInfo).\
                              filter(PdbInfo.structureId==pdb_id).\
                              filter(PdbInfo.chainId==chain).\
                              one()
            if db_data.source != organism:
                if db_data.source is None and organism == '?':
                    continue
                logging.info('Conflict found. Chain %s. Db: %s, cif: %s'
                              % (chain, db_data.source, organism))

    def get_organisms_by_chain(self, cif, pdb_id):
        """
        """
        chain_map = self._get_chain_id_map(cif)
        organism_map, organism_data = self._get_source_organism_map(cif)
        organisms = dict()
        for entity_id, chain_id in chain_map.iteritems():
            if entity_id in organism_map:
                organisms[chain_map[entity_id]] = organism_map[entity_id]
                logging.info('Chain %s from %s'
                              % (chain_map[entity_id], organism_map[entity_id]))
            """Output all four cif categories for comparison"""
            if entity_id in organism_data:
                output = [
                    pdb_id,
                    chain_map[entity_id],
                    organism_data[entity_id]['entity_src_nat']                if 'entity_src_nat' in organism_data[entity_id] else '',
                    organism_data[entity_id]['pdbx_entity_src_syn']           if 'pdbx_entity_src_syn' in organism_data[entity_id] else '',
                    organism_data[entity_id]['em_entity_assembly']            if 'em_entity_assembly' in organism_data[entity_id] else '',
                    organism_data[entity_id]['pdbx_reference_entity_src_nat'] if 'pdbx_reference_entity_src_nat' in organism_data[entity_id] else ''
                ]
                print '"' + '","'.join(output) + '"'



        self._compare_with_database(pdb_id, organisms)
        return organisms

    def update_source_organisms(pdb_id, organisms):
        """
        """
        pass

    def fix_organism_names(self, pdb_id):
        """
        """
        logging.info(pdb_id)
        try:
            cif = self.read_cif_file(pdb_id)
            organisms = self.get_organisms_by_chain(cif, pdb_id)
    #         self.update_source_organisms(pdb_id, organisms)
#             print '"' + '","'.join([pdb_id, ','.join(organisms.values())]) + '"'
        except:
            logging.warning(traceback.format_exc(sys.exc_info()))
            logging.warning('There was a problem with %s' % pdb_id)




def main(argv):
    """
    """
    logging.basicConfig(level=logging.DEBUG)

# NB! remove hardcoded cif location

    P = PdbInfoLoader()

    P.get_all_rna_pdbs()
#     P.pdbs = ['1MJ1']
#     P.pdbs = ['1E8S', '1S72']

#     P.pdbs = P.pdbs[100:200]

    for pdb_id in P.pdbs:
        P.fix_organism_names(pdb_id)

#     P.update_rna_containing_pdbs()
#     P.check_obsolete_structures()


if __name__ == "__main__":
    main(sys.argv[1:])
