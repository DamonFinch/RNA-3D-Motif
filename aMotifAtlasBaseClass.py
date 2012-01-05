"""

About

"""

__author__ = 'Anton Petrov'

import sys, logging, smtplib, ConfigParser, collections, datetime
from aMLSqlAlchemyClasses import session, PdbAnalysisStatus

class MotifAtlasBaseClass:
    """
    """

    def __init__(self):
        self.mlab   = False
        self.config = collections.defaultdict(dict)
        self.configfile = '/Users/anton/Dropbox/Code/PyMotifLoader/motifatlas.cfg'
        self.import_config()

    def filter_out_analyzed_pdbs(self, pdbs, column_name):
        """Checks whether the pdb files were processed . Returns only the files
        that need to be analyzed. The `column_name` parameters corresponds to
        the column name of the pdb_analysis_status table."""
        pdb_list = pdbs[:] # copy, not reference
        done = session.query(PdbAnalysisStatus). \
                       filter(PdbAnalysisStatus.id.in_(pdbs)). \
                       filter(getattr(PdbAnalysisStatus,column_name.lower()) != None). \
                       all()
        [pdb_list.remove(x.id) for x in done]
        if pdb_list:
            logging.info('New files to analyze: ' + ','.join(pdb_list))
        else:
            logging.info('No new files to analyze')
        return pdb_list

    def mark_pdb_as_analyzed(self, pdb_id, column_name):
        """
        """
        P = PdbAnalysisStatus(id = pdb_id)
        setattr(P,column_name.lower(),datetime.datetime.now())
        session.merge(P)
        session.commit()
        logging.info('Updated %s status for pdb %s', column_name, pdb_id)

    def _setup_matlab(self):
        if self.mlab:
            return
        logging.info('Starting up matlab')
        from mlabwrap import mlab
        self.mlab = mlab
        self.mlab.setup()
        # self.mlab._dont_proxy["cell"] = True
        logging.info('Matlab started')

    def import_config(self):
        """
        """
        try:
            logging.info('Importing configuration')
            config = ConfigParser.RawConfigParser()
            config.read(self.configfile)
            """email settings"""
            section = 'email'
            keys = ['from','to','login','password','subject']
            for k in keys: self.config[section][k] = config.get(section,k)
#             self.config['email']['from']     = config.get('Email', 'from')
#             self.config['email']['to']       = config.get('Email', 'to')
#             self.config['email']['login']    = config.get('Email', 'login')
#             self.config['email']['password'] = config.get('Email', 'password')
            """recalculation settings"""
            section = 'recalculate'
            keys = ['coordinates','distances','IL','HL','J3']
            for k in keys: self.config[section][k] = config.getboolean(section,k)
#             self.config['recalculate']['coordinates'] = config.getboolean('Recalculate', 'coordinates')
#             self.config['recalculate']['distances']   = config.getboolean('Recalculate', 'distances')
#             self.config['recalculate']['IL']          = config.getboolean('Recalculate', 'IL')
#             self.config['recalculate']['HL']          = config.getboolean('Recalculate', 'HL')
#             self.config['recalculate']['J3']          = config.getboolean('Recalculate', 'J3')
            """logging"""
            self.config['logfile'] = 'motifatlas.log'
            """locations"""
            self.config['locations']['loops_mat_files'] = config.get('locations','loops_mat_files')
            """release modes"""
            section = 'release_mode'
            keys = ['loops','motifs','nrlist']
            for k in keys: self.config[section][k] = config.get(section,k)
            logging.info('%s', '='*40)
        except:
            e = sys.exc_info()[1]
            self._crash(e)

    def send_report(self, logfile):
        """
        """
        try:
            fp = open(logfile, 'rb')
            msg = MIMEText(fp.read())
            fp.close()
            msg['Subject'] = ' '.join([self.config['Email']['subject'],
                                       date.today().isoformat()])
            server = smtplib.SMTP('smtp.gmail.com:587')
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.config['email']['login'],self.config['email']['password'])
            server.sendmail(self.config['email']['from'], self.config['email']['to'], msg.as_string())
            server.quit()
        except:
            sys.exit(2)

    def _crash(self, msg=None):
        """
        """
        if msg:
            logging.critical(msg)
        try:
            session.rollback()
        except:
            pass
        self.send_report('motifatlas.log')
        sys.exit(2)
