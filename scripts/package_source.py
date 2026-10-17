"""Package reviewed source folders only, never Git history or local run material."""
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    names = {'.gitignore', 'README.md', 'requirements.txt', 'requirements-stage2.txt'}
    allowed = {'.py', '.md', '.txt', '.json', '.csv'}
    for folder in ('tracelab', 'tests', 'docs', 'prompts', 'templates', 'examples', 'scripts'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and path.suffix in allowed and '__pycache__' not in path.parts:
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError('source path must remain inside repository')
                names.add(path.relative_to(root).as_posix())
    # Exclusive creation preserves every previous delivery artifact.
    from datetime import datetime, timezone
    import uuid
    out = root / 'outputs' / 'delivery-check' / ('source-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    manifest = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(names)}
    archive = out / 'AlphaTrace-source.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(names):
            bundle.write(root / name, name)
        bundle.writestr('SOURCE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    (out / 'sha256.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  AlphaTrace-source.zip\n', encoding='utf-8')
    print(json.dumps(dict(archive=str(archive), source_files=len(names)), ensure_ascii=False))


if __name__ == '__main__':
    main()
