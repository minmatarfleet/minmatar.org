/** The "Get it ready" checklist a manager sees before a campaign starts. */
import type { CampaignDetail } from '@dtypes/api.minmatar.org'
import type { TranslationKey } from '@helpers/i18n'

export interface CampaignReadyStep {
    id:             string;
    label_key:      TranslationKey;
    summary_key:    TranslationKey;
    values?:        Record<string, string | number>;
    done:           boolean;
}

/** One step per thing a strategic campaign needs before it starts. Structures only when the tab is on. */
export function campaign_ready_steps(campaign: CampaignDetail, features_count: number, dates: string): CampaignReadyStep[] {
    const parties = campaign.parties ?? []
    const count = (side: string) => parties.filter((party) => party.side === side).length
    const fittings_on = (campaign.fittings ?? []).length
    const structures = (campaign.structures ?? []).length
    const steps: CampaignReadyStep[] = [
        {
            id: 'dates',
            label_key: 'campaigns.ready.dates',
            summary_key: 'campaigns.ready.dates_summary',
            values: { dates },
            done: true,
        },
        {
            id: 'sides',
            label_key: 'campaigns.ready.sides',
            summary_key: parties.length ? 'campaigns.ready.sides_summary' : 'campaigns.ready.sides_empty',
            values: { enemies: count('enemy'), allies: count('ally'), third: count('third_party') },
            done: parties.length > 0,
        },
        {
            id: 'features',
            label_key: 'campaigns.ready.features',
            summary_key: 'campaigns.ready.features_summary',
            values: { count: features_count },
            done: true,
        },
        {
            id: 'briefing',
            label_key: 'campaigns.ready.briefing',
            summary_key: campaign.tagline && campaign.description_md ? 'campaigns.ready.briefing_done' : 'campaigns.ready.briefing_empty',
            done: Boolean(campaign.tagline && campaign.description_md),
        },
    ]
    if (campaign.features?.structures)
        steps.push({
            id: 'structures',
            label_key: 'campaigns.ready.structures',
            summary_key: structures ? 'campaigns.ready.structures_summary' : 'campaigns.ready.structures_empty',
            values: { count: structures },
            done: structures > 0,
        })
    steps.push(
        {
            id: 'fittings',
            label_key: 'campaigns.ready.fittings',
            summary_key: fittings_on ? 'campaigns.ready.fittings_summary' : 'campaigns.ready.fittings_empty',
            values: { count: fittings_on },
            done: fittings_on > 0,
        },
        {
            id: 'discord',
            label_key: 'campaigns.ready.discord',
            summary_key: campaign.coordination_ready ? 'campaigns.ready.discord_done' : 'campaigns.ready.discord_empty',
            done: campaign.coordination_ready,
        },
    )
    return steps
}
