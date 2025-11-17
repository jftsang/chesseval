import asyncio
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import fastapi
import uvicorn
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

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


def sanitize_povscore(score: chess.engine.Score) -> str:
    mate = score.mate()
    if mate is not None:
        return f"M{mate}"
    else:
        return f"{score.score()/100:+.2f}"


def sanitize_infodict(board: chess.Board, infod: chess.engine.InfoDict) -> dict:
    san = infod.copy()
    san["score"] = sanitize_povscore(san["score"].white())

    san["continuation"] = []
    board = board.copy()
    for move in san["pv"]:
        san["continuation"].append(board.san(move))
        board.push(move)

    game = chess.pgn.Game()
    game.setup(board)
    return san


class GameManager:
    directory: Path = Path(__file__).parent / "games"

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

    async def create_review(self, key: str) -> chess.pgn.Game:
        game = self.load(key)
        transport, engine = await chess.engine.popen_uci(ENGINE)

        async def _eval_inner(
            node: chess.pgn.GameNode, prevscore: chess.engine.PovScore | None
        ) -> None:
            # Evaluate the board at this node, which is the state AFTER
            # a move.

            board = node.board()
            info = await engine.analyse(board, chess.engine.Limit(time=0.1))
            score = info["score"]
            node.comment = sanitize_povscore(score.white())

            if prevscore is not None:
                # board.turn is the turn of the player about to take the
                # next move, so we need its inverse if we want to evaluate
                # the move that has just happened

                # checkmate is worth 10000 pawns
                prev_num = prevscore.pov(not board.turn).score(mate_score=10000)
                cur_num = score.pov(not board.turn).score(mate_score=10000)

                # a bad move will have a positive deficit
                deficit = prev_num - cur_num

                if deficit >= 500:  # loses a major piece
                    node.nags.add(chess.pgn.NAG_BLUNDER)
                elif deficit >= 300:  # loses a minor piece
                    node.nags.add(chess.pgn.NAG_MISTAKE)
                elif deficit >= 100:  # loses a pawn
                    node.nags.add(chess.pgn.NAG_DUBIOUS_MOVE)

            coros = []
            for var in node.variations:
                coros.append(_eval_inner(var, score))
            await asyncio.gather(*coros)

        try:
            await _eval_inner(game, prevscore=None)
            return game
        finally:
            await engine.quit()


@app.get("/review/{key}")
async def get_review(request: Request, key: str) -> Response:
    gm = GameManager()
    game = gm.load(key)
    reviewed_game = await gm.create_review(key)
    return templates.TemplateResponse(
        "board.html", {"request": request, "pgn": gm.as_pgn(reviewed_game)}
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
