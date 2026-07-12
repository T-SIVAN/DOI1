from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppSmokeTests(unittest.TestCase):
    def test_five_tabs_and_literature_search_controls_render(self):
        app = AppTest.from_file(str(APP_PATH)).run(timeout=30)

        self.assertFalse(app.exception)
        self.assertEqual(
            [tab.label for tab in app.tabs],
            ["PDF精读", "文献检索", "引用追踪", "写作工具", "PPT汇报"],
        )
        self.assertIn("研究问题或关键词", {widget.label for widget in app.text_area})
        checkbox_labels = {widget.label for widget in app.checkbox}
        self.assertTrue(
            {"PubMed", "Europe PMC", "OpenAlex", "Crossref"}.issubset(checkbox_labels)
        )
        self.assertIn("开始检索", {button.label for button in app.button})


if __name__ == "__main__":
    unittest.main()
