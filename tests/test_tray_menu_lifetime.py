"""Native GTK regression for tray menu ownership on SNI and classic trays.

v1.21.16 on Pop!_OS COSMIC crashed in music_tray_rebuild_idle at
gtk_widget_destroy after an indicator ref swap. Exercise the *production*
header helpers hundreds of times in an isolated GTK process under Xvfb.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"src/main.c").read_text(encoding="utf-8")


class TrayMenuLifetimeTests(unittest.TestCase):
    def test_main_uses_owned_reference_on_every_rebuild(self):
        self.assertIn('#include "tray_menu_lifetime.h"',MAIN)
        self.assertIn("tray_menu=now_tray_menu_owned_new();",MAIN)
        self.assertIn("now_tray_menu_owned_destroy(old);",MAIN)
        self.assertNotIn("if(old)gtk_widget_destroy(old);",MAIN)
        for action in ("tray_music_previous","tray_music_pause","tray_music_next"):
            self.assertIn("G_CALLBACK("+action+")",MAIN)

    def test_repeated_native_gtk_replacements_no_crash_or_leaked_menu(self):
        if not all(shutil.which(tool) for tool in ("cc","pkg-config","xvfb-run")):
            self.skipTest("Compiler or Xvfb unavailable")
        try:
            flags=subprocess.run(
                ["pkg-config","--cflags","--libs","gtk+-3.0"],
                check=True,capture_output=True,text=True,timeout=8).stdout.split()
        except (OSError,subprocess.CalledProcessError):
            self.skipTest("gtk+-3.0 headers unavailable")
        native=r'''
#include <gtk/gtk.h>
#include "tray_menu_lifetime.h"

static guint total_finalized;
static void finalized(gpointer data,GObject *object){
 (void)data;(void)object;
 total_finalized++;
}
int main(int argc,char **argv){
 gtk_init(&argc,&argv);
 guint count=0;
 for(int backend=0;backend<2;backend++){
  GtkWidget *owned=NULL,*indicator_menu=NULL;
  for(int i=0;i<400;i++){
   GtkWidget *old=owned;
   owned=now_tray_menu_owned_new();
   g_object_weak_ref(G_OBJECT(owned),finalized,NULL);
   count++;
   GtkWidget *item=gtk_menu_item_new_with_label("Now playing");
   gtk_menu_shell_append(GTK_MENU_SHELL(owned),item);
   gtk_widget_show_all(owned);
   if(backend){
    /* Fake AppIndicator: release its previous menu ref, then retain new. */
    if(indicator_menu)g_object_unref(indicator_menu);
    indicator_menu=g_object_ref(owned);
   }
   now_tray_menu_owned_destroy(old);
  }
  if(indicator_menu)g_object_unref(indicator_menu);
  now_tray_menu_owned_destroy(owned);
 }
 if(total_finalized!=count){
  g_printerr("Expected %u finalized, got %u\n",count,total_finalized);
  return 4;
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="bruiser-tray-ref-") as folder:
            root=Path(folder)
            (root/"check.c").write_text(native)
            executable=root/"check"
            compile=subprocess.run(
                ["cc","-std=c11","-Wall","-Wextra","-Werror",
                 "-I"+str(ROOT/"src"),str(root/"check.c"),"-o",
                 str(executable),*flags],
                capture_output=True,text=True,timeout=45)
            self.assertEqual(compile.returncode,0,compile.stderr[-3000:])
            run=subprocess.run(["xvfb-run","-a",str(executable)],
                               capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,
                             "stdout:\n"+run.stdout[-1200:]+
                             "\nstderr:\n"+run.stderr[-3000:])


if __name__=="__main__":
    unittest.main()
