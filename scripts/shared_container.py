"""Prepare the mounted disk, then run the hosted application as an unprivileged user."""
import os
from pathlib import Path
import pwd
import sys


if __name__ == "__main__":
    if os.geteuid() == 0:
        user = pwd.getpwnam("app")
        # A platform-mounted disk can replace the image's /data ownership.
        # Only initialize these two directories; never recursively rewrite data.
        for path in (Path("/data"), Path("/data/library")):
            path.mkdir(exist_ok=True)
            os.chown(path, user.pw_uid, user.pw_gid)
        os.setgroups([])
        os.setgid(user.pw_gid)
        os.setuid(user.pw_uid)
    os.execv(sys.executable, [sys.executable, "-m", "scripts.shared_server"])
