"""
disk.py — Analyse récursive de l'espace occupé par dossier sur un point de montage.
"""
import os


def scan_directory(path: str, max_depth: int = 3) -> list:
    """Parcourt un répertoire jusqu'à max_depth et retourne les tailles par dossier.

    Retourne une liste triée par taille décroissante, avec les champs :
      path, name, size_mb, depth
    """
    result = []
    try:
        for root, dirs, files in os.walk(path):
            depth = root[len(path):].count(os.sep)
            if depth >= max_depth:
                dirs.clear()  # Ne pas descendre plus profond
                continue

            total_size = 0
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except (OSError, PermissionError):
                    continue

            size_mb = total_size / (1024 * 1024)
            if size_mb > 0:
                result.append({
                    "path":    root,
                    "name":    os.path.basename(root),
                    "size_mb": round(size_mb, 2),
                    "depth":   depth,
                })
    except PermissionError:
        pass

    return sorted(result, key=lambda x: x["size_mb"], reverse=True)
