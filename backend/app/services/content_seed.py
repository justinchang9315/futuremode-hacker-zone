from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem

DEMO_CONTENT = (
    {
        "id": "poem-jing-ye-si",
        "title": "靜夜思",
        "author": "李白",
        "reference_text": "床前明月光，疑是地上霜。舉頭望明月，低頭思故鄉。",
    },
    {
        "id": "poem-deng-guan-que-lou",
        "title": "登鸛雀樓",
        "author": "王之渙",
        "reference_text": "白日依山盡，黃河入海流。欲窮千里目，更上一層樓。",
    },
    {
        "id": "poem-chun-xiao",
        "title": "春曉",
        "author": "孟浩然",
        "reference_text": "春眠不覺曉，處處聞啼鳥。夜來風雨聲，花落知多少。",
    },
)


def seed_content(db: Session) -> None:
    for item in DEMO_CONTENT:
        if db.scalar(select(ContentItem.id).where(ContentItem.id == item["id"])):
            continue
        db.add(
            ContentItem(
                **item,
                content_type="POEM",
                grade_level=2,
                source="中國古典詩作原文（公版內容）",
                license_label="PUBLIC_DOMAIN_ORIGINAL_TEXT",
                scoring_config={
                    "unit": "character",
                    "accuracy_weight": 0.60,
                    "completeness_weight": 0.25,
                    "fluency_weight": 0.15,
                },
            )
        )
    db.commit()
