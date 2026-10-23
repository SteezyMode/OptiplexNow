"""Offline storage-mount mapping tests. No Docker/socket or file writes."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"server"))
from download_storage import (StorageMappingError,bind_mounts,
                              container_to_host,host_to_container)


def c(mounts):
    return {"Id":"a"*64,"Mounts":mounts}


def bind(src, dest, rw=True):
    return {"Type":"bind","Source":src,"Destination":dest,"RW":rw}


class DownloadStorageTests(unittest.TestCase):
    def test_genre_folder_round_trip(self):
        rec=c([bind("/media/Movies","/downloads/Movies"),
               bind("/storage/Torrent","/downloads/incomplete")])
        self.assertEqual(container_to_host("/downloads/Movies/Horror",
                                           rec),"/media/Movies/Horror")
        self.assertEqual(host_to_container("/media/Movies/Horror",rec),
                         "/downloads/Movies/Horror")
        self.assertEqual(host_to_container("/media/Movies/Western Classics",rec),
                         "/downloads/Movies/Western Classics")
        self.assertEqual(container_to_host("/downloads/incomplete",rec),
                         "/storage/Torrent")

    def test_nested_mounts_take_precedence(self):
        rec=c([bind("/srv/library","/data"),
               bind("/srv/other","/data/isolated",False)])
        self.assertEqual(container_to_host("/data/isolated/file",rec),
                         "/srv/other/file")
        self.assertEqual(container_to_host("/data/horror/file",rec),
                         "/srv/library/horror/file")
        with self.assertRaises(StorageMappingError):
            container_to_host("/data/isolated",rec,require_writable=True)
        with self.assertRaises(StorageMappingError):
            host_to_container("/srv/other/file",rec)
        # A host path under the outer bind could land on an overlaying
        # nested Docker mount; do not produce a misleading save target.
        with self.assertRaises(StorageMappingError):
            host_to_container("/srv/library/isolated/file",rec)

    def test_missing_or_read_only_roots_block_writes(self):
        rec=c([bind("/mnt/ro","/ro",False)])
        self.assertEqual(container_to_host("/ro/a",rec),"/mnt/ro/a")
        with self.assertRaises(StorageMappingError):
            host_to_container("/mnt/ro/a",rec)
        with self.assertRaises(StorageMappingError):
            container_to_host("/ro/a",rec,require_writable=True)
        with self.assertRaises(StorageMappingError):
            container_to_host("/etc/passwd",rec)

    def test_invalid_paths_never_escape(self):
        rec=c([bind("/mnt/data","/downloads")])
        for path in ("/downloads/../etc/passwd", "/downloads/./file",
                     "/downloads//file", "/downloads/file\nname",
                     "//downloads/file", "/downloads/dir\x00file",
                     "relative/file", "", "/downloads/"+"x"*4097):
            with self.subTest(path=repr(path)), self.assertRaises(StorageMappingError):
                container_to_host(path,rec)

    def test_unsupported_mounts_and_ambiguity(self):
        for mounts in (
            None,
            [bind("/","/all")],
            [bind("/safe","/")],
            [bind("/mnt/a","/downloads"),bind("/mnt/b","/downloads")],
            [{"Type":"bind","Source":"/mnt/a",
              "Destination":"/downloads","RW":"true"}],
            [{"Type":"bind","Source":"/mnt/a",
              "Destination":"/downloads","RW":True},
             {"Type":"bind","Source":"/mnt/b",
              "Destination":"/downloads","RW":True}],
            [bind("/mnt","/downloads")]*129,
        ):
            with self.subTest(mounts=repr(mounts)[:100]),self.assertRaises(
                    StorageMappingError):
                bind_mounts(c(mounts))

    def test_volumes_not_guessed_and_paths_not_auto_created(self):
        rec=c([{"Type":"volume","Source":"/var/lib/docker/volumes/a",
               "Destination":"/downloads","RW":True}])
        self.assertEqual(bind_mounts(rec),[])
        with self.assertRaises(StorageMappingError):
            container_to_host("/downloads/movie",rec)
        with self.assertRaises(StorageMappingError):
            host_to_container("/home/user/Music",rec)


if __name__ == "__main__":
    unittest.main()
