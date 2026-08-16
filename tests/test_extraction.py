"""Unit tests for Names, Emails, Addresses, UK Postcodes, Dates, and 31-Field Record Extraction."""

import unittest
from extraction.address import extract_address_block
from extraction.dates import clean_ocr_date, locate_date_tokens
from extraction.email import clean_email_token
from extraction.extractor import extract_31_fields
from extraction.person import extract_father_name, extract_names, extract_title
from extraction.postcode import is_valid_postcode, repair_postcode_characters
from ocr.tokens import BoundingBox, OCRRow, OCRToken, RawRecord


class TestExtraction(unittest.TestCase):
    def _create_token(self, text: str, x: int = 10, y: int = 10) -> OCRToken:
        return OCRToken(
            text=text,
            bbox=BoundingBox(x=x, y=y, width=len(text) * 10, height=20),
            confidence=95.0,
        )

    def test_clean_ocr_date(self):
        self.assertEqual(clean_ocr_date("17/03/1991"), "17/03/1991")
        self.assertEqual(clean_ocr_date("o1/09/2023"), "01/09/2023")
        self.assertEqual(clean_ocr_date("14/O8/1988"), "14/08/1988")
        self.assertEqual(clean_ocr_date("06/07/2020"), "06/07/2020")
        self.assertIsNone(clean_ocr_date("32/01/2020"))  # Invalid day
        self.assertIsNone(clean_ocr_date("15/13/2020"))  # Invalid month

    def test_email_cleaning_and_domain_repair(self):
        email, pre = clean_email_token("hilary@jisc.ac.uk")
        self.assertEqual(email, "hilary@jisc.ac.uk")
        self.assertEqual(pre, "")

        email, pre = clean_email_token("user@domaincom")
        self.assertEqual(email, "user@domain.com")

        email, pre = clean_email_token("info@tiscalicouk")
        self.assertEqual(email, "info@tiscali.co.uk")

        email, pre = clean_email_token("Smith_smith@example.com")
        self.assertEqual(email, "smith@example.com")
        self.assertEqual(pre, "Smith")

    def test_postcode_normalization(self):
        self.assertTrue(is_valid_postcode("S16 8AG"))
        self.assertTrue(is_valid_postcode("YO61 4AD"))
        self.assertTrue(is_valid_postcode("HG1 3EZ"))
        self.assertTrue(is_valid_postcode("CV8 2LY"))
        self.assertTrue(is_valid_postcode("SO41 6DY"))

        # Contextual OCR repair: O -> 0, I -> 1, B -> 8
        repaired = repair_postcode_characters("HG13EZ")
        self.assertEqual(repaired, "HG1 3EZ")

        repaired2 = repair_postcode_characters("S168AG")
        self.assertEqual(repaired2, "S16 8AG")

    def test_father_name_title_stripping(self):
        # Phy.D Benton
        tok_email = self._create_token("hilary@jisc.ac.uk", 10, 10)
        tok_phyd = self._create_token("Phy.D", 100, 10)
        tok_benton = self._create_token("Benton", 150, 10)
        tok_dob = self._create_token("17/03/1991", 220, 10)

        tokens = [tok_email, tok_phyd, tok_benton, tok_dob]
        f_val, _ = extract_father_name(tokens, email_idx=0, dob_idx=3)
        self.assertEqual(f_val, "Benton")

    def test_address_street_and_city_split(self):
        # OtleyRoad Leeds, North Yorkshire S16 8AG England
        words = ["OtleyRoad", "Leeds,", "North", "Yorkshire", "S16", "8AG", "England"]
        tokens = [self._create_token(w, idx * 60, 20) for idx, w in enumerate(words)]

        s_val, _, c_val, _, p_val, _, cnt_val, _ = extract_address_block(tokens, 0, len(tokens))
        self.assertEqual(s_val, "OtleyRoad")
        self.assertEqual(c_val, "Leeds, North Yorkshire")
        self.assertEqual(p_val, "S16 8AG")
        self.assertEqual(cnt_val, "England")

    def test_full_record_31_fields_sample_row_1(self):
        # Ms. Hillary Benton hilary@jisc.ac.uk Phy.D Benton 17/03/1991 Female Service OtleyRoad Leeds, North Yorkshire S16 8AG England Vodafone Tango - 4616541 VfoneB4YT!@##&T3 JiVawB150239190I089 GSM Siemens MC60 473871 - 33 - 751054 -6 *@S!S - #!-521315-9 TurboCall MasterCardPremiumGold €580 06/07/2020 06/01/2022
        line1 = "Ms. Hillary Benton hilary@jisc.ac.uk Phy.D Benton 17/03/1991 Female Service OtleyRoad Leeds, North Yorkshire S16 8AG"
        line2 = "England Vodafone Tango - 4616541 VfoneB4YT!@##&T3 JiVawB150239190I089 GSM Siemens MC60 473871 - 33 - 751054 -6"
        line3 = "*@S!S - #!-521315-9 TurboCall MasterCardPremiumGold €580 06/07/2020 06/01/2022"

        rows = []
        for y_idx, line in enumerate([line1, line2, line3]):
            toks = [self._create_token(w, x_idx * 50, y_idx * 40) for x_idx, w in enumerate(line.split())]
            rows.append(OCRRow(y=y_idx * 40, words=toks, text=line))

        raw_rec = RawRecord(record_number=1, rows=rows)
        res = extract_31_fields(raw_rec, file_no="28", form_no=110)
        fields = res["fields"]

        self.assertEqual(fields["File No"]["value"], "28")
        self.assertEqual(fields["Form No"]["value"], "110")
        self.assertEqual(fields["Title"]["value"], "Ms")
        self.assertEqual(fields["First Name"]["value"], "Hillary")
        self.assertEqual(fields["Last Name"]["value"], "Benton")
        self.assertEqual(fields["Email"]["value"], "hilary@jisc.ac.uk")
        self.assertEqual(fields["Father Name"]["value"], "Benton")
        self.assertEqual(fields["DOB"]["value"], "17/03/1991")
        self.assertEqual(fields["Gender"]["value"], "Female")
        self.assertEqual(fields["Profession"]["value"], "Service")
        self.assertEqual(fields["Mailing Street"]["value"], "OtleyRoad")
        self.assertEqual(fields["City"]["value"], "Leeds, North Yorkshire")
        self.assertEqual(fields["Postal Code"]["value"], "S16 8AG")
        self.assertEqual(fields["Country"]["value"], "England")
        self.assertEqual(fields["Service Provider"]["value"], "Vodafone")
        self.assertEqual(fields["File Ref"]["value"], "Tango - 4616541")
        self.assertEqual(fields["Reference No"]["value"], "VfoneB4YT!@##&T3")
        self.assertEqual(fields["SIM No"]["value"], "JiVawB150239190I089")
        self.assertEqual(fields["Network Type"]["value"], "GSM")
        self.assertEqual(fields["Mobile Model"]["value"], "Siemens MC60")
        self.assertEqual(fields["IMEI 1"]["value"], "473871 - 33 - 751054 -6")
        self.assertEqual(fields["IMEI 2"]["value"], "*@S!S - #!-521315-9")
        self.assertEqual(fields["Plan Type"]["value"], "TurboCall")
        self.assertEqual(fields["Card Type"]["value"], "MasterCardPremiumGold")
        self.assertEqual(fields["Contact"]["value"], "580")
        self.assertEqual(fields["Issue Date"]["value"], "06/07/2020")
        self.assertEqual(fields["Renewal Date"]["value"], "06/01/2022")


if __name__ == "__main__":
    unittest.main()
