const btn = document.getElementById("toggle");
let btnst = true;
btn.onclick = () => {
  btnst = !btnst;
  if (btnst) {
    document.querySelector('.toggle span').classList.add('toggle');
    document.getElementById('sidebar').classList.remove('sidebarhide');
    document.getElementById('main').classList.remove('mainfull');
  } else {
    document.querySelector('.toggle span').classList.remove('toggle');
    document.getElementById('sidebar').classList.add('sidebarhide');
    document.getElementById('main').classList.add('mainfull');
  }
};

let filename = location.pathname.split("/").at(-1);
if (filename) {
  filename = filename.substr(0, filename.length - 5);
}
const timer = document.getElementsByClassName("breadcrumbs")?.[0]
  ?.parentElement?.appendChild(document.createElement("span"));
if (timer) {
  timer.id = "timer";
  let time = 0, start;
  const controls = Object.fromEntries(["time", "play", "pause", "stop"].map(c => [c, timer.appendChild(document.createElement("span"))]));

  function playPause(play, pause) {
    controls.pause.style.display = play ? "inline" : "none";
    controls.stop.style.display = (play || pause) ? "inline" : "none";
    controls.play.style.display = play ? "none" : "inline";
  }
  function showTime() {
    const quarters = Math.max(time / (60 * 60 * 1000), 1);
    const mins = (quarters % 4) * 25;
    controls.time.textContent = "#" + filename + " " + Math.floor(quarters / 4) + (mins ? ("." + mins) : "") + "h ";
  }

  Object.entries(controls).forEach(e => e[1].className = e[0])
  controls.pause.style.display = "none";
  controls.stop.style.display = "none";
  playPause(false);
  controls.play.onclick = () => {
    start = new Date();
    playPause(true);
  }
  controls.pause.onclick = () => {
    time += new Date() - start;
    showTime();
    playPause(false, true);
  }
  controls.stop.onclick = () => {
    showTime();
    time = 0;
    playPause(false);
  }
}
