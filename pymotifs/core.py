import os
import abc
import logging
import datetime
import collections as coll
from contextlib import contextmanager

try:
    from mlabwrap import mlab
except:
    pass

from fr3d.cif.reader import Cif
from fr3d.cif.reader import ComplexOperatorException
from fr3d.data import Structure

from pymotifs import models as mod
from pymotifs import utils as ut

# This is a very large virus file that should be skipped. Add other files as necessary
SKIP = set(['4V3P'])


class StageFailed(Exception):
    """This is raised when one stage of the pipeline fails.
    """
    pass


class InvalidState(Exception):
    """This is an exception meant to be used when we have entered into some
    sort of invalid state in a stage. For example, we require that chain breaks
    be loaded before we do nt-nt correspondences but if the programs are run
    out of order this will be raised.
    """
    pass


class Skip(Exception):
    """Base class for skipping things.
    """
    pass


class MatlabFailed(Exception):
    """An exception meant to be used if matlab commands fail for some reason.
    """
    pass


class Matlab(object):
    """A simple wrapper around mlab. This is useful because it sets the root as
    well as calling the setup function before running matlab.
    """

    def __init__(self, root):
        self.logger = logging.getLogger('core.Matlab')
        self.mlab = None
        self._root = root

    def __del__(self):
        if self.mlab:
            del self.mlab

    def __startup__(self):
        self.logger.debug('Starting up matlab')
        self.mlab = mlab
        # self.mlab._autosync_dirs = False
        self.mlab.setup()
        os.chdir(self._root)
        self.logger.debug('Matlab started')

    def __getattr__(self, key):
        if self.mlab is None:
            os.chdir(self._root)
            self.__startup__()
        self.logger.debug("Running %s", key)

        attr = getattr(self.mlab, key)

        def func(*args, **kwargs):
            corrected = []
            for arg in args:
                if isinstance(arg, basestring):
                    corrected.append(str(arg))
                else:
                    corrected.append(arg)
            return attr(*corrected, **kwargs)

        return func


class Session(object):
    """A wrapper around a session maker to provide the types of logging and
    rollbacks that we desire.
    """

    def __init__(self, session_maker):
        self.logger = logging.getLogger('core.Session')
        self.maker = session_maker

    @contextmanager
    def __call__(self):
        """Context handler for the session. This creates a new session and
        yields it. It will catch, log, and re raise any exceptions that occur.
        It will also commit and close all sessions.
        """
        session = self.maker()
        try:
            yield session
            session.commit()
        except Skip:
            session.rollback()
            raise
        except Exception:
            self.logger.error("Transaction failed. Rolling back.")
            session.rollback()
            raise
        finally:
            session.close()


class Base(object):
    """This is a simple utility class. Several things in core and outside of
    core need a basic class to inherit from that adds a logger, session
    handler, config, etc. This provides such a base class.
    """

    def __init__(self, config, session_maker):
        """Build a new Base.

        :config: The config object to build with.
        :session_maker: The Session object to handle database connections.
        """

        self.config = coll.defaultdict(dict)
        self.config.update(config)
        self.name = self.__class__.__module__
        self.session = Session(session_maker)
        self.logger = logging.getLogger(self.name)


