import unittest
from unittest.mock import patch
from backend.geospatial_backend import barangay_geocoding as geo


class TestBarangayGeocoding(unittest.TestCase):
    def test_place_variant_names(self):
        self.assertEqual(geo._norm_city('City of Cebu'), geo._norm_city('Cebu City'))
        self.assertEqual(geo._norm_city('City of Mandaue'), geo._norm_city('Mandaue City'))

    def test_reject_city_center(self):
        record = {"country_code":"ph","result_type":"city","name":"Basak Pardo",
                  "city":"Cebu City","lat":10.3,"lon":123.9}
        self.assertFalse(geo._candidate_matches(record,'Basak Pardo','City of Cebu','Cebu'))

    def test_requires_exact_barangay_and_city(self):
        record = {"country_code":"ph","result_type":"suburb","suburb":"Guadalupe",
                  "city":"Cebu City","lat":10.32,"lon":123.89}
        self.assertTrue(geo._candidate_matches(record,'Guadalupe','City of Cebu','Cebu'))
        self.assertFalse(geo._candidate_matches(record,'Guadalupe','Mandaue City','Cebu'))
        self.assertFalse(geo._candidate_matches(record,'Basak Pardo','City of Cebu','Cebu'))

    def test_no_unverified_patient_geocoding(self):
        with patch.object(geo,'resolve_barangay_coordinates',return_value=None):
            value=geo.enrich_patient_coordinates({'psgc_barangay_code':'0730600029','barangay':'Guadalupe','city':'Cebu City','province':'Cebu','latitude':None,'longitude':None})
            self.assertIsNone(value['latitude'])

    def test_keep_existing(self):
        with patch.object(geo,'resolve_barangay_coordinates') as mocked:
            value=geo.enrich_patient_coordinates({'psgc_barangay_code':'0731300002','latitude':10.339,'longitude':123.929,'location_precision':'barangay'})
            self.assertEqual(value['latitude'],10.339)
            mocked.assert_not_called()


if __name__=='__main__':
    unittest.main()
