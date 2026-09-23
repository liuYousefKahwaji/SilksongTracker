import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import install_live_bridge


class LiveInstallerTests(unittest.TestCase):
    def test_upgrade_replaces_only_own_dll_and_keeps_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "tracker"
            game = Path(temporary) / "game"
            dll = Path(temporary) / "SilksongLiveBridge.dll"
            root.mkdir()
            (game / "BepInEx/core").mkdir(parents=True)
            (game / "Hollow Knight Silksong_Data/Managed").mkdir(parents=True)
            (game / "BepInEx/core/BepInEx.dll").write_bytes(b"fixture")
            (game / "Hollow Knight Silksong_Data/Managed/Assembly-CSharp.dll").write_bytes(b"fixture")
            dll.write_bytes(b"version-one")
            args = ["installer", "--game-dir", str(game), "--dll", str(dll)]
            with patch.object(install_live_bridge, "ROOT", root), patch.object(sys, "argv", args), redirect_stdout(io.StringIO()):
                install_live_bridge.main()
            token = (root / ".live-bridge-token").read_text()
            config = game / "BepInEx/config/dev.silksongtracker.livebridge.cfg"
            settings = config.read_bytes()
            dll.write_bytes(b"version-two")
            with patch.object(install_live_bridge, "ROOT", root), patch.object(sys, "argv", args + ["--upgrade"]), redirect_stdout(io.StringIO()):
                install_live_bridge.main()
            self.assertEqual((game / "BepInEx/plugins/SilksongLiveBridge.dll").read_bytes(), b"version-two")
            self.assertEqual(config.read_bytes(), settings)
            self.assertEqual((root / ".live-bridge-token").read_text(), token)


if __name__ == "__main__":
    unittest.main()
