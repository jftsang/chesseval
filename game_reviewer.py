import asyncio
import os
from functools import lru_cache

import chess
import chess.engine
import chess.pgn
import dotenv

from utils import sanitize_povscore

dotenv.load_dotenv()

ENGINE = os.getenv("STOCKFISH")
default_fen = chess.STARTING_FEN


class GameReviewer:
    async def create_review(self, game: chess.pgn.Game) -> chess.pgn.Game:
        transport, engine = await chess.engine.popen_uci(ENGINE)

        @lru_cache(maxsize=1024)
        async def _eval_fen(fen: str) -> chess.engine.PovScore:
            board = chess.Board(fen)
            info = await engine.analyse(board, chess.engine.Limit(time=0.1))
            return info["score"]

        async def _eval_inner(
            node: chess.pgn.GameNode, prevscore: chess.engine.PovScore | None
        ) -> None:
            # Evaluate the board at this node, which is the state AFTER
            # a move.

            board = node.board()
            score = await _eval_fen(board.fen())

            if prevscore is not None:
                # board.turn is the turn of the player about to take the
                # next move, so we need its inverse if we want to evaluate
                # the move that has just happened

                # checkmate is worth 20 pawns
                prev_num = prevscore.pov(not board.turn).score(mate_score=20_00)
                cur_num = score.pov(not board.turn).score(mate_score=20_00)

                # a bad move will have a positive deficit
                deficit = prev_num - cur_num

                if deficit >= 500:  # loses a major piece
                    node.nags.add(chess.pgn.NAG_BLUNDER)
                elif deficit >= 300:  # loses a minor piece
                    node.nags.add(chess.pgn.NAG_MISTAKE)
                elif deficit >= 100:  # loses a pawn
                    node.nags.add(chess.pgn.NAG_DUBIOUS_MOVE)

            if node.nags:
                node.comment = sanitize_povscore(score.white())

            coros = []
            for var in node.variations:
                coros.append(_eval_inner(var, score))
            await asyncio.gather(*coros)

        try:
            await _eval_inner(game, prevscore=None)
            return game
        finally:
            await engine.quit()
