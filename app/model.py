import json
from selectors import SelectSelector
import uuid
from enum import Enum, IntEnum
from typing import Optional, List, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id =:leader_card_id WHERE `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )

MAX_USER = 4

class JudgeScore(Enum):
    perfect = 0
    great = 1
    good = 2
    bad = 3
    miss = 4

class LiveDifficulty(Enum):
    normal = 1
    hard = 2

class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3

class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = MAX_USER

class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, select_difficulty, joined_user_count) VALUES (:live_id, :select_difficulty, :joined_user_count)"
            ),
            {"live_id": live_id, "select_difficulty": select_difficulty.value, "joined_user_count":1},
        )
        room_id = result.lastrowid
        user = get_user_by_token(token)
        conn.execute(
            text(
                "INSERT INTO `room_members` (room_id, select_difficulty, user_id, token, is_host) VALUES (:room_id, :select_difficulty, :user_id, :token, :is_host)"
            ),
            {"room_id":room_id, "select_difficulty":select_difficulty.value, "user_id":user.id, "token":token, "is_host":True}
        )
        return room_id

def get_room_list(live_id: int) -> Optional[RoomInfo]:
    exist_rooms = []
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count` FROM `room`"
                ),
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count` FROM `room` WHERE `live_id`=:live_id"
                ),
                {"live_id": live_id},
            )
        result = result.all()
        for row in result:
            exist_rooms.append(RoomInfo(room_id=row.room_id, live_id=row.live_id, joined_user_count=row.joined_user_count))
        return exist_rooms

def join_room(room_id: int, select_difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `joined_user_count` FROM `room` WHERE `room_id`=:room_id AND `select_difficulty`=:select_difficulty"
            ),
            {"room_id":room_id, "select_difficulty":select_difficulty.value},
        )
        result = result.one()
        try:
            if result.joined_user_count < MAX_USER: # 人数追加可能
                conn.execute(
                    text(
                        "UPDATE `room` SET `joined_user_count`=:plus_user_count WHERE `room_id`=:room_id AND `select_difficulty`=:select_difficulty"
                    ),
                    {"plus_user_count":result.joined_user_count+1, "room_id":room_id, "select_difficulty":select_difficulty.value},
                )
                user = get_user_by_token(token)
                conn.execute(
                    text(
                        "INSERT INTO `room_members` (room_id, select_difficulty, user_id, token, is_host) VALUES (:room_id, :select_difficulty, :user_id, :token, :is_host)"
                    ),
                    {"room_id":room_id, "select_difficulty":select_difficulty.value, "user_id":user.id, "token":token, "is_host":False}
                )
                return JoinRoomResult.Ok
            else: # 四人揃ってる状態
                return JoinRoomResult.RoomFull
        except NoResultFound: # 解散済み
            return JoinRoomResult.Disbanded

def _get_room_status(room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        status = conn.execute(
            text(
                "SELECT `room_status` FROM `room` WHERE `room_id`=:room_id"
            ),
            {"room_id":room_id},
        )
        try:
            room_status = status.one()
            if room_status == 1:
                return WaitRoomStatus.Waiting
            elif room_status == 2:
                return WaitRoomStatus.LiveStart
            else:
                return WaitRoomStatus.Dissolution
        except NoResultFound:
            return WaitRoomStatus.Dissolution

def _get_room_users(room_id: int, token: str) -> List[RoomUser]:
    room_users = []
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `select_difficulty`, `token`, `is_host` FROM `room_members` WHERE `room_id`=:room_id" 
            ),
            {"room_id":room_id},
        )
        result = result.all()
        for row in result:
            user_info = get_user_by_token(row.token)
            room_users.append(
                RoomUser(
                    user_id=row.user_id,
                    name=user_info.name,
                    leader_card_id=user_info.leader_card_id,
                    select_difficulty=row.select_difficulty,
                    is_me=(token==row.token),
                    is_host=row.is_host,
                )
            )
        return room_users

def room_wait(room_id: int, token: str) -> Tuple[WaitRoomStatus, List[RoomUser]]:
    room_status = _get_room_status(room_id)
    room_users = _get_room_users(room_id, token)
    return (room_status, room_users)

def room_start(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "SELECT `is_host` FROM `room_members` WHERE `room_id`=:room_id AND `token`=:token"
            ),
            {"room_id":room_id, "token":token},
        )
        is_host = res.one()[0]
        if is_host == 1:
            conn.execute(
                text(
                    "UPDATE `room` SET `room_status`=:room_status WHERE `room_id`=:room_id"
                ),
                {"room_status":WaitRoomStatus.LiveStart.value, "room_id":room_id},
            )
        else:
            raise HTTPException(status_code=500)

def _score_list(judge_count_list: list[int]) -> List[int]:
    score_list = [0,0,0,0,0]
    for i in range(len(judge_count_list)):
        score_list[i] = judge_count_list[i]
    return score_list

def room_end(room_id: int, judge_count_list: list[int], score: int, token: str) -> None:
    judge_count_list = _score_list(judge_count_list)
    perfect_score = judge_count_list[JudgeScore.perfect.value]
    great_score = judge_count_list[JudgeScore.great.value]
    good_score = judge_count_list[JudgeScore.good.value]
    bad_score = judge_count_list[JudgeScore.bad.value]
    miss_score = judge_count_list[JudgeScore.miss.value]
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `room_members` SET `score`=:score, `perfect`=:perfect, `great`=:great, `good`=:good, `bad`=:bad, `miss`=:miss WHERE `room_id`=:room_id AND`token`=:token"
            ),
            {"score":score, "perfect":perfect_score, "great":great_score, "good":good_score, "bad":bad_score, "miss":miss_score, "room_id":room_id, "token":token},
        )

def room_result(room_id: int) -> List[ResultUser]:
    result_user_list: list[ResultUser] = []
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `score`, `perfect`, `great`, `good`, `bad`, `miss` FROM `room_members` WHERE  `room_id`=:room_id"
            ),
            {"room_id":room_id},
        )
    results = result.all()
    for row in results:
        if row.score == -1: return []
        res = ResultUser(
            user_id=row.user_id,
            judge_count_list=[row.perfect, row.great, row.good, row.bad, row.miss],
            score=row.score,
        )
        result_user_list.append(res)
    return result_user_list

def room_leave(room_id: int) -> None:
    pass