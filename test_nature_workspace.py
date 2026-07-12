import unittest

import pandas as pd

from nature_workspace import build_scientific_figure


class ScientificFigureTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            {
                "time": [1, 2, 3, 1, 2, 3],
                "value": [2.1, 2.8, 4.2, 1.8, 3.0, 3.7],
                "group": ["control"] * 3 + ["treated"] * 3,
                "marker": [0.2, 0.4, 0.7, 0.1, 0.5, 0.8],
            }
        )

    def test_scatter_exports_nonempty_submission_formats(self):
        png, svg, pdf = build_scientific_figure(
            self.data, "散点图", "time", "value", "group", "Treatment response"
        )
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertIn(b"<svg", svg[:500])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(png), 1000)

    def test_heatmap_exports(self):
        png, svg, pdf = build_scientific_figure(
            self.data, "热图", "time", None, None, "Correlation"
        )
        self.assertGreater(min(map(len, (png, svg, pdf))), 500)

    def test_rejects_non_numeric_y(self):
        with self.assertRaises(ValueError):
            build_scientific_figure(self.data, "散点图", "time", "group")


if __name__ == "__main__":
    unittest.main()
