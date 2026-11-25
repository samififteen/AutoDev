import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPoint } from "../types";
import { shortDate } from "../utils/format";

const COMPLETED = "#8ba974";
const FAILED = "#bf5d43";
const PULL_REQUESTS = "#d4562f";

const tooltipStyle = {
  backgroundColor: "#121110",
  border: "1px solid rgba(245, 240, 230, 0.14)",
  borderRadius: 2,
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 10,
  color: "#eae3d5",
  boxShadow: "none",
};

export function ActivityChart({ data }: { data: ChartPoint[] }) {
  const hasActivity = data.some(
    (point) => point.completed > 0 || point.failed > 0 || point.pull_requests > 0,
  );
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-4 font-mono text-[9px] uppercase tracking-[0.08em] text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 bg-emerald-400" /> Completed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 bg-rose-400" /> Failed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 bg-accent-500" /> Pull requests
        </span>
      </div>
      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 6, left: -24, bottom: 0 }}>
            <CartesianGrid
              stroke="rgba(245,240,230,0.08)"
              strokeDasharray="2 4"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fill: "#8c8272", fontSize: 10, fontFamily: "IBM Plex Mono, monospace" }}
              axisLine={false}
              tickLine={false}
              minTickGap={18}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#8c8272", fontSize: 10, fontFamily: "IBM Plex Mono, monospace" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(label) => shortDate(String(label))}
              cursor={{ fill: "rgba(245,240,230,0.025)" }}
            />
            <Bar
              dataKey="pull_requests"
              name="Pull requests"
              barSize={8}
              fill={PULL_REQUESTS}
              opacity={0.4}
              radius={0}
            />
            <Line
              type="linear"
              dataKey="completed"
              name="Completed"
              stroke={COMPLETED}
              strokeWidth={1.5}
              dot={{ r: 1.5, strokeWidth: 0, fill: COMPLETED }}
              activeDot={{ r: 3, fill: COMPLETED }}
            />
            <Line
              type="linear"
              dataKey="failed"
              name="Failed"
              stroke={FAILED}
              strokeWidth={1.5}
              dot={{ r: 1.5, strokeWidth: 0, fill: FAILED }}
              activeDot={{ r: 3, fill: FAILED }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {!hasActivity ? (
        <p className="mt-2 text-center font-mono text-[9px] uppercase tracking-[0.06em] text-slate-600">
          No executions yet. Run a task from Issues &amp; Tasks to populate this chart.
        </p>
      ) : null}
    </div>
  );
}
