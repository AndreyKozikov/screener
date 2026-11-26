import unittest

from vector_service.algorithms.series import extract_series


class SeriesTests(unittest.TestCase):
    def test_secname_examples(self):
        examples = {
            "Газпром нефть БО 003P-15R": "003P-15R",
            "ДОМ.РФ (ПАО) обл. сер. А15": "А15",
            "Главная дорога АО об.сер. 03": "03",
            "«Газпром» ПАО БО-19": "БО-19",
            "РЖД-32 обл": "32",
            "ОФЗ-ПД 26207 03/02/27": None,
            "Эмитент серия БО 001 03/02/27": "001",
            "Эмитент серия 03/02/27": None,
            "": None,
            None: None,
        }
        for name, expected in examples.items():
            with self.subTest(name=name):
                self.assertEqual(extract_series(name), expected)

    def test_issuename_examples(self):
        examples = {
            "неконвертируемые документарные купонные облигации на предъявителя серии А15": "А15",
            "Неконвертируемые процентные документарные облигации серии 03 на предъявителя": "03",
            "облигации серии 01, с обязательным централизованным хранением": "01",
            "облигации серии \"А2\"": "А2",
        }
        for name, expected in examples.items():
            with self.subTest(name=name):
                self.assertEqual(extract_series(name), expected)