class Stage(Base):
    """
    This is a base class for both loaders and exporters to inherit from. It
    contains the functionality common to all things that are part of our
    pipeline.
    """

    """ If we should stop the whole stage if one part fails. """
    stop_on_failure = True

    """ Maximum length of time between updates. False for forever. """
    update_gap = None

    """ What stages this stage depends upon. """
    dependencies = set()

    """Flag if we should mark stuff as processed."""
    mark = True

    """If we should skip complex operators"""
    skip_complex = True

    def __init__(self, *args, **kwargs):
        """Build a new Stage.

        :config: The config object to build with.
        :session_maker: The Session object to handle database connections.
        """
        super(Stage, self).__init__(*args, **kwargs)
        self._cif = ut.CifFileFinder(self.config)

    @abc.abstractmethod
    def is_missing(self, entry, **kwargs):
        """Determine if we do not have any data. If we have no data then we
        will recompute.

        :entry: The thing to check for.
        :kwargs: Generic keyword arguments
        :returns: True or False
        """
        pass

    @abc.abstractmethod
    def process(self, entry, **kwargs):
        """Process this entry. In the case of loaders this will parse the data
        and put it into the database, exporters may go to the database and then
        generate the file.

        :entry: The entry to process.
        :kwargs: Generic keyword arguments.
        :returns: Nothing and is ignored.
        """
        pass

    def cif(self, pdb):
        """A method to load the cif file for a given pdb id.

        :pdb: PDB id to parse.
        :returns: A parsed cif file.
        """
        if isinstance(pdb, Cif):
            return pdb

        try:
            with open(self._cif(pdb), 'rb') as raw:
                return Cif(raw)
        except ComplexOperatorException as err:
            if self.skip_complex:
                self.logger.warning("Got a complex operator for %s, skipping",
                                    pdb)
                raise Skip("Complex operator must be skipped")
            raise err

    def structure(self, pdb):
        """A method to load the cif file and get the structure for the given

        :pdb: The pdb id to get the structure for.
        :returns: The FR3D structure for the given PDB.
        """
        if isinstance(pdb, Structure):
            return pdb

        return self.cif(pdb).structure()

    def must_recompute(self, pdb, recalculate=False, **kwargs):
        """Detect if we have been told to recompute this stage for this pdb.
        """
        return bool(recalculate or self.config[self.name].get('recompute'))

    def been_long_enough(self, pdb):
        """Determine if it has been long enough to recompute the data for the
        given pdb. This uses the udpate_gap property which tells how long to
        wait between updates. If that is False then we never update based upon
        time.
        """
        if not self.update_gap:
            return False

        with self.session() as session:
            current = session.query(mod.PdbAnalysisStatus).\
                filter_by(pdb=pdb, stage=self.name).\
                first()
            if not current:
                return True
            current = current.time
        # If this has been marked as done in the far future do it anyway. That
        # is a silly thing to do
        diff = abs(datetime.datetime.now() - current)
        return diff > self.update_gap

    def should_process(self, entry, **kwargs):
        """Determine if we should process this entry. This is true if we are
        told to recompute, if we do not have data for this pdb or it has been
        long enough since the last update.

        :entry: The entry to check.
        :kwargs: Some keyword arguments for determining if we should process
        :returns: True or False
        """
        if self.must_recompute(entry, **kwargs):
            self.logger.debug("Performing a forced recompute")
            return True

        too_long = self.been_long_enough(entry)
        if too_long:
            self.logger.debug("Time gap for %s too large, recomputing", entry)
            return True

        if self.is_missing(entry, **kwargs):
            self.logger.debug("Missing data from %s. Will recompute", entry)
            return True
        return False

    def to_process(self, pdbs, **kwargs):
        """Compute the things to process. For things that work with PDBs the
        default one will work well. For things that work with groups this could
        simply ignore the given pdbs and return the names of the groups to work
        with.

        :pdbs: Input pdbs
        :kwargs: Generic keyword arguments.
        :returns: The stuff to process.
        """
        return [pdb.upper() for pdb in pdbs]

    def mark_processed(self, pdb, dry_run=False, **kwargs):
        """Mark that we have finished computing the results for the given pdb.

        :pdb: The pdb to mark done.
        """

        if dry_run:
            self.logger.debug("Marking %s as done", pdb)
        else:
            with self.session() as session:
                status = mod.PdbAnalysisStatus(pdb=pdb, stage=self.name,
                                               time=datetime.datetime.now())
                session.merge(status)
        self.logger.info('Updated %s status for pdb %s', self.name, pdb)

    def __call__(self, given, **kwargs):
        """Process all given inputs. This will first transform all inputs with
        the `to_process` method. If there are no entries then a critical
        exception is raised. We then use `should_process` to determine if we
        should process each entry. If this returns
        true then we call `process`. Once done we call `mark_processed`.

        :given: A list of pdbs to process.
        :kwargs: Keyword arguments passed on to various methods.
        :returns: Nothing
        """

        entries = self.to_process(given, **kwargs)
        if not entries:
            self.logger.critical("Nothing to process")
            raise InvalidState("Nothing to process")

        for index, entry in enumerate(entries):
            self.logger.info("Processing %s: %s/%s", entry, index + 1,
                             len(entries))

            if entry in SKIP:
                self.logger.warning("Hardcoded skipping of %s" % entry)
                continue

            try:
                if not self.should_process(entry, **kwargs):
                    self.logger.debug("No need to process %s", entry)
                    continue
                self.process(entry, **kwargs)

            except Skip as err:
                self.logger.warn("Skipping entry %s. Reason %s",
                                 entry, str(err))
                continue

            except Exception as err:
                self.logger.error("Error raised in processing of %s", entry)
                self.logger.exception(err)
                if self.stop_on_failure:
                    self.remove(entry)
                    raise StageFailed(self.name)
                continue

            if self.mark:
                self.mark_processed(entry, **kwargs)


