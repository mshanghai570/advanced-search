"""Deterministic behavior-category search for Binary Ninja views."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    terms: tuple[str, ...]
    regexes: tuple[str, ...] = ()


CATEGORIES: dict[str, Category] = {
    "purchase": Category("Purchase / commerce", "Payment, checkout, billing, and purchase workflows.", ("purchase", "checkout", "cart", "order", "invoice", "billing", "payment", "pay", "stripe", "paypal", "iap", "receipt", "sku", "price", "product", "transaction"), (r"https?://[^\\s]*pay", r"/checkout", r"/purchase", r"/billing")),
    "credential_access": Category("Credential access", "Credential collection, authentication, tokens, and secrets.", ("password", "passwd", "credential", "token", "oauth", "jwt", "cookie", "login", "signin", "auth", "secret", "keychain", "ssh", "private key"), (r"authorization:\s*bearer", r"/oauth", r"/login", r"/token")),
    "networking": Category("Networking", "Network communication, sockets, HTTP, DNS, and remote services.", ("socket", "connect", "send", "recv", "http", "https", "tls", "ssl", "dns", "curl", "wininet", "url", "websocket", "proxy", "tcp", "udp"), (r"https?://", r"[a-z0-9.-]+\.(com|net|org|io|ru|cn|dev)")),
    "file_activity": Category("File activity", "File reads/writes, staging, archives, and path manipulation.", ("open", "read", "write", "fopen", "createfile", "deletefile", "rename", "copyfile", "tmp", "temp", "archive", "zip", "tar", "path", "directory"), (r"/[a-z0-9_.-]+/[a-z0-9_.-]+", r"[A-Z]:\\\\")),
    "process_execution": Category("Process execution", "Process creation, shell execution, injection, and code loading.", ("exec", "spawn", "system", "shell", "cmd", "powershell", "createprocess", "winexec", "process", "inject", "loadlibrary", "dlopen", "fork", "ptrace"), (r"powershell(?:\.exe)?", r"cmd(?:\.exe)?\s*/[cCkK]", r"/bin/(?:sh|bash)")),
    "persistence": Category("Persistence", "Startup, services, scheduled tasks, and autorun mechanisms.", ("startup", "autorun", "run key", "registry", "service", "scheduled task", "cron", "launchagent", "launchdaemon", "boot", "login item"), (r"software\\\\microsoft\\\\windows\\\\currentversion\\\\run", r"/etc/cron", r"schtasks")),
    "surveillance": Category("Surveillance / collection", "Screenshots, keylogging, microphone, camera, clipboard, and discovery.", ("screenshot", "keylog", "keyboard", "microphone", "camera", "webcam", "clipboard", "screen", "record", "enumerate", "browser history", "location", "contacts"), (r"getasynckeystate", r"bitblt", r"clipboard")),
    "crypto": Category("Cryptography / crypto-mining", "Cryptographic operations, certificate handling, and mining indicators.", ("encrypt", "decrypt", "aes", "rsa", "sha", "md5", "bcrypt", "certificate", "crypto", "wallet", "miner", "stratum"), (r"stratum\+tcp://", r"-----begin (?:rsa|ec|private) key-----")),
    "anti_analysis": Category("Anti-analysis", "Debugger checks, virtual-machine checks, packing, and evasion.", ("debugger", "anti-debug", "virtual machine", "vmware", "virtualbox", "sandbox", "isdebuggerpresent", "ollydbg", "x64dbg", "upx", "packed", "sleep"), (r"isdebuggerpresent", r"vmware|virtualbox|qemu", r"x64dbg|ollydbg")),
}


@dataclass
class FeatureHit:
    category: str
    score: int
    reasons: list[str] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _disassembly_line_text(line: Any) -> str:
    """Normalize Binary Ninja DisassemblyTextLine and legacy tuple-like lines."""
    text = getattr(line, "text", None)
    if text is not None:
        return _text(text)
    tokens = getattr(line, "tokens", None)
    if tokens is not None:
        return " ".join(_text(getattr(token, "text", token)) for token in tokens)
    if isinstance(line, (tuple, list)):
        return " ".join(_text(part) for part in line)
    return _text(line)


def _function_evidence(function: Any) -> tuple[str, list[str]]:
    chunks: list[str] = []
    names: list[str] = []
    for attr in ("name", "symbol"):
        value = getattr(function, attr, None)
        if value:
            names.append(_text(value))
            chunks.append(_text(value))
    for string in getattr(function, "strings", []) or []:
        chunks.append(_text(getattr(string, "value", string)))
    for block in getattr(function, "basic_blocks", []) or []:
        for insn in getattr(block, "disassembly_text", []) or []:
            chunks.append(_disassembly_line_text(insn))
    return " ".join(chunks).lower(), names


def search_view(bv: Any, category_keys: Iterable[str], query: str = "", limit: int = 100) -> list[FeatureHit]:
    """Search functions and their visible evidence without requiring a third-party dependency."""
    selected = [CATEGORIES[k] for k in category_keys if k in CATEGORIES]
    if not selected:
        selected = list(CATEGORIES.values())
    query_l = query.strip().lower()
    hits: list[FeatureHit] = []
    for function in getattr(bv, "functions", []) or []:
        evidence, names = _function_evidence(function)
        if query_l and query_l not in evidence:
            continue
        for category in selected:
            reasons: list[str] = []
            score = 0
            for term in category.terms:
                if term in evidence:
                    score += 2
                    reasons.append(term)
            for pattern in category.regexes:
                if re.search(pattern, evidence, re.IGNORECASE):
                    score += 4
                    reasons.append(f"regex:{pattern}")
            if score:
                addr = getattr(function, "start", getattr(function, "address", 0))
                hits.append(FeatureHit(category.name, score, reasons[:8], [{"name": names[0] if names else "sub_" + format(int(addr), "x"), "address": int(addr)}]))
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


def categories_for_prompt() -> str:
    return "\n".join(f"- {key}: {value.name} — {value.description}" for key, value in CATEGORIES.items())


def compact_view_summary(bv: Any, max_functions: int = 250) -> list[dict[str, Any]]:
    rows = []
    for function in (getattr(bv, "functions", []) or [])[:max_functions]:
        evidence, names = _function_evidence(function)
        addr = getattr(function, "start", getattr(function, "address", 0))
        rows.append({"name": names[0] if names else "sub_" + format(int(addr), "x"), "address": int(addr), "evidence": evidence[:1200]})
    return rows


__all__ = ["CATEGORIES", "Category", "FeatureHit", "search_view", "categories_for_prompt", "compact_view_summary"]

if __name__ == "__main__":
    print("Categories:")
    print(categories_for_prompt())
