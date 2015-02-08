"""
This is the main module for running updates. Running this package will run an
update for all parts of the pipeline.
"""

from pymotifs import core
from pymotifs import units


class Loader(core.MultiLoader):
    stages = [units.Loader]
