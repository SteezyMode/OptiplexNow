"""Contract for the invisible Dashboard GPU shortcut, without live host access."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DashboardGpuShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src/main.c").read_text(encoding="utf-8")

    def test_exact_existing_label_styling_and_transparent_hit_target(self):
        source = self.source
        self.assertIn('metric_gpu=label("GPU   --","metric");', source)
        self.assertIn('gtk_event_box_set_visible_window(GTK_EVENT_BOX(gpu_hitbox),FALSE)', source)
        self.assertIn('gtk_container_add(GTK_CONTAINER(gpu_hitbox),metric_gpu);', source)
        self.assertIn('gtk_grid_attach(GTK_GRID(metrics),gpu_hitbox,1,0,1,1);', source)
        self.assertIn('g_signal_connect(gpu_hitbox,"button-press-event",', source)
        self.assertNotIn('gtk_grid_attach(GTK_GRID(metrics),metric_gpu,1,0,1,1);', source)
        self.assertIn('"#metric {background:', source)

    def test_click_routes_without_changing_owner_only_control_boundary(self):
        source = self.source
        callback = re.search(
            r'static gboolean on_dashboard_gpu_pressed\(.*?\n \}\n',
            source, re.S)
        self.assertIsNotNone(callback)
        body = callback.group()
        self.assertIn('event->button!=GDK_BUTTON_PRIMARY', body)
        self.assertIn('if(now_ui_state_gpu_power_enabled())', body)
        self.assertIn('on_gpu_power_settings(NULL,NULL);', body)
        self.assertIn('on_settings(NULL,NULL);', body)
        self.assertIn('"now-settings-stack"', body)
        self.assertIn('"gpu"', body)
        self.assertIn('return TRUE;', body)
        # No raw LACT/SSH access in the dashboard click path.
        self.assertNotIn('ssh', body.lower())
        self.assertNotIn('lactd.sock', body)


if __name__ == "__main__":
    unittest.main()
