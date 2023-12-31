import pytest

from test import QueryUtilTest

from pymotifs.utils import structures as st


class SourceTest(QueryUtilTest):
    query_class = st.Structure

    def test_can_find_a_simple_taxon_id(self):
        self.assertEquals([562], self.db_obj.source('4V4Q', 'AA'))

    def test_knows_when_there_is_no_known_taxon_id(self):
        self.assertEquals([], self.db_obj.source('1ET4', 'A'))

    @pytest.mark.skip(reason="Seems annotations on this have changed")
    def test_can_find_several_species_ids(self):
        self.assertEquals([11103, 32630], self.db_obj.source('3T4B', 'A'))

    @pytest.mark.skip()
    def test_fails_if_it_cannot_find_all_taxon_ids(self):
        pass

    def test_can_simplify_multiple_to_synthenic(self):
        self.assertEquals(32630, self.db_obj.source('3T4B', 'A', simplify=True))

    def test_simplifies_to_just_first_id(self):
        self.assertEquals(562, self.db_obj.source('4V4Q', 'AA', simplify=True))

    def test_can_handle_annotations_that_disagree(self):
        self.assertEquals(2238, self.db_obj.source('3CPW', 'A', simplify=True))


class RnaChainsTest(QueryUtilTest):
    query_class = st.Structure

    def test_can_get_all_rna_chains_in_a_structure(self):
        self.assertEquals(['A'], self.db_obj.rna_chains('3T4B'))

    def test_will_filter_out_non_rna_chains(self):
        ans = set(['AA', 'CA', 'BA', 'DA', 'BB', 'DB'])
        self.assertEquals(ans, set(self.db_obj.rna_chains('4V4Q')))

    def test_can_return_ids_and_names(self):
        val = self.db_obj.rna_chains('4V4Q', return_id=True)[0]
        assert ('AA', 2008) == val


class LoopLoadingTest(QueryUtilTest):
    query_class = st.Structure

    @pytest.mark.skip()
    def test_can_load_data(self):
        val = self.db_obj.loops('IL_1FG0_007')
        ans = {
            'id': 'IL_1FG0_007',
            'nts': [],
            'endpoints': [('1FG0_AU_1_A_2331_C_', '1FG0_AU_1_A_2333_G_'),
                          ('1FG0_AU_1_A_2351_C_', '1FG0_AU_1_A_2355_G_')]
        }
        self.assertEquals(ans, val)
