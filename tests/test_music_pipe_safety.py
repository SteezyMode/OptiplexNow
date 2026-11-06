"""Native regression: playback initialization must survive a broken worker pipe.

On GLib < 2.82 SIGPIPE is not ignored by GSubprocess automatically.
Write/seek/pause of a newly exited music helper can otherwise kill Bruiser.
Run the harness in a child process so a regression cannot kill the test runner.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class MusicPipeSafetyTests(unittest.TestCase):
    def test_music_player_ignores_sigpipe_before_writing_to_worker(self):
        if not shutil.which("cc") or not shutil.which("pkg-config"):
            self.skipTest("native compiler or pkg-config unavailable")
        try:
            flags=subprocess.run(
                ["pkg-config", "--cflags", "--libs", "gio-2.0"],
                check=True,capture_output=True,text=True).stdout.split()
        except (subprocess.CalledProcessError,OSError):
            self.skipTest("gio-2.0 development headers unavailable")
        code=r"""
#include "music_playback.h"
#include <signal.h>
#include <stdio.h>
int main(void) {
    NowMusicPlayback *p=now_music_playback_new(NULL,NULL);
    if(!p)return 10;
#ifdef SIGPIPE
    struct sigaction state;
    if(sigaction(SIGPIPE,NULL,&state)!=0)return 11;
    if(state.sa_handler!=SIG_IGN)return 12;
    /* A default SIGPIPE handler would terminate this process right here. */
    raise(SIGPIPE);
#endif
    now_music_playback_free(p);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            program=root/"pipe.c"
            executable=root/"test-playback-pipe"
            program.write_text(code)
            compile=subprocess.run(
                ["cc","-Wall","-Wextra","-Werror",f"-I{SRC}",
                 str(program),str(SRC/"music_playback.c"),
                 str(SRC/"music_helper_paths.c"),"-o",str(executable),*flags],
                capture_output=True,text=True,timeout=45)
            self.assertEqual(compile.returncode,0,compile.stderr[-5000:])
            run=subprocess.run([str(executable)],capture_output=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
