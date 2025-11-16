import asyncio
import uuid
from io import StringIO
from typing import Any, Coroutine

import chess
import chess.engine
import chess.pgn
import fastapi
import pydantic
import uvicorn
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from streamerate import stream

ENGINE = "/Users/jmft2/.local/bin/stockfish.exe"
default_fen = chess.STARTING_FEN

app = fastapi.FastAPI()
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)
app.mount(
    "/jspgnviewer",
    StaticFiles(directory="jspgnviewer/src/main"),
    name="jspgnviewer",
)
app.mount(
    "/img",
    StaticFiles(directory="jspgnviewer/img"),
    name="img",
)


templates = Jinja2Templates(directory="templates")


def sanitize_povscore(ps: chess.engine.PovScore) -> str:
    white_score = ps.white()
    mate = white_score.mate()
    if mate is not None:
        if mate > 0:
            return f"+M{mate}"
        elif mate < 0:
            return f"-M{mate}"
        else:
            raise ValueError
    else:
        return f"{white_score.score()/100:+.2f}"


def sanitize_infodict(board: chess.Board, infod: chess.engine.InfoDict) -> dict:
    san = infod.copy()
    san["score"] = sanitize_povscore(san["score"])

    san["continuation"] = []
    board = board.copy()
    for move in san["pv"]:
        san["continuation"].append(board.san(move))
        board.push(move)

    game = chess.pgn.Game()
    game.setup(board)
    return san


class GameInfo(pydantic.BaseModel):
    scores: list[str]
    moves: list[chess.Move]


class GameReview:
    def __init__(self, game: chess.pgn.Game) -> None:
        self.game: chess.pgn.Game = game
        self.ready: bool = False

    async def do_review(self) -> None:
        if self.ready:
            return

        transport, engine = await chess.engine.popen_uci(ENGINE)

        async def _eval_inner(cn: chess.pgn.GameNode) -> None:
            board = cn.board()
            info = await engine.analyse(board, chess.engine.Limit(time=0.1))
            score = sanitize_povscore(info["score"])
            cn.comment = score

            coros = []
            for var in cn.variations:
                coros.append(_eval_inner(var))
            await asyncio.gather(*coros)

        try:
            await _eval_inner(self.game)
            self.ready = True
        finally:
            await engine.quit()

    def as_pgn(self):
        exporter = chess.pgn.StringExporter()
        output = self.game.accept(exporter)
        return output


reviews: dict[str, GameReview] = {}


@app.post("/review")
async def create_review(pgn: str) -> JSONResponse:
    h = uuid.uuid4().hex
    game: chess.pgn.Game = chess.pgn.read_game(StringIO(pgn))
    reviews[h] = GameReview(game)
    asyncio.create_task(reviews[h].do_review())
    return JSONResponse(h, status_code=201)


@app.get("/reviews")
async def list_reviews() -> list[dict]:
    # return stream(reviews.items()).starmap(lambda key, gr: (key, gr.ready)).to_list()
    return [{"h": h, "ready": gr.ready} for h, gr in reviews.items()]


@app.get("/reviews/{gid}")
async def get_review(gid: str) -> str | None:
    try:
        game_review = reviews[gid]
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found")
    if not game_review.ready:
        return None

    game = game_review.game
    exporter = chess.pgn.StringExporter()
    output = game.accept(exporter)
    return output


@app.get("/view")
async def view(request: Request) -> Response:
    pgn = open("games/yahoo.pgn").read()
    return templates.TemplateResponse("board.html", {"request": request, "pgn": pgn})


@app.get("/view/{h}")
async def view(request: Request, h: str) -> Response:
    try:
        gr = reviews[h]
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found")
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": gr.as_pgn()}
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
