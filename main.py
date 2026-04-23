from pathlib import Path

from adapters import PyMuPdfBackend
from core import ExportService, ThumbnailService, WorkspaceManager


def build_workspace(project_root: Path) -> WorkspaceManager:
    backend = PyMuPdfBackend()
    thumbnail_dir = project_root / "thumbnails"
    return WorkspaceManager(backend=backend, thumbnail_dir=thumbnail_dir)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    workspace = build_workspace(root)
    thumb_service = ThumbnailService(workspace)
    export_service = ExportService(workspace)
    print("Project scaffold ready.")
    print(f"Workspace root: {root}")
    print(f"Thumbnail dir: {root / 'thumbnails'}")
