"""Inactive offline v3 observation primitive, NOT application authorization.

Injected samples and immutable signed evidence only. No collector/network calls,
nonce consumption, startup adapter or recovery. Elapsed checks are not a hard
deadline: callbacks, signature verification and commit may stall.
"""

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import model_validator

from ciq_api.worker_guard_state import (
    GuardStateConfig,
    GuardStateDenied,
    GuardStateSnapshot,
    OfflineGuardState,
)
from ciq_api.worker_health import (
    MAX_INTEGER,
    HealthNow,
    Integer,
    StrictModel,
    _check_measurement,
    check_envelope,
)


class ObservedInterval(StrictModel):
    """Inclusive uncertainty bounds for one observation, never cached readiness."""

    lower_ns: Integer
    upper_ns: Integer

    @model_validator(mode="after")
    def ordered(self):
        if self.lower_ns > self.upper_ns:
            raise ValueError("Invalid interval")
        return self

    @classmethod
    def from_wall_error(cls, wall_ns: int, error_ns: int) -> "ObservedInterval":
        """Exact inclusive bounds; never clamp, round or widen claim validity."""
        if (
            type(wall_ns) is not int
            or type(error_ns) is not int
            or not 0 <= error_ns <= wall_ns <= MAX_INTEGER
            or wall_ns > MAX_INTEGER - error_ns
        ):
            raise ValueError("Invalid interval arithmetic")
        return cls(lower_ns=wall_ns - error_ns, upper_ns=wall_ns + error_ns)


class OfflineHealthGuard(OfflineGuardState):
    """Signed health and time continuity in the same v3 transaction.

    Key fingerprint is SHA256 of DER SubjectPublicKeyInfo, never a PEM string or
    private key. Configuration errors fail before opening or rewriting state.
    """

    def __init__(
        self,
        path: Path,
        *,
        config: GuardStateConfig,
        public_key: RSAPublicKey,
        sample: Callable[[], HealthNow],
    ):
        super().__init__(path, config=config)
        if (
            not isinstance(public_key, RSAPublicKey)
            or not callable(sample)
            or sha256(
                public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
            ).hexdigest()
            != self._config.health_key_sha256
        ):
            raise ValueError("Invalid guard health configuration")
        self._key, self._sample = public_key, sample

    def _now(self) -> HealthNow:
        raw = self._sample()
        if not isinstance(raw, HealthNow):
            raise ValueError("Invalid sample")
        now = HealthNow.model_validate(raw.model_dump())
        if now.boot_id != self._config.binding.boot_id or now.boottime_ns < now.monotonic_ns:
            raise ValueError("Invalid clock domain")
        return now

    def _elapsed(self, before: HealthNow, after: HealthNow, limit: int) -> None:
        deltas = (
            after.wall_ns - before.wall_ns,
            after.monotonic_ns - before.monotonic_ns,
            after.boottime_ns - before.boottime_ns,
        )
        if (
            min(deltas) < 0
            or max(deltas) > limit
            or max(deltas) - min(deltas) > self._config.health_policy.max_read_skew_ns
        ):
            raise ValueError("Uncertain elapsed time")

    def _since_state(self, state: GuardStateSnapshot, now: HealthNow) -> None:
        self._elapsed(
            HealthNow(
                boot_id=self._config.binding.boot_id,
                wall_ns=state.wall,
                monotonic_ns=state.mono,
                boottime_ns=state.boottime,
            ),
            now,
            self._config.max_gap_ns,
        )

    def observe(self, evidence: Callable[[], str]) -> ObservedInterval:
        """Persist valid high-water marks or only unsafe; never touch nonces.

        Evidence callback must deliver a previously collected immutable bounded
        envelope, not collect or perform network/source/membership work here.
        No result is returned until commit acknowledgement. Failed storage denies
        without promising a durable latch or retrying an ambiguous commit.
        """
        with self._transaction() as (db, state, _nonces):
            try:
                before = self._now()
                self._since_state(state, before)
                delivered = evidence()
                after = self._now()
                self._elapsed(before, after, self._config.max_step_ns)
                self._since_state(state, after)
                checked = check_envelope(
                    delivered,
                    public_key=self._key,
                    binding=self._config.binding,
                    now=after,
                    policy=self._config.health_policy,
                )
                claim = checked.evidence
                ends = (
                    claim.window.end_wall_ns,
                    claim.window.end_monotonic_ns,
                    claim.window.end_boottime_ns,
                    claim.reference_wall_ns,
                )
                if (
                    claim.sequence < state.sequence
                    or (claim.sequence == state.sequence and checked.content_sha256 != state.digest)
                    or any(
                        new < old
                        for new, old in zip(
                            ends,
                            (state.end_wall, state.end_mono, state.end_boot, state.reference),
                            strict=True,
                        )
                    )
                ):
                    raise ValueError("Invalid evidence continuity")
                final = self._now()  # AFTER cryptographic and retained-continuity work.
                self._elapsed(after, final, self._config.max_step_ns)
                self._elapsed(before, final, self._config.max_step_ns)
                self._since_state(state, final)
                # Recheck the SAME immutable verified claim, without another
                # signature callback whose elapsed time would escape sampling.
                _age, error = _check_measurement(
                    claim,
                    binding=self._config.binding,
                    now=final,
                    policy=self._config.health_policy,
                )
                interval = ObservedInterval.from_wall_error(final.wall_ns, error)
            except Exception:
                db.execute("UPDATE guard_state SET unsafe=1 WHERE singleton=1")
                db.commit()
                raise GuardStateDenied("Guard state denied") from None
            db.execute(
                "UPDATE guard_state SET sequence=?,digest=?,wall=?,mono=?,boottime=?,"
                "end_wall=?,end_mono=?,end_boot=?,reference=? WHERE singleton=1",
                (
                    claim.sequence,
                    checked.content_sha256,
                    final.wall_ns,
                    final.monotonic_ns,
                    final.boottime_ns,
                    *ends,
                ),
            )
            db.commit()
            return interval