class Loader(Stage):
    """An abstract baseclass for all things that load data into our database.
    This provides a constituent interface for all loaders to use. This extends
    Stage by making the process method
    """

    __metaclass__ = abc.ABCMeta

    """ Max number of things to insert at once. """
    insert_max = 1000

    """ A flag to indicate it is ok to produce no data. """
    allow_no_data = False

    """ A flag to indicate if we should use sessions .merge instead of .add """
    merge_data = False

    @abc.abstractmethod
    def data(self, pdb, **kwargs):
        """Compute the data for the given cif file.
        """
        pass

    @abc.abstractmethod
    def has_data(self, pdb, **kwargs):
        """Check if we have already stored data for this pdb file in the
        database. This is used to determine if we should attempt to compute new
        data.
        """
        pass

    @abc.abstractmethod
    def remove(self, pdb):
        """Remove any old data for this pdb. This is used both when we have
        failed to store all data as well as when we are overwriting existing
        data. This should never raise anything unless something is drastically
        wrong.
        """
        pass

    def is_missing(self, entry, **kwargs):
        """Determine if the data is missing by using the has_data method.

        :entry: The transformed entry to check for.
        :kwargs: Keyword arguments
        :returns: A boolean if the requested data is missing or not.
        """
        return not self.has_data(entry, **kwargs)

    def store(self, data, dry_run=False, **kwargs):
        """Store the given data. The data is written in chunks of
        self.insert_max at a time. The data can be a list or a nested set of
        iterables. If dry_run is true then this will not actually store
        anything, but instead will log the attempt. If this loader has
        'merge_data' set to True then this will merge instead of adding data.

        :data: The data to store. May be a list, an iterable nested one level
        deep or a single object to store.
        :dry_run: A flag to indicate if this should perform a dry run.
        :kwargs: Keyword arguments.
        """

        if not data:
            self.logger.warning("Nothing to store")
            return

        self.logger.debug("Storing data")
        with self.session() as session:

            def add(data):
                if dry_run:
                    self.logger.debug("Storing: %s", data)
                else:
                    if self.merge_data:
                        session.merge(data)
                    else:
                        session.add(data)

            if not isinstance(data, coll.Iterable):
                add(data)
            else:
                saved = False
                for index, datum in enumerate(data):
                    add(datum)
                    saved = True
                    if index % self.insert_max == 0:
                        session.commit()

                if not saved:
                    if not self.allow_no_data:
                        self.logger.error("No data produced")
                        raise InvalidState("No data produced")
                    else:
                        self.logger.warning("No data saved")

            session.commit()
            self.logger.debug("Done committing")

    def process(self, entry, **kwargs):
        """Get the data for a particular entry. This will get the data and then
        store it. IT will remove data as needed and makes sure that data is
        produced if required.

        :entry: The entry to process.
        :kwargs: Generic keyword arguments to be passed along to other methods.
        """

        if self.must_recompute(entry, **kwargs):
            if kwargs['dry_run']:
                self.logger.debug("Skipping removal in dry run")
            else:
                self.logger.debug("Removing old data for %s", entry)
                self.remove(entry)

        data = self.data(entry)

        if not self.allow_no_data and not data:
            self.logger.error("No data produced")
            raise InvalidState("Stage %s produced no data processing %s" %
                               (self.name, entry))
        elif not data:
            if data is not None:
                self.logger.warning("No data produced")
            return

        self.store(data, **kwargs)


