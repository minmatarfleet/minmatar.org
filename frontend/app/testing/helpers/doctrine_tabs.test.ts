import { expect, test } from "vitest";
import { doctrine_tabs, doctrines_at, tab_for_location } from "@helpers/doctrine_tabs";

const location = (location_id: number, short_name: string) => ({
  location_id,
  name: `${short_name} Station`,
  short_name,
  solar_system_name: short_name,
});

const stagings = {
  home: location(1, "Home"),
  deployments: [location(2, "Forward"), location(3, "Outpost")],
};

test("no tabs without a deployment or a home", () => {
  expect(doctrine_tabs({ home: location(1, "Home"), deployments: [] })).toEqual([]);
  expect(doctrine_tabs({ home: null, deployments: [location(2, "Forward")] })).toEqual([]);
});

test("Home and Deployed tabs cover the right locations", () => {
  const tabs = doctrine_tabs(stagings);
  expect(tabs.map((tab) => tab.id)).toEqual(["home", "deployed"]);
  expect(tabs[0].location_ids).toEqual([1]);
  expect(tabs[1].names).toEqual(["Forward", "Outpost"]);
  expect(tabs[1].location_ids).toEqual([2, 3]);
});

test("doctrines_at keeps doctrines staged at any listed location", () => {
  const doctrines = [
    { id: 1, location_ids: [1] },
    { id: 2, location_ids: [3] },
    { id: 3, location_ids: [1, 2] },
    { id: 4 },
  ];
  expect(doctrines_at(doctrines, [2, 3]).map((doctrine) => doctrine.id)).toEqual([2, 3]);
});

test("an old location_id link opens its tab, and Home otherwise", () => {
  const tabs = doctrine_tabs(stagings);
  expect(tab_for_location(tabs, 3)).toBe("deployed");
  expect(tab_for_location(tabs, 1)).toBe("home");
  expect(tab_for_location(tabs, 99)).toBe("home");
});
