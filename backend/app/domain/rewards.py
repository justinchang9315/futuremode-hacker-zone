from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import AssessmentStatus, Currency
from app.exceptions import ConflictError, NotFoundError
from app.models import (
    PersonalBest,
    ReadingAssessment,
    RewardItemOwnership,
    RewardTransaction,
    Wallet,
    new_id,
)
from app.schemas import RewardGrant


@dataclass(frozen=True)
class CatalogItem:
    code: str
    currency: Currency
    cost: int
    label: str
    description: str
    max_quantity: int = 1


FIRST_COMPLETION_COINS = 10
GOOD_READING_COINS = 5
PERSONAL_BEST_COINS = 5
PERSONAL_BEST_MIN_GAIN = 5
CONTENT_MASTERY_GEMS = 1

REWARD_CATALOG: dict[str, CatalogItem] = {
    "star_badge": CatalogItem(
        "star_badge", Currency.COIN, 20, "星星徽章", "顯示在學習成果卡上。"
    ),
    "trophy": CatalogItem(
        "trophy", Currency.COIN, 25, "冠軍獎盃", "放到房間的架子上，代表念完很多篇。"
    ),
    "blue_glow": CatalogItem(
        "blue_glow", Currency.GEM, 1, "藍色光環", "讓夥伴的舞台亮起藍色光環。"
    ),
}


def get_or_create_wallet(db: Session, child_id: str) -> Wallet:
    wallet = db.scalar(
        select(Wallet).where(Wallet.child_id == child_id).with_for_update()
    )
    if wallet is None:
        wallet = Wallet(child_id=child_id)
        db.add(wallet)
        db.flush()
    return wallet


