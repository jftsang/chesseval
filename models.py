from io import StringIO
from typing import Self

import chess
import chess.engine
import chess.pgn
from sqlmodel import Field, SQLModel


class GameDTO(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, unique=True)
    name: str = Field(unique=True)
    pgn: str


class Game(chess.pgn.Game):
    def as_pgn(self) -> str:
        exporter = chess.pgn.StringExporter()
        output = self.accept(exporter)
        return output

    def as_dto(self) -> GameDTO:
        return GameDTO(pgn=self.as_pgn())

    @classmethod
    def from_dto(cls, dto: GameDTO) -> Self:
        f = StringIO(dto.pgn)
        return chess.pgn.read_game(f)
