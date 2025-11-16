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
from starlette.responses import Response, JSONResponse

ENGINE = "/Users/jmft2/.local/bin/stockfish.exe"

app = fastapi.FastAPI()

default_fen = chess.STARTING_FEN


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


reviews: dict[str, GameReview] = {}


@app.post("/review")
async def create_review(pgn: str) -> JSONResponse:
    h = uuid.uuid4().hex
    if h in reviews:
        return h

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


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


main()
