import datetime

from pymotifs import core
from pymotifs.models import LoopReleases
from pymotifs.utils.releases import Release


class Loader(core.MassLoader):
    def data(self, *args, **kwargs):
        now = datetime.datetime.now()
        helper = Release(self.config, self.session.maker)
        current = helper.current('loop')
        next = helper.next(current, mode=self.config['release_mode']['loops'])
        return LoopReleases(id=next, date=now)