def _credit(
    db: Session,
    *,
    wallet: Wallet,
    assessment_id: str,
    currency: Currency,
    amount: int,
    reason_code: str,
    idempotency_key: str,
    settings: Settings,
    extra_data: dict | None = None,
) -> RewardGrant | None:
    existing = db.scalar(
        select(RewardTransaction).where(
            RewardTransaction.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return None

    transaction = RewardTransaction(
        child_id=wallet.child_id,
        assessment_id=assessment_id,
        currency=currency.value,
        amount=amount,
        reason_code=reason_code,
        idempotency_key=idempotency_key,
        policy_version=settings.reward_policy_version,
        extra_data=extra_data or {},
    )
    db.add(transaction)
    if currency is Currency.COIN:
        wallet.coin_balance += amount
        wallet.lifetime_coins += amount
    else:
        wallet.gem_balance += amount
        wallet.lifetime_gems += amount
    db.flush()
    return RewardGrant(currency=currency, amount=amount, reason_code=reason_code)


def apply_assessment_rewards(
    db: Session,
    *,
    child_id: str,
    content_id: str,
    assessment: ReadingAssessment,
    previous_best: PersonalBest | None,
    settings: Settings,
) -> list[RewardGrant]:
    if assessment.status != AssessmentStatus.FINAL.value or assessment.total_score is None:
        return []

    wallet = get_or_create_wallet(db, child_id)
    rewards: list[RewardGrant] = []

    first_completion = _credit(
        db,
        wallet=wallet,
        assessment_id=assessment.id,
        currency=Currency.COIN,
        amount=FIRST_COMPLETION_COINS,
        reason_code="FIRST_COMPLETION",
        idempotency_key=f"{child_id}:{content_id}:first-completion",
        settings=settings,
    )
    if first_completion:
        rewards.append(first_completion)

    if assessment.total_score >= settings.good_reading_score:
        good_reading = _credit(
            db,
            wallet=wallet,
            assessment_id=assessment.id,
            currency=Currency.COIN,
            amount=GOOD_READING_COINS,
            reason_code="GOOD_READING",
            idempotency_key=f"{child_id}:{content_id}:good-reading",
            settings=settings,
        )
        if good_reading:
            rewards.append(good_reading)

    if (
        previous_best
        and assessment.total_score >= previous_best.best_score + PERSONAL_BEST_MIN_GAIN
    ):
        improvement = _credit(
            db,
            wallet=wallet,
            assessment_id=assessment.id,
            currency=Currency.COIN,
            amount=PERSONAL_BEST_COINS,
            reason_code="PERSONAL_BEST_IMPROVEMENT",
            idempotency_key=f"{assessment.id}:personal-best-improvement",
            settings=settings,
            extra_data={"previous_best": previous_best.best_score},
        )
        if improvement:
            rewards.append(improvement)

    if (
        assessment.total_score >= settings.mastery_score
        and assessment.assessment_confidence >= settings.mastery_confidence
    ):
        mastery = _credit(
            db,
            wallet=wallet,
            assessment_id=assessment.id,
            currency=Currency.GEM,
            amount=CONTENT_MASTERY_GEMS,
            reason_code="CONTENT_MASTERY",
            idempotency_key=f"{child_id}:{content_id}:mastery",
            settings=settings,
        )
        if mastery:
            rewards.append(mastery)

    if previous_best is None:
        db.add(
            PersonalBest(
                child_id=child_id,
                content_id=content_id,
                best_score=assessment.total_score,
                assessment_id=assessment.id,
            )
        )
    elif assessment.total_score > previous_best.best_score:
        previous_best.best_score = assessment.total_score
        previous_best.assessment_id = assessment.id
    db.flush()
    return rewards


def redeem_catalog_item(
    db: Session,
    *,
    child_id: str,
    item_code: str,
    request_id: str,
    settings: Settings,
) -> tuple[CatalogItem, Wallet, list[RewardItemOwnership]]:
    item = REWARD_CATALOG.get(item_code)
    if item is None:
        raise NotFoundError("找不到指定的兌換項目。")

    wallet = get_or_create_wallet(db, child_id)
    idempotency_key = f"redemption:{child_id}:{request_id}"
    existing_transaction = db.scalar(
        select(RewardTransaction).where(
            RewardTransaction.idempotency_key == idempotency_key
        )
    )
    if existing_transaction is not None:
        existing_code = existing_transaction.extra_data.get("item_code")
        if existing_code != item_code:
            raise ConflictError("同一個 request_id 不可用於不同兌換項目。")
        return item, wallet, list_reward_items(db, child_id)

    ownership = db.scalar(
        select(RewardItemOwnership)
        .where(
            RewardItemOwnership.child_id == child_id,
            RewardItemOwnership.item_code == item_code,
        )
        .with_for_update()
    )
    if ownership is not None and ownership.quantity >= item.max_quantity:
        raise ConflictError("這個獎勵已經擁有，不需要重複兌換。")
    balance = wallet.coin_balance if item.currency is Currency.COIN else wallet.gem_balance
    if balance < item.cost:
        raise ConflictError("目前餘額不足，無法兌換。")

    transaction = RewardTransaction(
        id=new_id(),
        child_id=child_id,
        assessment_id=None,
        currency=item.currency.value,
        amount=-item.cost,
        reason_code="CATALOG_REDEMPTION",
        idempotency_key=idempotency_key,
        policy_version=settings.reward_policy_version,
        extra_data={"item_code": item_code},
    )
    db.add(transaction)
    if item.currency is Currency.COIN:
        wallet.coin_balance -= item.cost
    else:
        wallet.gem_balance -= item.cost
    if ownership is None:
        db.add(RewardItemOwnership(child_id=child_id, item_code=item_code, quantity=1))
    else:
        ownership.quantity += 1
    transaction.extra_data["balance_after"] = (
        wallet.coin_balance if item.currency is Currency.COIN else wallet.gem_balance
    )
    db.flush()
    return item, wallet, list_reward_items(db, child_id)


def list_reward_items(db: Session, child_id: str) -> list[RewardItemOwnership]:
    return list(
        db.scalars(
            select(RewardItemOwnership)
            .where(RewardItemOwnership.child_id == child_id)
            .order_by(RewardItemOwnership.acquired_at)
        )
    )
