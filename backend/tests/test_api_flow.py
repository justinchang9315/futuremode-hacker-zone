from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.rewards import REWARD_CATALOG
from app.models import DialogueTurn, ReadingAttempt


def _start_session(client: TestClient) -> dict:
    response = client.post(
        "/v1/sessions",
        json={
            "age": 7,
            "grade_level": 2,
            "guardian_present": True,
            "guardian_acknowledged_ai": True,
            "guardian_acknowledged_privacy": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _session_headers(session: dict) -> dict[str, str]:
    return {"X-Session-Token": session["session_token"]}


def _guardian_headers(session: dict) -> dict[str, str]:
    return {"X-Guardian-Token": session["guardian_token"]}


def _score(client: TestClient, session: dict, content_id: str, transcript: str) -> dict:
    response = client.post(
        "/v1/reading-attempts/transcript",
        headers=_session_headers(session),
        json={
            "session_id": session["id"],
            "content_id": content_id,
            "request_id": str(uuid4()),
            "transcript": transcript,
            "recognition_confidence": 1.0,
            "duration_ms": 5_000,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_guardian_consent_and_access_token_are_required(client: TestClient) -> None:
    response = client.post(
        "/v1/sessions",
        json={
            "age": 7,
            "grade_level": 2,
            "guardian_present": False,
            "guardian_acknowledged_ai": True,
            "guardian_acknowledged_privacy": True,
        },
    )
    assert response.status_code == 403

    session = _start_session(client)
    no_token = client.get(f"/v1/children/{session['child_id']}/wallet")
    assert no_token.status_code == 401
    wrong_role = client.get(
        f"/v1/children/{session['child_id']}/wallet",
        headers={"X-Session-Token": session["guardian_token"]},
    )
    assert wrong_role.status_code == 401


def test_learning_reward_inventory_and_level_progression(client: TestClient) -> None:
    session = _start_session(client)
    child_id = session["child_id"]

    first = _score(client, session, "poem-jing-ye-si", "床前明月")
    second = _score(client, session, "poem-deng-guan-que-lou", "白日依山")
    assert first["companion"]["speech"] is None
    assert second["current_level"] == 1

    improved_first = _score(
        client,
        session,
        "poem-jing-ye-si",
        "床前明月光，疑是地上霜。舉頭望明月，低頭思故鄉。",
    )
    improved_second = _score(
        client,
        session,
        "poem-deng-guan-que-lou",
        "白日依山盡，黃河入海流。欲窮千里目，更上一層樓。",
    )
    assert improved_first["score"] == 100
    assert improved_second["current_level"] == 2
    assert improved_second["pending_level"] == 3

    wallet = client.get(
        f"/v1/children/{child_id}/wallet", headers=_session_headers(session)
    ).json()
    # 兩篇 x (FIRST_COMPLETION 10 + GOOD_READING 5 + PERSONAL_BEST_IMPROVEMENT 5)。
    # 第一次只念了開頭幾個字，分數不到 GOOD_READING_SCORE，所以那 5 金幣是念完整之後才拿到的。
    assert wallet["coin_balance"] == 40
    assert wallet["gem_balance"] == 2

    approval = client.put(
        f"/v1/children/{child_id}/level-3-approval",
        headers=_guardian_headers(session),
        json={"approved": True},
    )
    assert approval.status_code == 200
    assert approval.json()["current_level"] == 3

    request_id = str(uuid4())
    redemption_body = {
        "child_id": child_id,
        "item_code": "star_badge",
        "request_id": request_id,
    }
    redemption = client.post(
        "/v1/rewards/redeem",
        headers=_session_headers(session),
        json=redemption_body,
    )
    repeated = client.post(
        "/v1/rewards/redeem",
        headers=_session_headers(session),
        json=redemption_body,
    )
    assert redemption.status_code == repeated.status_code == 200
    assert repeated.json()["wallet"]["coin_balance"] == 40 - REWARD_CATALOG["star_badge"].cost
    assert repeated.json()["inventory"][0]["item_code"] == "star_badge"

    dialogue = client.post(
        "/v1/dialogue",
        headers=_session_headers(session),
        json={
            "session_id": session["id"],
            "request_id": str(uuid4()),
            "message": "我想知道月亮為什麼會發光",
        },
    )
    assert dialogue.status_code == 201
    assert dialogue.json()["response"]["response_source"] == "CONSTRAINED_LLM"


def test_safety_privacy_feedback_summary_and_delete(
    client: TestClient, db_session: Session
) -> None:
    session = _start_session(client)
    response = client.post(
        "/v1/dialogue",
        headers=_session_headers(session),
        json={
            "session_id": session["id"],
            "request_id": str(uuid4()),
            "message": "我今天被打，我很害怕",
        },
    )
    body = response.json()
    assert body["safety_level"] == 2
    assert body["response"]["response_source"] == "SAFETY_OVERRIDE"
    stored = db_session.scalar(select(DialogueTurn).where(DialogueTurn.id == body["turn_id"]))
    assert stored is not None and stored.input_text == "[NOT_STORED]"

    feedback = client.post(
        "/v1/feedback",
        headers=_session_headers(session),
        json={
            "session_id": session["id"],
            "dialogue_turn_id": body["turn_id"],
            "helpful": True,
            "relevance": 5,
        },
    )
    assert feedback.status_code == 201

    summary = client.get(
        f"/v1/sessions/{session['id']}/summary",
        headers=_guardian_headers(session),
    )
    assert summary.status_code == 200
    assert summary.json()["safety_events"] == 1

    deleted = client.delete(
        f"/v1/children/{session['child_id']}",
        headers={**_guardian_headers(session), "X-Confirm-Delete": "DELETE"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_low_confidence_asr_does_not_issue_rewards(client: TestClient) -> None:
    session = _start_session(client)
    response = client.post(
        "/v1/reading-attempts/transcript",
        headers=_session_headers(session),
        json={
            "session_id": session["id"],
            "content_id": "poem-chun-xiao",
            "request_id": str(uuid4()),
            "transcript": "春眠不覺曉",
            "recognition_confidence": 0.4,
            "duration_ms": 2_000,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["score"] is None
    assert body["rewards"] == []


def test_fake_audio_websocket_and_minimized_transcript(
    client: TestClient, db_session: Session
) -> None:
    session = _start_session(client)
    request_id = str(uuid4())
    audio_response = client.post(
        "/v1/reading-attempts/audio",
        headers=_session_headers(session),
        data={
            "session_id": session["id"],
            "content_id": "poem-chun-xiao",
            "request_id": request_id,
        },
        files={
            "audio": (
                "fake-transcript.txt",
                "春眠不覺曉，處處聞啼鳥。夜來風雨聲，花落知多少。".encode(),
                "text/plain",
            )
        },
    )
    assert audio_response.status_code == 201
    attempt = db_session.scalar(
        select(ReadingAttempt).where(ReadingAttempt.request_id == request_id)
    )
    assert attempt is not None and attempt.transcript.startswith("sha256:")

    with client.websocket_connect(
        f"/v1/ws/sessions/{session['id']}?access_token={session['session_token']}"
    ) as websocket:
        websocket.send_json(
            {
                "type": "dialogue.submit",
                "payload": {"request_id": str(uuid4()), "message": "你是誰？"},
            }
        )
        response = websocket.receive_json()
    assert response["type"] == "dialogue.completed", response
    assert response["payload"]["response"]["response_source"] == "APPROVED_TEMPLATE"
