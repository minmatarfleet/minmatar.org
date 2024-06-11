import { sqliteTable, integer, numeric, real, index, primaryKey, text, uniqueIndex } from "drizzle-orm/sqlite-core"

export const fleet_push_subscriptions = sqliteTable('fleet_push_subscriptions', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  user_id: integer('user_id', { mode: 'number' }),
  subscription: text('subscription', { mode: 'json' }),
});