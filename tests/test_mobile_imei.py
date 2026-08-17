"""Unit tests for Mobile Model and IMEI boundary separation."""

import unittest
from ocr.tokens import BoundingBox, OCRToken
from extraction.mobile import extract_mobile_model
from extraction.imei import extract_imei_pair


class TestMobileIMEISeparation(unittest.TestCase):
    def _create_tokens(self, words: list[str]) -> list[OCRToken]:
        tokens = []
        for idx, w in enumerate(words):
            tokens.append(
                OCRToken(
                    text=w,
                    bbox=BoundingBox(x=idx * 50, y=100, width=45, height=20),
                    confidence=95.0,
                )
            )
        return tokens

    def test_siemens_mc60(self):
        # Siemens MC60 473871 - 33 - 751054 -6 *@S!S - #!-521315-9 TurboCall
        words = ["Siemens", "MC60", "473871", "-", "33", "-", "751054", "-6", "*@S!S", "-", "#!-521315-9", "TurboCall"]
        tokens = self._create_tokens(words)

        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Siemens MC60")
        self.assertEqual(len(model_toks), 2)
        self.assertEqual(next_idx, 2)

        # Extract IMEI pair from next_idx to TurboCall (idx 11)
        imei1, _, imei2, _ = extract_imei_pair(tokens, next_idx, 11)
        self.assertEqual(imei1, "473871 - 33 - 751054 -6")
        self.assertEqual(imei2, "*@S!S - #!-521315-9")

    def test_nokia_7210(self):
        # Nokia 7210 202608 - 23 - 634756 - 1 +2%7%& - +| - 156677 - 8 Classic
        words = ["Nokia", "7210", "202608", "-", "23", "-", "634756", "-", "1", "+2%7%&", "-", "+|", "-", "156677", "-", "8", "Classic"]
        tokens = self._create_tokens(words)

        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Nokia 7210")
        self.assertEqual(len(model_toks), 2)
        self.assertEqual(next_idx, 2)

        imei1, _, imei2, _ = extract_imei_pair(tokens, next_idx, 16)
        self.assertEqual(imei1, "202608 - 23 - 634756 - 1")
        self.assertEqual(imei2, "+2%7%& - +| - 156677 - 8")

    def test_nokia_6610(self):
        # Nokia 6610 316803 - 51-554797-8 |&ll*? - $1 - 995095 -2 Classic
        words = ["Nokia", "6610", "316803", "-", "51-554797-8", "|&ll*?", "-", "$1", "-", "995095", "-2", "Classic"]
        tokens = self._create_tokens(words)

        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Nokia 6610")
        self.assertEqual(next_idx, 2)

        imei1, _, imei2, _ = extract_imei_pair(tokens, next_idx, 11)
        self.assertEqual(imei1, "316803 - 51-554797-8")
        self.assertEqual(imei2, "|&ll*? - $1 - 995095 -2")

    def test_nokia_6800(self):
        # Nokia 6800 607198 - 24-653336-5 !%%SS!-!#-798797-7 SMSPro
        words = ["Nokia", "6800", "607198", "-", "24-653336-5", "!%%SS!-!#-798797-7", "SMSPro"]
        tokens = self._create_tokens(words)

        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Nokia 6800")
        self.assertEqual(next_idx, 2)

        imei1, _, imei2, _ = extract_imei_pair(tokens, next_idx, 6)
        self.assertEqual(imei1, "607198 - 24-653336-5")
        self.assertEqual(imei2, "!%%SS!-!#-798797-7")

    def test_samsung_s40(self):
        words = ["Samsung", "S40", "490154203237518", "*&!%992837", "UltraPlus"]
        tokens = self._create_tokens(words)

        model_val, _, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Samsung S40")
        self.assertEqual(next_idx, 2)


if __name__ == "__main__":
    unittest.main()
