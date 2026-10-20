"""Pure identifier normalization shared by source adapters and tool boundaries."""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import SplitResult, unquote, unquote_plus, urlsplit, urlunsplit


class IdentifierError(ValueError):
    """An identifier does not have a supported form."""


@dataclass(frozen=True)
class Identifier:
    scheme: str
    value: str
    version: int | None = None


def _text(s: str) -> str:
    if not isinstance(s, str) or not s.strip():
        raise IdentifierError("Expected a non-empty identifier")
    return s.strip()


def _prefix(s: str, prefix: str) -> str:
    return re.sub(rf"^(?:{prefix}):\s*", "", _text(s), flags=re.I)


def _match(s: str, pattern: str) -> str:
    if not re.fullmatch(pattern, s, flags=re.ASCII):
        raise IdentifierError("Invalid identifier form")
    return s


def _url(s: str) -> SplitResult:
    try:
        # urlsplit silently removes some controls, which could change identity.
        if any(ord(char) < 32 or ord(char) == 127 for char in s):
            raise ValueError
        parts = urlsplit(s)
        if (
            parts.scheme.lower() not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or re.search(r"\s", s)
        ):
            raise ValueError
        _ = parts.port
        return parts
    except ValueError as exc:
        raise IdentifierError("Invalid HTTP URL") from exc


def _resolver(
    s: str, hosts: set[str], path_prefix: str = "", keep_trailing_slash: bool = False
) -> str:
    if "://" not in s:
        return s
    parts = _url(s)
    if parts.hostname not in hosts:
        raise IdentifierError("Unexpected identifier host")
    # Resolver paths are percent-encoded; the identifier is the decoded form.
    # Strict decoding keeps distinct invalid byte escapes from collapsing to U+FFFD.
    try:
        path = unquote(parts.path, errors="strict")
    except UnicodeDecodeError as exc:
        raise IdentifierError("Invalid percent-encoding in identifier URL") from exc
    path = path.lstrip("/") if keep_trailing_slash else path.strip("/")
    if path_prefix:
        path = re.sub(path_prefix, "", path, flags=re.I)
    return path


def normalize_doi(s: str) -> str:
    # A trailing slash can belong to the DOI suffix, as in the bare form.
    value = _resolver(
        _prefix(s, "doi"), {"doi.org", "dx.doi.org"}, keep_trailing_slash=True
    ).lower()
    value = value.rstrip(".,;:!?\"'")
    # Preserve balanced brackets that are part of a DOI suffix.
    brackets = {")": "(", "]": "[", "}": "{"}
    while value and value[-1] in brackets:
        closing = value[-1]
        if value.count(closing) <= value.count(brackets[closing]):
            break
        value = value[:-1].rstrip(".,;:!?\"'")
    _reject_unicode_space(value)
    return _match(value, r"10\.\d{4,9}/\S+")


def _reject_unicode_space(value: str) -> None:
    # ASCII matching alone would let Unicode whitespace such as U+00A0 through.
    if any(c.isspace() or unicodedata.category(c).startswith("C") for c in value):
        raise IdentifierError("Invalid identifier form")


def normalize_arxiv(s: str) -> tuple[str, int | None]:
    value = _resolver(_prefix(s, "arxiv"), {"arxiv.org", "www.arxiv.org"}, r"^(abs|pdf)/")
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    version_match = re.search(r"v([1-9][0-9]*)$", value, flags=re.I)
    try:
        version = int(version_match[1]) if version_match else None
    except ValueError as exc:  # Python caps int() at 4300 digits.
        raise IdentifierError("Invalid arXiv version") from exc
    if version_match:
        value = value[: version_match.start()]
    if "/" in value:
        archive, number = value.split("/", 1)
        archive = archive.lower()
        if "." in archive:
            base, subject = archive.split(".", 1)
            archive = base + "." + subject.upper()
        value = archive + "/" + number
    return _match(value, r"(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})"), version


def normalize_pmid(s: str) -> str:
    return _match(_resolver(_prefix(s, "pmid"), {"pubmed.ncbi.nlm.nih.gov"}), r"\d+")


def normalize_pmcid(s: str) -> str:
    value = _resolver(
        _prefix(s, "pmcid"),
        {"pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"},
        r"^(?:pmc/)?articles/",
    )
    return "PMC" + _match(re.sub(r"^PMC", "", value, flags=re.I), r"\d+")


def normalize_openalex(s: str) -> str:
    value = _resolver(
        _prefix(s, "openalex"),
        {"openalex.org", "www.openalex.org", "api.openalex.org"},
        r"^works/",
    )
    return _match(value.upper(), r"W\d+")


def normalize_s2(s: str) -> str:
    value = _resolver(
        _prefix(s, "s2|semantic_scholar"),
        {"semanticscholar.org", "www.semanticscholar.org"},
        r"^paper/(?:.*/)?",
    )
    return _match(value.lower(), r"[0-9a-f]{40}")


def normalize_core(s: str) -> str:
    return _match(_resolver(_prefix(s, "core"), {"core.ac.uk"}, r"^(?:works|outputs)/"), r"\d+")


def normalize_nct(s: str) -> str:
    value = _resolver(
        _prefix(s, "nct"),
        {"clinicaltrials.gov", "www.clinicaltrials.gov"},
        r"^(?:study|ct2/show)/",
    )
    value = re.sub(r"^NCT", "", value, flags=re.I)
    return "NCT" + _match(value, r"\d{8}")


def normalize_rfc(s: str) -> str:
    value = _resolver(
        _prefix(s, "rfc"),
        {"rfc-editor.org", "www.rfc-editor.org", "datatracker.ietf.org"},
        r"^(?:rfc/|doc/html/)",
    )
    value = re.sub(r"^rfc\s*", "", value, flags=re.I)
    value = re.sub(r"\.(?:txt|html)$", "", value, flags=re.I)
    # Strip zeros as text: int() rejects strings over 4300 digits.
    return _match(value, r"\d+").lstrip("0") or "0"