class SimpleLoader(Loader):
    """
    A SimpleLoader is a subclass of Loader that has a default implementation
    of has_data and remove. These depend on the abstract method query which
    generates the query to use for these things. Basically this is what to use
    if we are simply adding things to a table in the database.
    """

    __metaclass__ = abc.ABCMeta

    def has_data(self, *args, **kwargs):
        with self.session() as session:
            return bool(self.query(session, *args).count())

    def remove(self, *args, **kwargs):
        with self.session() as session:
            self.query(session, *args).delete(synchronize_session=False)

    @abc.abstractmethod
    def query(self, session, *args):
        """
        A method to generate the query that can be used to access data for this
        loader. The resutling query is used in remove and has_data.

        :session: The session object to use.
        :*args: Arguments from process.
        """
        pass


class MassLoader(Loader):
    """A MassLoader is a Loader that works on collections of PDB files. For
    example, when getting all PDB info we do that for all PDB files at once in
    a single request. Here we do many of the normal things that a stage does
    but we simply do it on all pdbs at once.
    """

    __metaclass__ = abc.ABCMeta

    def to_process(self, pdbs, **kwargs):
        return tuple(super(MassLoader, self).to_process(pdbs))

    def mark_processed(self, pdbs, **kwargs):
        for pdb in pdbs:
            super(MassLoader, self).mark_processed(pdb, **kwargs)

    def remove(self, pdbs, **kwargs):
        self.logger.debug("Remove does nothing in MassLoaders")
        pass

    def has_data(self, pdbs, **kwargs):
        """This means we never have the data for a mass loader. Generally this
        is the case.
        """
        return False

    def process(self, pdbs, **kwargs):
        data = self.data(pdbs)

        if not self.allow_no_data and not data:
            self.logger.error("No data produced")
            raise InvalidState("Missing data")
        elif not data:
            self.logger.warning("No data produced")
            return

        self.store(data, **kwargs)

    @abc.abstractmethod
    def data(self, pdbs, **kwargs):
        pass

    def __call__(self, given, **kwargs):
        entries = tuple(self.to_process(given, **kwargs))
        if not entries:
            self.logger.critical("Nothing to process")
            raise InvalidState("Nothing to process")

        self.logger.info("Processing all %s entries", len(entries))

        try:
            if not self.should_process(entries, **kwargs):
                self.logger.debug("No need to process %s", entries)
                return
            self.process(entries, **kwargs)
        except Skip as err:
            self.logger.warn("Skipping processing all entries. %s Reason %s",
                             str(err))
            return
        except Exception as err:
            self.logger.error("Error raised in process all entries")
            self.logger.exception(err)
            if self.stop_on_failure:
                raise StageFailed(self.name)
            return

        self.mark_processed(entries, **kwargs)


class MultiStageLoader(Stage):
    """This acts as a simple way to aggregate a bunch of loaders into one
    stage. It is really useful sometimes to simply run say all unit loaders
    without having to do each one individually or know which ones depend on
    each other. The loader itself does nothing but provide a way to run all
    other loaders this depends on.
    """

    """The list of stages that are children of this loader"""
    stages = []

    def is_missing(self, *args, **kwargs):
        """We always rerun the given input.
        """
        return True

    def process(self, *args, **kwargs):
        """Run each stage with the given input.
        """
        for stage in self.stages:
            stage(*args, **kwargs)


class Exporter(Stage):
    """A base class for all stages that export data from our database.
    """

    """ The mode of the file to write """
    mode = None

    def __init__(self, *args, **kwargs):
        super(Exporter, self).__init__(*args, **kwargs)
        if not self.mode:
            raise InvalidState("Must define the mode")

    @abc.abstractmethod
    def filename(self, entry):
        """Compute the filename for the given entry.

        :entry: The entry to write out.
        """
        pass

    @abc.abstractmethod
    def text(self, entry, **kwargs):
        pass

    def process(self, entry, **kwargs):
        with open(self.filename(entry), self.mode) as raw:
            raw.write(self.text(entry, **kwargs))


class PdbExporter(Exporter):
    """An exporter that write a single pdb to a single file.
    """
    mode = 'w'

    def is_missing(self, entry, **kwargs):
        """Will check if the file produce by filename() exists.
        """
        return not os.path.exists(self.filename(entry))
