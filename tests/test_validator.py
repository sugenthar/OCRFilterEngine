"""Unit tests for Validation and Cross-field rules."""

import unittest
from validator import validate_record


class TestValidator(unittest.TestCase):
    def _create_valid_record(self) -> dict:
        fields = {
            "File No": {"value": "28"},
            "Form No": {"value": "110"},
            "Title": {"value": "Ms"},
            "First Name": {"value": "Hillary"},
            "Last Name": {"value": "Benton"},
            "Initial": {"value": "MHB"},
            "Email": {"value": "hilary@jisc.ac.uk"},
            "Father Name": {"value": "Benton"},
            "DOB": {"value": "17/03/1991"},
            "Gender": {"value": "Female"},
            "Profession": {"value": "Service"},
            "Mailing Street": {"value": "OtleyRoad"},
            "City": {"value": "Leeds, North Yorkshire"},
            "Postal Code": {"value": "S16 8AG"},
            "Country": {"value": "England"},
            "Service Provider": {"value": "Vodafone"},
            "File Ref": {"value": "Tango - 4616541"},
            "Reference No": {"value": "VfoneB4YT!@##&T3"},
            "SIM No": {"value": "JiVawB150239190I089"},
            "Network Type": {"value": "GSM"},
            "Mobile Model": {"value": "Siemens MC60"},
            "IMEI 1": {"value": "473871 - 33 - 751054 -6"},
            "IMEI 2": {"value": "*@S!S - #!-521315-9"},
            "Plan Type": {"value": "TurboCall"},
            "Card Type": {"value": "MasterCardPremiumGold"},
            "Contact": {"value": "580"},
            "Issue Date": {"value": "06/07/2020"},
            "Renewal Date": {"value": "06/01/2022"},
            "Installments": {"value": "34.49"},
            "Amount in Words": {"value": "Thirty Four Point Four Nine"},
            "Remarks": {"value": "Not Applicable"},
        }
        return {"record_number": 1, "form_no": 110, "fields": fields, "MY": 24}

    def test_clean_record_passes(self):
        record = self._create_valid_record()
        issues = validate_record(record)
        self.assertEqual(len(issues), 0)

    def test_invalid_email(self):
        record = self._create_valid_record()
        record["fields"]["Email"]["value"] = "invalid_email_format"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "INVALID_EMAIL" for i in issues))

    def test_dob_after_issue_date_cross_validation(self):
        record = self._create_valid_record()
        record["fields"]["DOB"]["value"] = "01/01/2025"
        record["fields"]["Issue Date"]["value"] = "01/01/2020"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "DOB_AFTER_ISSUE_DATE" for i in issues))

    def test_renewal_before_issue_date_cross_validation(self):
        record = self._create_valid_record()
        record["fields"]["Issue Date"]["value"] = "01/01/2023"
        record["fields"]["Renewal Date"]["value"] = "01/01/2020"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "RENEWAL_BEFORE_ISSUE_DATE" for i in issues))

    def test_invalid_postal_code(self):
        record = self._create_valid_record()
        record["fields"]["Postal Code"]["value"] = "INVALID_POSTCODE_999"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "INVALID_POSTAL_CODE" for i in issues))

    def test_mobile_model_imei_conflict(self):
        record = self._create_valid_record()
        record["fields"]["Mobile Model"]["value"] = "473871337510546"
        record["fields"]["IMEI 1"]["value"] = "473871337510546"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "MOBILE_MODEL_IMEI_CONFLICT" for i in issues))

    def test_my_zero_installments_valid(self):
        record = self._create_valid_record()
        record["MY"] = 0
        record["fields"]["Installments"]["value"] = "INVALID"
        record["fields"]["Amount in Words"]["value"] = ""
        issues = validate_record(record)
        self.assertEqual(len(issues), 0)

    def test_low_confidence_ocr_requires_review(self):
        record = self._create_valid_record()
        record["fields"]["Email"].update({"confidence": 42.0, "needs_review": True})
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "LOW_OCR_CONFIDENCE" for i in issues))

    def test_short_imei_is_not_accepted_as_a_model_number(self):
        record = self._create_valid_record()
        record["fields"]["IMEI 1"]["value"] = "7210"
        issues = validate_record(record)
        self.assertTrue(any(i["reason"] == "INVALID_IMEI1" for i in issues))


if __name__ == "__main__":
    unittest.main()
