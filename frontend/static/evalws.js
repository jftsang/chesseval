const evalbar = document.getElementById("evalbar")
let ws = null;
function startEvaluationWs() {
  ws = new WebSocket("ws://localhost:8000/evaluation");
  ws.onmessage = function(event) {
    console.log(event.data);
    const evaluation = JSON.parse(event.data);
    evalbar.value = evaluation.score;
  };
  ws.onclose = () => {
    ws = null;
    setTimeout(startEvaluationWs, 1000);
  }

  let boardState = board.getFen();
  setInterval(() => {
    const newBoardState = board.getFen();
    if (boardState === newBoardState) {
      return;
    }
    if (ws === null)
      return;
    ws.send(newBoardState);
    boardState = newBoardState;
  }, 100)


}
startEvaluationWs();
