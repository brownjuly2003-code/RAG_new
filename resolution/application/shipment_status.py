from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import NAMESPACE_URL, UUID, uuid5

from resolution.contracts import ResolutionContract, TerminalOutcome, contract_digest

# Two shipment reference forms, because the repository has always had two.
# `SHP-` is what the kernel's own scenarios use. `AC-<digits>` is what the
# fixture TMS that ships with this package actually holds
# (`resolution/adapters/fixtures/shipment-status-v0.1.json`) and what every
# wiring and end-to-end test asks about.
#
# Until 2026-08-25 only `SHP-` was recognised, so no question about a shipment
# the fixture contains could reach an observation: the journey answered
# CLARIFICATION_REQUIRED / SHIPMENT_ID_REQUIRED every time, and the evidence
# bundle behind `/api/ask` never carried a source, a policy or a single claim.
# The shadow ran; there was simply nothing in it to look at, which phase A.3
# found by trying to render it.
#
# The `AC-` form requires digits so ordinary prose ("AC-DC") is not read as a
# shipment reference. A false positive would cost an escalation inside the
# shadow and nothing else, but there is no reason to invite one.
_SHIPMENT_ID_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:SHP-[A-Z0-9]{1,32}|AC-[0-9]{1,32})(?![A-Z0-9])",
    re.IGNORECASE,
)
# An incomplete `SHP-` or `AC-` prefix is a truncated shipment reference, not
# an intent phrase. The negative lookahead makes this distinct from a valid ID
# matched by `_SHIPMENT_ID_PATTERN` above.
_TRUNCATED_SHIPMENT_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:SHP-|AC-)(?![A-Z0-9])",
    re.IGNORECASE,
)
# English tokens stay the T-01 class `[a-z0-9]+`. Russian tokens are a
# separate `[а-яё]+` pass over the same text, so a mixed-script run like
# `cargoгде` still yields English `cargo` rather than one glued token.
# Hyphens still split (`авиа-накладная` → авиа, накладная), as they did for
# English (`cut-off`).
_ENGLISH_ADMISSION_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_RUSSIAN_ADMISSION_TOKEN_PATTERN = re.compile(r"[а-яё]+")

