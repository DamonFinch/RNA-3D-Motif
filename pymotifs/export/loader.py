from pymotifs.core import StageContainer

from pymotifs.export.cifatom import Exporter as CifAtom
from pymotifs.export.interactions import InteractionExporter
from pymotifs.export.loops import Exporter as LoopExporter


class Exporter(StageContainer):
    stages = [CifAtom, LoopExporter, InteractionExporter]