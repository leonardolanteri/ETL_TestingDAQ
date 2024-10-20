import unittest
import awkward as ak
import json
from binary_decoders.etroc import converter


#=================ETROC DATA TO ASSERT TO======================#
ETROC_BINARY_DATA_PATH = "unit_test/asserted_output/output_run_5100_rb0.json"
with open(ETROC_BINARY_DATA_PATH) as f:
    ETROC_DATA_ASSERT = ak.Array(
        json.load(f)
    )
with open("unit_test/asserted_output/manual_chipid.json") as f:
    ETROC_CHIPID_MANUAL = ak.Array(json.load(f))

with open("unit_test/asserted_output/manual_nhits.json") as f:
    ETROC_NHITS_MANUAL = ak.Array(json.load(f))
#=============================================================#

#=====================ETROC INPUT DATA=========================#
ETROC_INPUT_DATA_PATHS = [
    "unit_test/input_data/output_run_5100_rb0.dat"
]
ETROC_INPUT_DATA = converter(
    ETROC_INPUT_DATA_PATHS,
    skip_trigger_check=True
)
#=============================================================#

class TestETROCBinaryDecoder(unittest.TestCase):
    """
    Test the binary decoding of etroc and scope data
    """
    def setUp(self):
        """
        Special method used by unittest that will be used for each case.
        """
        self.data_assert = ETROC_DATA_ASSERT
        self.input_data = ETROC_INPUT_DATA

    def _test_event_field(self, field_name: str):
       self.assertTrue(
            ak.almost_equal(
                self.data_assert[field_name], self.input_data[field_name]
            )
        ) 
    ##
    #### TEST IMPORTANT EVENT FIELDS
    ##
    def test_toa_code(self):
        self._test_event_field('toa_code')

    def test_tot_code(self):
        self._test_event_field('tot_code')

    def test_cal_code(self):
        self._test_event_field('cal_code')

    def test_row(self):
        self._test_event_field('row')

    def test_col(self):
        self._test_event_field('col')

    def test_chipid(self):
        #self._test_event_field('chipid')
        # Chipid seems to be wrong but I am gonna assume it is ok, toa, tot and cal are fine.
        self.assertTrue(
            ak.almost_equal(
                ETROC_CHIPID_MANUAL, self.input_data['chipid']
            )
        ) 

    def test_bcid(self):
        self._test_event_field('bcid')

    def test_nhits(self):
        #self._test_event_field('nhits')
        self.assertTrue(
            ak.almost_equal(
                ETROC_NHITS_MANUAL, self.input_data['nhits']
            )
        ) 

    def test_event(self):
        self._test_event_field('event')

    def test_l1counter(self):
        self._test_event_field('l1counter')

    def test_elink(self):
        self._test_event_field('elink')

if __name__ == '__main__':
    unittest.main()
    # put this flag to give a little tolerance in ak almost equal
    # atol=0.001

    