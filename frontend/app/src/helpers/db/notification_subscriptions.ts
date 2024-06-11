import { db } from '@helpers/main_db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/main/schema.ts';
import type { NotificationSubscription } from '@dtypes/layout_components'

export async function get_subscription_by_user(user_id:number) {
    const q = await db.select({
        id: schema.fleet_push_subscriptions.id,
        subscription: schema.fleet_push_subscriptions.subscription,
    })
    .from(schema.fleet_push_subscriptions)
    .where(
        eq(schema.fleet_push_subscriptions.user_id, user_id)
    )
    .limit(1)

    if (q.length > 0) {
        return {
            id: q[0].id,
            subscription: q[0].subscription,
        } as NotificationSubscription
    } else {
        return null
    }
}

export async function create_subscription(user_id:number, subscription:string) {
    const q = await db.insert(schema.fleet_push_subscriptions)
    .values({ user_id: user_id, subscription: subscription })
    .returning()

    if (q.length > 0) {
        return q[0].id
    } else {
        return null
    }
}

export async function remove_subscription(subscription_id:number) {
    const q = await db.delete(schema.fleet_push_subscriptions)
    .where(
        eq(schema.fleet_push_subscriptions.id, subscription_id)
    )
    .returning({
        deleted_id: schema.fleet_push_subscriptions.id
    });

    if (q?.length > 0)
        return q[0].deleted_id
    else
        return null
}

export async function get_all_subscriptions() {
    return await db.select({
        id: schema.fleet_push_subscriptions.id,
        user_id: schema.fleet_push_subscriptions.user_id,
        subscription: schema.fleet_push_subscriptions.subscription,
    })
    .from(schema.fleet_push_subscriptions)
}