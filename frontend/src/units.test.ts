import { unitOf, unitsFromProfile } from "./units";

it.each([
  ["Annual fossil and industry CO2 emissions, excluding land-use change, million tonnes (Mt). Default metric.", "Mt"],
  ["Share of global annual CO2 emissions, percent (%).", "%"],
  ["Annual CO2 emissions per person, tonnes per person (t/person).", "t/person"],
  ["Population (people).", "people"],
  ["Gross domestic product, international-$ at 2011 prices (Maddison Project). Available up to 2022 only.", null],
  ["Calendar year.", null],
  [null, null],
])("unit of %s", (comment, unit) => {
  expect(unitOf(comment)).toBe(unit);
});

it("drops names whose unit differs between tables", () => {
  const column = (name: string, comment: string) => ({ name, type: "numeric", nullable: true, comment, primary_key: false, sensitive: false });
  const table = (name: string, columns: ReturnType<typeof column>[]) => ({ schema_name: "public", name, kind: "table", comment: null, estimated_rows: null, columns });
  const profile = {
    database_id: "x",
    dialect: "postgresql",
    tables: [table("a", [column("co2", "(Mt)"), column("value", "(Mt)")]), table("b", [column("value", "(%)")])],
  };
  expect(unitsFromProfile(profile)).toEqual({ co2: "Mt" });
});
