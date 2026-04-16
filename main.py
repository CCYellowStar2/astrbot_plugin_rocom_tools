from __future__ import annotations

from typing import Any

import httpx

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from astrbot.api import AstrBotConfig
except ImportError:  # pragma: no cover
    AstrBotConfig = dict  # type: ignore[misc,assignment]

try:
    from .egg_service import EggQueryService, split_egg_query_terms
    from .wiki_service import (
        DEFAULT_BASE_URL,
        DEFAULT_BROWSER_UA,
        DEFAULT_CANDIDATE_LIMIT,
        DEFAULT_SUMMARY_LENGTH,
        DEFAULT_TIMEOUT,
        RocomWikiClient,
        extract_keyword_from_message,
        format_lookup_message,
        format_skill_lookup_message,
    )
    from .rendering import (
        SKILL_CARD_TEMPLATE,
        WIKI_CARD_TEMPLATE,
        build_card_context,
        build_skill_card_context,
    )
except ImportError:  # pragma: no cover
    from egg_service import EggQueryService, split_egg_query_terms  # type: ignore[no-redef]
    from wiki_service import (  # type: ignore[no-redef]
        DEFAULT_BASE_URL,
        DEFAULT_BROWSER_UA,
        DEFAULT_CANDIDATE_LIMIT,
        DEFAULT_SUMMARY_LENGTH,
        DEFAULT_TIMEOUT,
        RocomWikiClient,
        extract_keyword_from_message,
        format_lookup_message,
        format_skill_lookup_message,
    )
    from rendering import (  # type: ignore[no-redef]
        SKILL_CARD_TEMPLATE,
        WIKI_CARD_TEMPLATE,
        build_card_context,
        build_skill_card_context,
    )