def normalize_handle(s: str) -> str:
    # The whole resolver path is the handle: suffixes may hold slashes, and a
    # trailing slash is part of the handle, so it is kept as in normalize_doi.
    value = _resolver(_prefix(s, "handle|hdl"), {"hdl.handle.net"}, keep_trailing_slash=True)
    _reject_unicode_space(value)
    return _match(value, r"\d+(?:\.\d+)*/\S+")


def normalize_dspace_uuid(s: str) -> str:
    return _match(
        _prefix(s, "dspace_uuid|dspace|uuid").lower(),
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
    )


def normalize_github(s: str) -> str:
    raw = _prefix(s, "github")
    value = _resolver(raw, {"github.com", "www.github.com"}).lower()
    # Only a clone URL carries a .git suffix; the bare owner/repo form is canonical
    # and kept as given, so normalizing twice cannot strip a second suffix.
    if "://" in raw:
        value = value.removesuffix(".git")
    return _match(value, r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/[a-z0-9_.-]+")


def normalize_url(s: str) -> str:
    parts = _url(_prefix(s, "url"))
    scheme = parts.scheme.lower()
    host = parts.hostname
    if host is None:
        raise IdentifierError("Missing URL host")
    host = host.lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port is not None and (scheme, parts.port) not in {
        ("http", 80),
        ("https", 443),
    }:
        host += f":{parts.port}"
    # Keep the raw query pairs: decoding and re-encoding would merge distinct
    # non-UTF-8 octets into the same replacement character.
    pairs = []
    for pair in parts.query.split("&"):
        key = unquote_plus(pair.partition("=")[0]).lower()
        if pair and not key.startswith("utm_") and key not in {"fbclid", "gclid", "msclkid"}:
            pairs.append(pair)
    query = "&".join(pairs)
    return urlunsplit((scheme, host, parts.path or "/", query, ""))


_NORMALIZERS = {
    "doi": normalize_doi,
    "pmid": normalize_pmid,
    "pmcid": normalize_pmcid,
    "openalex": normalize_openalex,
    "s2": normalize_s2,
    "core": normalize_core,
    "nct": normalize_nct,
    "rfc": normalize_rfc,
    "handle": normalize_handle,
    "dspace_uuid": normalize_dspace_uuid,
    "github": normalize_github,
    "url": normalize_url,
}


def parse_any(s: str) -> Identifier:
    value = _text(s)
    if "://" not in value and (
        value.lower().endswith(".pdf") or re.match(r"^(?:doi|core)_", value, re.I)
    ):
        raise IdentifierError("File names are not identifiers")
    prefix = value.partition(":")[0].lower()
    prefix = {
        "hdl": "handle",
        "uuid": "dspace_uuid",
        "dspace": "dspace_uuid",
        "semantic_scholar": "s2",
    }.get(prefix, prefix)
    if prefix == "arxiv":
        ident, version = normalize_arxiv(value)
        return Identifier("arxiv", ident, version)
    if prefix in _NORMALIZERS:
        return Identifier(prefix, _NORMALIZERS[prefix](value))
    if "://" in value:
        host = _url(value).hostname
        hosts = {
            "doi.org": "doi",
            "dx.doi.org": "doi",
            "arxiv.org": "arxiv",
            "pubmed.ncbi.nlm.nih.gov": "pmid",
            "pmc.ncbi.nlm.nih.gov": "pmcid",
            "www.ncbi.nlm.nih.gov": "pmcid",
            "openalex.org": "openalex",
            "api.openalex.org": "openalex",
            "semanticscholar.org": "s2",
            "core.ac.uk": "core",
            "clinicaltrials.gov": "nct",
            "rfc-editor.org": "rfc",
            "datatracker.ietf.org": "rfc",
            "hdl.handle.net": "handle",
            "github.com": "github",
        }
        if host is None:
            raise IdentifierError("Missing URL host")
        scheme = hosts.get(host, hosts.get(host.removeprefix("www."), "url"))
        if scheme == "arxiv":
            ident, version = normalize_arxiv(value)
            return Identifier(scheme, ident, version)
        return Identifier(scheme, _NORMALIZERS[scheme](value))
    for scheme, pattern in (
        ("doi", r"10\."),
        ("arxiv", r"(?:\d{4}\.\d{4,5}(?:v[1-9]\d*)?$|[a-z-]+(?:\.[A-Z]{2})?/\d{7})"),
        ("pmcid", r"PMC\d"),
        ("openalex", r"W\d"),
        ("nct", r"NCT\d"),
        ("rfc", r"RFC\s*\d"),
        ("dspace_uuid", r"[a-f0-9]{8}-"),
        ("s2", r"[a-f0-9]{40}$"),
        ("handle", r"\d+(?:\.\d+)*/"),
        ("pmid", r"\d+$"),
    ):
        if re.match(pattern, value, re.I):
            if scheme == "arxiv":
                ident, version = normalize_arxiv(value)
                return Identifier(scheme, ident, version)
            return Identifier(scheme, _NORMALIZERS[scheme](value))
    raise IdentifierError("Unknown identifier scheme")


# A small, fixed English stop list keeps title matching deterministic.
_STOP_WORDS = frozenset(
    ["a", "an", "the", "and", "or", "of", "in", "on", "to", "for", "with", "by", "at", "from"]
)


def title_key(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold()
    value = "".join(" " if unicodedata.category(c).startswith("P") else c for c in value)
    return " ".join(word for word in value.split() if word not in _STOP_WORDS)
