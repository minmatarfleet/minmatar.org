import { SignJWT } from "jose";
import { expect, test } from "vitest";
import { account_user_id_query } from "@helpers/account_user_query";

const secret = new TextEncoder().encode("test-secret-key-32-bytes-long!!");

test("account_user_id_query is empty without a token", () => {
  expect(account_user_id_query(false)).toBe("");
  expect(account_user_id_query(undefined)).toBe("");
  expect(account_user_id_query("")).toBe("");
});

test("account_user_id_query appends the JWT user id", async () => {
  const token = await new SignJWT({ user_id: 4048 })
    .setProtectedHeader({ alg: "HS256" })
    .sign(secret);
  expect(account_user_id_query(token)).toBe("&account_user_id=4048");
});

test("account_user_id_query is empty for invalid JWT", () => {
  expect(account_user_id_query("not-a-jwt")).toBe("");
});
