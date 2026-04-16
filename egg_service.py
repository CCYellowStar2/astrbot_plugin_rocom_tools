from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx

try:
    from .matching import fuzzy_name_score, normalize_text
except ImportError:  # pragma: no cover
    from matching import fuzzy_name_score, normalize_text  # type: ignore[no-redef]


DEFAULT_EGG_API_BASE = "https://roco.gptvip.chat/api"
DEFAULT_EGG_API_TIMEOUT = 12.0
DEFAULT_SEARCH_LIMIT = 16
DEFAULT_GROUP_PAGE_SIZE = 100
MATCH_THRESHOLD = 58
GROUP_ID_TO_NAME = {
    1: "无法孵蛋",
    2: "巨灵组",
    3: "两栖组",
    4: "昆虫组",
    5: "天空组",
    6: "动物组",
    7: "妖精组",
    8: "植物组",
    9: "拟人组",
    10: "软体组",
    11: "大地组",
    12: "魔力组",
    13: "海洋组",
    14: "龙组",
    15: "机械组",
}


@dataclass
class EggPet:
    base_id: str
    page_name: str
    display_name: str
    can_hatch: bool
    egg_group_display: str
    egg_group_ids: list[int] = field(default_factory=list)
    egg_group_names: list[str] = field(default_factory=list)
    maternal_text: str = ""
    paternal_text: str = ""
    hatch_hint: str = ""
    hatch_status_text: str = ""
    class_name: str = ""
    type_name: str = ""
    avatar_url: str = ""
    body_url: str = ""
    species_code: str = ""


@dataclass
class EggLookupResult:
    pet: EggPet | None
    candidates: list[str] = field(default_factory=list)
    paternal_count: int = 0
    paternal_preview: list[EggPet] = field(default_factory=list)


@dataclass
class EggPairResult:
    left: EggPet
    right: EggPet
    can_breed: bool
    common_egg_groups: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class EggGroupLookupResult:
    group_name: str = ""
    group_id: int = 0
    description: str = ""
    member_count: int = 0
    hatchable_member_count: int = 0
    pet_names: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)


def split_egg_query_terms(text: str) -> list[str]:
    parts = str(text or "").replace("，", " ").replace("、", " ").replace(",", " ").split()
    return [part.strip() for part in parts if part.strip()]


