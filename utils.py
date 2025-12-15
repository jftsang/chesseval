import chess
import chess.engine

ENGINE = "/Users/jmft2/.local/bin/stockfish.exe"
default_fen = chess.STARTING_FEN


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
