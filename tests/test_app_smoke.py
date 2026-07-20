from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppSmokeTests(unittest.TestCase):
    def test_sidebar_navigation_and_core_workspaces_render(self):
        app = AppTest.from_file(str(APP_PATH)).run(timeout=30)

        self.assertFalse(app.exception)
        navigation = app.sidebar.radio[0]
        self.assertEqual(
            list(navigation.options),
            ["PDF精读", "文献检索", "引用追踪", "科研任务", "科研绘图", "PPT汇报", "科研对话"],
        )
        self.assertIn("上传 PDF 文献", {widget.label for widget in app.file_uploader})

        navigation.set_value("文献检索").run(timeout=30)
        self.assertFalse(app.exception)
        self.assertIn("研究问题或关键词", {widget.label for widget in app.text_area})
        self.assertIn("上传研究材料（可选）", {widget.label for widget in app.file_uploader})
        checkbox_labels = {widget.label for widget in app.checkbox}
        self.assertTrue(
            {"PubMed", "Europe PMC", "OpenAlex", "Crossref"}.issubset(checkbox_labels)
        )
        self.assertIn("开始检索", {button.label for button in app.button})

        task_app = AppTest.from_file(str(APP_PATH)).run(timeout=30)
        task_app.sidebar.radio[0].set_value("科研任务").run(timeout=30)
        self.assertFalse(task_app.exception)
        self.assertNotIn("能力覆盖", {tab.label for tab in task_app.tabs})
        self.assertIn("上传附件（可选）", {widget.label for widget in task_app.file_uploader})


if __name__ == "__main__":
    unittest.main()