COMMAND_NAME = "精灵wiki"
COMMAND_ALIASES = {"rocomwiki", "洛克wiki"}
SKILL_COMMAND_NAME = "技能wiki"
SKILL_COMMAND_ALIASES = {"skillwiki", "洛克技能wiki"}
EGG_COMMAND_NAME = "生蛋查询"
EGG_COMMAND_ALIASES = {"蛋配查询", "生蛋"}
EGG_GROUP_COMMAND_NAME = "蛋组查询"
EGG_GROUP_COMMAND_ALIASES = {"蛋组", "蛋组精灵"}


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@register(
    "astrbot_plugin_rocom_tools",
    "CCYellowStar2",
    "洛克王国世界工具箱",
    "0.1.0",
    "https://github.com/CCYellowStar2/astrbot_plugin_rocom_tools",
)
class RocomWikiBotPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self.summary_length = _as_int(self.config.get("summary_length"), DEFAULT_SUMMARY_LENGTH)
        self.render_as_image = bool(self.config.get("render_as_image", True))
        self.client = RocomWikiClient(
            base_url=str(self.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/"),
            timeout=_as_float(self.config.get("request_timeout"), DEFAULT_TIMEOUT),
            candidate_limit=_as_int(self.config.get("candidate_limit"), DEFAULT_CANDIDATE_LIMIT),
            user_agent=str(self.config.get("user_agent") or DEFAULT_BROWSER_UA),
        )
        self.egg_service = EggQueryService()

    @filter.command(COMMAND_NAME, alias=COMMAND_ALIASES)
    async def query_wiki(self, event: AstrMessageEvent):
        """查询洛克王国世界 Wiki 词条。"""
        message_text = getattr(event, "message_str", "")
        keyword = extract_keyword_from_message(message_text, {COMMAND_NAME, *COMMAND_ALIASES})

        if not keyword:
            yield event.plain_result("用法: /精灵wiki <关键词>\n示例: /精灵wiki 迪莫")
            return

        logger.info(f"rocom_wiki_bot lookup keyword={keyword}")

        try:
            entry = await self.client.lookup(keyword)
        except httpx.HTTPError as exc:
            logger.warning(f"rocom_wiki_bot request failed: {exc}")
            yield event.plain_result("Wiki 暂时无法访问，请稍后再试。")
            return
        except Exception as exc:  # pragma: no cover
            logger.error(f"rocom_wiki_bot unexpected error: {exc}")
            yield event.plain_result("查询时发生了意外错误，请稍后重试。")
            return

        if entry is None:
            yield event.plain_result(format_lookup_message(entry, keyword, self.summary_length))
            return

        if self.render_as_image:
            try:
                image_url = await self.html_render(WIKI_CARD_TEMPLATE, build_card_context(entry))
                yield event.image_result(image_url)
                return
            except Exception as exc:  # pragma: no cover
                logger.warning(f"rocom_wiki_bot html render failed: {exc}")

        yield event.plain_result(format_lookup_message(entry, keyword, self.summary_length))

    @filter.command(SKILL_COMMAND_NAME, alias=SKILL_COMMAND_ALIASES)
    async def query_skill_wiki(self, event: AstrMessageEvent):
        """查询洛克王国世界 Wiki 技能词条。"""
        message_text = getattr(event, "message_str", "")
        keyword = extract_keyword_from_message(message_text, {SKILL_COMMAND_NAME, *SKILL_COMMAND_ALIASES})

        if not keyword:
            yield event.plain_result("用法: /技能wiki <关键词>\n示例: /技能wiki 焰火")
            return

        logger.info(f"rocom_wiki_bot skill lookup keyword={keyword}")

        try:
            entry = await self.client.lookup_skill(keyword)
        except httpx.HTTPError as exc:
            logger.warning(f"rocom_wiki_bot skill request failed: {exc}")
            yield event.plain_result("Wiki 暂时无法访问，请稍后再试。")
            return
        except Exception as exc:  # pragma: no cover
            logger.error(f"rocom_wiki_bot skill unexpected error: {exc}")
            yield event.plain_result("查询技能时发生了意外错误，请稍后重试。")
            return

        if entry is None:
            yield event.plain_result(format_skill_lookup_message(entry, keyword, self.summary_length))
            return

        if self.render_as_image:
            try:
                image_url = await self.html_render(SKILL_CARD_TEMPLATE, build_skill_card_context(entry))
                yield event.image_result(image_url)
                return
            except Exception as exc:  # pragma: no cover
                logger.warning(f"rocom_wiki_bot skill html render failed: {exc}")

        yield event.plain_result(format_skill_lookup_message(entry, keyword, self.summary_length))

    @filter.command(EGG_COMMAND_NAME, alias=EGG_COMMAND_ALIASES)
    async def query_egg(self, event: AstrMessageEvent):
        """查询洛克王国世界精灵生蛋匹配。"""
        message_text = getattr(event, "message_str", "")
        query_text = extract_keyword_from_message(message_text, {EGG_COMMAND_NAME, *EGG_COMMAND_ALIASES})
        terms = split_egg_query_terms(query_text)

        if not terms:
            yield event.plain_result("用法: /生蛋查询 <目标精灵>\n或: /生蛋查询 <精灵A> <精灵B>")
            return

        try:
            if len(terms) >= 2:
                left_result = await self.egg_service.lookup_pet(terms[0])
                right_result = await self.egg_service.lookup_pet(terms[1])
                if left_result.pet is None or right_result.pet is None:
                    missing = []
                    if left_result.pet is None:
                        missing.append(f"没有找到“{terms[0]}”")
                    if right_result.pet is None:
                        missing.append(f"没有找到“{terms[1]}”")
                    yield event.plain_result("；".join(missing))
                    return

                pair_result = await self.egg_service.check_pair(left_result.pet, right_result.pet)
                yield event.plain_result(self.egg_service.format_pair_result(pair_result))
                return

            lookup_result = await self.egg_service.lookup_pet(terms[0])
            yield event.plain_result(await self.egg_service.format_single_pet_result(terms[0], lookup_result))
        except Exception as exc:  # pragma: no cover
            logger.error(f"rocom_wiki_bot egg query unexpected error: {exc}")
            yield event.plain_result("查询生蛋信息时发生了意外错误，请稍后重试。")

    @filter.command(EGG_GROUP_COMMAND_NAME, alias=EGG_GROUP_COMMAND_ALIASES)
    async def query_egg_group(self, event: AstrMessageEvent):
        """查询蛋组对应的精灵列表。"""
        message_text = getattr(event, "message_str", "")
        keyword = extract_keyword_from_message(message_text, {EGG_GROUP_COMMAND_NAME, *EGG_GROUP_COMMAND_ALIASES})

        if not keyword:
            yield event.plain_result("用法: /蛋组查询 <蛋组名>\n示例: /蛋组查询 龙组")
            return

        try:
            result = await self.egg_service.lookup_group(keyword)
            yield event.plain_result(self.egg_service.format_group_result(keyword, result))
        except Exception as exc:  # pragma: no cover
            logger.error(f"rocom_wiki_bot egg group query unexpected error: {exc}")
            yield event.plain_result("查询蛋组信息时发生了意外错误，请稍后重试。")
