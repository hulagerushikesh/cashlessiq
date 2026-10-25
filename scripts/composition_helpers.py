"""Inactive, one-role disposable material install/read-back coordinator.

Uses a separate explicit helper journal (same invocation prefix, different
private parent) so helper observations cannot masquerade as application launch
intentions. Trusted bounded engine/headroom and an observed resource journal are
mandatory. No normal entrypoint, removal, retry, discovery or readiness receipt.
The closed state-helper subclass reuses this lifecycle with its own mount and
wire contract; caller input cannot select arbitrary helper code or configuration.
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
        super().__init__("Disposable composition helpers denied; retained outcome requires review")


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

    modes = ("install", "verify")
    kind = "material"
    destination = "/material"
    entrypoint = ENTRYPOINT
    probe_user = "10001:10001"

    def __init__(self, plan, staged, *, image, journal, resources, engine, headroom):
        require(type(plan) is Inventory and type(staged) is Staged)
        require(staged.expected.fingerprint == plan.fingerprint(staged.expected.role))
        self.staged = staged
        self._initialize(
            plan,
            staged.expected.role,
            image=image,
            journal=journal,
            resources=resources,
            engine=engine,
            headroom=headroom,
        )

    def _initialize(self, plan, role, *, image, journal, resources, engine, headroom):
        require(type(image) is str and image.startswith("sha256:") and _hex(image[7:]))
        require(journal is not resources and callable(engine) and callable(headroom))
        require(
            callable(getattr(engine, "execute", None))
            and callable(getattr(engine, "permit_incarnation", None))
        )
        self.plan, self.image, self.role = plan, image, role
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

    def volume_name(self):
        return self.plan.volume(self.role, self.kind)

    def material_fingerprint(self):
        return self.plan.fingerprint(self.role)

    def check_volume(self, row):
        self.plan.check_volume(self.role, self.kind, row)

    def name(self, mode):
        require(mode in self.modes)
        return f"{self.plan.prefix}-{self.kind}-{self.role}-{mode}"

    def fingerprint(self, mode):
        return sha256(
            canonical(
                dict(
                    name=self.name(mode),
                    image=self.image,
                    volume=self.volume_name(),
                    fingerprint=self.material_fingerprint(),
                    mode=mode,
                )
            )
        ).hexdigest()

    def user(self, mode):
        return "0:0" if mode == self.modes[0] else self.probe_user

    def capabilities(self, mode):
        return ["CHOWN"] if mode == self.modes[0] else []

    def mounts(self, mode):
        return [(self.volume_name(), self.destination, self.writable(mode))]

    def create(self, mode):
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
            self.user(mode),
            "--cap-drop",
            "ALL",
        ]
        for capability in self.capabilities(mode):
            args += ["--cap-add", capability]
        mount_args = []
        for name, destination, writable in self.mounts(mode):
            mount_args += [
                "--mount",
                f"type=volume,src={name},dst={destination}" + ("" if writable else ",readonly"),
            ]
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
                *mount_args,
                self.image,
                mode,
            ]
        )

    def commands(self):
        return (
            ("image", "inspect", self.image),
            ("volume", "inspect", self.volume_name()),
            ("container", "ls", "--all", "--format", "{{.Names}}"),
            *(self.create(mode) for mode in self.modes),
            ("inspect", "{incarnation}"),
            ("start", "--attach", "--interactive", "{incarnation}"),
            ("stop", "--time", "1", "{incarnation}"),
        )

    def writable(self, mode):
        return mode == self.modes[0]

    def body(self, mode):
        return request(self.staged, install=mode == self.modes[0])

    def receipt(self, mode):
        return dict(
            state="INSTALLED" if mode == self.modes[0] else "VERIFIED",
            role=self.role,
            fingerprint=self.material_fingerprint(),
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
        volume = self.volume_name()
        require(prefix == self.plan.prefix and not fenced)
        require(rows.get(("volume", volume), (None, None, None))[1:] == (volume, "PRESENT"))

    def _check(self, row, mode, *, exited=False, configuration_only=False):
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
        require(config["User"] == self.user(mode))
        require(config["Entrypoint"] == self.entrypoint and config["Cmd"] == [mode])
        require(config.get("Env") == self.config.get("Env"))
        require(config["OpenStdin"] is True and not config.get("Tty"))
        require(not config.get("ExposedPorts") and not config.get("Healthcheck"))
        require(host["ReadonlyRootfs"] is True and host["Privileged"] is False)
        require(not host.get("AutoRemove"))
        require(host["CapDrop"] == ["ALL"])
        observed_caps = host.get("CapAdd") or []
        expected_caps = self.capabilities(mode)
        # Docker engines may canonicalize --cap-add CHOWN to CAP_CHOWN.
        # Accept only that exact singleton alias, never extra/duplicate caps.
        require(
            observed_caps in (["CHOWN"], ["CAP_CHOWN"])
            if expected_caps == ["CHOWN"]
            else observed_caps == expected_caps
        )
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
        expected_mounts = self.mounts(mode)
        require(len(mounts) == len(expected_mounts))
        require(len({mount["Destination"] for mount in mounts}) == len(mounts))
        for name, destination, writable in expected_mounts:
            matches = [m for m in mounts if m["Destination"] == destination]
            require(len(matches) == 1)
            mount = matches[0]
            require(mount["Type"] == "volume" and mount["Name"] == name)
            require(mount["RW"] is writable)
        networks = row["NetworkSettings"]["Networks"]
        require(type(networks) is dict and set(networks) <= {"none"})
        require(
            all(
                not n.get("IPAddress") and not n.get("GlobalIPv6Address") for n in networks.values()
            )
        )
        if configuration_only:
            return
        require(state["Running"] is False and type(state["Pid"]) is int and state["Pid"] == 0)
        require(
            not any(state.get(k) for k in ("Paused", "Restarting", "Dead", "OOMKilled", "Error"))
        )
        require(row.get("RestartCount", 0) == 0)
        require(state["Status"] == ("exited" if exited else "created"))
        if exited:
            require(type(state["ExitCode"]) is int and state["ExitCode"] == 0)

    def contain(self):
        """Fence and inspect/stop exact acknowledged CIDs; never certify readiness.

        Uses the engine's existing bounded inspection/stop slots even after a
        failed run. Unknown create acknowledgements are not recovered by name.
        Every reserved intention must have fresh stopped proof and a durable
        journal observation for True. No retry, removal or readiness follows.
        """
        require(self.used)
        self.engine.fenced = True
        durable = True
        try:
            self.journal.check()
            if not fold(self.journal.events)[2]:
                self.journal.fence()
        except Exception:
            durable = False
        complete = True
        for mode in self.modes:
            cid = self.owned.get(mode)
            if cid is None:
                complete = False
                continue
            try:
                row = self._read("inspect", cid)
                self._check(row, mode, configuration_only=True)
                state = row["State"]
                require(
                    all(
                        type(state.get(k, False)) is bool
                        for k in ("Running", "Paused", "Restarting", "Dead")
                    )
                )
                require(type(state["Pid"]) is int and state["Pid"] >= 0)
                require(not state.get("Dead") and row.get("RestartCount", 0) == 0)
                if any(state.get(k) for k in ("Running", "Paused", "Restarting")):
                    # A lost stop acknowledgement is not proof either way.
                    with suppress(Exception):
                        self.engine("stop", "--time", "1", cid)
                row = self._read("inspect", cid)
                self._check(row, mode, configuration_only=True)
                state = row["State"]
                require(
                    state["Running"] is False and type(state["Pid"]) is int and state["Pid"] == 0
                )
                require(state["Status"] in {"created", "exited"})
                require(not any(state.get(k) for k in ("Paused", "Restarting", "Dead", "Error")))
                require(row.get("RestartCount", 0) == 0)
                self.journal.check()
                _, rows, _ = fold(self.journal.events)
                previous = rows[("container", self.name(mode))]
                require(previous[0] == self.fingerprint(mode))
                if previous[2] == "UNKNOWN":
                    self._record("observe", mode, cid)
                else:
                    require(previous[1] == cid and previous[2] in {"PRESENT", "STOPPED"})
                if previous[2] != "STOPPED":
                    self._record("stopped", mode, cid)
            except Exception:
                complete = False
        try:
            self.journal.check()
        except Exception:
            durable = False
        return complete and durable

    def run(self):
        require(not self.used)
        self.used = True
        try:
            self.journal.check()
            self._volume_intention()
            require(self.headroom() is True)
            for mode in self.modes:
                self._record("reserve", mode)
            image = self._read("image", "inspect", self.image)
            require(image["Id"] == self.image)
            self.config = image["Config"]
            require(
                self.config["Entrypoint"] == self.entrypoint
                and self.config.get("Cmd") in (None, [])
            )
            require(self.config["User"] == self.probe_user)
            require(
                not any(
                    self.config.get(k) for k in ("Volumes", "ExposedPorts", "Healthcheck", "Labels")
                )
            )
            self.check_volume(
                self._read("volume", "inspect", self.volume_name()),
            )
            existing = self.engine("container", "ls", "--all", "--format", "{{.Names}}")
            require(not {self.name(m) for m in self.modes}.intersection(existing.splitlines()))
            for mode in self.modes:
                self.journal.check()
                self._volume_intention()
                require(self.headroom() is True)
                self.check_volume(
                    self._read("volume", "inspect", self.volume_name()),
                )
                body = self.body(mode)
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
                require(result == self.receipt(mode))
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
