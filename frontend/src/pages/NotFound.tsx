import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonStyles } from "../components/ui";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 text-center">
      <Compass className="h-8 w-8 text-accent-500" />
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-accent-400">Error 404</p>
        <h1 className="mt-2 font-display text-[42px] leading-none text-slate-50">
          Page not found
        </h1>
        <p className="mt-3 text-[12px] text-slate-500">
          This route does not exist in the AutoDev workspace.
        </p>
      </div>
      <Link to="/" className={buttonStyles("secondary")}>
        Back to overview
      </Link>
    </div>
  );
}
