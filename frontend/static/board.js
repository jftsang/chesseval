// The pgn-viewer library is loaded as a global script, so PGNV is available globally
const PGNV = window.PGNV;

const pgn = document.getElementById("pgn").innerText;

const options = {
  position: 'start',
  showCoords: true,
  orientation: 'white',
  theme: 'sportverlag',
  pieceStyle: 'uscf',
  figurine: 'merida',
  locale: 'en',
  timerTime: '',
  width: '1000px',
  boardSize: '600px',
  layout: 'left',
  headers: true,
  showFen: true,
  coordsInner: true,
  manyGames: false,
  coordsFactor: '-5',
  coordsFontSize: '',
  colorMarker: 'circle',
  startPlay: '',
  hideMovesBefore: false,
  notation: 'short',
  notationLayout: 'list',
  resizable: true,
};

const {base, board} = PGNV.pgnView('b1', {pgn: pgn, ...options});
