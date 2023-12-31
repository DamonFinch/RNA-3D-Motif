import pytest

from pymotifs import core
from pymotifs import models as mod
from pymotifs.nr.ordering import Loader

from test import StageTest


class ProcessTest(StageTest):
    loader_class = Loader

    def test_it_will_use_ids_from_given_pdbs(self):
        val = self.loader.to_process([], manual={'nr_release_id': '1.0'})
        assert len(val) == 165


class QueryingTest(StageTest):
    loader_class = Loader

    def test_knows_if_has_no_data(self):
        assert self.loader.has_data(-1) is False

    @pytest.mark.skip()
    def test_knows_if_has_data(self):
        assert self.loader.has_data(1) is True


class MembersTest(StageTest):
    loader_class = Loader

    def test_can_load_all_members_for_a_class(self):
        assert self.loader.members(9) == [
            ('1UTD|1|0', 12),
            ('1UTD|1|2', 13),
            ('1UTD|1|3', 14),
            ('1UTD|1|4', 15),
            ('1UTD|1|5', 16),
            ('1UTD|1|6', 17),
            ('1UTD|1|7', 18),
            ('1UTD|1|8', 19),
            ('1UTD|1|9', 20),
            ('1UTD|1|Z', 21),
            ('1UTD|1|1', 22),
        ]

    def test_it_will_fail_if_no_members(self):
        with pytest.raises(core.InvalidState):
            self.loader.members(-1)


class DistancesTest(StageTest):
    loader_class = Loader

    @pytest.mark.xfail(reason="1UTD|1|1 has no similarities yet")
    def test_it_can_load_all_distances(self):
        members = self.loader.members(9)
        distances = self.loader.distances(9, members)
        ans = sorted(['1UTD|1|0', '1UTD|1|1', '1UTD|1|2', '1UTD|1|3',
                      '1UTD|1|4', '1UTD|1|5', '1UTD|1|6', '1UTD|1|7',
                      '1UTD|1|8', '1UTD|1|9', '1UTD|1|Z'])

        assert sorted(m[0] for m in members) == ans
        assert sorted(distances['1UTD|1|0'].keys()) == ans
        assert len(distances) == len(members)
        assert distances['1UTD|1|0'] == {
            '1UTD|1|1': 1.11285,
            '1UTD|1|2': 0.130253,
            '1UTD|1|3': 0.0671009,
            '1UTD|1|4': 0.0800629,
            '1UTD|1|5': 0.0636083,
            '1UTD|1|6': 0.0980047,
            '1UTD|1|7': 0.0930357,
            '1UTD|1|8': 0.0721325,
            '1UTD|1|9': 0.136114,
            '1UTD|1|Z': 0.079315,
        }

    def test_it_will_raise_skip_if_no_members(self):
        with pytest.raises(core.Skip):
            self.loader.distances(-1, [])


class OrderingTest(StageTest):
    loader_class = Loader

    def class_for(self, release, resolution, ife):
        with self.loader.session() as session:
            query = session.query(mod.NrChains).\
                join(mod.NrClasses,
                     mod.NrClasses.nr_class_id == mod.NrChains.nr_class_id).\
                filter(mod.NrChains.nr_release_id == release).\
                filter(mod.NrChains.ife_id == ife).\
                first()
            return query.nr_class_id

    def ordering_for(self, release, resolution, ife):
        class_id = self.class_for(release, resolution, ife)
        members = self.loader.members(class_id)
        distances = self.loader.distances(class_id, members)
        return [d[0] for d in self.loader.ordered(members, distances)]

    def test_it_creates_correct_ordering(self):
        val = self.ordering_for('1.0', '3.0', '1VY4|1|AA')
        assert val == [
            '4V9K|1|AA',
            '4V9K|1|CA',
            '4V8G|1|AA',
            '1J5E|1|A',
            '1IBK|1|A',
            '4V7W|1|AA',
            '4V7W|1|CA',
            '4V8G|1|CA',
            '4V8I|1|CA',
            '1VY4|1|CA',
            '1VY4|1|AA',
            '4V8I|1|AA'
        ]
