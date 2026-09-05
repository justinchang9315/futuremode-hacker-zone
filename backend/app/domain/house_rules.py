"""本站規則（獎勵怎麼拿、等級怎麼升）的唯一事實來源。

同一組事實有兩個用途：

1. `answer_for()` 直接回答孩子問的規則問題，完全不經過 LLM，
   避免它照著一般常識自己編一套（例如「幫忙做家事就能拿到星星」）。
2. `llm_context()` 當作 context 餵給 LLM，讓沒有被規則攔截到的問法也有正確依據。

數字全部從 `rewards.REWARD_CATALOG`、`rewards` 的獎勵常數與 `Settings` 讀出來，
不要在這裡寫死，否則調整 `.env` 之後小芽會講錯。
"""

from math import ceil

from app.config import Settings
from app.domain.rewards import (
    CONTENT_MASTERY_GEMS,
    FIRST_COMPLETION_COINS,
    GOOD_READING_COINS,
    PERSONAL_BEST_COINS,
    PERSONAL_BEST_MIN_GAIN,
    REWARD_CATALOG,
)


def _star_badge_answer(settings: Settings) -> str:
    item = REWARD_CATALOG["star_badge"]
    best = FIRST_COMPLETION_COINS + GOOD_READING_COINS
    return (
        f"{item.label}要用 {item.cost} 個金幣換。"
        f"每念完一篇新的詩會得到 {FIRST_COMPLETION_COINS} 個金幣，"
        f"念到 {settings.good_reading_score} 分以上再多拿 {GOOD_READING_COINS} 個，"
        f"所以念得好的話 {ceil(item.cost / best)} 篇就夠了。"
        f"換好之後可以在我的房間把它放到架子上。"
    )


def _trophy_answer(settings: Settings) -> str:
    item = REWARD_CATALOG["trophy"]
    best = FIRST_COMPLETION_COINS + GOOD_READING_COINS
    return (
        f"{item.label}要用 {item.cost} 個金幣換，比星星徽章難一點。"
        f"每念完一篇新的詩會得到 {FIRST_COMPLETION_COINS} 個金幣，"
        f"念到 {settings.good_reading_score} 分以上再多拿 {GOOD_READING_COINS} 個，"
        f"所以念得好的話 {ceil(item.cost / best)} 篇就夠了。"
        f"換好之後可以在我的房間把它放到架子上。"
    )


def _blue_glow_answer(settings: Settings) -> str:
    item = REWARD_CATALOG["blue_glow"]
    return (
        f"{item.label}要用 {item.cost} 個鑽石換。"
        f"一篇詩念到 {settings.mastery_score} 分以上就會拿到 {CONTENT_MASTERY_GEMS} 個鑽石。"
        f"換好之後可以在我的房間幫我點亮光環。"
    )


def _coin_answer(settings: Settings) -> str:
    return (
        f"金幣要靠念詩拿到。每念完一篇新的詩、成功評分可以得到 {FIRST_COMPLETION_COINS} 個金幣，"
        f"念到 {settings.good_reading_score} 分以上再多拿 {GOOD_READING_COINS} 個；"
        f"如果比自己上次的最好成績再高 {PERSONAL_BEST_MIN_GAIN} 分以上，"
        f"還會多拿 {PERSONAL_BEST_COINS} 個。"
        f"金幣可以在我的房間換{REWARD_CATALOG['star_badge'].label}"
        f"和{REWARD_CATALOG['trophy'].label}。"
    )


def _gem_answer(settings: Settings) -> str:
    return (
        f"鑽石要念得很好才有。一篇詩拿到 {settings.mastery_score} 分以上，"
        f"就會得到 {CONTENT_MASTERY_GEMS} 個鑽石。"
        f"鑽石可以在我的房間換{REWARD_CATALOG['blue_glow'].label}。"
    )


def _level_answer(settings: Settings) -> str:
    return (
        f"我升到 Level 2 需要累積 {settings.level_2_lifetime_coins} 個金幣，"
        f"而且完成 {settings.level_2_completed_contents} 篇教材。"
        f"再到 Level 3 還要 {settings.level_3_lifetime_gems} 個鑽石、"
        f"{settings.level_3_mastered_contents} 篇念到 {settings.mastery_score} 分以上，"
        f"最後要由家長按下核准。換道具不會讓我退級。"
    )


# 先比對比較具體的道具名稱，再比對幣別，避免「徽章要幾個金幣」被當成金幣問題。
_RULE_TOPICS: tuple[tuple[tuple[str, ...], object], ...] = (
    (("星星徽章", "徽章"), _star_badge_answer),
    (("冠軍獎盃", "獎盃", "獎杯"), _trophy_answer),
    (("藍色光環", "光環"), _blue_glow_answer),
    (("升級", "等級", "level", "解鎖", "變厲害"), _level_answer),
    (("金幣", "錢幣"), _coin_answer),
    (("鑽石",), _gem_answer),
)


def answer_for(message: str, settings: Settings) -> str | None:
    """孩子問的是本站規則就回傳固定答案，否則回傳 None 交給原本的流程。"""
    compact = message.replace(" ", "").lower()
    for keywords, build in _RULE_TOPICS:
        if any(keyword.lower() in compact for keyword in keywords):
            return build(settings)
    return None


def llm_context(settings: Settings) -> dict[str, str]:
    """給 LLM 的事實脈絡，讓沒被攔截的問法也不會亂編。"""
    return {
        "金幣": _coin_answer(settings),
        "鑽石": _gem_answer(settings),
        REWARD_CATALOG["star_badge"].label: _star_badge_answer(settings),
        REWARD_CATALOG["trophy"].label: _trophy_answer(settings),
        REWARD_CATALOG["blue_glow"].label: _blue_glow_answer(settings),
        "等級": _level_answer(settings),
    }
