import chess
import chess.engine

default_fen = chess.STARTING_FEN

def none_throws[T](x: T | None) -> T:
    if x is None:
        raise ValueError("Value is None")
    return x


def sanitize_povscore(score: chess.engine.Score) -> str:
    mate = score.mate()
    if mate is not None:
        return f"M{mate}"
    else:
        return f"{score.score()/100:+.2f}"


def sanitize_infodict(board: chess.Board, infod: chess.engine.InfoDict) -> dict:
    san = infod.copy()
    # san["score"] = sanitize_povscore(san["score"].white())
    san["score"] = san["score"].white().score(mate_score=20_00)

    san["continuation"] = []
    board = board.copy()
    if "pv" in san:
        for move in san["pv"]:
            san["continuation"].append(board.san(move))
            board.push(move)
        del san["pv"]

    game = chess.pgn.Game()
    game.setup(board)
    return san
