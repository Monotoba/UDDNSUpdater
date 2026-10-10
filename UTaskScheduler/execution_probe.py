"""Harmless, offline execution evidence for manual native scheduler checks."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
from uuid import uuid4


def write_probe(output_directory, arguments):
    """Write one exclusive JSON record in an existing, trusted directory."""
    directory = Path(output_directory)
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink():
        raise ValueError('Use an existing absolute output directory without a symlink.')
    record = {
        'schema_version': 1,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'pid': os.getpid(),
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'executable': sys.executable,
        'working_directory': str(Path.cwd()),
        'arguments': list(arguments),
    }
    destination = directory / ('uddns-probe-' + uuid4().hex + '.json')
    # Never append to or overwrite another run's evidence.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=True, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER,
                        help='Harmless test arguments after --; recorded verbatim.')
    options = parser.parse_args(argv)
    arguments = options.arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    try:
        write_probe(options.output_directory, arguments)
    except (OSError, ValueError):
        print('Scheduler probe could not write execution evidence.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
