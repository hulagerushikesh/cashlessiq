"""Bounded private operator files; no creation, symlinks, repair or fallback."""

import json
import os
import stat


def require(value):
    if not value:
        raise ValueError("private_file_unavailable")


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def directory(parent, name, uid):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                 dir_fd=parent)
    try:
        item = os.fstat(fd)
        require(item.st_uid in (0, uid) and not item.st_mode & 0o022)
    except BaseException:
        os.close(fd)
        raise
    return fd


def read_private(path, maximum):
    # Callers supply fixed source constants, never browser/IPC/argument paths.
    require(path.is_absolute() and ".." not in path.parts)
    uid = os.getuid()
    parent = directory(None, "/", uid)
    try:
        for name in path.parent.parts[1:]:
            child = directory(parent, name, uid)
            os.close(parent)
            parent = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=parent)
        try:
            item = os.fstat(fd)
            require(stat.S_ISREG(item.st_mode) and item.st_uid == uid and item.st_nlink == 1
                    and stat.S_IMODE(item.st_mode) == 0o600 and 0 < item.st_size <= maximum)
            raw = os.read(fd, maximum + 1)
            require(0 < len(raw) <= maximum)
            return raw
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def private_object(path, maximum):
    value = json.loads(read_private(path, maximum), object_pairs_hook=unique)
    require(type(value) is dict)
    return value
