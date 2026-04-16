from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
import re
from typing import Iterable, Optional
from urllib.parse import quote, unquote, urlparse

import httpx

try:
    from .matching import fuzzy_name_score, is_fuzzy_match, normalize_match_key
except ImportError:  # pragma: no cover
    from matching import fuzzy_name_score, is_fuzzy_match, normalize_match_key  # type: ignore[no-redef]

DEFAULT_BASE_URL = "https://wiki.biligame.com/rocom"
DEFAULT_TIMEOUT = 10.0
DEFAULT_CANDIDATE_LIMIT = 5
DEFAULT_SUMMARY_LENGTH = 280
DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|section|li|ul|ol|h[1-6]|br|tr|td|th)[^>]*>", re.IGNORECASE)
_NOISE_RE = re.compile(
    r"<(?:script|style|table|sup|noscript)[^>]*>.*?</(?:script|style|table|sup|noscript)>",
    re.IGNORECASE | re.DOTALL,
)
_IMG_ALT_RE = re.compile(r'<img[^>]+alt="([^"]+)"[^>]*>', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
_IMAGE_TYPE_RE = re.compile(r"属性\s*([^\s.]+)\.png")
_TYPE_ICON_ALT_RE = re.compile(r"(?:图标\s+)?(?:宠物\s+)?属性\s+([^\s.]+)\.png")
_TRAIT_ICON_ALT_RE = re.compile(r"(?:图标\s+)?特性\s+(.+?)\.png")
_SECTION_STOP_RE = re.compile(r"^(?:LV\d+|技能表|图鉴课题|获得方式|获取方式|相关攻略|参考资料|导航)$")
_FIELD_VALUE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?(?:[%a-zA-Z\u4e00-\u9fa5/]+)?)")
_PAGE_TITLE_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_PAGE_BODY_RE = re.compile(
    r'<div class="mw-parser-output">(.*?)(?:<div class="printfooter"|<div id="catlinks"|</main>)',
    re.IGNORECASE | re.DOTALL,
)
_SEARCH_RESULT_RE = re.compile(r'href="/rocom/([^"#?]+)"[^>]*title="([^"]+)"', re.IGNORECASE)
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_A_TAG_RE = re.compile(r"<a\b[^>]*href=(?:\"([^\"]*)\"|'([^']*)')[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_VARIANT_SLOT_RE = re.compile(
    r"""<li\b[^>]*id\s*=\s*(?:"receptor_grament_list_(\d+)"|'receptor_grament_list_(\d+)')[^>]*>(.*?)</li>""",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r"""([a-zA-Z_:][a-zA-Z0-9_:\-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_EVOLUTION_CLASS_RE = re.compile(r"rocom_spirit_evolution_(\d+)")
_EVOLUTION_OPEN_TAG_RE = re.compile(
    r"""<(?P<tag>[a-zA-Z0-9]+)\b(?P<attrs>[^>]*)class\s*=\s*(?:"[^"]*rocom_spirit_evolution_(?P<index1>\d+)[^"]*"|'[^']*rocom_spirit_evolution_(?P<index2>\d+)[^']*')(?P<rest>[^>]*)>""",
    re.IGNORECASE | re.DOTALL,
)

STAT_LABELS = ("生命", "物攻", "魔攻", "物防", "魔防", "速度")
PROFILE_LABELS = ("身高", "体重", "重量")
TOTAL_VALUE_LABELS = ("种族值", "总和")
EVOLUTION_STOP_LABELS = {"特性", "精灵属性", "选择性格", "克制表", "技能表", "图鉴课题", "获得方式", "获取方式"}
EVOLUTION_NOISE_TERMS = {
    "进化条件",
    "进化方向",
    "进化信息",
    "进化说明",
    "超进化条件",
    "进化",
    "条件",
    "暂无",
    "无",
}
GENERIC_IMAGE_ALTS = {
    "界面 宠物 本体.png",
    "界面 宠物 异色.png",
    "界面 宠物 果实.png",
    "界面 宠物 宠物蛋.png",
}
ICON_EXCLUDE_TERMS = {"技能", "招式", "魔法", "物理", "变化"}
SKILL_CATEGORY_NAMES = ("物攻", "魔攻", "变化", "辅助")
SKILL_SECTION_STOP_LABELS = {
    "可以学会的精灵",
    "可以学会的精灵:",
    "可学会的精灵",
    "可学会的精灵:",
    "图鉴课题",
    "获得方式",
    "获取方式",
    "相关攻略",
    "参考资料",
    "导航",
}


@dataclass
class SearchCandidate:
    title: str
    snippet: str = ""
    url: str = ""
    pageid: Optional[int] = None


@dataclass
class WikiEntry:
    title: str
    url: str
    summary: str = ""
    snippet: str = ""
    is_exact_match: bool = False
    image_url: str = ""
    shiny_image_url: str = ""
    egg_image_url: str = ""
    fruit_image_url: str = ""
    types: list[str] = field(default_factory=list)
    type_icons: list[tuple[str, str]] = field(default_factory=list)
    evolution_image_urls: list[str] = field(default_factory=list)
    evolution_chain: list[str] = field(default_factory=list)
    total_species_value: str = ""
    stats: list[tuple[str, str]] = field(default_factory=list)
    profile_fields: list[tuple[str, str]] = field(default_factory=list)
    trait_name: str = ""
    trait_icon_url: str = ""
    trait_desc: str = ""
    restraint: "RestraintProfile | None" = None
    restraint_icon_rows: list["RestraintIconRow"] = field(default_factory=list)
    candidates: list[SearchCandidate] = field(default_factory=list)


@dataclass
class SkillEntry:
    title: str
    url: str
    snippet: str = ""
    is_exact_match: bool = False
    type_name: str = ""
    type_icon_url: str = ""
    category_name: str = ""
    category_icon_url: str = ""
    power: str = ""
    cost: str = ""
    effect: str = ""
    skill_icon_url: str = ""
    learners: list[str] = field(default_factory=list)
    candidates: list[SearchCandidate] = field(default_factory=list)


@dataclass
class RestraintProfile:
    restrain: list[str] = field(default_factory=list)
    restrained_by: list[str] = field(default_factory=list)
    resist: list[str] = field(default_factory=list)
    resisted_by: list[str] = field(default_factory=list)


@dataclass
class RestraintIconRow:
    label: str
    items: list[tuple[str, str]] = field(default_factory=list)


def normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def build_page_url(base_url: str, title: str) -> str:
    safe_title = quote(title.replace(" ", "_"), safe="")
    return f"{base_url.rstrip('/')}/{safe_title}"


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = _NOISE_RE.sub(" ", value)
    text = _IMG_ALT_RE.sub(lambda match: f" {match.group(1)} ", text)
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _MULTI_NEWLINE_RE.sub("\n", text)
    return text.strip(" \n")


def truncate_text(value: str, limit: int) -> str:
    if limit <= 0 or len(value) <= limit:
        return value
    shortened = value[: max(limit - 1, 1)].rstrip()
    return f"{shortened}…"


def pick_primary_candidate(keyword: str, candidates: Iterable[SearchCandidate]) -> Optional[SearchCandidate]:
    normalized_keyword = normalize_keyword(keyword)
    candidate_list = list(candidates)
    for candidate in candidate_list:
        if normalize_keyword(candidate.title) == normalized_keyword:
            return candidate
    return candidate_list[0] if candidate_list else None


def _is_relevant_title(keyword: str, title: str) -> bool:
    return is_fuzzy_match(keyword, title)


def _filter_relevant_candidates(keyword: str, candidates: Iterable[SearchCandidate]) -> list[SearchCandidate]:
    candidate_list = list(candidates)
    scored = [(fuzzy_name_score(keyword, candidate.title), candidate) for candidate in candidate_list]
    filtered = [candidate for score, candidate in scored if score >= 58]
    if filtered:
        filtered.sort(key=lambda candidate: (-fuzzy_name_score(keyword, candidate.title), candidate.title))
        return filtered

    primary = pick_primary_candidate(keyword, candidate_list)
    return [primary] if primary and _is_relevant_title(keyword, primary.title) else []


def format_lookup_message(entry: Optional[WikiEntry], keyword: str, summary_length: int) -> str:
    if entry is None:
        return f"没有找到与“{keyword}”相关的 Wiki 词条。"

    lines: list[str] = []
    if not entry.is_exact_match and normalize_keyword(entry.title) != normalize_keyword(keyword):
        lines.append(f"未找到“{keyword}”的完全匹配词条，已返回最相关结果。")

    lines.append(f"【{entry.title}】")

    if entry.types:
        lines.append(f"属性: {' / '.join(entry.types)}")

    if entry.total_species_value:
        lines.append(f"种族值: {entry.total_species_value}")

    if entry.stats:
        stat_text = " / ".join(f"{label} {value}" for label, value in entry.stats)
        lines.append(f"六维: {stat_text}")

    if entry.profile_fields:
        profile_text = " / ".join(f"{label} {value}" for label, value in entry.profile_fields)
        lines.append(f"基础信息: {profile_text}")

    summary = truncate_text(entry.summary.strip() or entry.snippet.strip(), summary_length)
    if summary:
        lines.append(summary)
    else:
        lines.append("该词条暂时没有可提取的摘要内容。")

    if entry.trait_name:
        trait_text = entry.trait_name
        if entry.trait_desc:
            trait_text = f"{trait_text}: {entry.trait_desc}"
        lines.append(f"特性: {trait_text}")

    if entry.restraint:
        restraint_lines = _format_restraint_lines(entry.restraint)
        if restraint_lines:
            lines.extend(restraint_lines)

    lines.append(f"链接: {entry.url}")

    other_titles = [
        candidate.title
        for candidate in entry.candidates
        if normalize_keyword(candidate.title) != normalize_keyword(entry.title)
    ]
    if other_titles:
        preview = "、".join(other_titles[:3])
        lines.append(f"其他候选: {preview}")

    return "\n".join(lines)


def format_skill_lookup_message(entry: Optional[SkillEntry], keyword: str, summary_length: int) -> str:
    if entry is None:
        return f"没有找到与“{keyword}”相关的 Wiki 技能词条。"

    lines: list[str] = []
    if not entry.is_exact_match and normalize_keyword(entry.title) != normalize_keyword(keyword):
        lines.append(f"未找到“{keyword}”的完全匹配技能词条，已返回最相关结果。")

    lines.append(f"【{entry.title}】")

    meta_parts = [part for part in (entry.type_name, entry.category_name) if part]
    if meta_parts:
        lines.append(f"分类: {' / '.join(meta_parts)}")

    stat_parts = []
    if entry.cost:
        stat_parts.append(f"耗能 {entry.cost}")
    if entry.power:
        stat_parts.append(f"技能威力 {entry.power}")
    if stat_parts:
        lines.append(" / ".join(stat_parts))

    effect = truncate_text(entry.effect.strip() or entry.snippet.strip(), summary_length)
    if effect:
        lines.append(effect)
    else:
        lines.append("该技能词条暂时没有提取到技能效果。")

    if entry.learners:
        lines.append(f"可学精灵: {'、'.join(entry.learners[:8])}")

    lines.append(f"链接: {entry.url}")

    other_titles = [
        candidate.title
        for candidate in entry.candidates
        if normalize_keyword(candidate.title) != normalize_keyword(entry.title)
    ]
    if other_titles:
        lines.append(f"其他候选: {'、'.join(other_titles[:3])}")

    return "\n".join(lines)


def _format_restraint_lines(restraint: RestraintProfile) -> list[str]:
    rows = []
    mapping = [
        ("克制", restraint.restrain),
        ("被克制", restraint.restrained_by),
        ("抵抗", restraint.resist),
        ("被抵抗", restraint.resisted_by),
    ]
    for label, values in mapping:
        if values:
            rows.append(f"{label}: {'、'.join(values)}")
    return rows


def extract_keyword_from_message(message: str, command_names: Iterable[str]) -> str:
    text = (message or "").strip()
    if not text:
        return ""

    without_prefix = text[1:].strip() if text.startswith("/") else text
    lowered = without_prefix.casefold()
    for command_name in sorted(command_names, key=len, reverse=True):
        command_lower = command_name.casefold()
        if lowered == command_lower:
            return ""
        if lowered.startswith(f"{command_lower} "):
            return without_prefix[len(command_name) :].strip()

    parts = without_prefix.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return without_prefix


class RocomWikiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
        user_agent: str = DEFAULT_BROWSER_UA,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api.php"
        self.timeout = timeout
        self.candidate_limit = max(candidate_limit, 1)
        self.user_agent = user_agent

    async def lookup(self, keyword: str) -> Optional[WikiEntry]:
        cleaned_keyword = keyword.strip()
        if not cleaned_keyword:
            return None

        try:
            return await self._lookup_via_api(cleaned_keyword)
        except httpx.HTTPError:
            return await self._lookup_via_html(cleaned_keyword)

    async def lookup_skill(self, keyword: str) -> Optional[SkillEntry]:
        cleaned_keyword = keyword.strip()
        if not cleaned_keyword:
            return None

        try:
            return await self._lookup_skill_via_api(cleaned_keyword)
        except httpx.HTTPError:
            return await self._lookup_skill_via_html(cleaned_keyword)

    async def _lookup_via_api(self, keyword: str) -> Optional[WikiEntry]:
        candidates = await self._search(keyword)
        direct_result = await self._fetch_page_entry(keyword, keyword, candidates)
        if direct_result is not None:
            return direct_result

        for candidate in _filter_relevant_candidates(keyword, candidates):
            result = await self._fetch_page_entry(candidate.title, keyword, candidates, snippet=candidate.snippet)
            if result is not None:
                return result
        return None

    async def _lookup_via_html(self, keyword: str) -> Optional[WikiEntry]:
        direct_result = await self._fetch_page_entry(keyword, keyword, [])
        if direct_result is not None:
            return direct_result

        candidates = await self._search_html(keyword)
        for candidate in _filter_relevant_candidates(keyword, candidates):
            result = await self._fetch_page_entry(candidate.title, keyword, candidates, snippet=candidate.snippet)
            if result is not None:
                return result
        return None

    async def _lookup_skill_via_api(self, keyword: str) -> Optional[SkillEntry]:
        candidates = await self._search(keyword)
        direct_result = await self._fetch_skill_entry(keyword, keyword, candidates)
        if direct_result is not None:
            return direct_result

        for candidate in _filter_relevant_candidates(keyword, candidates):
            result = await self._fetch_skill_entry(candidate.title, keyword, candidates, snippet=candidate.snippet)
            if result is not None:
                return result
        return None

    async def _lookup_skill_via_html(self, keyword: str) -> Optional[SkillEntry]:
        direct_result = await self._fetch_skill_entry(keyword, keyword, [])
        if direct_result is not None:
            return direct_result

        candidates = await self._search_html(keyword)
        for candidate in _filter_relevant_candidates(keyword, candidates):
            result = await self._fetch_skill_entry(candidate.title, keyword, candidates, snippet=candidate.snippet)
            if result is not None:
                return result
        return None

    async def _search(self, keyword: str) -> list[SearchCandidate]:
        payload = await self._request_json(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "utf8": "1",
                "list": "search",
                "srsearch": keyword,
                "srlimit": str(self.candidate_limit),
                "srprop": "snippet",
            }
        )
        raw_results = payload.get("query", {}).get("search", [])

        results: list[SearchCandidate] = []
        for item in raw_results:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            snippet = strip_html(str(item.get("snippet", "")))
            results.append(
                SearchCandidate(
                    title=title,
                    snippet=snippet,
                    url=build_page_url(self.base_url, title),
                    pageid=item.get("pageid"),
                )
            )
        return results

    async def _get_page_html(self, title: str) -> str:
        payload = await self._request_json(
            {
                "action": "parse",
                "format": "json",
                "formatversion": "2",
                "page": title,
                "prop": "text",
                "section": "0",
                "disabletoc": "1",
                "disableeditsection": "1",
            }
        )
        return str(payload.get("parse", {}).get("text", ""))

    async def _search_html(self, keyword: str) -> list[SearchCandidate]:
        html = await self._request_text(
            f"{self.base_url}/index.php",
            {
                "search": keyword,
                "title": "Special:搜索",
                "profile": "default",
                "fulltext": "1",
            },
        )

        candidates: list[SearchCandidate] = []
        seen: set[str] = set()
        for href_title, title in _SEARCH_RESULT_RE.findall(html):
            clean_title = unescape(title).strip()
            if not clean_title or clean_title in seen:
                continue
            seen.add(clean_title)
            candidates.append(
                SearchCandidate(
                    title=clean_title,
                    url=f"{self.base_url}/{href_title}",
                )
            )
            if len(candidates) >= self.candidate_limit:
                break
        return candidates

    async def _fetch_page_entry(
        self,
        title: str,
        keyword: str,
        candidates: list[SearchCandidate],
        snippet: str = "",
    ) -> Optional[WikiEntry]:
        response = await self._request_page(title)
        page_text = _extract_page_text(response.text)
        actual_title = _extract_title_from_html(response.text) or _derive_title_from_url(str(response.url)) or title
        if not page_text or _is_missing_page(page_text, actual_title):
            return None

        entry = _build_entry_from_page_text(
            title=actual_title,
            url=str(response.url),
            raw_html=response.text,
            page_text=page_text,
            snippet=snippet,
            candidates=candidates,
            keyword=keyword,
        )
        return entry if _looks_like_pet_entry(entry, page_text) else None

    async def _fetch_skill_entry(
        self,
        title: str,
        keyword: str,
        candidates: list[SearchCandidate],
        snippet: str = "",
    ) -> Optional[SkillEntry]:
        response = await self._request_page(title)
        page_text = _extract_page_text(response.text)
        actual_title = _extract_title_from_html(response.text) or _derive_title_from_url(str(response.url)) or title
        if not page_text or _is_missing_page(page_text, actual_title):
            return None

        entry = _build_skill_entry_from_page_text(
            title=actual_title,
            url=str(response.url),
            raw_html=response.text,
            page_text=page_text,
            snippet=snippet,
            candidates=candidates,
            keyword=keyword,
        )
        return entry if entry and _looks_like_skill_entry(entry, page_text) else None

    async def _request_json(self, params: dict[str, str]) -> dict:
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._build_headers(),
            follow_redirects=True,
        ) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            return response.json()

    async def _request_text(self, url: str, params: dict[str, str]) -> str:
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._build_headers(referer=self.base_url),
            follow_redirects=True,
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text

    async def _request_page(self, title: str) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        candidates = [
            build_page_url(self.base_url, title),
            f"{self.base_url}/index.php?title={quote(title, safe='')}",
            f"{self.base_url}/index.php?search={quote(title, safe='')}&title=Special:%E6%90%9C%E7%B4%A2&profile=default&fulltext=1",
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._build_headers(referer=self.base_url),
            follow_redirects=True,
        ) as client:
            for candidate_url in candidates:
                try:
                    response = await client.get(candidate_url)
                    response.raise_for_status()
                    return response
                except httpx.HTTPError as exc:
                    last_error = exc

        if last_error is not None:
            raise last_error
        raise httpx.HTTPError("request page failed")

    def _build_headers(self, referer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if referer:
            headers["Referer"] = referer
        return headers


def extract_types(cleaned_page_text: str) -> list[str]:
    lines = _split_lines(cleaned_page_text)
    types: list[str] = []
    feature_index = lines.index("特性") if "特性" in lines else len(lines)
    for line in lines[:feature_index]:
        for type_name in _IMAGE_TYPE_RE.findall(line):
            if type_name not in types:
                types.append(type_name)
        if len(types) >= 2:
            break
    return types


def extract_type_icons(raw_html: str, types: list[str]) -> list[tuple[str, str]]:
    icon_map: dict[str, str] = {}
    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        if not src or not alt:
            continue

        parsed_type = _parse_type_icon_alt(alt)
        if not parsed_type:
            continue
        type_name = parsed_type
        if type_name and type_name not in icon_map:
            icon_map[type_name] = src

    return [(type_name, icon_map.get(type_name, "")) for type_name in types]


def extract_trait_icon_url(raw_html: str, trait_name: str) -> str:
    trait_name = trait_name.strip()
    if not trait_name:
        return ""

    target = _strip_parenthetical(trait_name)
    best_match: tuple[int, str] | None = None

    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        title = unescape(attrs.get("title", "")).strip()
        if not src:
            continue

        candidate_name = _extract_trait_candidate_name(alt, title)
        if not candidate_name:
            continue

        candidate_normalized = _strip_parenthetical(candidate_name)
        score = 0
        if candidate_normalized == target:
            score += 100
        elif target and (target in candidate_normalized or candidate_normalized in target):
            score += 60

        if title and _strip_parenthetical(title) == target:
            score += 30
        if alt and _strip_parenthetical(alt.replace(".png", "")) == target:
            score += 20

        width_text = attrs.get("width", "")
        height_text = attrs.get("height", "")
        if width_text.isdigit() and height_text.isdigit() and width_text == height_text:
            score += 5

        if score <= 0:
            continue

        if best_match is None or score > best_match[0]:
            best_match = (score, src)

    return best_match[1] if best_match else ""


def build_restraint_icon_rows(raw_html: str, restraint: RestraintProfile | None) -> list[RestraintIconRow]:
    if restraint is None:
        return []

    icon_map = {name: icon for name, icon in extract_type_icons(raw_html, _collect_restraint_types(restraint))}
    mapping = [
        ("克制", restraint.restrain),
        ("被克制", restraint.restrained_by),
        ("抵抗", restraint.resist),
        ("被抵抗", restraint.resisted_by),
    ]
    rows: list[RestraintIconRow] = []
    for label, values in mapping:
        rows.append(
            RestraintIconRow(
                label=label,
                items=[(value, icon_map.get(value, "")) for value in values],
            )
        )
    return rows


def extract_preview_image_url(raw_html: str, title: str) -> str:
    matches: list[tuple[int, str]] = []
    normalized_title = normalize_keyword(title)

    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        if not src or not alt:
            continue

        normalized_alt = normalize_keyword(alt)
        score = 0
        if "页面宠物立绘" in normalized_alt and "异色" not in normalized_alt:
            score += 100
        if normalized_title and normalized_title in normalized_alt:
            score += 30
        if "立绘" in alt:
            score += 20
        if "异色" in alt or "宠物蛋" in alt or "果实" in alt:
            score -= 50

        if score > 0:
            matches.append((score, src))

    if not matches:
        return ""

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def extract_pet_variant_image_url(raw_html: str, title: str, variant: str) -> str:
    slot_map = {"果实": 3, "宠物蛋": 4}
    slot_index = slot_map.get(variant)
    if slot_index is not None:
        slot_image_url = _extract_variant_slot_image_url(raw_html, title, slot_index)
        if slot_image_url:
            return slot_image_url

    matches: list[tuple[int, str]] = []
    normalized_title = normalize_keyword(title)
    normalized_variant = normalize_keyword(variant)
    prefer_named_asset = variant in {"宠物蛋", "果实"}

    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        img_title = unescape(attrs.get("title", "")).strip()
        if not src:
            continue

        normalized_alt = normalize_keyword(alt)
        normalized_img_title = normalize_keyword(img_title)
        combined = f"{normalized_alt} {normalized_img_title}".strip()
        score = 0
        if "页面宠物立绘" in combined and normalized_variant in combined:
            score += 120
        elif normalized_variant in combined and "立绘" in combined:
            score += 90
        elif normalized_variant in combined:
            score += 50

        if normalized_title and normalized_title in combined:
            score += 30
        elif prefer_named_asset:
            score -= 25

        if variant != "宠物蛋" and "宠物蛋" in combined:
            score -= 50
        if variant != "果实" and "果实" in combined:
            score -= 50
        if alt in GENERIC_IMAGE_ALTS and normalized_variant not in combined:
            score -= 80

        width_text = attrs.get("width", "")
        height_text = attrs.get("height", "")
        if width_text.isdigit() and height_text.isdigit() and width_text == height_text:
            score += 5

        if score > 0:
            matches.append((score, src))

    if not matches:
        for tag in _IMG_TAG_RE.findall(raw_html):
            attrs = _parse_attrs(tag)
            src = _normalize_image_src(attrs.get("src", ""))
            alt = unescape(attrs.get("alt", "")).strip()
            img_title = unescape(attrs.get("title", "")).strip()
            combined = normalize_keyword(f"{alt} {img_title}")
            if not src or normalized_variant not in combined:
                continue
            if variant != "宠物蛋" and "宠物蛋" in combined:
                continue
            if variant != "果实" and "果实" in combined:
                continue
            matches.append((10, src))

    if not matches:
        for href_double, href_single, inner_html in _A_TAG_RE.findall(raw_html):
            href = _normalize_image_src(href_double or href_single)
            if not href or not re.search(r"\.(?:png|jpg|jpeg|webp)(?:$|\?)", href, re.IGNORECASE):
                continue

            inner_text = strip_html(inner_html)
            normalized_inner = normalize_keyword(inner_text)
            score = 0
            if normalized_variant in normalized_inner:
                score += 30
            if "页面宠物立绘" in normalized_inner and normalized_variant in normalized_inner:
                score += 60
            if normalized_title and normalized_title in normalized_inner:
                score += 20
            elif prefer_named_asset:
                score -= 20
            if variant != "宠物蛋" and "宠物蛋" in normalized_inner:
                score -= 40
            if variant != "果实" and "果实" in normalized_inner:
                score -= 40

            if score > 0:
                matches.append((score, href))

    if not matches:
        return ""

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def extract_shiny_image_url(raw_html: str, title: str) -> str:
    return extract_pet_variant_image_url(raw_html, title, "异色")


def extract_egg_image_url(raw_html: str, title: str) -> str:
    return extract_pet_variant_image_url(raw_html, title, "宠物蛋")


def extract_fruit_image_url(raw_html: str, title: str) -> str:
    return extract_pet_variant_image_url(raw_html, title, "果实")


def _extract_variant_slot_image_url(raw_html: str, title: str, slot_index: int) -> str:
    normalized_title = normalize_keyword(title)
    for index_double, index_single, inner_html in _VARIANT_SLOT_RE.findall(raw_html):
        index_text = index_double or index_single
        if str(slot_index) != index_text:
            continue

        for tag in _IMG_TAG_RE.findall(inner_html):
            attrs = _parse_attrs(tag)
            src = _normalize_image_src(attrs.get("src", ""))
            alt = unescape(attrs.get("alt", "")).strip()
            img_title = unescape(attrs.get("title", "")).strip()
            if not src:
                continue

            combined = normalize_keyword(f"{alt} {img_title}")
            if normalized_title and normalized_title in combined:
                return src
            if alt or img_title:
                return src
    return ""


def extract_evolution_image_urls(raw_html: str) -> list[str]:
    ordered_block_urls = _extract_ordered_evolution_block_urls(raw_html)
    if ordered_block_urls:
        return ordered_block_urls[:5]

    ordered_matches: list[tuple[int, str, str]] = []
    urls: list[str] = []
    seen_keys: set[str] = set()
    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        class_name = attrs.get("class", "")
        normalized_alt = normalize_keyword(alt)
        if not src or not alt:
            continue
        if "页面宠物立绘" not in normalized_alt:
            continue
        if "异色" in alt or "果实" in alt or "宠物蛋" in alt:
            continue

        class_match = _EVOLUTION_CLASS_RE.search(class_name)
        if class_match:
            ordered_matches.append((int(class_match.group(1)), src, alt))
            continue

        dedupe_key = _portrait_dedupe_key(alt, src)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        urls.append(src)

    if ordered_matches:
        ordered_urls: list[str] = []
        seen_ordered: set[str] = set()
        for _, src, alt in sorted(ordered_matches, key=lambda item: item[0]):
            dedupe_key = _portrait_dedupe_key(alt, src)
            if dedupe_key in seen_ordered:
                continue
            seen_ordered.add(dedupe_key)
            ordered_urls.append(src)
        return ordered_urls[:5]

    return urls[:5]


def extract_evolution_chain(cleaned_page_text: str, raw_html: str, title: str) -> list[str]:
    lines = _split_lines(cleaned_page_text)
    if "进化链" not in lines:
        return _extract_evolution_chain_from_images(raw_html, title)

    start = lines.index("进化链") + 1
    chain: list[str] = []
    for line in lines[start:]:
        if line in EVOLUTION_STOP_LABELS or _SECTION_STOP_RE.match(line):
            break
        if _should_skip_evolution_line(line):
            continue
        if line not in chain:
            chain.append(line)

    chain = [item for item in chain if item not in EVOLUTION_NOISE_TERMS and "条件" not in item]
    if chain:
        return chain
    return _extract_evolution_chain_from_images(raw_html, title)


def _build_entry_from_page_text(
    title: str,
    url: str,
    raw_html: str,
    page_text: str,
    snippet: str,
    candidates: list[SearchCandidate],
    keyword: str,
) -> WikiEntry:
    types = extract_types(page_text)
    trait_name, trait_desc = extract_trait(page_text)
    restraint = extract_restraint(page_text)
    return WikiEntry(
        title=title,
        url=url,
        summary=extract_summary(page_text) or snippet,
        snippet=snippet,
        is_exact_match=normalize_keyword(title) == normalize_keyword(keyword),
        image_url=extract_preview_image_url(raw_html, title),
        shiny_image_url=extract_shiny_image_url(raw_html, title),
        egg_image_url=extract_egg_image_url(raw_html, title),
        fruit_image_url=extract_fruit_image_url(raw_html, title),
        types=types,
        type_icons=extract_type_icons(raw_html, types),
        evolution_image_urls=extract_evolution_image_urls(raw_html),
        evolution_chain=extract_evolution_chain(page_text, raw_html, title),
        total_species_value=extract_total_species_value(page_text),
        stats=extract_named_fields(page_text, STAT_LABELS),
        profile_fields=extract_named_fields(page_text, PROFILE_LABELS),
        trait_name=trait_name,
        trait_icon_url=extract_trait_icon_url(raw_html, trait_name),
        trait_desc=trait_desc,
        restraint=restraint,
        restraint_icon_rows=build_restraint_icon_rows(raw_html, restraint),
        candidates=candidates,
    )


def _build_skill_entry_from_page_text(
    title: str,
    url: str,
    raw_html: str,
    page_text: str,
    snippet: str,
    candidates: list[SearchCandidate],
    keyword: str,
) -> SkillEntry | None:
    type_names = extract_types(page_text) or _extract_skill_type_names(page_text)
    type_name = type_names[0] if type_names else ""
    category_name = extract_skill_category(page_text, raw_html)
    cost = extract_skill_field(page_text, ("耗能", "PP"))
    power = extract_skill_field(page_text, ("技能威力", "威力"))
    effect = extract_skill_effect(page_text)
    learners = extract_skill_learners(page_text)
    type_icon_url = extract_type_icons(raw_html, [type_name])[0][1] if type_name else ""
    category_icon_url = extract_skill_category_icon_url(raw_html, category_name)
    skill_icon_url = extract_skill_icon_url(raw_html, title)

    entry = SkillEntry(
        title=title,
        url=url,
        snippet=snippet,
        is_exact_match=normalize_keyword(title) == normalize_keyword(keyword),
        type_name=type_name,
        type_icon_url=type_icon_url,
        category_name=category_name,
        category_icon_url=category_icon_url,
        power=power,
        cost=cost,
        effect=effect,
        skill_icon_url=skill_icon_url,
        learners=learners,
        candidates=candidates,
    )
    return entry if _looks_like_skill_entry(entry, page_text) else None


def extract_named_fields(cleaned_page_text: str, labels: tuple[str, ...]) -> list[tuple[str, str]]:
    lines = _split_lines(cleaned_page_text)
    found: dict[str, str] = {}

    for index, line in enumerate(lines):
        compact_line = line.replace("：", ":")

        for label in labels:
            if label in found:
                continue

            inline_value = _extract_inline_value(compact_line, label)
            if inline_value:
                found[label] = inline_value
                continue

            if compact_line == label and index + 1 < len(lines):
                next_value = _clean_field_value(lines[index + 1])
                if next_value:
                    found[label] = next_value
                    continue

            if _looks_like_label_line(compact_line, label):
                next_value = _extract_next_value(lines, index)
                if next_value:
                    found[label] = next_value

    return [(label, found[label]) for label in labels if label in found]


def extract_total_species_value(cleaned_page_text: str) -> str:
    for label, value in extract_named_fields(cleaned_page_text, TOTAL_VALUE_LABELS):
        if value:
            return value
    return ""


def extract_skill_field(cleaned_page_text: str, labels: tuple[str, ...]) -> str:
    lines = _split_lines(cleaned_page_text)
    for index, line in enumerate(lines):
        compact_line = line.replace("：", ":")
        for label in labels:
            inline_value = _extract_inline_value(compact_line, label)
            if inline_value:
                return inline_value

            if compact_line == label:
                previous_value = _extract_prev_value(lines, index)
                if previous_value:
                    return previous_value
                next_value = _extract_next_value(lines, index)
                if next_value:
                    return next_value

            if compact_line.endswith(label):
                previous_part = _clean_field_value(compact_line[: -len(label)])
                if previous_part:
                    return previous_part

            if compact_line.startswith(label):
                suffix = _clean_field_value(compact_line[len(label) :])
                if suffix:
                    return suffix

    return ""


def extract_skill_category(cleaned_page_text: str, raw_html: str) -> str:
    icon_value = _extract_skill_category_name_from_html(raw_html)
    if icon_value:
        return icon_value

    lines = _split_lines(cleaned_page_text)
    for line in lines[:20]:
        candidate = line.strip()
        if candidate in SKILL_CATEGORY_NAMES:
            return candidate
    return ""


def extract_skill_effect(cleaned_page_text: str) -> str:
    lines = _split_lines(cleaned_page_text)
    if not lines:
        return ""

    for index, line in enumerate(lines):
        if line.startswith(("✦", "◆", "•", "●")):
            effect_lines = [line.lstrip("✦◆•● ").strip()]
            for extra in lines[index + 1 :]:
                if extra in SKILL_SECTION_STOP_LABELS or _SECTION_STOP_RE.match(extra):
                    break
                if extra in {"耗能", "PP", "技能威力", "威力"}:
                    continue
                if _clean_field_value(extra):
                    if extra not in effect_lines:
                        effect_lines.append(extra)
                        if len(effect_lines) >= 3:
                            break
            return "\n".join(line for line in effect_lines if line)

    for index, line in enumerate(lines):
        if line in {"技能效果", "效果"}:
            effect_lines: list[str] = []
            for extra in lines[index + 1 :]:
                if extra in SKILL_SECTION_STOP_LABELS or _SECTION_STOP_RE.match(extra):
                    break
                if extra and not extra.endswith(".png") and not extra.startswith("Image:"):
                    effect_lines.append(extra)
                    if len(effect_lines) >= 3:
                        break
            if effect_lines:
                return "\n".join(effect_lines)

    return ""


def extract_skill_learners(cleaned_page_text: str) -> list[str]:
    lines = _split_lines(cleaned_page_text)
    learners: list[str] = []
    start_index = next(
        (
            idx
            for idx, line in enumerate(lines)
            if line in {"可以学会的精灵", "可以学会的精灵:", "可学会的精灵", "可学会的精灵:"}
        ),
        -1,
    )
    if start_index < 0:
        return learners

    for line in lines[start_index + 1 :]:
        if line in SKILL_SECTION_STOP_LABELS or _SECTION_STOP_RE.match(line):
            break
        candidate = line.strip(":： ")
        if not candidate or candidate.startswith("Image:") or candidate.endswith(".png"):
            continue
        if candidate in learners:
            continue
        if candidate in {"耗能", "PP", "技能威力", "威力", "效果", "技能效果"}:
            continue
        if re.fullmatch(r"[0-9./%]+", candidate):
            continue
        learners.append(candidate)
        if len(learners) >= 12:
            break
    return learners


def _extract_skill_type_names(cleaned_page_text: str) -> list[str]:
    lines = _split_lines(cleaned_page_text)
    types: list[str] = []
    for line in lines[:18]:
        candidate = line.strip()
        if candidate.endswith("系") and 1 <= len(candidate) <= 4:
            type_name = candidate[:-1]
            if type_name and type_name not in types:
                types.append(type_name)
    return types


def extract_trait(cleaned_page_text: str) -> tuple[str, str]:
    lines = _split_lines(cleaned_page_text)
    if "特性" not in lines:
        return "", ""

    start = lines.index("特性") + 1
    end = min(start + 16, len(lines))
    for idx, line in enumerate(lines[start:], start=start):
        if idx <= start:
            continue
        if line in {"精灵属性", "选择性格", "进化链", "克制表", "技能表", "图鉴课题", "获得方式", "获取方式"}:
            end = idx
            break
        if _SECTION_STOP_RE.match(line):
            end = idx
            break
    trait_lines = [
        line
        for line in lines[start:end]
        if line and not line.startswith("Image:") and "属性 " not in line and not line.endswith(".png")
    ]
    if not trait_lines:
        return "", ""

    trait_name = trait_lines[0]
    trait_desc = ""
    for line in trait_lines[1:]:
        if line == trait_name:
            continue
        if len(line) >= 4:
            trait_desc = line
            break
    return trait_name, trait_desc


def extract_summary(cleaned_page_text: str) -> str:
    lines = _split_lines(cleaned_page_text)
    if not lines:
        return ""

    if "特性" in lines:
        end = lines.index("特性")
        if "精灵分布:行踪神秘" in lines[:end]:
            start = lines.index("精灵分布:行踪神秘")
            summary_lines = _clean_summary_lines(lines[start:end])
            if summary_lines:
                return "\n".join(summary_lines)

        distribution_index = next((idx for idx, line in enumerate(lines[:end]) if line.startswith("精灵分布:")), None)
        if distribution_index is not None:
            summary_lines = _clean_summary_lines(lines[distribution_index:end])
            if summary_lines:
                return "\n".join(summary_lines)

        summary_lines = _clean_summary_lines(lines[max(0, end - 4) : end])
        if summary_lines:
            return "\n".join(summary_lines)

    return "\n".join(_clean_summary_lines(lines[:4]))


def extract_restraint(cleaned_page_text: str) -> RestraintProfile | None:
    lines = _split_lines(cleaned_page_text)
    if "克制表" not in lines:
        return None

    section_lines: list[str] = []
    for line in lines[lines.index("克制表") + 1 :]:
        if _SECTION_STOP_RE.match(line):
            break
        section_lines.append(line)

    if not section_lines:
        return None

    mapping = {
        "克制": "restrain",
        "被克制": "restrained_by",
        "抵抗": "resist",
        "被抵抗": "resisted_by",
    }
    profile = RestraintProfile()
    current_label = ""

    for line in section_lines:
        if line in mapping:
            current_label = line
            continue
        if not current_label:
            continue

        types = _extract_types_from_line(line)
        if not types:
            continue

        target = getattr(profile, mapping[current_label])
        for type_name in types:
            if type_name not in target:
                target.append(type_name)

    if any([profile.restrain, profile.restrained_by, profile.resist, profile.resisted_by]):
        return profile
    return None


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _extract_types_from_line(value: str) -> list[str]:
    return [match for match in _IMAGE_TYPE_RE.findall(value) if match]


def _collect_restraint_types(restraint: RestraintProfile) -> list[str]:
    result: list[str] = []
    for values in (restraint.restrain, restraint.restrained_by, restraint.resist, restraint.resisted_by):
        for value in values:
            if value not in result:
                result.append(value)
    return result


def _clean_summary_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        if not line:
            continue
        if line in {"特性", "精灵属性", "选择性格", "进化链", "克制表"}:
            continue
        if line.startswith("NO") and "." in line:
            continue
        if line.startswith("图标 ") or line.startswith("Image:"):
            continue
        if line.endswith(".png"):
            continue
        if re.fullmatch(r"[★☆\s]+", line):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", line):
            continue
        cleaned.append(line)
    return cleaned


def _should_skip_evolution_line(line: str) -> bool:
    if not line:
        return True
    if line in EVOLUTION_NOISE_TERMS:
        return True
    if "条件" in line:
        return True
    if line.startswith("进化条件"):
        return True
    if line.startswith("图标 ") or line.startswith("Image:"):
        return True
    if line.endswith(".png"):
        return True
    if line in TOTAL_VALUE_LABELS or line in STAT_LABELS or line in PROFILE_LABELS:
        return True
    if re.fullmatch(r"[★☆\s>→\-]+", line):
        return True
    if re.fullmatch(r"\d+(?:\.\d+)?", line):
        return True
    return False


def _extract_ordered_evolution_block_urls(raw_html: str) -> list[str]:
    matches: list[tuple[int, str, str]] = []
    for block in _EVOLUTION_OPEN_TAG_RE.finditer(raw_html):
        index_text = block.group("index1") or block.group("index2") or ""
        if not index_text:
            continue

        search_window = raw_html[block.end() : block.end() + 1200]
        img_tag_match = _IMG_TAG_RE.search(search_window)
        if not img_tag_match:
            continue

        attrs = _parse_attrs(img_tag_match.group(0))
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        if not src or not alt:
            continue
        if "异色" in alt or "果实" in alt or "宠物蛋" in alt:
            continue
        matches.append((int(index_text), src, alt))

    if not matches:
        return []

    urls: list[str] = []
    seen_keys: set[str] = set()
    for _, src, alt in sorted(matches, key=lambda item: item[0]):
        dedupe_key = _portrait_dedupe_key(alt, src)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        urls.append(src)
    return urls


def _extract_evolution_chain_from_images(raw_html: str, title: str) -> list[str]:
    chain: list[str] = []
    normalized_title = normalize_keyword(title)

    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        alt = unescape(attrs.get("alt", "")).strip()
        candidate = _clean_evolution_alt(alt)
        if not candidate:
            continue
        if candidate not in chain:
            chain.append(candidate)

    if title:
        if not chain:
            return [title]
        if not any(normalize_keyword(item) == normalized_title for item in chain):
            chain.append(title)

    return chain


def _clean_evolution_alt(alt: str) -> str:
    candidate = alt.strip()
    if not candidate:
        return ""
    if candidate in GENERIC_IMAGE_ALTS:
        return ""
    if candidate in EVOLUTION_NOISE_TERMS:
        return ""
    if candidate.startswith("页面 ") or candidate.startswith("图标 ") or candidate.startswith("界面 "):
        return ""
    if any(token in candidate for token in ("属性", "立绘", "本体", "异色", "果实", "宠物蛋", "进化条件")):
        return ""
    if candidate.endswith(".png"):
        candidate = candidate[:-4].strip()
    if not candidate or candidate in EVOLUTION_NOISE_TERMS:
        return ""
    if "条件" in candidate:
        return ""
    if re.fullmatch(r"[A-Za-z0-9 _\-.]+", candidate):
        return ""
    return candidate


def _parse_attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, double_quoted, single_quoted in _ATTR_RE.findall(tag):
        attrs[key] = double_quoted or single_quoted
    return attrs


def _parse_type_icon_alt(alt: str) -> str:
    normalized = _normalize_alt(alt)
    if not normalized or any(term in normalized for term in ICON_EXCLUDE_TERMS):
        return ""

    for prefix in ("图标 宠物 属性 ", "宠物 属性 ", "图标 属性 ", "属性 "):
        if normalized.startswith(prefix) and normalized.endswith(".png"):
            value = normalized[len(prefix) : -4].strip()
            if value and " " not in value:
                return value
    return ""


def _parse_trait_icon_alt(alt: str) -> str:
    normalized = _normalize_alt(alt)
    if not normalized or any(term in normalized for term in ICON_EXCLUDE_TERMS):
        return ""

    for prefix in ("图标 特性 ", "特性 "):
        if normalized.startswith(prefix) and normalized.endswith(".png"):
            value = normalized[len(prefix) : -4].strip()
            return value
    return ""


def _extract_trait_candidate_name(alt: str, title: str) -> str:
    title_normalized = _normalize_alt(title)
    alt_normalized = _normalize_alt(alt)

    if title_normalized and not any(term in title_normalized for term in ICON_EXCLUDE_TERMS):
        if not title_normalized.endswith(".png"):
            return title_normalized
        return title_normalized[:-4].strip()

    return _parse_trait_icon_alt(alt_normalized)


def _parse_skill_category_icon_alt(alt: str) -> str:
    normalized = _normalize_alt(alt)
    if not normalized:
        return ""

    for prefix in ("图标 技能 技能分类 ", "技能 技能分类 ", "图标 技能分类 ", "技能分类 "):
        if normalized.startswith(prefix) and normalized.endswith(".png"):
            value = normalized[len(prefix) : -4].strip()
            if value in SKILL_CATEGORY_NAMES:
                return value
    return ""


def _extract_skill_category_name_from_html(raw_html: str) -> str:
    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        alt = unescape(attrs.get("alt", "")).strip()
        title = unescape(attrs.get("title", "")).strip()
        candidate = _parse_skill_category_icon_alt(alt) or _parse_skill_category_icon_alt(title)
        if candidate:
            return candidate
    return ""


def extract_skill_category_icon_url(raw_html: str, category_name: str) -> str:
    if not category_name:
        return ""

    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        title = unescape(attrs.get("title", "")).strip()
        candidate = _parse_skill_category_icon_alt(alt) or _parse_skill_category_icon_alt(title)
        if candidate == category_name and src:
            return src
    return ""


def extract_skill_icon_url(raw_html: str, title: str) -> str:
    target = normalize_keyword(title)
    best_match: tuple[int, str] | None = None
    for tag in _IMG_TAG_RE.findall(raw_html):
        attrs = _parse_attrs(tag)
        src = _normalize_image_src(attrs.get("src", ""))
        alt = unescape(attrs.get("alt", "")).strip()
        img_title = unescape(attrs.get("title", "")).strip()
        if not src:
            continue

        candidate = img_title or alt
        candidate_normalized = normalize_keyword(candidate.replace(".png", ""))
        if not candidate_normalized:
            continue
        if any(token in candidate for token in ("属性", "技能分类", "宠物", "立绘", "进化")):
            continue

        score = 0
        if candidate_normalized == target:
            score += 100
        elif target and target in candidate_normalized:
            score += 50

        width_text = attrs.get("width", "")
        height_text = attrs.get("height", "")
        if width_text.isdigit() and height_text.isdigit() and width_text == height_text:
            score += 10

        if score > 0 and (best_match is None or score > best_match[0]):
            best_match = (score, src)

    return best_match[1] if best_match else ""


def _normalize_alt(alt: str) -> str:
    return re.sub(r"\s+", " ", alt.strip())


def _strip_parenthetical(value: str) -> str:
    return normalize_keyword(re.sub(r"[（(].*?[）)]", "", value))


def _portrait_dedupe_key(alt: str, src: str) -> str:
    candidate = alt.strip()
    if candidate.endswith(".png"):
        candidate = candidate[:-4].strip()
    candidate = re.sub(r"\s+\d+$", "", candidate).strip()
    if "立绘" in candidate:
        candidate = candidate.split("立绘", 1)[-1].strip()
    if candidate:
        return normalize_keyword(candidate)
    return _canonical_image_path(src)


def _extract_inline_value(line: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}\s*[:：]?\s*([^\s]+)")
    match = pattern.search(line)
    if not match:
        return ""
    return _clean_field_value(match.group(1))


def _clean_field_value(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if candidate in STAT_LABELS or candidate in PROFILE_LABELS or candidate in TOTAL_VALUE_LABELS:
        return ""
    if candidate in {"特性", "精灵属性", "选择性格", "进化链", "克制表"}:
        return ""
    if candidate.startswith("图标 ") or candidate.startswith("Image:"):
        return ""
    if candidate.endswith(".png"):
        return ""
    match = _FIELD_VALUE_RE.search(candidate)
    return match.group(1) if match else ""


def _looks_like_label_line(line: str, label: str) -> bool:
    if label not in line:
        return False
    return line.endswith(label) or ".png" in line or line.startswith(label)


def _extract_next_value(lines: list[str], index: int) -> str:
    for next_index in range(index + 1, min(index + 4, len(lines))):
        value = _clean_field_value(lines[next_index])
        if value:
            return value
    return ""


def _extract_prev_value(lines: list[str], index: int) -> str:
    for previous_index in range(index - 1, max(index - 4, -1), -1):
        value = _clean_field_value(lines[previous_index])
        if value:
            return value
    return ""


def _looks_like_pet_entry(entry: WikiEntry, page_text: str = "") -> bool:
    if not entry:
        return False

    signals = 0
    if entry.trait_name:
        signals += 1
    if entry.total_species_value:
        signals += 1
    if len(entry.stats) >= 3:
        signals += 1
    if entry.profile_fields:
        signals += 1
    if entry.restraint and any(
        (entry.restraint.restrain, entry.restraint.restrained_by, entry.restraint.resist, entry.restraint.resisted_by)
    ):
        signals += 1
    if len(entry.evolution_image_urls) >= 2 or len(entry.evolution_chain) >= 2:
        signals += 1

    normalized = normalize_keyword(page_text)
    if any(marker in normalized for marker in ("特性", "进化链", "克制表", "精灵属性", "种族值")):
        signals += 1

    return signals >= 2


def _looks_like_skill_entry(entry: SkillEntry, page_text: str = "") -> bool:
    if not entry:
        return False

    strong_signals = 0
    weak_signals = 0
    if entry.category_name in SKILL_CATEGORY_NAMES:
        strong_signals += 1
    if entry.cost:
        strong_signals += 1
    if entry.power:
        strong_signals += 1
    if entry.learners:
        strong_signals += 1
    if entry.effect:
        weak_signals += 1
    if entry.skill_icon_url:
        weak_signals += 1
    if entry.type_name:
        weak_signals += 1

    normalized = normalize_keyword(page_text)
    skill_markers = ("耗能", "技能威力", "威力", "可以学会的精灵", "可学会的精灵", "技能效果")
    pet_markers = ("特性", "进化链", "克制表", "精灵属性", "种族值")
    has_skill_marker = any(marker in normalized for marker in skill_markers)
    has_unique_skill_marker = any(marker in normalized for marker in ("可以学会的精灵", "可学会的精灵", "技能效果"))
    pet_marker_hits = sum(1 for marker in pet_markers if marker in normalized)

    if has_skill_marker:
        strong_signals += 1

    if pet_marker_hits >= 2 and not (entry.learners or has_unique_skill_marker):
        return False

    if pet_marker_hits >= 2 and strong_signals < 3:
        return False

    return strong_signals >= 2 or (strong_signals >= 1 and weak_signals >= 2 and has_skill_marker)


def _extract_page_text(html: str) -> str:
    body_match = _PAGE_BODY_RE.search(html)
    return strip_html(body_match.group(1) if body_match else html)


def _extract_title_from_html(html: str) -> str:
    match = _PAGE_TITLE_RE.search(html)
    if not match:
        return ""
    title = strip_html(match.group(1))
    return title.split(" - ", 1)[0].strip()


def _derive_title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    return unquote(path.rsplit("/", 1)[-1]).replace("_", " ").strip()


def _is_missing_page(page_text: str, title: str) -> bool:
    compact = page_text.replace(" ", "")
    missing_markers = (
        "当前页面不存在",
        "您可以创建此页面",
        "没有这个页面",
        "搜索结果",
        "创建页面",
    )
    if any(marker in compact for marker in missing_markers):
        return True
    if title and normalize_keyword(title) not in normalize_keyword(compact[:2000]):
        return False
    return False


def _normalize_image_src(src: str) -> str:
    value = src.strip()
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return f"https://wiki.biligame.com{value}"
    return value


def _canonical_image_path(src: str) -> str:
    normalized = _normalize_image_src(src)
    parsed = urlparse(normalized)
    path = parsed.path
    if "/thumb/" in path:
        thumb_part = path.split("/thumb/", 1)[1]
        segments = thumb_part.split("/")
        if len(segments) >= 4:
            path = "/images/" + "/".join(segments[:3])
    return normalize_keyword(unquote(path))
