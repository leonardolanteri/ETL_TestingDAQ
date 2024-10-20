import unittest
import awkward as ak
from awkward import Array as akArray
import json
from binary_decoders import etroc
import importlib
importlib.reload(etroc)

def load_json(path: str) -> akArray:
    with open(path) as f:
        return ak.Array(json.load(f))

#=====================ETROC INPUT DATA=========================#
SINGLE_RB_INPUT = etroc.converter(
    ["unit_test/input_data/run_5100/output_run_5100_rb0.dat"],
    skip_trigger_check=True
)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  #
MULTI_RB_INPUT = etroc.converter(
    ["unit_test/input_data/run_6000/output_run_6000_rb0.dat", 
     "unit_test/input_data/run_6000/output_run_6000_rb1.dat", 
     "unit_test/input_data/run_6000/output_run_6000_rb2.dat"],
    skip_trigger_check=True
)
#=============================================================#


#=================ETROC DATA TO ASSERT TO======================#
SINGLE_RB_ASSERT        = load_json("unit_test/asserted_output/run_5100/output_run_5100_rb0.json")
SINGLE_RB_CHIPID_ASSERT = load_json("unit_test/asserted_output/run_5100/manual_chipid.json") # overrides chipid from SINGLE RB ASSERT
SINGLE_RB_NHITS_ASSERT  = load_json("unit_test/asserted_output/run_5100/manual_nhits.json")  # overrides nhits from SINGLE RB ASSERT
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  #
MULTI_RB_ASSERT         = load_json("unit_test/asserted_output/run_6000/output_run_6000_rb0.json")
MULTI_RB_CHIPID_ASSERT  = load_json("unit_test/asserted_output/run_6000/manual_chipid.json") # overrides chipid from SINGLE RB ASSERT
MULTI_RB_NHITS_ASSERT   = load_json("unit_test/asserted_output/run_6000/manual_nhits.json")  # overrides nhits from SINGLE RB ASSERT
#=============================================================#


class TestETROCBinaryDecoder(unittest.TestCase):
    """
    Test the binary decoding of etroc and scope data
    """
    def _test_event_field(self, field_name: str, single_rb_assert:akArray = SINGLE_RB_ASSERT, multi_rb_assert:akArray = MULTI_RB_ASSERT):
        #SINGLE RB FIELD CHECK
        with self.subTest(f"Single RB Check on: {field_name}"):
            ak.almost_equal(single_rb_assert[field_name], SINGLE_RB_INPUT[field_name])

        #MULTI RB FIELD CHECK
        with self.subTest(f"Multi RB Check on: {field_name}"):
            ak.almost_equal(multi_rb_assert[field_name], MULTI_RB_INPUT[field_name])

    ##
    #### TEST IMPORTANT EVENT FIELDS
    ##
    def test_chipid(self):
        self._test_event_field(
            'chipid', 
            single_rb_assert=SINGLE_RB_CHIPID_ASSERT, 
            multi_rb_assert=MULTI_RB_CHIPID_ASSERT
        )

    def test_nhits(self):
        self._test_event_field(
            'nhits', 
            single_rb_assert=SINGLE_RB_NHITS_ASSERT, 
            multi_rb_assert=MULTI_RB_NHITS_ASSERT
        )

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

    def test_bcid(self):
        self._test_event_field('bcid')

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

    