# Lexical admission vocabulary: `shipment` and `status` come from the pinned
# shipment-status contract; `location`, `transit`, `hold`, and `delivered`
# come from its fixture TMS. `cargo`, `air waybill`, and `awb` are the minimal
# air-cargo request nouns. `_matches_lexical_form` recognizes their regular
# plurals; `held` remains explicit because it is irregular.
#
# The Russian half is a translation of this English vocabulary, not a second
# list. Each entry names the English term it translates and is a stem plus a
# finite ending set: a Cyrillic token matches iff it equals stem+ending.
# Shared ending tuples are named by part of speech. A suppletive or
# alternating stem is another (stem, endings) pair on the same entry.
# A Russian term with no English counterpart is not added. English matching
# stays exact-or-regular-plural.
_SHIPMENT_STATUS_ADMISSION_VOCABULARY = {
    "domain_nouns": frozenset(
        {
            "shipment",
            "cargo",
            "air waybill",
            "awb",
        }
    ),
    "status_cues": frozenset(
        {
            "status",
            "where",
            "location",
            "eta",
            "transit",
            "hold",
            "held",
            "holding",
            "delay",
            "delayed",
            "delaying",
            "arrive",
            "arrived",
            "arriving",
            "arrival",
            "deliver",
            "delivered",
            "delivering",
            "delivery",
            "track",
            "tracked",
            "tracking",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class RussianAdmissionTranslation:
    """One Russian citation form, bound to the English term it translates.

    A token matches when it equals `stem + ending` for some ending in this
    entry's finite set. `alts` holds suppletive or alternating stems.
    """

    english: str
    citation: str
    stem: str
    endings: tuple[str, ...]
    alts: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not self.english or self.english != self.english.strip():
            raise ValueError("english must be non-empty without surrounding whitespace")
        if not self.citation or self.citation != self.citation.strip():
            raise ValueError("citation must be non-empty without surrounding whitespace")
        _validate_russian_paradigm(self.stem, self.endings)
        citation_tokens = tuple(self.citation.split())
        stem_tokens = tuple(self.stem.split())
        if len(citation_tokens) != len(stem_tokens):
            raise ValueError("stem must have one token per citation token")
        if citation_tokens[:-1] != stem_tokens[:-1]:
            raise ValueError("non-final stem tokens must equal the citation")
        if not any(
            citation_tokens[-1] == stem_tokens[-1] + ending for ending in self.endings
        ):
            raise ValueError("citation must equal stem plus one ending")
        for alt_stem, alt_endings in self.alts:
            _validate_russian_paradigm(alt_stem, alt_endings)

    @property
    def forms(self) -> frozenset[str]:
        """Finite surfaces generated by stem+endings, including alts."""
        generated: set[str] = set()
        for stem, endings in ((self.stem, self.endings), *self.alts):
            generated.update(_surface_forms(stem, endings))
        return frozenset(generated)


def _validate_russian_paradigm(stem: str, endings: tuple[str, ...]) -> None:
    if not stem or stem != stem.strip():
        raise ValueError("stem must be non-empty without surrounding whitespace")
    if not endings:
        raise ValueError("endings must be a non-empty tuple")
    if any("  " in stem_token for stem_token in stem.split()):
        raise ValueError("stem tokens must use single spaces")
    for ending in endings:
        if ending != ending.casefold() or " " in ending:
            raise ValueError("each ending must be casefolded and a single token")


def _surface_forms(stem: str, endings: tuple[str, ...]) -> frozenset[str]:
    parts = stem.split()
    last = parts[-1]
    prefix = " ".join(parts[:-1])
    head = f"{prefix} " if prefix else ""
    return frozenset(head + last + ending for ending in endings)


# Stem + ending audit. A token matches iff it equals stem+ending, not
# startswith. False friends the ending set deliberately excludes:
#   груз + _MASC_HARD_NOUN_ENDINGS → груз/груза/грузы/грузов.
#     Not грузин, грузчик, груздь, Грузия, грузовик (ин/чик/дь/ия/овик
#     are derivational).
#   холд + same → not холдинг (инг), холдер (ер).
#   прибы + past/tie endings → прибыл/прибыла/прибыли/прибытие.
#     Not прибыль (ль), прибыльный (льный).
#   достав + _PERFECTIVE_I_VERB_ENDINGS → доставить/доставьте/доставивший.
#     Not доставать (ать).
#   транзит + _MASC_HARD_NOUN_ENDINGS → not транзистор (ор is not an
#     inflection; the live word is транзис+тор).
#   отправк + _FEM_KA_NOUN_ENDINGS → not отправитель/отправление
#     (stems отправи/отправл).
#   авиа накладн + _ADJ_ENDINGS → first token is exact "авиа"; not
#     авиакомпания.
#   статус, где, локаци, ета, задержк, задержан, задержива, удержива,
#   удержан, доставля, доставлен, доставк, отслежива, отслед, отслежен,
#   прибыва, прибуд: stems long enough that shared POS endings stay
#     inside the lexeme. Missed inflections are accepted (legacy answer);
#     a false friend is not.
_EXACT_ENDINGS: tuple[str, ...] = ("",)
_MASC_HARD_NOUN_ENDINGS: tuple[str, ...] = (
    "",
    "а",
    "у",
    "ом",
    "е",
    "ы",
    "ов",
    "ам",
    "ами",
    "ах",
    "и",
)
_FEM_KA_NOUN_ENDINGS: tuple[str, ...] = (
    "а",
    "и",
    "у",
    "е",
    "ой",
    "ою",
    "ок",
    "ек",
    "ам",
    "ами",
    "ах",
)
_FEM_IYA_NOUN_ENDINGS: tuple[str, ...] = (
    "я",
    "и",
    "ю",
    "ей",
    "ею",
    "й",
    "ям",
    "ями",
    "ях",
)
_ADJ_ENDINGS: tuple[str, ...] = (
    "ая",
    "ой",
    "ую",
    "ое",
    "ые",
    "ых",
    "ым",
    "ыми",
    "ою",
    "ый",
    "ого",
    "ому",
    "ом",
)
_PAST_TENSE_ENDINGS: tuple[str, ...] = ("л", "ла", "ло", "ли")
_PAST_ACTIVE_ENDINGS: tuple[str, ...] = (
    "вший",
    "вшего",
    "вшему",
    "вшим",
    "вшем",
    "вшая",
    "вшей",
    "вшую",
    "вшее",
    "вшие",
    "вших",
    "вшими",
)
_ARRIVED_ENDINGS: tuple[str, ...] = _PAST_TENSE_ENDINGS + _PAST_ACTIVE_ENDINGS
_TIE_NOUN_ENDINGS: tuple[str, ...] = (
    "тие",
    "тия",
    "тию",
    "тием",
    "тии",
    "тий",
    "тиям",
    "тиями",
    "тиях",
)
_PAST_PASSIVE_ENDINGS: tuple[str, ...] = (
    "",
    "а",
    "о",
    "ы",
    "ный",
    "ного",
    "ному",
    "ным",
    "ном",
    "ная",
    "ной",
    "ную",
    "ное",
    "ные",
    "ных",
    "ными",
)
_PRESENT_U_ENDINGS: tuple[str, ...] = (
    "у",
    "ешь",
    "ет",
    "ем",
    "ете",
    "ут",
    "ь",
    "ьте",
)
_PERFECTIVE_I_VERB_ENDINGS: tuple[str, ...] = (
    "ить",
    "иться",
    "лю",
    "ишь",
    "ит",
    "им",
    "ите",
    "ят",
    "ил",
    "ила",
    "ило",
    "или",
    "ился",
    "илась",
    "илось",
    "ились",
    "ь",
    "ьте",
    "и",
    "ивший",
    "ившего",
    "ившему",
    "ившим",
    "ившем",
    "ившая",
    "ившей",
    "ившую",
    "ившее",
    "ившие",
    "ивших",
    "ившими",
)
_IMPERFECTIVE_VERB_ENDINGS: tuple[str, ...] = (
    "ть",
    "ться",
    "ю",
    "ешь",
    "ет",
    "ем",
    "ете",
    "ют",
    "юсь",
    "ешься",
    "ется",
    "емся",
    "етесь",
    "ются",
    "л",
    "ла",
    "ло",
    "ли",
    "лся",
    "лась",
    "лось",
    "лись",
    "ющий",
    "ющего",
    "ющему",
    "ющим",
    "ющем",
    "ющая",
    "ющей",
    "ющую",
    "ющее",
    "ющие",
    "ющих",
    "ющими",
    "емый",
    "емого",
    "емому",
    "емым",
    "емом",
    "емая",
    "емой",
    "емую",
    "емое",
    "емые",
    "емых",
    "емыми",
    "я",
    "ясь",
    "й",
    "йте",
    "ние",
    "ния",
    "нию",
    "нием",
    "нии",
    "ний",
    "ниям",
    "ниями",
    "ниях",
)
_SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY: dict[
    str, dict[str, RussianAdmissionTranslation]
] = {
    "domain_nouns": {
        "shipment": RussianAdmissionTranslation(
            english="shipment",
            citation="отправка",
            stem="отправк",
            endings=_FEM_KA_NOUN_ENDINGS,
        ),
        "cargo": RussianAdmissionTranslation(
            english="cargo",
            citation="груз",
            stem="груз",
            endings=_MASC_HARD_NOUN_ENDINGS,
        ),
        "air waybill": RussianAdmissionTranslation(
            english="air waybill",
            citation="авианакладная",
            stem="авианакладн",
            endings=_ADJ_ENDINGS,
        ),
        "awb": RussianAdmissionTranslation(
            english="awb",
            citation="авиа накладная",
            stem="авиа накладн",
            endings=_ADJ_ENDINGS,
        ),
    },
    "status_cues": {
        "status": RussianAdmissionTranslation(
            english="status",
            citation="статус",
            stem="статус",
            endings=_MASC_HARD_NOUN_ENDINGS,
        ),
        "where": RussianAdmissionTranslation(
            english="where", citation="где", stem="где", endings=_EXACT_ENDINGS
        ),
        "location": RussianAdmissionTranslation(
            english="location",
            citation="локация",
            stem="локаци",
            endings=_FEM_IYA_NOUN_ENDINGS,
        ),
        "eta": RussianAdmissionTranslation(
            english="eta", citation="ета", stem="ета", endings=_EXACT_ENDINGS
        ),
        "transit": RussianAdmissionTranslation(
            english="transit",
            citation="транзит",
            stem="транзит",
            endings=_MASC_HARD_NOUN_ENDINGS,
        ),
        "hold": RussianAdmissionTranslation(
            english="hold", citation="холд", stem="холд", endings=_MASC_HARD_NOUN_ENDINGS
        ),
        "held": RussianAdmissionTranslation(
            english="held",
            citation="удержан",
            stem="удержан",
            endings=_PAST_PASSIVE_ENDINGS,
        ),
        "holding": RussianAdmissionTranslation(
            english="holding",
            citation="удерживание",
            stem="удержива",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
        ),
        "delay": RussianAdmissionTranslation(
            english="delay",
            citation="задержка",
            stem="задержк",
            endings=_FEM_KA_NOUN_ENDINGS,
        ),
        "delayed": RussianAdmissionTranslation(
            english="delayed",
            citation="задержан",
            stem="задержан",
            endings=_PAST_PASSIVE_ENDINGS,
        ),
        "delaying": RussianAdmissionTranslation(
            english="delaying",
            citation="задерживание",
            stem="задержива",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
        ),
        "arrive": RussianAdmissionTranslation(
            english="arrive",
            citation="прибыть",
            stem="прибы",
            endings=("ть",),
            alts=(("прибуд", _PRESENT_U_ENDINGS),),
        ),
        "arrived": RussianAdmissionTranslation(
            english="arrived",
            citation="прибыл",
            stem="прибы",
            endings=_ARRIVED_ENDINGS,
        ),
        "arriving": RussianAdmissionTranslation(
            english="arriving",
            citation="прибывает",
            stem="прибыва",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
        ),
        "arrival": RussianAdmissionTranslation(
            english="arrival",
            citation="прибытие",
            stem="прибы",
            endings=_TIE_NOUN_ENDINGS,
        ),
        "deliver": RussianAdmissionTranslation(
            english="deliver",
            citation="доставить",
            stem="достав",
            endings=_PERFECTIVE_I_VERB_ENDINGS,
        ),
        "delivered": RussianAdmissionTranslation(
            english="delivered",
            citation="доставлен",
            stem="доставлен",
            endings=_PAST_PASSIVE_ENDINGS,
        ),
        "delivering": RussianAdmissionTranslation(
            english="delivering",
            citation="доставляет",
            stem="доставля",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
        ),
        "delivery": RussianAdmissionTranslation(
            english="delivery",
            citation="доставка",
            stem="доставк",
            endings=_FEM_KA_NOUN_ENDINGS,
        ),
        "track": RussianAdmissionTranslation(
            english="track",
            citation="отслеживать",
            stem="отслежива",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
            alts=(("отслед", _PERFECTIVE_I_VERB_ENDINGS),),
        ),
        "tracked": RussianAdmissionTranslation(
            english="tracked",
            citation="отслежен",
            stem="отслежен",
            endings=_PAST_PASSIVE_ENDINGS,
        ),
        "tracking": RussianAdmissionTranslation(
            english="tracking",
            citation="отслеживание",
            stem="отслежива",
            endings=_IMPERFECTIVE_VERB_ENDINGS,
        ),
    },
}
_SHIPMENT_CONTRACT_ID = "aircargo.shipment-status"
_SHIPMENT_CONTRACT_VERSION = "0.1.0"
_SHIPMENT_CONTRACT_DIGEST = "5d4d069f317df0c18f9e132b6fdbf9649bd6136808b2dc14507a0f2b10c99e38"
_POLICY_IMPLEMENTATION_VERSION = "typed-shipment-policy/v0.1"


class ShipmentObservationLike(Protocol):
    # Read-only members. The concrete adapters return frozen dataclasses, and
    # a Protocol declaring plain attributes demands settable ones -- so the
    # real FixtureShipmentSource did not satisfy ShipmentSourcePort. Nothing
    # caught it until phase A wired the loop up from typed production code:
    # the tests construct it too, but tests are outside the mypy scope.
    @property
    def tenant_id(self) -> str: ...

    @property
    def shipment_id(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def location(self) -> str: ...

    @property
    def estimated_delivery(self) -> str: ...

    @property
    def observed_at(self) -> datetime: ...

    @property
    def source_id(self) -> str: ...

    @property
    def source_version(self) -> str: ...

    @property
    def content_digest(self) -> str: ...


class PolicyEvidenceLike(Protocol):
    # Read-only members, same reason as ShipmentObservationLike above.
    @property
    def tenant_id(self) -> str: ...

    @property
    def authority(self) -> str: ...

    @property
    def data_revision(self) -> str: ...

    @property
    def recorded_at(self) -> datetime: ...

    @property
    def valid_from(self) -> datetime: ...

    @property
    def valid_to(self) -> datetime | None: ...

    @property
    def status_disclosure_allowed(self) -> bool: ...

    @property
    def content_digest(self) -> str: ...


class ShipmentSourcePort(Protocol):
    def lookup(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        timeout_seconds: int,
    ) -> ShipmentObservationLike | None: ...


class ShipmentPolicyPort(Protocol):
    def gather(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        effective_at: datetime,
    ) -> tuple[PolicyEvidenceLike, ...]: ...


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _matches_lexical_form(token: str, form: str) -> bool:
    if token == form:
        return True
    if token.endswith("ies") and token[:-3] + "y" == form:
        return True
    if token.endswith("es") and token[:-2] == form:
        return True
    return token.endswith("s") and token[:-1] == form


def _contains_admission_noun(tokens: tuple[str, ...], noun: str) -> bool:
    noun_tokens = tuple(noun.split())
    width = len(noun_tokens)
    return any(
        all(
            _matches_lexical_form(token, noun_token)
            for token, noun_token in zip(tokens[index : index + width], noun_tokens, strict=True)
        )
        for index in range(len(tokens) - width + 1)
    )


def _window_matches_stem_plus_endings(
    tokens: tuple[str, ...],
    stem: str,
    endings: tuple[str, ...],
) -> bool:
    stem_tokens = tuple(stem.split())
    width = len(stem_tokens)
    if width == 0 or width > len(tokens):
        return False
    lead = stem_tokens[:-1]
    last_stem = stem_tokens[-1]
    return any(
        tokens[index : index + width - 1] == lead
        and any(tokens[index + width - 1] == last_stem + ending for ending in endings)
        for index in range(len(tokens) - width + 1)
    )


def _russian_term_matches(tokens: tuple[str, ...], term: RussianAdmissionTranslation) -> bool:
    return any(
        _window_matches_stem_plus_endings(tokens, stem, endings)
        for stem, endings in ((term.stem, term.endings), *term.alts)
    )


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    claim_id: str
    text: str
    evidence_requirement_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim_id or self.claim_id != self.claim_id.strip():
            raise ValueError("claim_id must be non-empty without surrounding whitespace")
        if not self.text or self.text != self.text.strip():
            raise ValueError("claim text must be non-empty without surrounding whitespace")
        if len(set(self.evidence_requirement_ids)) != len(self.evidence_requirement_ids):
            raise ValueError("claim evidence requirements must be unique")


@dataclass(frozen=True, slots=True)
class ShipmentShadowRequest:
    tenant_id: str
    case_id: UUID
    correlation_id: UUID
    messages: tuple[str, ...]
    effective_at: datetime
    observed_at: datetime
    candidate_claims: tuple[ClaimCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id or self.tenant_id != self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty without surrounding whitespace")
        if self.case_id.int == 0 or self.correlation_id.int == 0:
            raise ValueError("case_id and correlation_id cannot be nil UUIDs")
        if any(not isinstance(message, str) for message in self.messages):
            raise TypeError("messages must contain strings")
        _require_aware(self.effective_at, "effective_at")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class ContractIdentity:
    schema_identity: str
    contract_id: str
    version: str
    digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schema_identity": self.schema_identity,
            "contract_id": self.contract_id,
            "version": self.version,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class SourceObservationExport:
    shipment_id: str
    status: str
    location: str
    estimated_delivery: str
    observed_at: datetime
    source_id: str
    source_version: str
    content_digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "shipment_id": self.shipment_id,
            "status": self.status,
            "location": self.location,
            "estimated_delivery": self.estimated_delivery,
            "observed_at": self.observed_at.isoformat(),
            "source_id": self.source_id,
            "source_version": self.source_version,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True, slots=True)
class PolicyDecisionExport:
    implementation_version: str
    data_revision: str
    authority: str
    content_digest: str
    decision: str
    # The policy's own time, not the shadow run's. Phase A.1b persists this
    # evidence as a bitemporal snapshot, and a snapshot stamped with the
    # instant it happened to be read would claim the policy became true when
    # the question was asked. The loop already held these values; it simply
    # was not exporting them.
    recorded_at: datetime
    valid_from: datetime
    valid_to: datetime | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "implementation_version": self.implementation_version,
            "data_revision": self.data_revision,
            "authority": self.authority,
            "content_digest": self.content_digest,
            "decision": self.decision,
            "recorded_at": self.recorded_at.isoformat(),
            "valid_from": self.valid_from.isoformat(),
            "valid_to": None if self.valid_to is None else self.valid_to.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ClaimEvidenceLink:
    claim_id: str
    text: str
    evidence_requirement_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "evidence_requirement_ids": list(self.evidence_requirement_ids),
            "evidence_digests": list(self.evidence_digests),
        }


@dataclass(frozen=True, slots=True)
class PostconditionVersion:
    postcondition_id: str
    version: str
    schema_digest: str
    result: str

    def as_dict(self) -> dict[str, str]:
        return {
            "postcondition_id": self.postcondition_id,
            "version": self.version,
            "schema_digest": self.schema_digest,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True)
class EscalationBrief:
    case_id: UUID
    contract_version: str
    evidence_summary: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": str(self.case_id),
            "contract_version": self.contract_version,
            "evidence_summary": list(self.evidence_summary),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ShipmentEvidenceExport:
    mode: str
    tenant_id: str
    case_id: UUID
    case_version: int
    correlation_id: UUID
    terminal_state: TerminalOutcome
    reason_codes: tuple[str, ...]
    contract: ContractIdentity
    source_observation: SourceObservationExport | None
    policy: PolicyDecisionExport | None
    claim_links: tuple[ClaimEvidenceLink, ...]
    postcondition_versions: tuple[PostconditionVersion, ...]
    escalation_brief: EscalationBrief | None

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "case_id": str(self.case_id),
            "case_version": self.case_version,
            "correlation_id": str(self.correlation_id),
            "terminal_state": self.terminal_state.value,
            "reason_codes": list(self.reason_codes),
            "contract": self.contract.as_dict(),
            "source_observation": (
                None if self.source_observation is None else self.source_observation.as_dict()
            ),
            "policy": None if self.policy is None else self.policy.as_dict(),
            "claim_links": [link.as_dict() for link in self.claim_links],
            "postcondition_versions": [
                postcondition.as_dict() for postcondition in self.postcondition_versions
            ],
            "escalation_brief": (
                None if self.escalation_brief is None else self.escalation_brief.as_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class ShipmentShadowResult:
    terminal_state: TerminalOutcome
    reason_codes: tuple[str, ...]
    response_text: str | None
    evidence_export: ShipmentEvidenceExport


@dataclass(frozen=True, slots=True)
class AdmissionSignals:
    """The exact facts evaluated by the shipment-status admission gate."""

    has_shipment_reference: bool
    has_domain_noun: bool
    has_status_cue: bool


class ShipmentStatusShadowLoop:
    """Deterministic fixture-backed shipment journey that never owns a legacy response."""

    def __init__(
        self,
        *,
        contract: ResolutionContract,
        source: ShipmentSourcePort,
        policy: ShipmentPolicyPort,
    ) -> None:
        digest = contract_digest(contract)
        if (
            contract.schema_version != "resolution-contract/v0.1"
            or contract.id != _SHIPMENT_CONTRACT_ID
            or contract.version != _SHIPMENT_CONTRACT_VERSION
            or digest != _SHIPMENT_CONTRACT_DIGEST
        ):
            raise ValueError("shipment shadow loop requires the pinned shipment-status contract")
        self._contract = contract
        self._source = source
        self._policy = policy
        self._contract_identity = ContractIdentity(
            schema_identity=contract.schema_version,
            contract_id=contract.id,
            version=contract.version,
            digest=digest,
        )
        self._source_max_age = self._evidence_max_age("shipment-observation")
        self._policy_max_age = self._evidence_max_age("shipment-policy")
        self._source_timeout = self._read_action_timeout("shipment-observation")
        self._postconditions = tuple(
            PostconditionVersion(
                postcondition_id=item.id,
                version=item.checker.version,
                schema_digest=item.checker.schema_digest,
                result="not_run",
            )
            for item in contract.postconditions
        )

    def run(self, request: ShipmentShadowRequest) -> ShipmentShadowResult:
        if not self._is_admitted(request.messages):
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.CANCELLED,
                reason_codes=("NOT_IN_JOURNEY",),
            )

        shipment_id = self._extract_shipment_id(request.messages)
        if shipment_id is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.CLARIFICATION_REQUIRED,
                reason_codes=("SHIPMENT_ID_REQUIRED",),
                response_text=self._clarification_response_text(),
            )

        try:
            observation = self._source.lookup(
                tenant_id=request.tenant_id,
                shipment_id=shipment_id,
                timeout_seconds=self._source_timeout,
            )
        except Exception:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
            )
        if observation is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
            )

        source_export = self._source_export(request, observation)
        if source_export is None or not self._is_current(
            recorded_at=observation.observed_at,
            checked_at=request.observed_at,
            max_age_seconds=self._source_max_age,
        ):
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_STALE",),
                source_observation=source_export,
            )

        try:
            policies = self._policy.gather(
                tenant_id=request.tenant_id,
                shipment_id=shipment_id,
                effective_at=request.effective_at,
            )
        except Exception:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if not policies:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if len(policies) != 1:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_CONFLICT",),
                source_observation=source_export,
                evidence_summary=tuple(
                    f"policy:{item.data_revision}:{item.content_digest}" for item in policies
                ),
            )

        policy = policies[0]
        policy_export = self._policy_export(request, policy)
        if policy_export is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if not self._is_current(
            recorded_at=policy.recorded_at,
            checked_at=request.observed_at,
            max_age_seconds=self._policy_max_age,
        ):
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_STALE",),
                source_observation=source_export,
                policy=policy_export,
            )
        if not policy.status_disclosure_allowed:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("POLICY_DENIED",),
                source_observation=source_export,
                policy=policy_export,
            )

        candidates = request.candidate_claims or self._default_claims(source_export)
        claim_links = self._compile_claims(
            candidates=candidates,
            source_observation=source_export,
            policy=policy_export,
        )
        if claim_links is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("UNSUPPORTED_CLAIM",),
                source_observation=source_export,
                policy=policy_export,
            )

        passed_postconditions = tuple(
            PostconditionVersion(
                postcondition_id=item.postcondition_id,
                version=item.version,
                schema_digest=item.schema_digest,
                result="pass",
            )
            for item in self._postconditions
        )
        response_text = " ".join(link.text for link in claim_links)
        return self._finish(
            request=request,
            terminal_state=TerminalOutcome.VERIFIED,
            reason_codes=(),
            source_observation=source_export,
            policy=policy_export,
            claim_links=claim_links,
            postconditions=passed_postconditions,
            response_text=response_text,
        )

    def _finish(
        self,
        *,
        request: ShipmentShadowRequest,
        terminal_state: TerminalOutcome,
        reason_codes: tuple[str, ...],
        source_observation: SourceObservationExport | None = None,
        policy: PolicyDecisionExport | None = None,
        claim_links: tuple[ClaimEvidenceLink, ...] = (),
        postconditions: tuple[PostconditionVersion, ...] | None = None,
        response_text: str | None = None,
        evidence_summary: tuple[str, ...] = (),
    ) -> ShipmentShadowResult:
        escalation_brief = None
        if terminal_state is TerminalOutcome.ESCALATED:
            summary = list(evidence_summary)
            if source_observation is not None:
                summary.append(
                    f"shipment:{source_observation.shipment_id}:{source_observation.content_digest}"
                )
            if policy is not None:
                summary.append(f"policy:{policy.data_revision}:{policy.content_digest}")
            escalation_brief = EscalationBrief(
                case_id=request.case_id,
                contract_version=(
                    f"{self._contract_identity.contract_id}@{self._contract_identity.version}"
                    f"#{self._contract_identity.digest}"
                ),
                evidence_summary=tuple(summary),
                reason_codes=reason_codes,
            )
        export = ShipmentEvidenceExport(
            mode="shadow",
            tenant_id=request.tenant_id,
            case_id=request.case_id,
            case_version=max(1, len(request.messages)),
            correlation_id=request.correlation_id,
            terminal_state=terminal_state,
            reason_codes=reason_codes,
            contract=self._contract_identity,
            source_observation=source_observation,
            policy=policy,
            claim_links=claim_links,
            postcondition_versions=(
                self._postconditions if postconditions is None else postconditions
            ),
            escalation_brief=escalation_brief,
        )
        return ShipmentShadowResult(
            terminal_state=terminal_state,
            reason_codes=reason_codes,
            response_text=response_text,
            evidence_export=export,
        )

    def _clarification_response_text(self) -> str:
        """Render the missing-input ask from the pinned contract vocabulary."""
        terminal = self._contract.terminal_outcomes[TerminalOutcome.CLARIFICATION_REQUIRED]
        disclosure = self._contract.disclosure
        if terminal.disclosure_id != disclosure.id or "en" not in disclosure.locales:
            raise ValueError("clarification response lacks its declared English disclosure")
        required_inputs = tuple(item.id for item in self._contract.required_inputs if item.required)
        if len(required_inputs) != 1:
            raise ValueError("shipment clarification requires exactly one declared input")

        def label(symbol: str) -> str:
            words = symbol.replace("-", "_").split("_")
            return " ".join(
                word.upper() if word.casefold() in {"ai", "id"} else word for word in words
            )

        return f"{label(disclosure.id)}: Please provide the {label(required_inputs[0])}."

    def _evidence_max_age(self, requirement_id: str) -> int:
        requirement = next(
            (item for item in self._contract.evidence_requirements if item.id == requirement_id),
            None,
        )
        if requirement is None:
            raise ValueError(f"contract lacks evidence requirement '{requirement_id}'")
        return int(requirement.freshness.max_age_seconds)

    def _read_action_timeout(self, evidence_requirement_id: str) -> int:
        for step in self._contract.steps:
            action = step.action
            if (
                action is not None
                and action.output_evidence_requirement_id == evidence_requirement_id
            ):
                return int(action.timeout_seconds)
        raise ValueError(f"contract lacks read action for '{evidence_requirement_id}'")

    @staticmethod
    def _extract_shipment_id(messages: tuple[str, ...]) -> str | None:
        matches: list[str] = []
        for message in messages:
            matches.extend(
                match.group(0).upper() for match in _SHIPMENT_ID_PATTERN.finditer(message)
            )
        return matches[-1] if matches else None

    @staticmethod
    def _is_admitted(messages: tuple[str, ...]) -> bool:
        signals = ShipmentStatusShadowLoop.admission_signals(messages)
        return signals.has_shipment_reference or signals.has_domain_noun and signals.has_status_cue

    @staticmethod
    def admission_signals(messages: tuple[str, ...]) -> AdmissionSignals:
        """Expose the exact lexical facts that the admission kernel evaluates."""
        has_shipment_reference = any(
            _SHIPMENT_ID_PATTERN.search(message) is not None
            or _TRUNCATED_SHIPMENT_REFERENCE_PATTERN.search(message) is not None
            for message in messages
        )
        english_tokens = tuple(
            token
            for message in messages
            for token in _ENGLISH_ADMISSION_TOKEN_PATTERN.findall(message.casefold())
        )
        russian_tokens = tuple(
            token
            for message in messages
            for token in _RUSSIAN_ADMISSION_TOKEN_PATTERN.findall(message.casefold())
        )
        vocabulary = _SHIPMENT_STATUS_ADMISSION_VOCABULARY
        russian = _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY
        has_domain_noun = any(
            _contains_admission_noun(english_tokens, noun)
            for noun in vocabulary["domain_nouns"]
        ) or any(
            _russian_term_matches(russian_tokens, term)
            for term in russian["domain_nouns"].values()
        )
        has_status_cue = any(
            _matches_lexical_form(token, cue)
            for token in english_tokens
            for cue in vocabulary["status_cues"]
        ) or any(
            _russian_term_matches(russian_tokens, term)
            for term in russian["status_cues"].values()
        )
        return AdmissionSignals(
            has_shipment_reference=has_shipment_reference,
            has_domain_noun=has_domain_noun,
            has_status_cue=has_status_cue,
        )

    @staticmethod
    def _is_current(*, recorded_at: datetime, checked_at: datetime, max_age_seconds: int) -> bool:
        _require_aware(recorded_at, "evidence recorded_at")
        age_seconds = (checked_at - recorded_at).total_seconds()
        return 0 <= age_seconds <= max_age_seconds

    @staticmethod
    def _source_export(
        request: ShipmentShadowRequest,
        observation: ShipmentObservationLike,
    ) -> SourceObservationExport | None:
        if observation.tenant_id != request.tenant_id:
            return None
        return SourceObservationExport(
            shipment_id=observation.shipment_id,
            status=observation.status,
            location=observation.location,
            estimated_delivery=observation.estimated_delivery,
            observed_at=observation.observed_at,
            source_id=observation.source_id,
            source_version=observation.source_version,
            content_digest=observation.content_digest,
        )

    @staticmethod
    def _policy_export(
        request: ShipmentShadowRequest,
        policy: PolicyEvidenceLike,
    ) -> PolicyDecisionExport | None:
        if policy.tenant_id != request.tenant_id:
            return None
        return PolicyDecisionExport(
            implementation_version=_POLICY_IMPLEMENTATION_VERSION,
            data_revision=policy.data_revision,
            authority=policy.authority,
            content_digest=policy.content_digest,
            decision="allow" if policy.status_disclosure_allowed else "deny",
            recorded_at=policy.recorded_at,
            valid_from=policy.valid_from,
            valid_to=policy.valid_to,
        )

    @staticmethod
    def _default_claims(observation: SourceObservationExport) -> tuple[ClaimCandidate, ...]:
        requirements = ("shipment-observation", "shipment-policy")
        return (
            ClaimCandidate(
                claim_id="shipment-status",
                text=f"Shipment {observation.shipment_id} status is {observation.status}.",
                evidence_requirement_ids=requirements,
            ),
            ClaimCandidate(
                claim_id="shipment-location",
                text=f"Last reported location is {observation.location}.",
                evidence_requirement_ids=requirements,
            ),
            ClaimCandidate(
                claim_id="estimated-delivery",
                text=f"Estimated delivery is {observation.estimated_delivery}.",
                evidence_requirement_ids=requirements,
            ),
        )

    @staticmethod
    def _compile_claims(
        *,
        candidates: tuple[ClaimCandidate, ...],
        source_observation: SourceObservationExport,
        policy: PolicyDecisionExport,
    ) -> tuple[ClaimEvidenceLink, ...] | None:
        allowed = {
            item.claim_id: item
            for item in ShipmentStatusShadowLoop._default_claims(source_observation)
        }
        digests: Mapping[str, str] = {
            "shipment-observation": source_observation.content_digest,
            "shipment-policy": policy.content_digest,
        }
        links: list[ClaimEvidenceLink] = []
        for candidate in candidates:
            expected = allowed.get(candidate.claim_id)
            if expected is None or candidate.text != expected.text:
                return None
            if candidate.evidence_requirement_ids != expected.evidence_requirement_ids:
                return None
            evidence_digests = tuple(digests[item] for item in candidate.evidence_requirement_ids)
            if not evidence_digests:
                return None
            links.append(
                ClaimEvidenceLink(
                    claim_id=candidate.claim_id,
                    text=candidate.text,
                    evidence_requirement_ids=candidate.evidence_requirement_ids,
                    evidence_digests=evidence_digests,
                )
            )
        return tuple(links) if links else None


