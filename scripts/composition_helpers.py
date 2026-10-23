"""Inactive, one-role disposable material install/read-back coordinator.

Uses a separate explicit helper journal (same invocation prefix, different
private parent) so helper observations cannot masquerade as application launch
intentions. Trusted bounded engine/headroom and an observed resource journal are
mandatory. No normal entrypoint, removal, retry, discovery or readiness receipt.
"""

import json
from contextlib import suppress
from hashlib import sha256

from .composition_inventory import LABEL, Inventory, _hex, canonical
from .composition_journal import fold
from .composition_material import Staged
from .composition_volume import request

ENTRYPOINT = ["python", "-m", "scripts.composition_volume"]


class HelpersDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable material helpers denied; retained outcome requires review")


def require(value):
    if not value:
        raise HelpersDenied()


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value)
        value[key] = item
    return value


class Helpers:
    """One attempt, two separately inspected containers; no installer-only success.

    A new bounded Engine per role keeps registrations separate from the eight
    application CIDs. A fresh helper journal is required, not the resource writer.
    Exact helper metadata and exit checks are necessary, not physical acceptance
    or exclusion of a privileged/same-UID daemon/host observer.
    """

    def __init__(self, plan, staged, *, image, journal, resources, engine, headroom):
        require(type(plan) is Inventory and type(staged) is Staged)
        require(type(image) is str and image.startswith("sha256:") and _hex(image[7:]))
        require(staged.expected.fingerprint == plan.fingerprint(staged.expected.role))
        require(journal is not resources and callable(engine) and callable(headroom))
        require(
            callable(getattr(engine, "execute", None))
            and callable(getattr(engine, "permit_incarnation", None))
        )
        self.plan, self.staged, self.image = plan, staged, image
        self.role = staged.expected.role
        self.journal, self.resources, self.engine, self.headroom = (
            journal,
            resources,
            engine,
            headroom,
        )
        self.used, self.owned = False, {}
        self.config = None
        journal.check()
        require(journal.events == [{"version": 1, "prefix": plan.prefix}])
        self._volume_intention()

    def name(self, mode):
        require(mode in {"install", "verify"})
        return f"{self.plan.prefix}-material-{self.role}-{mode}"

    def fingerprint(self, mode):
        return sha256(
            canonical(
                dict(
                    name=self.name(mode),
                    image=self.image,
                    volume=self.plan.volume(self.role, "material"),
                    fingerprint=self.plan.fingerprint(self.role),
                    mode=mode,
                )
            )
        ).hexdigest()

    def create(self, mode):
        installing = mode == "install"
        args = [
            "create",
            "--name",
            self.name(mode),
            "--label",
            f"{LABEL}={self.plan.prefix}",
            "--label",
            f"{LABEL}.helper={mode}",
            "--label",
            f"{LABEL}.role={self.role}",
            "--label",
            f"{LABEL}.fingerprint={self.fingerprint(mode)}",
            "--network",
            "none",
            "--read-only",
            "--interactive",
            "--user",
            "0:0" if installing else "10001:10001",
            "--cap-drop",
            "ALL",
        ]
        if installing:
            args += ["--cap-add", "CHOWN"]
        return tuple(
            [
                *args,
                "--security-opt",
                "no-new-privileges",
                "--memory",
                str(128 * 1024**2),
                "--cpus",
                "0.5",
                "--pids-limit",
                "32",
                "--restart",
                "no",
                "--ipc",
                "private",
                "--mount",
                f"type=volume,src={self.plan.volume(self.role, 'material')},dst=/material"
                + ("" if installing else ",readonly"),
                self.image,
                mode,
            ]
        )

    def commands(self):
        return (
            ("image", "inspect", self.image),
            ("volume", "inspect", self.plan.volume(self.role, "material")),
            ("container", "ls", "--all", "--format", "{{.Names}}"),
            *(self.create(mode) for mode in ("install", "verify")),
            ("inspect", "{incarnation}"),
            ("start", "--attach", "--interactive", "{incarnation}"),
            ("stop", "--time", "1", "{incarnation}"),
        )

    def _read(self, *args):
        rows = json.loads(self.engine(*args), object_pairs_hook=unique)
        require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict)
        return rows[0]

    def _record(self, action, mode, cid=None):
        self.journal.record(
            action,
            kind="container",
            name=self.name(mode),
            identity=cid,
            fingerprint=self.fingerprint(mode),
        )

    def _volume_intention(self):
        self.resources.check()
        prefix, rows, fenced = fold(self.resources.events)
        volume = self.plan.volume(self.role, "material")
        require(prefix == self.plan.prefix and not fenced)
        require(rows.get(("volume", volume), (None, None, None))[1:] == (volume, "PRESENT"))

    def _check(self, row, mode, *, exited=False):
        require(row["Id"] == self.owned[mode] and row["Name"] == "/" + self.name(mode))
        require(row["Image"] == self.image)
        config, host, state = row["Config"], row["HostConfig"], row["State"]
        require(
            config["Labels"]
            == {
                LABEL: self.plan.prefix,
                f"{LABEL}.helper": mode,
                f"{LABEL}.role": self.role,
                f"{LABEL}.fingerprint": self.fingerprint(mode),
            }
        )
        require(config["User"] == ("0:0" if mode == "install" else "10001:10001"))
        require(config["Entrypoint"] == ENTRYPOINT and config["Cmd"] == [mode])
        require(config.get("Env") == self.config.get("Env"))
        require(config["OpenStdin"] is True and not config.get("Tty"))
        require(not config.get("ExposedPorts") and not config.get("Healthcheck"))
        require(host["ReadonlyRootfs"] is True and host["Privileged"] is False)
        require(not host.get("AutoRemove"))
        require(host["CapDrop"] == ["ALL"])
        require((host.get("CapAdd") or []) == (["CHOWN"] if mode == "install" else []))
        require(host["SecurityOpt"] == ["no-new-privileges"])
        require(host["Memory"] == 128 * 1024**2 and host["NanoCpus"] == 500_000_000)
        require(host["PidsLimit"] == 32 and host["NetworkMode"] == "none")
        require(host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0})
        require(host.get("PidMode", "") == "" and host["IpcMode"] == "private")
        require(
            not any(
                host.get(k)
                for k in (
                    "Binds",
                    "VolumesFrom",
                    "Links",
                    "ExtraHosts",
                    "PortBindings",
                    "PublishAllPorts",
                    "Devices",
                    "DeviceRequests",
                    "DeviceCgroupRules",
                    "Sysctls",
                    "GroupAdd",
                    "Tmpfs",
                )
            )
        )
        mounts = row["Mounts"]
        require(len(mounts) == 1)
        mount = mounts[0]
        require(
            mount["Type"] == "volume" and mount["Name"] == self.plan.volume(self.role, "material")
        )
        require(mount["Destination"] == "/material" and mount["RW"] is (mode == "install"))
        networks = row["NetworkSettings"]["Networks"]
        require(type(networks) is dict and set(networks) <= {"none"})
        require(
            all(
                not n.get("IPAddress") and not n.get("GlobalIPv6Address") for n in networks.values()
            )
        )
        require(state["Running"] is False and type(state["Pid"]) is int and state["Pid"] == 0)
        require(
            not any(state.get(k) for k in ("Paused", "Restarting", "Dead", "OOMKilled", "Error"))
        )
        require(row.get("RestartCount", 0) == 0)
        require(state["Status"] == ("exited" if exited else "created"))
        if exited:
            require(type(state["ExitCode"]) is int and state["ExitCode"] == 0)

    def run(self):
        require(not self.used)
        self.used = True
        try:
            self.journal.check()
            self._volume_intention()
            require(self.headroom() is True)
            for mode in ("install", "verify"):
                self._record("reserve", mode)
            image = self._read("image", "inspect", self.image)
            require(image["Id"] == self.image)
            self.config = image["Config"]
            require(
                self.config["Entrypoint"] == ENTRYPOINT and self.config.get("Cmd") in (None, [])
            )
            require(self.config["User"] == "10001:10001")
            require(
                not any(
                    self.config.get(k) for k in ("Volumes", "ExposedPorts", "Healthcheck", "Labels")
                )
            )
            self.plan.check_volume(
                self.role,
                "material",
                self._read("volume", "inspect", self.plan.volume(self.role, "material")),
            )
            existing = self.engine("container", "ls", "--all", "--format", "{{.Names}}")
            require(
                not {self.name(m) for m in ("install", "verify")}.intersection(
                    existing.splitlines()
                )
            )
            for mode in ("install", "verify"):
                self.journal.check()
                self._volume_intention()
                require(self.headroom() is True)
                self.plan.check_volume(
                    self.role,
                    "material",
                    self._read("volume", "inspect", self.plan.volume(self.role, "material")),
                )
                body = request(self.staged, install=mode == "install")
                cid = self.engine(*self.create(mode)).strip()
                require(_hex(cid) and cid not in self.owned.values())
                self.owned[mode] = cid
                self.engine.permit_incarnation(cid)
                self._check(self._read("inspect", cid), mode)
                self._record("observe", mode, cid)
                output = self.engine.execute(
                    "start", "--attach", "--interactive", cid, private_input=body
                )
                del body
                result = json.loads(output, object_pairs_hook=unique)
                require(
                    result
                    == dict(
                        state="INSTALLED" if mode == "install" else "VERIFIED",
                        role=self.role,
                        fingerprint=self.plan.fingerprint(self.role),
                    )
                )
                self._check(self._read("inspect", cid), mode, exited=True)
                self._record("stopped", mode, cid)
            self.journal.check()
            return True
        except Exception:
            # No automatic stop/removal/adoption on ambiguous outcomes. The
            # bounded engine has already contained its CLI, not necessarily the
            # daemon helper. Retain all intentions and require owner inspection.
            self.engine.fenced = True
            with suppress(Exception):
                self.journal.fence()
            raise HelpersDenied() from None
