"""Unit tests for calculation formulas, MY derivation, and Amount in Words."""

import unittest
from amount_words import amount_to_words, integer_to_words
from calculations import calculate_fields


class TestCalculations(unittest.TestCase):
    def test_integer_to_words(self):
        self.assertEqual(integer_to_words(0), "Zero")
        self.assertEqual(integer_to_words(5), "Five")
        self.assertEqual(integer_to_words(14), "Fourteen")
        self.assertEqual(integer_to_words(34), "Thirty Four")
        self.assertEqual(integer_to_words(100), "One Hundred")
        self.assertEqual(integer_to_words(580), "Five Hundred Eighty")
        self.assertEqual(integer_to_words(1005), "One Thousand Five")

    def test_amount_to_words(self):
        self.assertEqual(amount_to_words("34.49"), "Thirty Four Point Four Nine")
        self.assertEqual(amount_to_words("24.33"), "Twenty Four Point Three Three")
        self.assertEqual(amount_to_words("24.41"), "Twenty Four Point Four One")
        self.assertEqual(amount_to_words("10.30"), "Ten Point Three Zero")
        self.assertEqual(amount_to_words(580), "Five Hundred Eighty Point Zero Zero")

    def test_calculate_fields_standard(self):
        record = {
            "fields": {
                "Title": {"value": "Ms"},
                "First Name": {"value": "Hillary"},
                "Last Name": {"value": "Benton"},
                "Initial": {"value": ""},
                "Issue Date": {"value": "06/07/2020"},
                "Renewal Date": {"value": "06/01/2022"},
                "Contact": {"value": "580"},
                "Installments": {"value": ""},
                "Amount in Words": {"value": ""},
            }
        }
        calculate_fields(record)
        self.assertEqual(record["fields"]["Initial"]["value"], "MHB")
        self.assertEqual(record["MY"], 24)
        # 580 / 24 + 10.33 = 24.1666... + 10.33 = 34.4966... -> rounded down 34.49
        self.assertEqual(record["fields"]["Installments"]["value"], "34.49")
        self.assertEqual(record["fields"]["Amount in Words"]["value"], "Thirty Four Point Four Nine")

    def test_calculate_fields_my_zero(self):
        record = {
            "fields": {
                "Title": {"value": "Mr"},
                "First Name": {"value": "Alex"},
                "Last Name": {"value": "Mccracken"},
                "Initial": {"value": ""},
                "Issue Date": {"value": "18/02/2022"},
                "Renewal Date": {"value": "18/02/2022"},
                "Contact": {"value": "341"},
                "Installments": {"value": ""},
                "Amount in Words": {"value": ""},
            }
        }
        calculate_fields(record)
        self.assertEqual(record["fields"]["Initial"]["value"], "MAM")
        self.assertEqual(record["MY"], 0)
        self.assertEqual(record["fields"]["Installments"]["value"], "INVALID")
        self.assertEqual(record["fields"]["Amount in Words"]["value"], "")

    def test_calculate_fields_major_general_initials(self):
        record = {
            "fields": {
                "Title": {"value": "Major General"},
                "First Name": {"value": "Arthur"},
                "Last Name": {"value": "Wellesley"},
                "Initial": {"value": ""},
                "Issue Date": {"value": "01/01/2020"},
                "Renewal Date": {"value": "01/01/2023"},
                "Contact": {"value": "720"},
                "Installments": {"value": ""},
                "Amount in Words": {"value": ""},
            }
        }
        calculate_fields(record)
        self.assertEqual(record["fields"]["Initial"]["value"], "MAW")
        self.assertEqual(record["MY"], 36)
        # 720 / 36 + 10.33 = 20.00 + 10.33 = 30.33
        self.assertEqual(record["fields"]["Installments"]["value"], "30.33")
        self.assertEqual(record["fields"]["Amount in Words"]["value"], "Thirty Point Three Three")


if __name__ == "__main__":
    unittest.main()