_ResponseT = TypeVar("_ResponseT")


def run_legacy_ask_shadow(
    *,
    response: _ResponseT,
    tenant_id: str,
    session_id: str,
    correlation_id: str,
    question: str,
    observer: Callable[[ShipmentShadowRequest], object] | None,
    observed_at: datetime | None = None,
) -> _ResponseT:
    """Run an isolated shadow observer while returning the exact legacy response object."""

    if observer is None:
        return response
    instant = observed_at or datetime.now(UTC)
    try:
        request = ShipmentShadowRequest(
            tenant_id=tenant_id,
            # One question, one case. The loop runs once per question and
            # produces exactly one terminal outcome, so a case keyed on the
            # session alone would reach a terminal status on the first turn and
            # have nowhere to go on the second — phase A.1b persists these as
            # real cases with a real transition graph, and that graph forbids
            # leaving a terminal state.
            case_id=uuid5(
                NAMESPACE_URL,
                f"rag-new:shipment-shadow:{tenant_id}:{session_id}:{correlation_id}",
            ),
            correlation_id=uuid5(NAMESPACE_URL, f"rag-new:correlation:{correlation_id}"),
            messages=(question,),
            effective_at=instant,
            observed_at=instant,
        )
        observer(request)
    except Exception:
        pass
    return response


__all__ = [
    "AdmissionSignals",
    "ClaimCandidate",
    "ClaimEvidenceLink",
    "ContractIdentity",
    "EscalationBrief",
    "PolicyDecisionExport",
    "PolicyEvidenceLike",
    "PostconditionVersion",
    "RussianAdmissionTranslation",
    "ShipmentEvidenceExport",
    "ShipmentObservationLike",
    "ShipmentPolicyPort",
    "ShipmentShadowRequest",
    "ShipmentShadowResult",
    "ShipmentSourcePort",
    "ShipmentStatusShadowLoop",
    "SourceObservationExport",
    "run_legacy_ask_shadow",
]
