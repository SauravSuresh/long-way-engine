// stdin: {"seasons": <seasons.yaml as JSON>, "state": <state as JSON>, "today": "YYYY-MM-DD"}
// stdout: the forecast as JSON. Used by tests/test_forecast_js.py.
import { forecast, normalizeSeasons, normalizeState } from "../docs/assets/forecast.js";

let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => (buf += c));
process.stdin.on("end", () => {
  const { seasons, state, today } = JSON.parse(buf);
  process.stdout.write(JSON.stringify(forecast(normalizeSeasons(seasons), normalizeState(state), today)));
});
