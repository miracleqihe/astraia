from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.nichibun import CORPUS, INDEX, nichibun_cards


class NichibunIntakeTests(unittest.TestCase):
    def test_publication_year_and_unclassified_record(self):
        fields = {
            "番号": "0640018", "呼称（ヨミ）": "カッパ", "呼称（漢字）": "川童",
            "執筆者": "佐々木繁", "論文名": "遠野雑記", "書名・誌名": "郷土研究",
            "発行年（西暦）": "1913年", "掲載箇所・開始頁": "51", "掲載箇所・終了頁": "52",
            "地域（都道府県名）": "岩手県", "地域（市・郡名）": "遠野市", "地域（区町村名）": "松崎町",
        }
        table = "".join(f"<tr><td>■</td><td>{key}</td><td>{value}</td></tr>" for key, value in fields.items())
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "0640018.html"
            path.write_text(f"<html><table>{table}</table></html>", encoding="utf-8")
            cards = list(nichibun_cards([path]))
        self.assertEqual(len(cards), 3)
        case, body = cards[2]
        self.assertEqual(case.genre, "unclassified")
        self.assertFalse(case.audit.reviewed_by_human)
        self.assertEqual(case.temporal.year_start, 1913)
        self.assertIn("出版时间", case.temporal.uncertainty_note)
        self.assertEqual(case.spatial.location_name, "岩手県 遠野市 松崎町（遠野市参考点）")
        self.assertEqual(case.spatial.lat, 39.31667)
        self.assertEqual(case.spatial.lng, 141.53333)
        self.assertEqual(case.sources[1].type, "gazetteer")
        self.assertEqual(case.standards.berezkin_codes, [])
        self.assertEqual({relation.target for relation in case.relations}, {CORPUS, INDEX})
        self.assertIn("引用页 51–52", case.sources[0].citation)
        self.assertIn("0640018", body)


if __name__ == "__main__":
    unittest.main()
