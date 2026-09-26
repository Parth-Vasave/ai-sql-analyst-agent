import { formatCell, formatTick } from "./format";

describe("formatCell", () => {
  it.each([
    ["year", 2023, "2023"],
    ["co2", 12172.009, "12,172.009"],
    ["population", 1438069597, "1,438,069,597"],
    ["share", 0.31836, "0.318"],
    ["name", "China", "China"],
    ["co2", null, "NULL"],
  ])("%s %s -> %s", (column, value, text) => {
    expect(formatCell(column, value)).toBe(text);
  });
});

describe("formatTick", () => {
  it("keeps years plain and shortens large numbers", () => {
    expect(formatTick("year", 2020)).toBe("2020");
    expect(formatTick("co2", 12000)).toBe("12K");
    expect(formatTick("co2", 3500)).toBe("3.5K");
    expect(formatTick("population", 1_400_000_000)).toBe("1.4B");
    expect(formatTick("co2", 986.9)).toBe("986.9");
  });
});
