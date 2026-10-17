import { expect, test } from 'vitest';

import { route_exists } from '@helpers/routes';

test('route_exists matches static pages with or without trailing slashes', () => {
    expect(route_exists('/')).toBe(true);
    expect(route_exists('/surveys/')).toBe(true);
    expect(route_exists('/ships/fittings')).toBe(true);
    expect(route_exists('/character/assets/user/')).toBe(true);
});

test('route_exists matches dynamic pages', () => {
    expect(route_exists('/surveys/1/results/')).toBe(true);
    expect(route_exists('/fleets/upcoming/92221')).toBe(true);
    expect(route_exists('/alliance/tribes/1/')).toBe(true);
    expect(route_exists('/alliance/corporations/minmatar-fleet-academy/')).toBe(true);
});

test('route_exists rejects path prefixes that have no page', () => {
    expect(route_exists('/character/')).toBe(false);
    expect(route_exists('/surveys/1/')).toBe(false);
    expect(route_exists('/intel/timers/')).toBe(false);
    expect(route_exists('/ships/fittings/normal/')).toBe(false);
});

test('route_exists does not treat a literal folder as a dynamic sibling', () => {
    // /alliance/corporations/[corporation] would match, but application/ is a folder of its own.
    expect(route_exists('/alliance/corporations/application/')).toBe(false);
    expect(route_exists('/alliance/corporations/application/98838663/')).toBe(false);
});

test('route_exists ignores query strings and hashes', () => {
    expect(route_exists('/fleets/upcoming/?audience=all#top')).toBe(true);
});
