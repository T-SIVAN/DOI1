from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppSmokeTests(unittest.TestCase):
    def test_five_tabs_and_literature_search_controls_render(self):
        app = AppTest.from_file(str(APP_PATH)).run(timeout=30)

        self.assertFalse(app.exception)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertEqual(tab_labels[:4], ["PDF精读", "文献检索", "引用追踪", "科研写作"])
        self.assertEqual(tab_labels[-1], "PPT汇报")
        self.assertTrue(
            {"写作与润色", "审稿与回复", "引用与数据", "科研绘图", "成果转化", "能力覆盖"}
            .issubset(set(tab_labels))
        )
        self.assertIn("研究问题或关键词", {widget.label for widget in app.text_area})
        checkbox_labels = {widget.label for widget in app.checkbox}
        self.assertTrue(
            {"PubMed", "Europe PMC", "OpenAlex", "Crossref"}.issubset(checkbox_labels)
        )
        self.assertIn("开始检索", {button.label for button in app.button})


if __name__ == "__main__":
    unittest.main()
