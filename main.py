import hashlib
from contextlib import asynccontextmanager
from io import StringIO
from typing import Annotated

import chess
import chess.engine
import chess.pgn
import fastapi
import uvicorn
from fastapi import Depends, FastAPI, Form
from sqlmodel import SQLModel, select
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket

from db import engine, get_session
from game_reviewer import ENGINE, GameReviewer
from models import Game, GameDTO
from utils import sanitize_infodict


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = fastapi.FastAPI(lifespan=lifespan)

app.frontend("/", directory="frontend/dist")

templates = Jinja2Templates(directory="frontend/dist/templates")


@app.get("/review/{id}")
async def get_review(
    request: Request, id: int, session=Depends(get_session)
) -> Response:
    dto: GameDTO | None = session.get(GameDTO, id)
    if dto is None:
        raise HTTPException(status_code=404)
    game = Game.from_dto(dto)

    reviewed_game = await GameReviewer().create_review(game)
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": str(game)}
    )


@app.websocket("/evaluation")
async def evaluation_ws(websocket: WebSocket):
    await websocket.accept()
    transport, engine = await chess.engine.popen_uci(ENGINE)
    while True:
        fen = await websocket.receive_text()
        board = chess.Board(fen)
        info = await engine.analyse(board, chess.engine.Limit(time=0.1))
        san = sanitize_infodict(board, info)
        await websocket.send_json(san)


@app.get("/")
@app.get("/games")
async def list_games(request: Request, session=Depends(get_session)) -> Response:
    games = session.exec(select(GameDTO)).all()
    return templates.TemplateResponse(
        "games.html", {"request": request, "games": games}
    )


@app.get("/games/new")
async def submit_new_game(request: Request) -> Response:
    return templates.TemplateResponse("new.html", {"request": request})


@app.post("/games/new")
async def submit_new_game_resp(
    request: Request,
    pgn: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
    session=Depends(get_session),
) -> Response:
    sio = StringIO(pgn)
    game = chess.pgn.read_game(sio)
    normalized_pgn = Game.as_pgn(game)

    if not name:
        name = hashlib.sha256(normalized_pgn.encode()).hexdigest()[:8]

    # find existing game with this name
    existing_game = session.exec(select(GameDTO).where(GameDTO.name == name)).first()
    if existing_game:
        return RedirectResponse(
            app.url_path_for("get_review", id=existing_game.id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    dto = GameDTO(name=name, pgn=normalized_pgn)
    session.add(dto)
    session.commit()
    session.refresh(dto)

    return RedirectResponse(
        app.url_path_for("get_review", id=dto.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/games/{id}")
async def view_game(
    request: Request, id: int, session=Depends(get_session)
) -> Response:
    dto: GameDTO | None = session.get(GameDTO, id)
    if dto is None:
        raise HTTPException(status_code=404)
    game = Game.from_dto(dto)
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": game.as_pgn()}
    )


@app.delete("/games/{id}")
async def delete_game(
    request: Request, id: int, session=Depends(get_session)
) -> Response:
    dto: GameDTO | None = session.get(GameDTO, id)
    if dto is None:
        raise HTTPException(status_code=404)
    session.delete(dto)
    session.commit()
    return RedirectResponse(
        app.url_path_for("list_games"), status_code=status.HTTP_303_SEE_OTHER
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
