"""Lightweight regression checks for the redesigned dashboard source."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DashboardRedesignTests(unittest.TestCase):
    def test_single_app_entry_point(self):
        self.assertTrue((ROOT / "app.py").is_file())
        self.assertFalse((ROOT / "Trackwise Dashboard").exists())

    def test_sidebar_navigation_removed(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        layout = (ROOT / "components" / "layout.py").read_text(encoding="utf-8")
        self.assertNotIn("render_sidebar(user", source)
        self.assertIn("[data-testid=\"stSidebar\"]{display:none", (ROOT / "assets" / "styles.css").read_text(encoding="utf-8"))
        self.assertIn("Navigation is now tab-based", layout)

    def test_role_pages_use_tabs(self):
        for name in ["student_home.py", "instructor_home.py", "admin_home.py"]:
            source = (ROOT / "pages" / name).read_text(encoding="utf-8")
            self.assertIn("st.tabs", source)

    def test_operational_pages_do_not_use_final_result(self):
        for name in ["student_home.py", "instructor_home.py"]:
            source = (ROOT / "pages" / name).read_text(encoding="utf-8")
            self.assertNotIn("final_result", source)
        admin = (ROOT / "pages" / "admin_home.py").read_text(encoding="utf-8")
        self.assertIn("Research", admin)

    def test_prediction_is_optional_and_separate(self):
        service = (ROOT / "services" / "learning_service.py").read_text(encoding="utf-8")
        self.assertIn("load_prediction_data", service)
        self.assertIn("prediction_for_student", service)
        self.assertIn("load_recommendation_summary", service)


if __name__ == "__main__":
    unittest.main()
