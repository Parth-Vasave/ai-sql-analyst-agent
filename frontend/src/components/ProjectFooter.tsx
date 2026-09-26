import { DATA_LICENSE_URL, DATA_URL, EVALUATION_URL, REPO_URL } from "../links";

export function ProjectFooter() {
  return (
    <footer className="mt-12 border-t border-rule bg-surface">
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-8 text-sm text-ink-2 sm:px-6 md:grid-cols-3">
        <section>
          <h2 className="font-semibold text-ink">How it stays safe</h2>
          <p className="mt-1.5">
            The database account can only read four tables, with a statement timeout. Every generated query is parsed
            and checked before it runs, and it runs with a row limit. Numbers in a written answer must appear in the
            rows the database returned.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">Evaluation</h2>
          <p className="mt-1.5">
            Recorded on 26 September 2026: all 28 adversarial SQL statements in the offline safety suite were blocked.
            The 73-question accuracy run has not been done yet, so no accuracy figure is published.{" "}
            <a href={EVALUATION_URL}>Evaluation plan and history</a>
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">Data</h2>
          <p className="mt-1.5">
            <a href={DATA_URL}>CO₂ and Greenhouse Gas Emissions</a> by Our World in Data, licensed{" "}
            <a href={DATA_LICENSE_URL}>CC BY 4.0</a>, loaded from a pinned commit. Yearly values for countries,
            regions and income groups, 1750 to 2024.
          </p>
          <p className="mt-3">
            <a href={REPO_URL}>Source code on GitHub</a>
          </p>
        </section>
      </div>
    </footer>
  );
}