class EggQueryService:
    def __init__(
        self,
        api_base: str = DEFAULT_EGG_API_BASE,
        timeout: float = DEFAULT_EGG_API_TIMEOUT,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        group_page_size: int = DEFAULT_GROUP_PAGE_SIZE,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.search_limit = max(int(search_limit), 1)
        self.group_page_size = max(int(group_page_size), 1)

    async def lookup_pet(self, keyword: str) -> EggLookupResult:
        query = keyword.strip()
        if not query:
            return EggLookupResult(None, [])

        payload = await self._request_json(
            "/hatch-search",
            {"q": query, "limit": str(self.search_limit)},
        )
        cards = payload.get("cards", []) if isinstance(payload, dict) else []
        selected_card, candidate_names = _pick_search_card(query, cards)
        if selected_card is None:
            return EggLookupResult(None, candidate_names)

        base_id = _extract_card_base_id(selected_card)
        if not base_id:
            return EggLookupResult(None, candidate_names)

        pet, paternal_count, paternal_preview = await self.fetch_pet_detail(base_id)
        return EggLookupResult(
            pet=pet,
            candidates=candidate_names,
            paternal_count=paternal_count,
            paternal_preview=paternal_preview,
        )

    async def fetch_pet_detail(self, base_id: str | int) -> tuple[EggPet | None, int, list[EggPet]]:
        payload = await self._request_json("/hatch-pet", {"base_id": str(base_id)})
        if not isinstance(payload, dict) or not payload.get("ok"):
            return None, 0, []

        pet = _parse_pet(payload.get("pet"))
        paternal_count = int(payload.get("paternal_count") or 0)
        paternal_preview = [_parse_pet(item) for item in payload.get("paternal_preview", [])]
        paternal_preview = [item for item in paternal_preview if item is not None]
        return pet, paternal_count, paternal_preview

    async def compatible_partners(self, pet: EggPet, limit: int = 30) -> tuple[int, list[EggPet]]:
        detail_pet, paternal_count, paternal_preview = await self.fetch_pet_detail(pet.base_id)
        if detail_pet is None:
            return 0, []
        return paternal_count, paternal_preview[:limit]

    async def check_pair(self, left: EggPet, right: EggPet) -> EggPairResult:
        payload = await self._request_json(
            "/hatch-check-pair",
            {
                "maternal_base_id": left.base_id,
                "paternal_base_id": right.base_id,
            },
        )
        if not isinstance(payload, dict):
            return EggPairResult(left=left, right=right, can_breed=False, reasons=["接口返回异常"])

        maternal = _parse_pet(payload.get("maternal")) or left
        paternal = _parse_pet(payload.get("paternal")) or right
        common_groups = [
            GROUP_ID_TO_NAME.get(int(group_id), str(group_id))
            for group_id in payload.get("common_groups", [])
            if str(group_id).strip()
        ]
        reason = str(payload.get("reason", "")).strip()
        reasons = [] if payload.get("can_breed") else ([reason] if reason else ["蛋组不兼容"])
        return EggPairResult(
            left=maternal,
            right=paternal,
            can_breed=bool(payload.get("can_breed")),
            common_egg_groups=_dedupe_texts(common_groups),
            reasons=reasons,
        )

    async def lookup_group(self, keyword: str) -> EggGroupLookupResult:
        query = keyword.strip()
        if not query:
            return EggGroupLookupResult()

        group_id, candidates = _pick_group_id(query)
        if group_id is None:
            return EggGroupLookupResult(candidates=candidates)

        page = 1
        all_cards: list[dict[str, Any]] = []
        group_info: dict[str, Any] = {}
        total_pages = 1

        while page <= total_pages:
            payload = await self._request_json(
                "/egg-group-members",
                {
                    "group_id": str(group_id),
                    "page": str(page),
                    "page_size": str(self.group_page_size),
                },
            )
            if not isinstance(payload, dict) or not payload.get("ok"):
                break

            all_cards.extend(payload.get("cards", []))
            group_info = payload.get("group", {}) if isinstance(payload.get("group"), dict) else {}
            total_pages = int(payload.get("total_pages") or 1)
            page += 1

        group_name = str(group_info.get("group_display") or GROUP_ID_TO_NAME.get(group_id, ""))
        pet_names = _extract_group_pet_names(all_cards)
        return EggGroupLookupResult(
            group_name=group_name,
            group_id=group_id,
            description=str(group_info.get("description", "")).strip(),
            member_count=int(group_info.get("member_count") or len(pet_names)),
            hatchable_member_count=int(group_info.get("hatchable_member_count") or 0),
            pet_names=pet_names,
            candidates=candidates,
        )

    async def format_single_pet_result(self, keyword: str, result: EggLookupResult, limit: int = 30) -> str:
        if result.pet is None:
            return f"没有找到与“{keyword}”相关的生蛋精灵。"

        pet = result.pet
        paternal_count = result.paternal_count
        paternal_preview = result.paternal_preview[:limit]
        if not paternal_preview and pet.base_id:
            paternal_count, paternal_preview = await self.compatible_partners(pet, limit=limit)

        lines = [f"【{pet.page_name or pet.display_name}】", f"状态: {pet.hatch_status_text or ('可生蛋' if pet.can_hatch else '暂不可生蛋')}"]
        if pet.egg_group_display:
            lines.append(f"蛋组: {pet.egg_group_display}")
        if pet.maternal_text:
            lines.append(f"母系产蛋: {pet.maternal_text}")
        if pet.paternal_text:
            lines.append(f"父系规则: {pet.paternal_text}")
        if pet.hatch_hint:
            lines.append(pet.hatch_hint)

        if paternal_preview:
            preview_names = _dedupe_texts(item.page_name or item.display_name for item in paternal_preview)
            lines.append(f"可匹配精灵(部分): {'、'.join(preview_names)}")
            if paternal_count > len(preview_names):
                lines.append(f"父系候选总数: {paternal_count}")
        elif pet.can_hatch:
            lines.append("可匹配精灵: 暂无可展示候选")

        other_titles = [name for name in result.candidates if name != (pet.page_name or pet.display_name)]
        if other_titles:
            lines.append(f"其他候选: {'、'.join(other_titles[:3])}")

        return "\n".join(lines)

    def format_pair_result(self, pair_result: EggPairResult) -> str:
        left_name = pair_result.left.page_name or pair_result.left.display_name
        right_name = pair_result.right.page_name or pair_result.right.display_name
        lines = [f"【{left_name}】 × 【{right_name}】"]

        if pair_result.can_breed:
            lines.append("结论: 可以生蛋")
            if pair_result.common_egg_groups:
                lines.append(f"共同蛋组: {'、'.join(pair_result.common_egg_groups)}")
            if pair_result.left.maternal_text:
                lines.append(f"若 {left_name} 为母系: {pair_result.left.maternal_text}")
            if pair_result.right.maternal_text:
                lines.append(f"若 {right_name} 为母系: {pair_result.right.maternal_text}")
            return "\n".join(lines)

        lines.append("结论: 不可以生蛋")
        if pair_result.reasons:
            lines.extend(f"原因: {reason}" for reason in pair_result.reasons)
        return "\n".join(lines)

    def format_group_result(self, keyword: str, result: EggGroupLookupResult) -> str:
        if not result.group_name:
            return f"没有找到与“{keyword}”相关的蛋组。"

        lines = [f"【{result.group_name}】", f"精灵数量: {len(result.pet_names) or result.member_count}"]
        if result.description:
            lines.append(result.description)
        if result.pet_names:
            lines.append(f"精灵列表: {'、'.join(result.pet_names)}")
        if result.hatchable_member_count:
            lines.append(f"可生蛋成员数: {result.hatchable_member_count}")
        other_groups = [name for name in result.candidates if name != result.group_name]
        if other_groups:
            lines.append(f"其他候选: {'、'.join(other_groups[:3])}")
        return "\n".join(lines)

    async def _request_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(f"{self.api_base}{path}", params=params)
            response.raise_for_status()
            return response.json()


def _parse_pet(payload: Any) -> EggPet | None:
    if not isinstance(payload, dict):
        return None

    egg_group_ids = [int(value) for value in payload.get("egg_group_ids", []) if str(value).strip()]
    egg_group_names = [GROUP_ID_TO_NAME.get(group_id, str(group_id)) for group_id in egg_group_ids]
    return EggPet(
        base_id=str(payload.get("base_id", "")).strip(),
        page_name=str(payload.get("page_name", "")).strip(),
        display_name=str(payload.get("display_name", "")).strip(),
        can_hatch=bool(payload.get("can_hatch")),
        egg_group_display=str(payload.get("egg_group_display", "")).strip(),
        egg_group_ids=egg_group_ids,
        egg_group_names=egg_group_names,
        maternal_text=str(payload.get("maternal_text", "")).strip(),
        paternal_text=str(payload.get("paternal_text", "")).strip(),
        hatch_hint=str(payload.get("hatch_hint", "")).strip(),
        hatch_status_text=str(payload.get("hatch_status_text", "")).strip(),
        class_name=str(payload.get("class_name", "")).strip(),
        type_name=str(payload.get("type_name", "")).strip(),
        avatar_url=str(payload.get("avatar_url", "")).strip(),
        body_url=str(payload.get("body_url", "")).strip(),
        species_code=str(payload.get("species_code", "") or "").strip(),
    )


def _pick_search_card(keyword: str, cards: Iterable[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    scored_cards: list[tuple[int, dict[str, Any]]] = []
    candidate_names: list[str] = []

    for card in cards:
        if not isinstance(card, dict):
            continue
        representative_name = str(card.get("representative_name", "")).strip()
        if representative_name:
            candidate_names.append(representative_name)
        score = _score_search_card(keyword, card)
        if score >= MATCH_THRESHOLD:
            scored_cards.append((score, card))

    if not scored_cards:
        return None, _dedupe_texts(candidate_names)

    scored_cards.sort(
        key=lambda item: (
            -item[0],
            normalize_text(str(item[1].get("representative_name", ""))),
        )
    )
    return scored_cards[0][1], _dedupe_texts(candidate_names)


def _score_search_card(keyword: str, card: dict[str, Any]) -> int:
    names: list[str] = []
    for value in (
        card.get("representative_name"),
        *(card.get("member_names", []) if isinstance(card.get("member_names"), list) else []),
        *(card.get("final_stage_candidates", []) if isinstance(card.get("final_stage_candidates"), list) else []),
        card.get("family_chain"),
    ):
        text = str(value or "").strip()
        if text:
            names.append(text)

    best = 0
    for index, name in enumerate(names):
        score = fuzzy_name_score(keyword, name)
        if score:
            best = max(best, score - index * 2)
    return best


def _extract_card_base_id(card: dict[str, Any]) -> str:
    representative_base_id = str(card.get("representative_base_id", "")).strip()
    if representative_base_id:
        return representative_base_id
    representative = card.get("representative", {})
    if isinstance(representative, dict):
        return str(representative.get("base_id", "")).strip()
    return ""


def _pick_group_id(keyword: str) -> tuple[int | None, list[str]]:
    scored = sorted(
        (
            (_score_group_name(keyword, group_name), group_id, group_name)
            for group_id, group_name in GROUP_ID_TO_NAME.items()
        ),
        key=lambda item: (-item[0], item[2]),
    )
    candidates = [group_name for score, _, group_name in scored if score >= MATCH_THRESHOLD][:5]
    if not candidates:
        return None, []
    for score, group_id, group_name in scored:
        if group_name == candidates[0]:
            return group_id, candidates
    return None, candidates


def _score_group_name(keyword: str, group_name: str) -> int:
    variants = [group_name]
    if group_name.endswith("组"):
        variants.append(group_name[:-1])
    return max((fuzzy_name_score(keyword, variant) for variant in variants if variant), default=0)


def _extract_group_pet_names(cards: Iterable[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        family_chain = str(card.get("family_chain", "")).strip()
        if family_chain:
            for part in family_chain.split("→"):
                for candidate in str(part).replace(",", "，").split("，"):
                    text = candidate.strip()
                    if text and text not in names:
                        names.append(text)
        representative = card.get("representative", {})
        if isinstance(representative, dict):
            for field_name in ("page_name", "display_name"):
                text = str(representative.get(field_name, "")).strip()
                if text and text not in names:
                    names.append(text)
    return names


def _dedupe_texts(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
