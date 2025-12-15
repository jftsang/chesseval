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

from game_reviewer import GameReviewer

app = fastapi.FastAPI()
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

templates = Jinja2Templates(directory="templates")


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
