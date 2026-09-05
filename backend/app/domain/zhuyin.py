"""把教材原文標上注音，給前端「這個字怎麼念」用。

用 pypinyin 依「整句上下文」推斷，破音字才會對
（「花落知多少」是 ㄕㄠˇ、「少年」是 ㄕㄠˋ）。
標點符號與非漢字回傳 None，前端就不會把它們變成可點的字。
"""

from pypinyin import Style, pinyin


def _no_reading(chars: str) -> list[None]:
    """pypinyin 遇到非漢字時的處理：長度要對齊，內容留空。"""
    return [None] * len(chars)


def annotate(text: str) -> list[str | None]:
    """回傳與 `text` 等長的注音清單，非漢字為 None。"""
    if not text:
        return []
    readings = pinyin(text, style=Style.BOPOMOFO, errors=_no_reading)
    result: list[str | None] = []
    for candidates in readings:
        reading = candidates[0] if candidates else None
        result.append(reading if isinstance(reading, str) and reading.strip() else None)
    # pypinyin 對某些組合會回傳合併後的詞，長度不一定對得上，這裡保險對齊。
    if len(result) != len(text):
        return [None] * len(text)
    return result
