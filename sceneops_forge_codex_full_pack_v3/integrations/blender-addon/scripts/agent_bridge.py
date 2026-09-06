"""Fixed bootstrap; no client-supplied program is ever evaluated."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "sceneops_blender"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from agent_host import serve

serve(Path(sys.argv[sys.argv.index("--") + 1]))
