import hashlib
import os
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path
from typing import Annotated

import chess
import chess.engine
import chess.pgn
import dotenv
import fastapi
import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException
from sqlmodel import Field, SQLModel, Session, create_engine
from starlette import status
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from game_reviewer import GameReviewer

dotenv.load_dotenv()

DATABASE = os.getenv("DATABASE")
connect_args = {
    # "check_same_thread": False
}
engine = create_engine(DATABASE, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    app.mount(
        "/static",
        StaticFiles(directory="static"),
        name="static",
    )
    yield


app = fastapi.FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")


class GameDTO(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pgn: str


class GameManager:
    directory: Path = Path(__file__).parent / "games"

    def list(self) -> list[str]:
        return [
            f.name
            for f in self.directory.iterdir()
            if f.is_file() and f.suffix == ".pgn"
        ]

    def load(self, key: str) -> chess.pgn.Game:
        p = self.directory / key
        if not p.exists():
            raise HTTPException(status_code=404, detail="Game not found")
        if not p.parent == self.directory:
            raise HTTPException(status_code=403, detail="Game not found")

        with open(p) as f:
            game = chess.pgn.read_game(f)
        return game

    def save(self, key: str, game: chess.pgn.Game) -> None:
        p = self.directory / key
        if not p.parent == self.directory:
            raise HTTPException(status_code=403, detail="Game not found")

        with open(p, "w") as f:
            f.write(self.as_pgn(game))

    def as_pgn(self, game):
        exporter = chess.pgn.StringExporter()
        output = game.accept(exporter)
        return output


@app.get("/review/{key}")
async def get_review(request: Request, key: str) -> Response:
    gm = GameManager()
    game = gm.load(key)
    reviewed_game = await GameReviewer().create_review(game)
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": gm.as_pgn(reviewed_game)}
    )


@app.get("/games")
async def list_games(request: Request) -> Response:
    gm = GameManager()
    return templates.TemplateResponse(
        "games.html", {"request": request, "games": gm.list()}
    )


@app.get("/new")
async def submit_new_game(request: Request) -> Response:
    return templates.TemplateResponse("new.html", {"request": request})


@app.post("/submit")
async def submit_new_game_resp(
    request: Request, pgn: Annotated[str, Form()]
) -> Response:
    gm = GameManager()
    sio = StringIO(pgn)
    game = chess.pgn.read_game(sio)

    normalized_pgn = gm.as_pgn(game)
    newkey = hashlib.sha256(normalized_pgn.encode("utf-8")).hexdigest()[:12] + ".pgn"
    gm.save(newkey, game)

    return RedirectResponse(
        app.url_path_for("get_review", key=newkey),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/view/{key}")
async def view(request: Request, key: str) -> Response:
    gm = GameManager()
    game = gm.load(key)
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": gm.as_pgn(game)}
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
