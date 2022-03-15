from enum import Enum
from ntpath import join
from select import select

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import JoinRoomResult, SafeUser, WaitRoomStatus
from .model import LiveDifficulty, RoomInfo, RoomUser, ResultUser

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs

class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty

class RoomID(BaseModel):
    room_id: int

class RoomListRequest(BaseModel):
    live_id: int

class RoomListResponse(BaseModel):
    room_list: list[RoomInfo]

class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty

class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult

class RoomWaitRequest(BaseModel):
    room_id: int

class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]

class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int

class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]

@app.post("/room/create", response_model=RoomID)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    room_id = model.create_room(req.live_id, req.select_difficulty, token)
    return RoomID(room_id=room_id)

@app.post("/room/list", response_model=RoomListResponse)
def get_room_list(req: RoomListRequest):
    exist_rooms = model.get_room_list(req.live_id)
    return RoomListResponse(room_list=exist_rooms)

@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    join_room_result = model.join_room(req.room_id, req.select_difficulty, token)
    return RoomJoinResponse(join_room_result=join_room_result)

@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    status, room_user_list = model.room_wait(req.room_id, token)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)

@app.post("/room/start", response_model=Empty)
def room_start(req: RoomID, token: str = Depends(get_auth_token)):
    model.room_start(req.room_id, token)

@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    model.room_end(req.room_id, req.judge_count_list, req.score, token)

@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomID):
    result_user_list = model.room_result(req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)

@app.post("/room/leave", response_model=Empty)
def room_leave(req: RoomID):
    model.room_leave(req.room_id)